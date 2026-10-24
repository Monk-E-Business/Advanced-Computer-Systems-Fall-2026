// kernels.cpp - simple streaming kernels for correlating cache/TLB misses with
// runtime:   mul:   z[i] = x[i] * y[i]        saxpy: y[i] = a * x[i] + y[i]
//
// --order seq      i = 0, 1, 2, ...                       (unit stride)
// --order stride   for o < s: for i = o; i < n; i += s     (same work, worse locality)
// --order rand     i = idx[k] for a random permutation    (adds a 4 B index stream)
//
// Every element is processed exactly once per pass in every order, so the work
// is constant and only locality changes. Counters cover only timed passes.
#include <cmath>
#include <vector>

#include "common.hpp"

#define HEADER                                                                                        \
    "label,bench,kernel,order,stride,pages,footprint_bytes,n,cpu,rep,passes,ns_total,ns_per_elem,gbps," \
    "ghz,huge_kb,check_ok"

static const char *USAGE =
    "--size FOOTPRINT_BYTES [options]\n"
    "  --kernel mul|saxpy        (default mul)\n"
    "  --order seq|stride|rand   (default seq)\n"
    "  --stride S                element stride for --order stride (default 8)\n"
    "  --pages 4k|large|thp|hugetlb  (default 4k)\n"
    "  --cpu N --reps R (0 = setup only) --ms T --perf --label L --out FILE --meta FILE\n"
    "  --header --header-only --check\n";

enum class Kern { Mul, Saxpy };
enum class Order { Seq, Stride, Rand };

__attribute__((noinline)) static void mul_seq(double *__restrict__ z, const double *__restrict__ x,
                                              const double *__restrict__ y, size_t n) {
    for (size_t i = 0; i < n; i++) z[i] = x[i] * y[i];
}
__attribute__((noinline)) static void mul_stride(double *__restrict__ z, const double *__restrict__ x,
                                                 const double *__restrict__ y, size_t n, size_t s) {
    for (size_t o = 0; o < s; o++)
        for (size_t i = o; i < n; i += s) z[i] = x[i] * y[i];
}
__attribute__((noinline)) static void mul_idx(double *__restrict__ z, const double *__restrict__ x,
                                              const double *__restrict__ y, const uint32_t *idx, size_t n) {
    for (size_t k = 0; k < n; k++) {
        size_t i = idx[k];
        z[i] = x[i] * y[i];
    }
}
__attribute__((noinline)) static void saxpy_seq(double a, const double *__restrict__ x, double *__restrict__ y,
                                                size_t n) {
    for (size_t i = 0; i < n; i++) y[i] = a * x[i] + y[i];
}
__attribute__((noinline)) static void saxpy_stride(double a, const double *__restrict__ x, double *__restrict__ y,
                                                   size_t n, size_t s) {
    for (size_t o = 0; o < s; o++)
        for (size_t i = o; i < n; i += s) y[i] = a * x[i] + y[i];
}
__attribute__((noinline)) static void saxpy_idx(double a, const double *__restrict__ x, double *__restrict__ y,
                                                const uint32_t *idx, size_t n) {
    for (size_t k = 0; k < n; k++) {
        size_t i = idx[k];
        y[i] = a * x[i] + y[i];
    }
}

struct Run {
    Kern k;
    Order o;
    size_t n, s;
    double a;
    double *x, *y, *z;
    uint32_t *idx;
};

static void run_pass(const Run &r) {
    // stride 1 uses the same (vectorisable) loop as --order seq, so the
    // locality sweep's baseline differs only in locality, never in codegen
    Order o = (r.o == Order::Stride && r.s == 1) ? Order::Seq : r.o;
    if (r.k == Kern::Mul) {
        if (o == Order::Seq) mul_seq(r.z, r.x, r.y, r.n);
        else if (o == Order::Stride) mul_stride(r.z, r.x, r.y, r.n, r.s);
        else mul_idx(r.z, r.x, r.y, r.idx, r.n);
    } else {
        if (o == Order::Seq) saxpy_seq(r.a, r.x, r.y, r.n);
        else if (o == Order::Stride) saxpy_stride(r.a, r.x, r.y, r.n, r.s);
        else saxpy_idx(r.a, r.x, r.y, r.idx, r.n);
    }
}

static void init_arrays(Run &r) {
    for (size_t i = 0; i < r.n; i++) {
        r.x[i] = 1.0 + (double)(i % 7) * 0.25;
        r.y[i] = 2.0 + (double)(i % 5) * 0.125;
        if (r.z) r.z[i] = 0.0;
    }
}

// Reference: plain sequential loop on fresh inputs, compared element-wise.
static bool validate(Run &r) {
    init_arrays(r);
    std::vector<double> ref(r.n);
    for (size_t i = 0; i < r.n; i++) {
        double xi = 1.0 + (double)(i % 7) * 0.25, yi = 2.0 + (double)(i % 5) * 0.125;
        ref[i] = (r.k == Kern::Mul) ? xi * yi : r.a * xi + yi;
    }
    run_pass(r);
    const double *out = (r.k == Kern::Mul) ? r.z : r.y;
    bool ok = true;
    for (size_t i = 0; i < r.n; i++)
        if (std::fabs(out[i] - ref[i]) > 1e-12 * std::fabs(ref[i])) { ok = false; break; }
    init_arrays(r);
    return ok;
}

