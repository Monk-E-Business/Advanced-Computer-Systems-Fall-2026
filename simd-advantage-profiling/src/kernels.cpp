// kernels.cpp - the code under test. Compiled once per variant with different g++ flags.
// Keep these loops plain: the point is to see what the compiler does with them.
// noinline + separate translation unit (no LTO) means the harness cannot fold
// repeated calls or hoist work out of the timing loop.
#include "kernels.hpp"

#define K __attribute__((noinline))

#define DEF_KERNELS(T, S)                                                                  \
    K void saxpy_##S(size_t n, T a, const T *RESTRICT x, T *RESTRICT y) {                  \
        for (size_t i = 0; i < n; i++) y[i] = a * x[i] + y[i];                             \
    }                                                                                      \
    /* Plain reduction: strict FP semantics forbid reassociation. */                       \
    K T dot_##S(size_t n, const T *RESTRICT x, const T *RESTRICT y) {                      \
        T s = 0;                                                                           \
        for (size_t i = 0; i < n; i++) s += x[i] * y[i];                                   \
        return s;                                                                          \
    }                                                                                      \
    /* Same loop, reassociation explicitly allowed by the programmer. */                   \
    K T dotsimd_##S(size_t n, const T *RESTRICT x, const T *RESTRICT y) {                  \
        T s = 0;                                                                           \
        _Pragma("omp simd reduction(+:s)")                                                 \
        for (size_t i = 0; i < n; i++) s += x[i] * y[i];                                   \
        return s;                                                                          \
    }                                                                                      \
    K void mul_##S(size_t n, const T *RESTRICT x, const T *RESTRICT y, T *RESTRICT z) {    \
        for (size_t i = 0; i < n; i++) z[i] = x[i] * y[i];                                 \
    }                                                                                      \
    K void stencil_##S(size_t n, T a, T b, T c, const T *RESTRICT x, T *RESTRICT y) {      \
        for (size_t i = 1; i + 1 < n; i++)                                                 \
            y[i] = a * x[i - 1] + b * x[i] + c * x[i + 1];                                 \
    }

extern "C" {

DEF_KERNELS(float, f32)
DEF_KERNELS(double, f64)
DEF_KERNELS(uint32_t, i32)

K float read_f32(size_t n, const float *RESTRICT x) {
    float s = 0;
    _Pragma("omp simd reduction(+:s)")
    for (size_t i = 0; i < n; i++) s += x[i];
    return s;
}

K void write_f32(size_t n, float v, float *RESTRICT y) {
    for (size_t i = 0; i < n; i++) y[i] = v;
}

#define DEF_STRIDE(SS)                                                                     \
    K void saxpy_s##SS##_f32(size_t n, float a, const float *RESTRICT x, float *RESTRICT y) { \
        for (size_t i = 0; i < n; i++) y[i * SS] = a * x[i * SS] + y[i * SS];              \
    }
DEF_STRIDE(1)
DEF_STRIDE(2)
DEF_STRIDE(4)
DEF_STRIDE(8)
DEF_STRIDE(16)

K void saxpy_gather_f32(size_t n, float a, const uint32_t *RESTRICT idx, const float *RESTRICT x,
                        float *RESTRICT y) {
    for (size_t i = 0; i < n; i++) y[i] = a * x[idx[i]] + y[i];
}

} // extern "C"
