// loaded.cpp - loaded latency (MLC-style): one thread measures random
// pointer-chase latency while generator threads inject traffic. Sweeping
// --delay from large to 0 traces the throughput-vs-latency curve.
#include <atomic>
#include <memory>
#include <thread>
#include <vector>

#include "bwkern.hpp"
#include "chase.hpp"
#include "common.hpp"
#include "threads.hpp"

#define HEADER                                                                                           \
    "label,bench,gen_pattern,pages,chase_size,gen_size,gran,stride,read_pct,nt,delay,gens,pinned,chase_cpu," \
    "rep,lat_ns,lat_cycles,ghz,gen_gbps,gen_line_gbps,huge_kb"

static const char *USAGE =
    "[options]\n"
    "  --chase-cpu N            CPU for the latency thread (default 0, -1 = unpinned)\n"
    "  --chase-size B           chase buffer (default 512M)\n"
    "  --cpus LIST|none         generator CPUs (count = number of generators)\n"
    "  --gens N                 generators when --cpus none (unpinned)\n"
    "  --gen-size B             per-generator buffer (default 256M)\n"
    "  --pattern/--gran/--stride/--read-pct/--nt/--delay   generator traffic\n"
    "  --pages 4k|large|thp|hugetlb  chase buffer (default 4k)\n"
    "  --gen-pages 4k|large|thp|hugetlb  generator buffers (default 4k; they only make traffic,\n"
    "                                and fall back to 4k with a warning if large pages run out)\n"
    "  --reps R --ms T --label L --out FILE --header --header-only\n";

struct alignas(64) Gen {
    std::atomic<unsigned long long> bytes{0};
    int tid = 0, cpu = -1, err = 0;
};

