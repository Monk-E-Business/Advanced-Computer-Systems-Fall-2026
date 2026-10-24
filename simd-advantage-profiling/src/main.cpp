/* main.cpp - benchmark harness, correctness checker, and peak/clock/topology probes.
 *
 * Compiled with the SAME fixed flags in every variant (vectorization off, no FP contraction),
 * so the timing loop, data initialisation and the reference implementation are identical
 * across builds. Only kernels.cpp differs between bench_<variant> binaries.
 * Builds with g++ on Windows (MSYS2 UCRT64) and Linux; OS specifics live in platform.hpp.
 *
 * Usage:
 *   bench_<v> --kernel saxpy --type f32 --n 1024,4096 [--offset BYTES] [--pattern seq|random]
 *             [--yshift BYTES] [--samples 7] [--min-time 0.01] [--header] [--cpu N]
 *   (--cpu N pins the process to logical CPU N; on Windows it also uses HIGH priority class)
 *   (--yshift moves y/z relative to x; SIMD_DEBUG_ADDR=1 prints the array addresses)
 *   bench_<v> --check --kernel saxpy --type f32 --n 0,1,17,1000 [--offset 4]
 *   bench_<v> --peak        measured peak FLOP/s per ISA (CSV)
 *   bench_<v> --ghz         effective core clock estimate
 *   bench_<v> --license     core clock right after sustained scalar / AVX2 / AVX-512 work (CSV)
 *   bench_<v> --info        variant name and kernel compile flags
 *   bench_<v> --sysinfo     CPU brand, caches, cores/SMT/hybrid topology, timer (JSON)
 *
 * Kernels: saxpy dot dotsimd mul stencil read write saxpy_s{1,2,4,8,16} gather
 *          mask_avx2 mask_avx512      (types f32 f64 i32 for the first five; others f32 only)
 */
#include "kernels.hpp"
#include "platform.hpp"
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#if defined(_WIN32)
#include <fcntl.h>
#include <io.h>
#endif

using plat::now_sec;

#ifndef VARIANT_NAME
#define VARIANT_NAME "unknown"
#endif
#ifndef VARIANT_FLAGS
#define VARIANT_FLAGS "unknown"
#endif

enum { T_F32, T_F64, T_I32 };
enum { K_SAXPY, K_DOT, K_DOTSIMD, K_MUL, K_STENCIL, K_READ, K_WRITE, K_STRIDE, K_GATHER,
       K_MASK_AVX2, K_MASK_AVX512 };
static const char *TYPE_NAMES[] = {"f32", "f64", "i32"};
#define GUARD 64          /* sentinel elements after every array */
#define SENTINEL_BYTE 0x5A

typedef struct {
    int kernel, type;
    const char *kname;
    size_t n, stride, offset, yshift, len;
    int pattern; /* 0 = seq, 1 = random (gather only) */
    void *x, *y, *z, *y0;
    uint32_t *idx;
    void *bx, *by, *bz, *by0, *bidx; /* malloc bases */
} ctx_t;

static volatile double g_sink;

static size_t esize(int t) { return t == T_F64 ? 8 : 4; }

/* ---------- allocation: 4 KiB aligned base + deliberate byte offset ---------- */
static void *alloc_off(size_t bytes, size_t offset, void **base) {
    void *p = plat::aligned_alloc_bytes(bytes + offset + 4096, 4096);
    *base = p;
    return (char *)p + offset;
}

static uint64_t rng_state = 0x9E3779B97F4A7C15ull;
static uint64_t xorshift64(void) {
    uint64_t x = rng_state;
    x ^= x << 13; x ^= x >> 7; x ^= x << 17;
    return rng_state = x;
}
static double urand(void) { return (double)(xorshift64() >> 11) * (1.0 / 9007199254740992.0); }

