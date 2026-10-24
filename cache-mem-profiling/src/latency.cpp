// latency.cpp - pointer-chase load-to-use latency and memory-level parallelism.
//
// One CSV row per repetition. With --chains K, K independent chains are walked
// in lockstep: latency per hop stays at the idle value until K exceeds the
// number of misses the core can keep in flight (Little's Law).
#include "chase.hpp"
#include "common.hpp"

#define HEADER                                                                                         \
    "label,bench,pattern,pages,size_bytes,stride,chains,cpu,rep,accesses,ns_total,lat_ns,lat_cycles," \
    "ghz,gbps,huge_kb,chain_ok"

static const char *USAGE =
    "--size BYTES [options]\n"
    "  --pattern seq|rand|page     access pattern (default rand)\n"
    "  --stride B                  node spacing for seq/rand (default 64)\n"
    "  --page-size B               node spacing for page pattern (default 4096)\n"
    "  --pages 4k|large|thp|hugetlb  backing page size (default 4k)\n"
    "  --chains K                  independent chains (1..32, default 1)\n"
    "  --cpu N                     pin to logical CPU N (default: no pinning)\n"
    "  --reps R                    repetitions (default 5; 0 = setup only)\n"
    "  --ms T                      target milliseconds per repetition (default 200)\n"
    "  --ghz G                     use G GHz for cycle conversion, skip calibration\n"
    "  --perf                      collect hardware counters (Linux)\n"
    "  --seed S --label L --out FILE --meta FILE --header --header-only --check\n";

int main(int argc, char **argv) {
    Args a(argc, argv,
           {{"size", true}, {"pattern", true}, {"stride", true}, {"page-size", true}, {"pages", true},
            {"chains", true}, {"cpu", true}, {"reps", true}, {"ms", true}, {"ghz", true}, {"perf", false},
            {"seed", true}, {"label", true}, {"out", true}, {"meta", true}, {"header", false}, {"header-only", false},
            {"check", false}},
           USAGE);
    if (a.has("header-only")) {
        std::printf(HEADER);
        perf_print_header(stdout);
        std::printf("\n");
        return 0;
    }
    size_t size = a.size("size", 0), stride = a.size("stride", 64), page = a.size("page-size", 4096);
    ChasePat pat = ChasePat::Rand;
    PageMode pages = PageMode::k4K;
    if (!parse_chase_pat(a.str("pattern", "rand"), pat)) a.fail("bad --pattern");
    if (!parse_pages(a.str("pages", "4k"), pages)) a.fail("bad --pages");
    int chains = (int)a.num("chains", 1), cpu = (int)a.num("cpu", -1), reps = (int)a.num("reps", 5);
    double ms = a.real("ms", 200.0), ghz_opt = a.real("ghz", 0.0);
    uint64_t seed = (uint64_t)a.num("seed", 12345);
    std::string label = a.str("label", "default");
    bool use_perf = a.has("perf");
    if (!size || !chase_k_supported(chains) || reps < 0) a.fail();

    maybe_raise_priority();
    pin_self(cpu);
    double ghz = ghz_opt > 0 ? ghz_opt : calibrate_ghz();

    Buffer b;
    if (buffer_alloc(b, size, pages, true)) return 1;
    void *start = nullptr;
    size_t nodes = chain_build(b.p, b.len, pat, stride, page, seed, &start);
    if (!nodes) {
        std::fprintf(stderr, "error: cannot build chain (size too small for stride/page?)\n");
        return 1;
    }
    void *pos[32];
    bool ok = chain_walk(start, nodes, b.p, b.len, chains, pos) == 0;
    if (a.has("check")) {
        std::fprintf(stderr, "latency check pattern=%s pages=%s size=%zu nodes=%zu: %s\n", chase_pat_name(pat),
                     pages_name(b.mode), size, nodes, ok ? "OK" : "FAIL");
        return ok ? 0 : 1;
    }
    if (!ok) std::fprintf(stderr, "error: chain validation failed\n");
    long huge_kb = buffer_huge_kb(b);

    // probe to size each repetition to ~ms; the probe also warms caches/TLB
    uint64_t probe = 1 << 14;
    chase_run(pos, chains, probe);
    double t0 = now_ns();
    probe = chase_run(pos, chains, probe);
    double tp = now_ns() - t0;
    uint64_t hops = (uint64_t)(ms * 1e6 / (tp / (double)probe));
    if (hops < probe) hops = probe;

    FILE *out = open_output(a);
    Perf pc;
    if (use_perf) pc.init();
    if (a.has("header")) {
        std::fprintf(out, HEADER);
        perf_print_header(out);
        std::fprintf(out, "\n");
    }
    for (int r = 0; r < reps; r++) {
        double v[NPERF];
        if (use_perf) pc.start();
        t0 = now_ns();
        uint64_t h = chase_run(pos, chains, hops);
        double t = now_ns() - t0;
        if (use_perf) {
            pc.stop();
            pc.read(v);
        }
        double acc = (double)h * chains;
        double lat = t / (double)h;
        std::fprintf(out, "%s,latency,%s,%s,%zu,%zu,%d,%d,%d,%.0f,%.0f,%.4f,%.3f,%.4f,%.4f,%ld,%d", label.c_str(),
                     chase_pat_name(pat), pages_name(b.mode), size, pat == ChasePat::Page ? page : stride, chains, cpu, r,
                     acc, t, lat, lat * ghz, ghz, acc * LINE_BYTES / t, huge_kb, ok ? 1 : 0);
        if (use_perf) perf_print_values(out, v);
        else perf_print_empty(out);
        std::fprintf(out, "\n");
        std::fflush(out);
    }
    g_sink = (uint64_t)(uintptr_t)pos[0];
    if (out != stdout) std::fclose(out);
    buffer_free(b);
    write_meta(a, ghz);
    return ok ? 0 : 1;
}
