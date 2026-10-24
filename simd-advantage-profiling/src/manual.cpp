/* manual.cpp - hand-written intrinsics, compiled with the same fixed flags in every binary.
 *   - masked-tail SAXPY (AVX2 maskload/maskstore, AVX-512 k-masks), used by the tail study
 *   - peak FLOP/s microkernels (many independent FMA chains), used by the roofline
 *   - effective clock estimate from a dependent integer-add chain (1 cycle/add on x86)
 * Functions use __attribute__((target(...))) and are only called after a runtime CPU check. */
#include "kernels.hpp"
#include "platform.hpp"
#include <cstdio>
#include <cstdlib>

using plat::now_sec;

#if defined(__x86_64__) || defined(__i386__)
#include <immintrin.h>
#define X86 1
#else
#define X86 0
#endif

#if X86
int has_avx2_fma(void) {
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx2") && __builtin_cpu_supports("fma");
}
int has_avx512f(void) {
    __builtin_cpu_init();
    return __builtin_cpu_supports("avx512f");
}

/* ---------- masked-tail SAXPY ---------- */
__attribute__((target("avx2,fma"))) void saxpy_mask_avx2_f32(size_t n, float a,
                                                             const float *RESTRICT x,
                                                             float *RESTRICT y) {
    const __m256 va = _mm256_set1_ps(a);
    size_t i = 0;
    for (; i + 32 <= n; i += 32) { /* unroll x4, like a typical compiler interleave count */
        __m256 y0 = _mm256_fmadd_ps(va, _mm256_loadu_ps(x + i), _mm256_loadu_ps(y + i));
        __m256 y1 = _mm256_fmadd_ps(va, _mm256_loadu_ps(x + i + 8), _mm256_loadu_ps(y + i + 8));
        __m256 y2 = _mm256_fmadd_ps(va, _mm256_loadu_ps(x + i + 16), _mm256_loadu_ps(y + i + 16));
        __m256 y3 = _mm256_fmadd_ps(va, _mm256_loadu_ps(x + i + 24), _mm256_loadu_ps(y + i + 24));
        _mm256_storeu_ps(y + i, y0);
        _mm256_storeu_ps(y + i + 8, y1);
        _mm256_storeu_ps(y + i + 16, y2);
        _mm256_storeu_ps(y + i + 24, y3);
    }
    for (; i + 8 <= n; i += 8)
        _mm256_storeu_ps(y + i, _mm256_fmadd_ps(va, _mm256_loadu_ps(x + i), _mm256_loadu_ps(y + i)));
    if (i < n) { /* one masked vector instead of a scalar remainder loop */
        const __m256i lane = _mm256_setr_epi32(0, 1, 2, 3, 4, 5, 6, 7);
        const __m256i m = _mm256_cmpgt_epi32(_mm256_set1_epi32((int)(n - i)), lane);
        __m256 vx = _mm256_maskload_ps(x + i, m);
        __m256 vy = _mm256_maskload_ps(y + i, m);
        _mm256_maskstore_ps(y + i, m, _mm256_fmadd_ps(va, vx, vy));
    }
}

__attribute__((target("avx512f"))) void saxpy_mask_avx512_f32(size_t n, float a,
                                                              const float *RESTRICT x,
                                                              float *RESTRICT y) {
    const __m512 va = _mm512_set1_ps(a);
    size_t i = 0;
    for (; i + 64 <= n; i += 64) {
        __m512 y0 = _mm512_fmadd_ps(va, _mm512_loadu_ps(x + i), _mm512_loadu_ps(y + i));
        __m512 y1 = _mm512_fmadd_ps(va, _mm512_loadu_ps(x + i + 16), _mm512_loadu_ps(y + i + 16));
        __m512 y2 = _mm512_fmadd_ps(va, _mm512_loadu_ps(x + i + 32), _mm512_loadu_ps(y + i + 32));
        __m512 y3 = _mm512_fmadd_ps(va, _mm512_loadu_ps(x + i + 48), _mm512_loadu_ps(y + i + 48));
        _mm512_storeu_ps(y + i, y0);
        _mm512_storeu_ps(y + i + 16, y1);
        _mm512_storeu_ps(y + i + 32, y2);
        _mm512_storeu_ps(y + i + 48, y3);
    }
    for (; i + 16 <= n; i += 16)
        _mm512_storeu_ps(y + i, _mm512_fmadd_ps(va, _mm512_loadu_ps(x + i), _mm512_loadu_ps(y + i)));
    if (i < n) {
        const __mmask16 m = (__mmask16)((1u << (n - i)) - 1u);
        __m512 vx = _mm512_maskz_loadu_ps(m, x + i);
        __m512 vy = _mm512_maskz_loadu_ps(m, y + i);
        _mm512_mask_storeu_ps(y + i, m, _mm512_fmadd_ps(va, vx, vy));
    }
}