static void fill(void *p, int t, size_t len) {
    for (size_t i = 0; i < len; i++) {
        switch (t) {
        case T_F32: ((float *)p)[i] = (float)(2.0 * urand() - 1.0); break;
        case T_F64: ((double *)p)[i] = 2.0 * urand() - 1.0; break;
        default: ((uint32_t *)p)[i] = (uint32_t)(xorshift64() % 17) - 8u; break;
        }
    }
}

static int parse_kernel(const char *s, size_t *stride) {
    *stride = 1;
    if (!strcmp(s, "saxpy")) return K_SAXPY;
    if (!strcmp(s, "dot")) return K_DOT;
    if (!strcmp(s, "dotsimd")) return K_DOTSIMD;
    if (!strcmp(s, "mul")) return K_MUL;
    if (!strcmp(s, "stencil")) return K_STENCIL;
    if (!strcmp(s, "read")) return K_READ;
    if (!strcmp(s, "write")) return K_WRITE;
    if (!strcmp(s, "gather")) return K_GATHER;
    if (!strcmp(s, "mask_avx2")) return K_MASK_AVX2;
    if (!strcmp(s, "mask_avx512")) return K_MASK_AVX512;
    if (!strncmp(s, "saxpy_s", 7)) {
        long v = atol(s + 7);
        if (v == 1 || v == 2 || v == 4 || v == 8 || v == 16) { *stride = (size_t)v; return K_STRIDE; }
    }
    fprintf(stderr, "unknown kernel '%s'\n", s);
    exit(2);
}

static void setup(ctx_t *c, size_t n) {
    size_t es = esize(c->type);
    c->n = n;
    c->len = (c->kernel == K_STRIDE) ? n * c->stride : n;
    size_t bytes = (c->len + GUARD) * es;
    c->x = alloc_off(bytes, c->offset, &c->bx);
    c->y = alloc_off(bytes, c->offset + c->yshift, &c->by); /* yshift: move outputs relative to x */
    c->z = alloc_off(bytes, c->offset + c->yshift, &c->bz);
    c->y0 = alloc_off(bytes, 0, &c->by0);
    memset(c->x, SENTINEL_BYTE, bytes);
    memset(c->y, SENTINEL_BYTE, bytes);
    memset(c->z, SENTINEL_BYTE, bytes);
    fill(c->x, c->type, c->len); /* first touch happens here, outside timing */
    fill(c->y, c->type, c->len);
    memcpy(c->y0, c->y, bytes);
    if (getenv("SIMD_DEBUG_ADDR")) /* explicit 0x hex: MinGW's %p prints no 0x prefix */
        fprintf(stderr, "x=0x%llx y=0x%llx z=0x%llx  (y-x) mod 4096 = %lld\n",
                (unsigned long long)(uintptr_t)c->x, (unsigned long long)(uintptr_t)c->y,
                (unsigned long long)(uintptr_t)c->z, (long long)(((uintptr_t)c->y - (uintptr_t)c->x) & 4095));
    c->idx = NULL;
    c->bidx = NULL;
    if (c->kernel == K_GATHER) {
        c->idx = static_cast<uint32_t *>(alloc_off(n * sizeof(uint32_t) + 64, c->offset, &c->bidx));
        for (size_t i = 0; i < n; i++) c->idx[i] = (uint32_t)i;
        if (c->pattern == 1) /* Fisher-Yates permutation: every x element used exactly once */
            for (size_t i = n; i > 1; i--) {
                size_t j = (size_t)(xorshift64() % i);
                uint32_t t = c->idx[i - 1]; c->idx[i - 1] = c->idx[j]; c->idx[j] = t;
            }
    }
}

static void teardown(ctx_t *c) {
    plat::aligned_free(c->bx); plat::aligned_free(c->by); plat::aligned_free(c->bz);
    plat::aligned_free(c->by0);
    if (c->bidx) plat::aligned_free(c->bidx);
}

/* One kernel invocation. parity alternates the sign of 'a' so in-place kernels (saxpy)
 * oscillate between y0 and y0 + a*x instead of growing without bound. */