int main(int argc, char **argv) {
    Args a(argc, argv,
           {{"size", true}, {"kernel", true}, {"order", true}, {"stride", true}, {"pages", true}, {"cpu", true},
            {"reps", true}, {"ms", true}, {"perf", false}, {"label", true}, {"out", true}, {"meta", true}, {"header", false},
            {"header-only", false}, {"check", false}},
           USAGE);
    if (a.has("header-only")) {
        std::printf(HEADER);
        perf_print_header(stdout);
        std::printf("\n");
        return 0;
    }
    Kern kern = Kern::Mul;
    Order order = Order::Seq;
    PageMode pages = PageMode::k4K;
    std::string ks = a.str("kernel", "mul"), os = a.str("order", "seq");
    if (ks == "mul") kern = Kern::Mul;
    else if (ks == "saxpy") kern = Kern::Saxpy;
    else a.fail("bad --kernel");
    if (os == "seq") order = Order::Seq;
    else if (os == "stride") order = Order::Stride;
    else if (os == "rand") order = Order::Rand;
    else a.fail("bad --order");
    if (!parse_pages(a.str("pages", "4k"), pages)) a.fail("bad --pages");
    size_t foot = a.size("size", 0), stride = (size_t)a.num("stride", 8);
    int cpu = (int)a.num("cpu", -1), reps = (int)a.num("reps", 5);
    double ms = a.real("ms", 200.0);
    std::string label = a.str("label", "default");
    bool use_perf = a.has("perf");
    if (!foot || stride < 1 || reps < 0) a.fail();

    maybe_raise_priority();
    pin_self(cpu);
    double ghz = calibrate_ghz();

    int narr = (kern == Kern::Mul) ? 3 : 2;
    size_t n = foot / (8 * (size_t)narr);
    if (n < 8 || n > 0xFFFFFFFFULL) {
        std::fprintf(stderr, "error: bad footprint\n");
        return 2;
    }
    // Arrays share one buffer but start at different offsets modulo 4 KB, so
    // x[i], y[i], z[i] do not 4K-alias (false store->load dependencies).
    const size_t pad = 4096 + 448;
    Buffer b;
    if (buffer_alloc(b, (size_t)narr * (n * 8 + pad), pages, true)) return 1;
    Run r{kern, order, n, order == Order::Stride ? stride : 1, 0.5, nullptr, nullptr, nullptr, nullptr};
    r.x = (double *)(b.p);
    r.y = (double *)(b.p + n * 8 + pad);
    r.z = (kern == Kern::Mul) ? (double *)(b.p + 2 * (n * 8 + pad)) : nullptr;

    Buffer ib;
    if (order == Order::Rand) {
        if (buffer_alloc(ib, n * sizeof(uint32_t), pages, true)) return 1;
        r.idx = (uint32_t *)ib.p;
        for (size_t i = 0; i < n; i++) r.idx[i] = (uint32_t)i;
        uint64_t s = 2024;
        for (size_t i = n - 1; i > 0; i--) {
            size_t j = (size_t)(xorshift64(s) % (i + 1));
            std::swap(r.idx[i], r.idx[j]);
        }
    }

    bool ok = validate(r);
    if (a.has("check")) {
        std::fprintf(stderr, "kernel check %s order=%s stride=%zu pages=%s n=%zu: %s\n", ks.c_str(), os.c_str(), r.s,
                     pages_name(b.mode), n, ok ? "OK" : "FAIL");
        return ok ? 0 : 1;
    }
    long huge_kb = buffer_huge_kb(b);

    run_pass(r);  // warm pass, then size repetitions
    double t0 = now_ns();
    run_pass(r);
    double tp = now_ns() - t0;
    long passes = (long)(ms * 1e6 / tp);
    if (passes < 1) passes = 1;

    // bytes per element the program demands: 2 loads + 1 store of 8 B
    // (+4 B index for rand). Write-allocate traffic is NOT included.
    double bpe = 24.0 + (order == Order::Rand ? 4.0 : 0.0);

    FILE *out = open_output(a);
    Perf pc;
    if (use_perf) pc.init();
    if (a.has("header")) {
        std::fprintf(out, HEADER);
        perf_print_header(out);
        std::fprintf(out, "\n");
    }
    for (int rep = 0; rep < reps; rep++) {
        double v[NPERF];
        if (use_perf) pc.start();
        t0 = now_ns();
        for (long p = 0; p < passes; p++) run_pass(r);
        double t = now_ns() - t0;
        if (use_perf) {
            pc.stop();
            pc.read(v);
        }
        double elems = (double)passes * (double)n;
        std::fprintf(out, "%s,kernel,%s,%s,%zu,%s,%zu,%zu,%d,%d,%ld,%.0f,%.5f,%.4f,%.4f,%ld,%d", label.c_str(),
                     ks.c_str(), os.c_str(), r.s, pages_name(b.mode), foot, n, cpu, rep, passes, t, t / elems,
                     elems * bpe / t, ghz, huge_kb, ok ? 1 : 0);
        if (use_perf) perf_print_values(out, v);
        else perf_print_empty(out);
        std::fprintf(out, "\n");
        std::fflush(out);
    }
    double cs = 0;
    const double *res = (kern == Kern::Mul) ? r.z : r.y;
    for (size_t i = 0; i < n; i += 97) cs += res[i];
    g_sink = (uint64_t)cs;
    if (out != stdout) std::fclose(out);
    if (ib.map) buffer_free(ib);
    buffer_free(b);
    write_meta(a, ghz);
    return ok ? 0 : 1;
}
