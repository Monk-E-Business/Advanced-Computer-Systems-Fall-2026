// bandwidth.cpp - multi-threaded bandwidth for sequential / strided / random
// patterns, access granularities and read/write mixes.
//
// Every thread pins itself, then allocates and first-touches its own buffer
// (NUMA-local). All threads start together on a barrier and run ~--ms per
// repetition. Aggregate bandwidth = sum of per-thread (bytes / thread time).
#include <memory>
#include <thread>
#include <vector>

#include "bwkern.hpp"
#include "common.hpp"
#include "threads.hpp"

#define HEADER                                                                                         \
    "label,bench,pattern,pages,size_bytes,gran,stride,read_pct,nt,delay,threads,pinned,rep,bytes,ns_max," \
    "gbps,line_gbps,gbps_min_thread,gbps_max_thread,huge_kb,init,ghz"

static const char *USAGE =
    "--size BYTES_PER_THREAD [options]\n"
    "  --threads T               number of threads (default 1)\n"
    "  --cpus LIST|none          CPUs to pin threads to (default 0..T-1; none = unpinned)\n"
    "  --pattern seq|stride|rand (default seq)\n"
    "  --gran B                  bytes per access, multiple of 8 (default 64)\n"
    "  --stride B                bytes between accesses for stride (default 256)\n"
    "  --read-pct P              percentage of reads: 100, 70, 50, 0 ... (default 100)\n"
    "  --nt                      non-temporal stores for writes\n"
    "  --delay D                 empty-loop iterations after each access\n"
    "  --pages 4k|large|thp|hugetlb  (default 4k)\n"
    "  --reps R --ms T --label L --out FILE --header --header-only\n"
    "  --no-init                 skip first-touch initialisation (pitfall demo)\n"
    "  --check                   run correctness self-test and exit\n";

struct Worker {
    int tid = 0, cpu = -1, err = 0;
    long huge_kb = 0;
    std::vector<double> bytes, ns;
};

int main(int argc, char **argv) {
    Args a(argc, argv,
           {{"size", true}, {"threads", true}, {"cpus", true}, {"pattern", true}, {"gran", true}, {"stride", true},
            {"read-pct", true}, {"nt", false}, {"delay", true}, {"pages", true}, {"reps", true}, {"ms", true},
            {"label", true}, {"out", true}, {"header", false}, {"header-only", false}, {"no-init", false},
            {"check", false}},
           USAGE);
    if (a.has("header-only")) {
        std::printf(HEADER "\n");
        return 0;
    }
    if (a.has("check")) {
        int f = bw_selftest();
        std::fprintf(stderr, "bandwidth selftest: %s\n", f ? "FAIL" : "OK");
        return f ? 1 : 0;
    }
    BwCfg cfg;
    cfg.size = a.size("size", 0);
    if (!parse_bw_pat(a.str("pattern", "seq"), cfg.pat)) a.fail("bad --pattern");
    if (!parse_pages(a.str("pages", "4k"), cfg.pages)) a.fail("bad --pages");
    cfg.gran = a.size("gran", 64);
    cfg.stride = a.size("stride", 256);
    cfg.read_pct = (int)a.num("read-pct", 100);
    cfg.nt = a.has("nt");
    cfg.delay = (unsigned)a.num("delay", 0);
    cfg.init = !a.has("no-init");
    int threads = (int)a.num("threads", 1), reps = (int)a.num("reps", 5);
    double ms = a.real("ms", 200.0);
    std::string label = a.str("label", "default");
    if (!cfg.size || threads < 1 || threads > 1024 || reps < 0 || cfg.read_pct < 0 || cfg.read_pct > 100 ||
        (cfg.pat == BwPat::Stride && cfg.stride < cfg.gran))
        a.fail();

    std::vector<int> cpus;
    bool pinned = true;
    if (a.has("cpus")) {
        cpus = parse_cpulist(a.str("cpus"));
        if (cpus.empty()) pinned = false;  // --cpus none
    } else {
        for (int i = 0; i < threads; i++) cpus.push_back(i);
    }
    if (pinned && (int)cpus.size() < threads) a.fail("--cpus lists fewer CPUs than --threads");

    maybe_raise_priority();
    pin_self(pinned ? cpus[0] : -1);  // frequency reference measured on the first CPU
    double ghz = calibrate_ghz();

    Barrier bar((size_t)threads + 1);
    std::vector<Worker> w(threads);
    std::vector<std::thread> th;
    for (int i = 0; i < threads; i++) {
        w[i].tid = i;
        w[i].cpu = pinned ? cpus[i] : -1;
        w[i].bytes.assign(reps, 0);
        w[i].ns.assign(reps, 0);
        th.emplace_back([&, i] {
            Worker &me = w[i];
            pin_self(me.cpu);
            BwState s;
            me.err = bw_state_init(s, cfg, me.tid);
            me.huge_kb = me.err ? -1 : buffer_huge_kb(s.buf);
            uint64_t chunk = bw_chunk_size(cfg);
            bar.wait();  // ready
            for (int r = 0; r < reps; r++) {
                bar.wait();  // start
                double bytes = 0, t0 = now_ns(), t = 0;
                if (!me.err) {
                    do {
                        bytes += (double)bw_chunk(s, chunk);
                        t = now_ns() - t0;
                    } while (t < ms * 1e6);
                }
                me.bytes[r] = bytes;
                me.ns[r] = t;
                bar.wait();  // end
            }
            if (!me.err) {
                g_sink += s.acc;
                bw_state_free(s);
            }
        });
    }
    pin_self(-1);
    bar.wait();  // ready
    int err = 0;
    for (auto &x : w) err |= x.err;
    FILE *out = open_output(a);
    if (a.has("header")) std::fprintf(out, HEADER "\n");
    double lb = bw_line_bytes_per_access(cfg) / (double)cfg.gran;
    for (int r = 0; r < reps; r++) {
        bar.wait();
        bar.wait();
        double bytes = 0, gbps = 0, nmax = 0, gmin = 1e30, gmax = 0;
        long hk = 0;
        for (auto &x : w) {
            double g = x.ns[r] > 0 ? x.bytes[r] / x.ns[r] : 0;
            bytes += x.bytes[r];
            gbps += g;
            if (x.ns[r] > nmax) nmax = x.ns[r];
            if (g < gmin) gmin = g;
            if (g > gmax) gmax = g;
            hk += x.huge_kb;
        }
        std::fprintf(out, "%s,bandwidth,%s,%s,%zu,%zu,%zu,%d,%d,%u,%d,%d,%d,%.0f,%.0f,%.4f,%.4f,%.4f,%.4f,%ld,%d,%.4f\n",
                     label.c_str(), bw_pat_name(cfg.pat), pages_name(cfg.pages), cfg.size, cfg.gran,
                     cfg.pat == BwPat::Stride ? cfg.stride : (cfg.pat == BwPat::Seq ? cfg.gran : (size_t)0),
                     cfg.read_pct, cfg.nt ? 1 : 0, cfg.delay, threads, pinned ? 1 : 0, r, bytes, nmax, gbps, gbps * lb,
                     gmin, gmax, hk, cfg.init ? 1 : 0, ghz);
        std::fflush(out);
    }
    for (auto &t : th) t.join();
    if (out != stdout) std::fclose(out);
    return err ? 1 : 0;
}