/* ---------- peak FLOP/s ----------
 * Each accumulator is an independent dependency chain: acc = acc*m + c.
 * Enough chains are used to cover latency x issue width (FMA: 4 cyc x 2 pipes = 8). */
#define UNROLL _Pragma("GCC unroll 32")
#define NCH_SSE 12
#define NCH_AVX2 12
#define NCH_AVX512 24

static double peak_sse_ss(long it) { /* scalar mul+add in plain C++ (what the scalar build can do) */
    float acc[NCH_SSE], m = 0.9999f, c = 1e-4f;
    __asm__("" : "+x"(m), "+x"(c));
    UNROLL
    for (int j = 0; j < NCH_SSE; j++) acc[j] = 1.0f + j;
    for (long i = 0; i < it; i++) {
        UNROLL
        for (int j = 0; j < NCH_SSE; j++) { acc[j] = acc[j] * m + c; __asm__("" : "+x"(acc[j])); }
    }
    float s = 0;
    for (int j = 0; j < NCH_SSE; j++) s += acc[j];
    return s;
}
static double peak_sse_ps(long it) { /* 4-wide mul+add (SSE2 build) */
    __m128 acc[NCH_SSE], m = _mm_set1_ps(0.9999f), c = _mm_set1_ps(1e-4f);
    UNROLL
    for (int j = 0; j < NCH_SSE; j++) acc[j] = _mm_set1_ps(1.0f + j);
    for (long i = 0; i < it; i++)
        UNROLL
        for (int j = 0; j < NCH_SSE; j++) { acc[j] = _mm_add_ps(_mm_mul_ps(acc[j], m), c); __asm__("" : "+x"(acc[j])); }
    float s = 0;
    UNROLL
    for (int j = 0; j < NCH_SSE; j++) s += _mm_cvtss_f32(acc[j]);
    return s;
}
static double peak_sse_pd(long it) {
    __m128d acc[NCH_SSE], m = _mm_set1_pd(0.9999), c = _mm_set1_pd(1e-4);
    UNROLL
    for (int j = 0; j < NCH_SSE; j++) acc[j] = _mm_set1_pd(1.0 + j);
    for (long i = 0; i < it; i++)
        UNROLL
        for (int j = 0; j < NCH_SSE; j++) { acc[j] = _mm_add_pd(_mm_mul_pd(acc[j], m), c); __asm__("" : "+x"(acc[j])); }
    double s = 0;
    UNROLL
    for (int j = 0; j < NCH_SSE; j++) s += _mm_cvtsd_f64(acc[j]);
    return s;
}
__attribute__((target("avx2,fma"))) static double peak_fma_ss(long it) {
    __m128 acc[NCH_AVX2], m = _mm_set_ss(0.9999f), c = _mm_set_ss(1e-4f);
    UNROLL
    for (int j = 0; j < NCH_AVX2; j++) acc[j] = _mm_set_ss(1.0f + j);
    for (long i = 0; i < it; i++)
        UNROLL
        for (int j = 0; j < NCH_AVX2; j++) { acc[j] = _mm_fmadd_ss(acc[j], m, c); __asm__("" : "+x"(acc[j])); }
    float s = 0;
    UNROLL
    for (int j = 0; j < NCH_AVX2; j++) s += _mm_cvtss_f32(acc[j]);
    return s;
}
__attribute__((target("avx2,fma"))) static double peak_avx2_ps(long it) {
    __m256 acc[NCH_AVX2], m = _mm256_set1_ps(0.9999f), c = _mm256_set1_ps(1e-4f);
    UNROLL
    for (int j = 0; j < NCH_AVX2; j++) acc[j] = _mm256_set1_ps(1.0f + j);
    for (long i = 0; i < it; i++)
        UNROLL
        for (int j = 0; j < NCH_AVX2; j++) { acc[j] = _mm256_fmadd_ps(acc[j], m, c); __asm__("" : "+x"(acc[j])); }
    float s = 0;
    UNROLL
    for (int j = 0; j < NCH_AVX2; j++) s += _mm256_cvtss_f32(acc[j]);
    return s;
}
__attribute__((target("avx2,fma"))) static double peak_avx2_pd(long it) {
    __m256d acc[NCH_AVX2], m = _mm256_set1_pd(0.9999), c = _mm256_set1_pd(1e-4);
    UNROLL
    for (int j = 0; j < NCH_AVX2; j++) acc[j] = _mm256_set1_pd(1.0 + j);
    for (long i = 0; i < it; i++)
        UNROLL
        for (int j = 0; j < NCH_AVX2; j++) { acc[j] = _mm256_fmadd_pd(acc[j], m, c); __asm__("" : "+x"(acc[j])); }
    double s = 0;
    UNROLL
    for (int j = 0; j < NCH_AVX2; j++) s += _mm256_cvtsd_f64(acc[j]);
    return s;
}
__attribute__((target("avx512f"))) static double peak_avx512_ps(long it) {
    __m512 acc[NCH_AVX512], m = _mm512_set1_ps(0.9999f), c = _mm512_set1_ps(1e-4f);
    UNROLL
    for (int j = 0; j < NCH_AVX512; j++) acc[j] = _mm512_set1_ps(1.0f + j);
    for (long i = 0; i < it; i++)
        UNROLL
        for (int j = 0; j < NCH_AVX512; j++) { acc[j] = _mm512_fmadd_ps(acc[j], m, c); __asm__("" : "+v"(acc[j])); }
    float s = 0;
    UNROLL
    for (int j = 0; j < NCH_AVX512; j++) s += _mm512_reduce_add_ps(acc[j]);
    return s;
}
__attribute__((target("avx512f"))) static double peak_avx512_pd(long it) {
    __m512d acc[NCH_AVX512], m = _mm512_set1_pd(0.9999), c = _mm512_set1_pd(1e-4);
    UNROLL
    for (int j = 0; j < NCH_AVX512; j++) acc[j] = _mm512_set1_pd(1.0 + j);
    for (long i = 0; i < it; i++)
        UNROLL
        for (int j = 0; j < NCH_AVX512; j++) { acc[j] = _mm512_fmadd_pd(acc[j], m, c); __asm__("" : "+v"(acc[j])); }
    double s = 0;
    UNROLL
    for (int j = 0; j < NCH_AVX512; j++) s += _mm512_reduce_add_pd(acc[j]);
    return s;
}