static void call(ctx_t *c, int parity) {
    size_t n = c->n;
    switch (c->type) {
    case T_F32: {
        float a = parity ? -0.5f : 0.5f;
        float *x = static_cast<float *>(c->x), *y = static_cast<float *>(c->y), *z = static_cast<float *>(c->z);
        switch (c->kernel) {
        case K_SAXPY: saxpy_f32(n, a, x, y); break;
        case K_DOT: g_sink += dot_f32(n, x, y); break;
        case K_DOTSIMD: g_sink += dotsimd_f32(n, x, y); break;
        case K_MUL: mul_f32(n, x, y, z); break;
        case K_STENCIL: stencil_f32(n, 0.25f, 0.5f, 0.25f, x, y); break;
        case K_READ: g_sink += read_f32(n, x); break;
        case K_WRITE: write_f32(n, a, y); break;
        case K_GATHER: saxpy_gather_f32(n, a, c->idx, x, y); break;
        case K_MASK_AVX2: saxpy_mask_avx2_f32(n, a, x, y); break;
        case K_MASK_AVX512: saxpy_mask_avx512_f32(n, a, x, y); break;
        case K_STRIDE:
            switch (c->stride) {
            case 1: saxpy_s1_f32(n, a, x, y); break;
            case 2: saxpy_s2_f32(n, a, x, y); break;
            case 4: saxpy_s4_f32(n, a, x, y); break;
            case 8: saxpy_s8_f32(n, a, x, y); break;
            default: saxpy_s16_f32(n, a, x, y); break;
            }
            break;
        }
        break;
    }
    case T_F64: {
        double a = parity ? -0.5 : 0.5;
        double *x = static_cast<double *>(c->x), *y = static_cast<double *>(c->y), *z = static_cast<double *>(c->z);
        switch (c->kernel) {
        case K_SAXPY: saxpy_f64(n, a, x, y); break;
        case K_DOT: g_sink += dot_f64(n, x, y); break;
        case K_DOTSIMD: g_sink += dotsimd_f64(n, x, y); break;
        case K_MUL: mul_f64(n, x, y, z); break;
        case K_STENCIL: stencil_f64(n, 0.25, 0.5, 0.25, x, y); break;
        default: fprintf(stderr, "kernel not available for f64\n"); exit(2);
        }
        break;
    }
    default: {
        uint32_t a = parity ? (uint32_t)0 - 3u : 3u;
        uint32_t *x = static_cast<uint32_t *>(c->x), *y = static_cast<uint32_t *>(c->y), *z = static_cast<uint32_t *>(c->z);
        switch (c->kernel) {
        case K_SAXPY: saxpy_i32(n, a, x, y); break;
        case K_DOT: g_sink += dot_i32(n, x, y); break;
        case K_DOTSIMD: g_sink += dotsimd_i32(n, x, y); break;
        case K_MUL: mul_i32(n, x, y, z); break;
        case K_STENCIL: stencil_i32(n, 1u, 2u, 1u, x, y); break;
        default: fprintf(stderr, "kernel not available for i32\n"); exit(2);
        }
        break;
    }
    }
}

/* Compulsory bytes moved, flops (or integer ops), and working-set size per call. */
static void cost(const ctx_t *c, double *bytes, double *flops, double *ws) {
    double n = (double)c->n, es = (double)esize(c->type), s = (double)c->stride;
    switch (c->kernel) {
    case K_SAXPY: case K_MASK_AVX2: case K_MASK_AVX512:
        *bytes = 3 * n * es; *flops = 2 * n; *ws = 2 * n * es; break;
    case K_DOT: case K_DOTSIMD: *bytes = 2 * n * es; *flops = 2 * n; *ws = 2 * n * es; break;
    case K_MUL: *bytes = 3 * n * es; *flops = n; *ws = 3 * n * es; break;
    case K_STENCIL: *bytes = 2 * n * es; *flops = n >= 2 ? 5 * (n - 2) : 0; *ws = 2 * n * es; break;
    case K_READ: *bytes = n * es; *flops = n; *ws = n * es; break;
    case K_WRITE: *bytes = n * es; *flops = 0; *ws = n * es; break;
    case K_STRIDE: *bytes = 3 * n * es; *flops = 2 * n; *ws = 2 * n * s * es; break;
    case K_GATHER: *bytes = n * (3 * es + 4); *flops = 2 * n; *ws = n * (2 * es + 4); break;
    default: *bytes = *flops = *ws = 0;
    }
}