int main(int argc, char **argv) {
    Args a(argc, argv,
           {{"chase-cpu", true}, {"chase-size", true}, {"cpus", true}, {"gens", true}, {"gen-size", true},
            {"pattern", true}, {"gran", true}, {"stride", true}, {"read-pct", true}, {"nt", false}, {"delay", true},
            {"pages", true}, {"gen-pages", true}, {"reps", true}, {"ms", true}, {"label", true}, {"out", true}, {"header", false},
            {"header-only", false}},
           USAGE);
    if (a.has("header-only")) {
        std::printf(HEADER "\n");
        return 0;
    }
    BwCfg cfg;
    cfg.size = a.size("gen-size", 256UL << 20);
    if (!parse_bw_pat(a.str("pattern", "seq"), cfg.pat)) a.fail("bad --pattern");
    PageMode chase_pages;
    if (!parse_pages(a.str("pages", "4k"), chase_pages)) a.fail("bad --pages");
    if (!parse_pages(a.str("gen-pages", "4k"), cfg.pages)) a.fail("bad --gen-pages");
    cfg.gran = a.size("gran", 64);
    cfg.stride = a.size("stride", 256);
    cfg.read_pct = (int)a.num("read-pct", 100);
    cfg.nt = a.has("nt");
    cfg.delay = (unsigned)a.num("delay", 0);
    cfg.seed = 7;
    size_t chase_size = a.size("chase-size", 512UL << 20);
    int chase_cpu = (int)a.num("chase-cpu", 0), reps = (int)a.num("reps", 3);
    double ms = a.real("ms", 300.0);
    std::string label = a.str("label", "default");
    std::vector<int> cpus;
    bool gens_unpinned = false;
    int ngens = 0;
    if (a.has("cpus")) {
        if (a.str("cpus") == "none") gens_unpinned = true;
        else cpus = parse_cpulist(a.str("cpus"));
        ngens = (int)cpus.size();
    }
    if (gens_unpinned) ngens = (int)a.num("gens", 0);
    if (ngens < 0 || ngens > 1024 || reps < 0) a.fail();

    maybe_raise_priority();
    pin_self(chase_cpu);
    double ghz = calibrate_ghz();

    Buffer cb;  // chase buffer: random single cycle of cache lines
    if (buffer_alloc(cb, chase_size, chase_pages, true)) return 1;
    void *start, *pos[1];
    size_t nodes = chain_build(cb.p, cb.len, ChasePat::Rand, LINE_BYTES, 4096, 99, &start);
    if (!nodes || chain_walk(start, nodes, cb.p, cb.len, 1, pos)) {
        std::fprintf(stderr, "error: chase chain invalid\n");
        return 1;
    }
    long huge_kb = buffer_huge_kb(cb);

    std::atomic<bool> run{true};
    Barrier bar((size_t)ngens + 1);
    std::unique_ptr<Gen[]> g(new Gen[ngens > 0 ? ngens : 1]);
    std::vector<std::thread> th;
    for (int i = 0; i < ngens; i++) {
        g[i].tid = i;
        g[i].cpu = gens_unpinned ? -1 : cpus[i];
        th.emplace_back([&, i] {
            Gen &me = g[i];
            pin_self(me.cpu);
            BwState s;
            me.err = bw_state_init(s, cfg, me.tid);
            uint64_t chunk = bw_chunk_size(cfg), total = 0;
            bar.wait();
            while (!me.err && run.load(std::memory_order_relaxed)) {
                total += bw_chunk(s, chunk);
                me.bytes.store(total, std::memory_order_relaxed);
            }
            if (!me.err) {
                g_sink += s.acc;
                bw_state_free(s);
            }
        });
    }
    bar.wait();
    int err = 0;
    for (int i = 0; i < ngens; i++) err |= g[i].err;
    if (err) {  // never report a "loaded" latency with missing load
        std::fprintf(stderr, "error: a load generator could not start; no rows written\n");
        run.store(false);
        for (auto &t : th) t.join();
        buffer_free(cb);
        return 1;
    }
    auto snapshot = [&] {
        double b = 0;
        for (int i = 0; i < ngens; i++) b += (double)g[i].bytes.load(std::memory_order_relaxed);
        return b;
    };

    // let generators reach steady state, and size each repetition
    uint64_t probe = 1 << 13;
    double t0 = now_ns();
    probe = chase_run(pos, 1, probe);
    double tp = now_ns() - t0;
    uint64_t hops = (uint64_t)(ms * 1e6 / (tp / (double)probe));
    if (hops < probe) hops = probe;

    FILE *out = open_output(a);
    if (a.has("header")) std::fprintf(out, HEADER "\n");
    double lb = bw_line_bytes_per_access(cfg) / (double)cfg.gran;
    for (int r = 0; r < reps; r++) {
        double b0 = snapshot();
        t0 = now_ns();
        uint64_t h = chase_run(pos, 1, hops);
        double t = now_ns() - t0;
        double b1 = snapshot();
        double lat = t / (double)h, gbps = (b1 - b0) / t;
        std::fprintf(out, "%s,loaded,%s,%s,%zu,%zu,%zu,%zu,%d,%d,%u,%d,%d,%d,%d,%.4f,%.3f,%.4f,%.4f,%.4f,%ld\n",
                     label.c_str(), bw_pat_name(cfg.pat), pages_name(cb.mode), chase_size, cfg.size, cfg.gran,
                     cfg.pat == BwPat::Stride ? cfg.stride : (cfg.pat == BwPat::Seq ? cfg.gran : (size_t)0),
                     cfg.read_pct, cfg.nt ? 1 : 0, cfg.delay, ngens, (!gens_unpinned && chase_cpu >= 0) ? 1 : 0,
                     chase_cpu, r, lat, lat * ghz, ghz, gbps, gbps * lb, huge_kb);
        std::fflush(out);
    }
    run.store(false);
    for (auto &t : th) t.join();
    g_sink = (uint64_t)(uintptr_t)pos[0];
    if (out != stdout) std::fclose(out);
    buffer_free(cb);
    return err ? 1 : 0;
}