double measure_ghz(void) {
    /* Chain of 16 dependent register-register adds per iteration (1 cycle each).
     * Register operands are used on purpose: recent Intel cores (Golden Cove and later)
     * can fold "add reg, imm" chains at rename time, which would overstate the clock. */
    const long iters = 2000000; /* 32 M dependent adds, ~10 ms at 3 GHz */
    double best = 0;
    for (int rep = 0; rep < 3; rep++) {
        unsigned long v = 0, one = 1;
        __asm__ volatile("" : "+r"(one)); /* value unknown to the compiler */
        double t0 = now_sec();
        for (long i = 0; i < iters; i++) {
            __asm__ volatile(
                "add %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\t"
                "add %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\t"
                "add %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\t"
                "add %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\t"
                : "+r"(v) : "r"(one));
        }
        double t = now_sec() - t0;
        double ghz = 16.0 * iters / t / 1e9;
        if (ghz > best) best = ghz;
    }
    return best;
}

typedef double (*peak_fn)(long);
static volatile double peak_sink;

/* Short clock probe (~0.5 ms): fast enough to catch the clock *while* a frequency licence from the
 * preceding vector work is still in force (Intel holds it for ~1-2 ms after the last heavy op). */
static double ghz_short(void) {
    const long iters = 100000; /* 1.6 M dependent adds */
    unsigned long v = 0, one = 1;
    __asm__ volatile("" : "+r"(one));
    double t0 = now_sec();
    for (long i = 0; i < iters; i++) {
        __asm__ volatile(
            "add %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\t"
            "add %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\t"
            "add %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\t"
            "add %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\tadd %1, %0\n\t"
            : "+r"(v) : "r"(one));
    }
    return 16.0 * iters / (now_sec() - t0) / 1e9;
}

/* Clock right after ~30 ms of sustained work of each kind (median of 7 trials). */
static void license_one(const char *label, peak_fn f) {
    double g[7];
    for (int r = 0; r < 7; r++) {
        if (f) {
            long it = 1000;
            double t0 = now_sec();
            while (now_sec() - t0 < 0.03) peak_sink = f(it);
        } else {
            double t0 = now_sec(); /* scalar-integer baseline: just spin */
            while (now_sec() - t0 < 0.03) {}
        }
        g[r] = ghz_short();
    }
    for (int i = 0; i < 7; i++)
        for (int j = i + 1; j < 7; j++)
            if (g[j] < g[i]) { double t = g[i]; g[i] = g[j]; g[j] = t; }
    printf("%s,%.4f,%.4f,%.4f\n", label, g[3], g[0], g[6]);
}