/* ------------------------------ timing ------------------------------ */
static double time_reps(ctx_t *c, long reps, long *parity) {
    double t0 = now_sec();
    for (long r = 0; r < reps; r++) call(c, (int)((*parity)++ & 1));
    return now_sec() - t0;
}

static void bench(ctx_t *c, int samples, double min_time, double ghz) {
    long parity = 0;
    /* warm-up: at least 2 calls and >= 20 ms (caches, TLB, branch predictors, clocks) */
    double tw = 0;
    long nw = 0;
    while (nw < 2 || tw < 0.02) { tw += time_reps(c, 1, &parity); nw++; }
    /* calibrate repetitions per sample so one sample lasts >= min_time */
    long reps = 1;
    for (;;) {
        double t = time_reps(c, reps, &parity);
        if (t >= min_time) break;
        double scale = t > 0 ? 1.25 * min_time / t : 16;
        if (scale < 2) scale = 2;
        if (scale > 1024) scale = 1024;
        reps = (long)(reps * scale);
    }
    double bytes, flops, ws;
    cost(c, &bytes, &flops, &ws);
    const char *pat = c->kernel == K_GATHER ? (c->pattern ? "random" : "seq") : "none";
    for (int s = 0; s < samples; s++) {
        double t = time_reps(c, reps, &parity);
        printf("%s,%s,%s,%zu,%zu,%zu,%s,%.0f,%.0f,%.0f,%ld,%d,%.9e,%.4f,%zu\n", VARIANT_NAME,
               c->kname, TYPE_NAMES[c->type], c->n, c->offset, c->stride, pat, ws, bytes, flops,
               reps, s, t / reps, ghz, c->yshift);
    }
    fflush(stdout);
}

/* ------------------------------ checking ------------------------------ */
static long double ld(const ctx_t *c, const void *p, size_t i) {
    switch (c->type) {
    case T_F32: return ((const float *)p)[i];
    case T_F64: return ((const double *)p)[i];
    default: return ((const uint32_t *)p)[i];
    }
}
static uint32_t u32(const void *p, size_t i) { return ((const uint32_t *)p)[i]; }

static int guard_ok(const ctx_t *c, const void *p) {
    const unsigned char *b = (const unsigned char *)p + c->len * esize(c->type);
    for (size_t i = 0; i < GUARD * esize(c->type); i++)
        if (b[i] != SENTINEL_BYTE) return 0;
    return 1;
}

