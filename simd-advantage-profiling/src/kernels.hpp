// kernels.hpp - kernel declarations.
//
// kernels.cpp is compiled once per build variant (scalar, sse2, avx2, native, avx512, ...),
// each time with different g++ flags, and linked into its own bench_<variant> binary.
// The harness (main.cpp) and the hand-written intrinsics (manual.cpp) are compiled with the
// SAME fixed flags in every binary, so only the kernels change between variants.
//
// extern "C": no C++ name mangling, so compiler reports and disassembly show plain names.
// "i32" kernels use uint32_t storage: 32-bit integer lanes with well-defined wrap-around;
// they compile to the same SIMD instructions as signed int32 (vpaddd / vpmulld) without
// signed-overflow UB in the repeated benchmark loops.
#pragma once
#include <cstddef>
#include <cstdint>

#define RESTRICT __restrict__

#define DECL_KERNELS(T, S)                                                               \
    void saxpy_##S(size_t n, T a, const T *RESTRICT x, T *RESTRICT y);                 \
    T dot_##S(size_t n, const T *RESTRICT x, const T *RESTRICT y);                     \
    T dotsimd_##S(size_t n, const T *RESTRICT x, const T *RESTRICT y);                 \
    void mul_##S(size_t n, const T *RESTRICT x, const T *RESTRICT y, T *RESTRICT z);   \
    void stencil_##S(size_t n, T a, T b, T c, const T *RESTRICT x, T *RESTRICT y);

extern "C" {
DECL_KERNELS(float, f32)
DECL_KERNELS(double, f64)
DECL_KERNELS(uint32_t, i32)

// Bandwidth probes (float32). read uses an omp-simd reduction so it is vectorized in
// every non-scalar build; write is a plain fill.
float read_f32(size_t n, const float *RESTRICT x);
void write_f32(size_t n, float v, float *RESTRICT y);

// Strided SAXPY with compile-time strides: touches x[i*S], y[i*S] for i < n.
void saxpy_s1_f32(size_t n, float a, const float *RESTRICT x, float *RESTRICT y);
void saxpy_s2_f32(size_t n, float a, const float *RESTRICT x, float *RESTRICT y);
void saxpy_s4_f32(size_t n, float a, const float *RESTRICT x, float *RESTRICT y);
void saxpy_s8_f32(size_t n, float a, const float *RESTRICT x, float *RESTRICT y);
void saxpy_s16_f32(size_t n, float a, const float *RESTRICT x, float *RESTRICT y);

// Gather SAXPY: y[i] = a * x[idx[i]] + y[i]
void saxpy_gather_f32(size_t n, float a, const uint32_t *RESTRICT idx, const float *RESTRICT x,
                      float *RESTRICT y);

// manual.cpp: hand-written intrinsics, same in every binary, runtime-dispatched.
int has_avx2_fma(void);
int has_avx512f(void);
void saxpy_mask_avx2_f32(size_t n, float a, const float *RESTRICT x, float *RESTRICT y);
void saxpy_mask_avx512_f32(size_t n, float a, const float *RESTRICT x, float *RESTRICT y);
void run_peak(void);        // prints CSV of measured peak FLOP/s per ISA
void run_license(void);     // prints CSV: core clock right after sustained scalar / AVX2 / AVX-512 work
double measure_ghz(void);   // effective core clock from a dependent integer-add chain
}