void run_license(void) {
    printf("after,ghz_median,ghz_min,ghz_max\n");
    license_one("idle_spin", nullptr);
    license_one("scalar_mul_add", peak_sse_ss);
    license_one("sse2_mul_add", peak_sse_ps);
    if (has_avx2_fma()) license_one("avx2_fma", peak_avx2_ps);
    if (has_avx512f()) license_one("avx512_fma", peak_avx512_ps);
    license_one("idle_spin_again", nullptr);
}

static void peak_one(const char *isa, const char *dt, int lanes, int nch, peak_fn f,
                     double flops_per_lane_op, double ghz) {
    long it = 1000;
    double t = 0;
    for (;;) { /* calibrate to >= 50 ms */
        double t0 = now_sec();
        peak_sink = f(it);
        t = now_sec() - t0;
        if (t > 0.05) break;
        it *= 2;
    }
    double best = t;
    for (int r = 0; r < 5; r++) {
        double t0 = now_sec();
        peak_sink = f(it);
        double tt = now_sec() - t0;
        if (tt < best) best = tt;
    }
    double flops = (double)it * nch * lanes * flops_per_lane_op;
    double gf = flops / best / 1e9;
    printf("%s,%s,%d,%.4f,%.4f,%.3f\n", isa, dt, lanes, gf, ghz, gf / ghz);
}

void run_peak(void) {
    double ghz = measure_ghz();
    printf("isa,dtype,lanes,gflops,ghz,flops_per_cycle\n");
    peak_one("scalar_sse", "f32", 1, NCH_SSE, peak_sse_ss, 2, ghz);
    peak_one("sse2", "f32", 4, NCH_SSE, peak_sse_ps, 2, ghz);
    peak_one("sse2", "f64", 2, NCH_SSE, peak_sse_pd, 2, ghz);
    if (has_avx2_fma()) {
        peak_one("scalar_fma", "f32", 1, NCH_AVX2, peak_fma_ss, 2, ghz);
        peak_one("avx2_fma", "f32", 8, NCH_AVX2, peak_avx2_ps, 2, ghz);
        peak_one("avx2_fma", "f64", 4, NCH_AVX2, peak_avx2_pd, 2, ghz);
    }
    if (has_avx512f()) {
        peak_one("avx512_fma", "f32", 16, NCH_AVX512, peak_avx512_ps, 2, ghz);
        peak_one("avx512_fma", "f64", 8, NCH_AVX512, peak_avx512_pd, 2, ghz);
    }
}

#else /* ---------------- non-x86 (e.g. aarch64 / NEON) fallbacks ---------------- */
int has_avx2_fma(void) { return 0; }
int has_avx512f(void) { return 0; }
void saxpy_mask_avx2_f32(size_t n, float a, const float *RESTRICT x, float *RESTRICT y) {
    (void)n; (void)a; (void)x; (void)y;
    fprintf(stderr, "AVX2 not available on this architecture\n");
    exit(2);
}
void saxpy_mask_avx512_f32(size_t n, float a, const float *RESTRICT x, float *RESTRICT y) {
    (void)n; (void)a; (void)x; (void)y;
    fprintf(stderr, "AVX-512 not available on this architecture\n");
    exit(2);
}
double measure_ghz(void) {
#if defined(__aarch64__)
    const long iters = 2000000;
    double best = 0;
    for (int rep = 0; rep < 3; rep++) {
        unsigned long v = 0;
        double t0 = now_sec();
        for (long i = 0; i < iters; i++) {
            __asm__ volatile(
                "add %0, %0, #1\n\tadd %0, %0, #1\n\tadd %0, %0, #1\n\tadd %0, %0, #1\n\t"
                "add %0, %0, #1\n\tadd %0, %0, #1\n\tadd %0, %0, #1\n\tadd %0, %0, #1\n\t"
                "add %0, %0, #1\n\tadd %0, %0, #1\n\tadd %0, %0, #1\n\tadd %0, %0, #1\n\t"
                "add %0, %0, #1\n\tadd %0, %0, #1\n\tadd %0, %0, #1\n\tadd %0, %0, #1\n\t"
                : "+r"(v));
        }
        double t = now_sec() - t0;
        double ghz = 16.0 * iters / t / 1e9;
        if (ghz > best) best = ghz;
    }
    return best;
#else
    return 0.0;
#endif
}
void run_peak(void) {
    printf("isa,dtype,lanes,gflops,ghz,flops_per_cycle\n");
    fprintf(stderr, "peak microkernels are only implemented for x86-64\n");
}
void run_license(void) { printf("after,ghz_median,ghz_min,ghz_max\n"); }
#endif