/* Returns max(|got-ref| / tolerance); <= 1 passes. Integer kernels must match exactly. */
static double check_one(ctx_t *c) {
    const int is_int = c->type == T_I32;
    const long double u = c->type == T_F32 ? 5.9604645e-8L : 1.1102230246251565e-16L;
    const long double tiny = 1e-30L;
    size_t n = c->n;
    double worst = 0;
#define UPD(err, tol) do { double r_ = (double)((err) / ((tol) + tiny)); if (r_ > worst) worst = r_; } while (0)
#define BAD() do { worst = INFINITY; } while (0)
    g_sink = 0;
    call(c, 0); /* one call, a = +0.5 (f) or +3 (i32) */
    long double a = is_int ? 3.0L : 0.5L;
    switch (c->kernel) {
    case K_SAXPY: case K_MASK_AVX2: case K_MASK_AVX512: case K_GATHER:
        for (size_t i = 0; i < n; i++) {
            size_t xi = c->kernel == K_GATHER ? c->idx[i] : i;
            if (is_int) {
                if (u32(c->y, i) != 3u * u32(c->x, xi) + u32(c->y0, i)) BAD();
            } else {
                long double e = a * ld(c, c->x, xi) + ld(c, c->y0, i);
                UPD(std::fabs(ld(c, c->y, i) - e), 2 * u * (std::fabs(a * ld(c, c->x, xi)) + std::fabs(ld(c, c->y0, i))));
            }
        }
        if (!guard_ok(c, c->y)) BAD();
        break;
    case K_STRIDE:
        for (size_t j = 0; j < c->len; j++) {
            if (j % c->stride == 0) {
                long double e = a * ld(c, c->x, j) + ld(c, c->y0, j);
                UPD(std::fabs(ld(c, c->y, j) - e), 2 * u * (std::fabs(a * ld(c, c->x, j)) + std::fabs(ld(c, c->y0, j))));
            } else if (memcmp((char *)c->y + j * 4, (char *)c->y0 + j * 4, 4) != 0) {
                BAD(); /* gap element was written */
            }
        }
        if (!guard_ok(c, c->y)) BAD();
        break;
    case K_DOT: case K_DOTSIMD: case K_READ: {
        long double e = 0, mag = 0;
        uint32_t ei = 0;
        for (size_t i = 0; i < n; i++) {
            long double t = c->kernel == K_READ ? ld(c, c->x, i) : ld(c, c->x, i) * ld(c, c->y, i);
            e += t; mag += std::fabs(t);
            if (is_int) ei += u32(c->x, i) * u32(c->y, i);
        }
        if (is_int) {
            if ((uint32_t)g_sink != ei) BAD();
        } else {
            UPD(std::fabs((long double)g_sink - e), (long double)(n + 2) * u * mag);
        }
        break;
    }
    case K_MUL:
        for (size_t i = 0; i < n; i++) {
            if (is_int) {
                if (u32(c->z, i) != u32(c->x, i) * u32(c->y, i)) BAD();
            } else {
                long double e = ld(c, c->x, i) * ld(c, c->y, i);
                UPD(std::fabs(ld(c, c->z, i) - e), 2 * u * std::fabs(e));
            }
        }
        if (!guard_ok(c, c->z)) BAD();
        break;
    case K_STENCIL: {
        long double ca = is_int ? 1 : 0.25L, cb = is_int ? 2 : 0.5L, cc = is_int ? 1 : 0.25L;
        for (size_t i = 0; i < n; i++) {
            if (i == 0 || i + 1 >= n) { /* boundary elements must be untouched */
                if (memcmp((char *)c->y + i * esize(c->type), (char *)c->y0 + i * esize(c->type), esize(c->type))) BAD();
                continue;
            }
            if (is_int) {
                if (u32(c->y, i) != u32(c->x, i - 1) + 2u * u32(c->x, i) + u32(c->x, i + 1)) BAD();
            } else {
                long double t0 = ca * ld(c, c->x, i - 1), t1 = cb * ld(c, c->x, i), t2 = cc * ld(c, c->x, i + 1);
                UPD(std::fabs(ld(c, c->y, i) - (t0 + t1 + t2)), 4 * u * (std::fabs(t0) + std::fabs(t1) + std::fabs(t2)));
            }
        }
        if (!guard_ok(c, c->y)) BAD();
        break;
    }
    case K_WRITE:
        for (size_t i = 0; i < n; i++)
            if (((float *)c->y)[i] != 0.5f) BAD();
        if (!guard_ok(c, c->y)) BAD();
        break;
    }
    return worst;
}

/* ------------------------------ CLI ------------------------------ */
static void usage(void) {
    fprintf(stderr, "see header of src/main.c for usage\n");
    exit(2);
}

int main(int argc, char **argv) {
#if defined(_WIN32)
    _setmode(_fileno(stdout), _O_BINARY); /* '\n' line endings in CSV output, not CRLF */
#endif
    const char *kname = "saxpy", *tname = "f32", *nlist = "4096", *pattern = "seq";
    size_t offset = 0, yshift = 0;
    int samples = 7, header = 0, do_check = 0, cpu = -1;
    double min_time = 0.01;
    for (int i = 1; i + 1 < argc; i++) /* pin first, so --peak / --ghz also run pinned */
        if (!strcmp(argv[i], "--cpu") && !plat::pin_to_cpu(atoi(argv[i + 1])))
            fprintf(stderr, "warning: could not pin to CPU %s\n", argv[i + 1]);
    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
#define NEXT() (i + 1 < argc ? argv[++i] : (usage(), ""))
        if (!strcmp(a, "--kernel")) kname = NEXT();
        else if (!strcmp(a, "--type")) tname = NEXT();
        else if (!strcmp(a, "--n")) nlist = NEXT();
        else if (!strcmp(a, "--offset")) offset = (size_t)atol(NEXT());
        else if (!strcmp(a, "--yshift")) yshift = (size_t)atol(NEXT());
        else if (!strcmp(a, "--pattern")) pattern = NEXT();
        else if (!strcmp(a, "--samples")) samples = atoi(NEXT());
        else if (!strcmp(a, "--min-time")) min_time = atof(NEXT());
        else if (!strcmp(a, "--header")) header = 1;
        else if (!strcmp(a, "--check")) do_check = 1;
        else if (!strcmp(a, "--peak")) { run_peak(); return 0; }
        else if (!strcmp(a, "--license")) { run_license(); return 0; }
        else if (!strcmp(a, "--ghz")) { printf("%.4f\n", measure_ghz()); return 0; }
        else if (!strcmp(a, "--info")) { printf("variant=%s\nflags=%s\n", VARIANT_NAME, VARIANT_FLAGS); return 0; }
        else if (!strcmp(a, "--sysinfo")) { plat::print_topology_json(); return 0; }
        else if (!strcmp(a, "--cpu")) cpu = atoi(NEXT());
        else usage();
    }
    ctx_t c;
    memset(&c, 0, sizeof c);
    c.kname = kname;
    c.kernel = parse_kernel(kname, &c.stride);
    c.type = !strcmp(tname, "f64") ? T_F64 : !strcmp(tname, "i32") ? T_I32 : T_F32;
    c.offset = offset;
    c.yshift = yshift;
    c.pattern = !strcmp(pattern, "random");
    if (c.kernel >= K_READ && c.type != T_F32) { fprintf(stderr, "%s is f32-only\n", kname); return 2; }
    if (c.kernel == K_MASK_AVX2 && !has_avx2_fma()) { fprintf(stderr, "CPU lacks AVX2/FMA\n"); return 4; }
    if (c.kernel == K_MASK_AVX512 && !has_avx512f()) { fprintf(stderr, "CPU lacks AVX-512F\n"); return 4; }

    double ghz = do_check ? 0 : measure_ghz();
    if (header && !do_check)
        printf("variant,kernel,type,n,offset,stride,pattern,ws_bytes,bytes,flops,reps,sample,sec_per_call,ghz,yshift\n");

    (void)cpu;
    int fails = 0;
    std::string list(nlist);
    size_t pos = 0;
    while (pos <= list.size()) {
        size_t comma = list.find(',', pos);
        if (comma == std::string::npos) comma = list.size();
        std::string tok = list.substr(pos, comma - pos);
        pos = comma + 1;
        if (tok.empty()) continue;
        size_t n = (size_t)strtoull(tok.c_str(), NULL, 10);
        rng_state = 0x9E3779B97F4A7C15ull ^ (n * 0x100000001B3ull); /* deterministic per n */
        setup(&c, n);
        if (do_check) {
            double r = check_one(&c);
            int ok = r <= 1.0;
            fails += !ok;
            printf("CHECK,%s,%s,%s,%zu,%zu,%zu,%s,%s,%.3g\n", VARIANT_NAME, kname, tname, n, offset,
                   c.stride, pattern, ok ? "PASS" : "FAIL", r);
        } else {
            bench(&c, samples, min_time, ghz);
        }
        teardown(&c);
    }
    return fails ? 1 : 0;
}
