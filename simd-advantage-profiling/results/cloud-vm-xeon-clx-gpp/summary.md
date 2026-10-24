# Results summary — cloud-vm-xeon-clx-gpp

CPU: **Intel(R) Xeon(R) Processor @ 2.80GHz** · Ubuntu 24.04.5 LTS · linux  · hypervisor: KVM  
Caches (from sysfs): L1d 32 KiB · L2 1024 KiB · LLC 33 MiB  
**Measured LLC knee: ~19 MiB.** The read stream falls to DRAM speed far below the 33 MiB that sysfs reports (shared / partitioned L3). Regimes below use the measured size.  
Measured clock (dependent-add chain): [3.2141, 3.2396, 3.264] GHz · frequency policy: governor: unavailable: /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor not readable; no_turbo: unavailab  
Cores: 2 physical / 2 logical · SMT active: False · hybrid (P/E cores): False · pinned CPU: 1 · timer: clock_gettime(CLOCK_MONOTONIC), resolution 1.0 ns  
Compiler: g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0

All numbers are medians over samples; speedup = scalar median / variant median. Brackets are the conservative IQR-based interval.

## 1. Speedup vs scalar build, by regime (float32)

| kernel | regime (WS) | scalar GFLOP/s | avx2 | sse2 | avx512 | native | scalar_native |
|---|---|---|---|---|---|---|---|
| saxpy | L1 (16 KiB) | 5.26 | 6.04× [5.42–6.56] | 3.03× [3.00–3.34] | 6.70× [6.24–7.34] | 5.91× [3.49–6.44] | 0.85× [0.84–0.92] |
| saxpy | L2 (512 KiB) | 5.10 | 3.83× [3.31–4.19] | 2.48× [2.36–2.59] | 3.37× [3.22–3.55] | 4.28× [4.16–4.41] | 0.79× [0.77–0.84] |
| saxpy | LLC (5792 KiB) | 4.87 | 1.44× [1.41–1.52] | 1.53× [1.51–1.57] | 1.38× [1.38–1.45] | 1.48× [1.46–1.54] | 0.89× [0.87–0.90] |
| saxpy | DRAM (1048576 KiB) | 2.20 | 1.21× [1.11–1.25] | 1.18× [1.12–1.21] | 1.16× [1.11–1.20] | 1.17× [1.11–1.18] | 1.00× [0.94–1.02] |
| dot | L1 (16 KiB) | 1.66 | 1.00× [0.98–1.01] | 1.00× [0.98–1.01] | 0.93× [0.93–0.95] | 1.01× [0.99–1.01] | 0.97× [0.97–0.99] |
| dot | L2 (512 KiB) | 1.61 | 1.02× [1.01–1.28] | 1.01× [0.99–1.28] | 0.91× [0.89–1.17] | 1.01× [0.99–1.28] | 1.02× [1.00–1.28] |
| dot | LLC (5792 KiB) | 1.57 | 1.02× [1.01–1.05] | 1.02× [1.00–1.05] | 0.95× [0.94–0.98] | 1.02× [1.01–1.05] | 1.00× [0.97–1.04] |
| dot | DRAM (1048576 KiB) | 1.39 | 1.04× [1.01–1.06] | 1.05× [0.99–1.05] | 0.97× [0.94–0.98] | 1.08× [1.01–1.08] | 1.06× [1.03–1.07] |
| dotsimd | L1 (16 KiB) | 1.67 | 7.36× [7.18–7.92] | 4.03× [4.02–4.16] | 18.04× [17.88–18.71] | 8.87× [8.83–9.13] | 0.99× [0.99–1.02] |
| dotsimd | L2 (512 KiB) | 1.64 | 7.98× [7.54–8.18] | 3.86× [3.83–4.02] | 15.02× [14.36–15.40] | 7.98× [7.95–8.17] | 1.00× [0.99–1.02] |
| dotsimd | LLC (5792 KiB) | 1.61 | 4.98× [4.87–5.05] | 3.90× [3.86–3.94] | 5.04× [4.91–5.10] | 4.86× [4.82–4.96] | 0.99× [0.99–1.00] |
| dotsimd | DRAM (1048576 KiB) | 1.39 | 1.93× [1.86–1.98] | 1.96× [1.91–2.04] | 1.96× [1.91–2.01] | 2.03× [1.97–2.06] | 1.06× [1.00–1.06] |
| mul | L1 (15 KiB) | 2.17 | 6.47× [6.29–6.82] | 4.03× [3.17–4.14] | 8.16× [7.04–8.37] | 6.43× [6.05–6.56] | 1.02× [0.93–1.03] |
| mul | L2 (512 KiB) | 2.15 | 3.77× [3.71–4.17] | 2.74× [2.64–2.92] | 3.18× [3.01–3.36] | 3.95× [3.84–4.24] | 0.95× [0.92–1.04] |
| mul | LLC (5792 KiB) | 1.34 | 1.87× [1.51–1.88] | 1.88× [1.51–1.92] | 1.69× [1.41–1.77] | 1.92× [1.59–1.96] | 1.33× [1.10–1.36] |
| mul | DRAM (1048575 KiB) | 0.92 | 1.03× [0.99–1.04] | 1.10× [1.04–1.12] | 1.03× [0.92–1.03] | 0.96× [0.90–0.99] | 1.04× [0.90–1.06] |
| stencil | L1 (16 KiB) | 6.48 | 6.07× [6.04–6.62] | 3.53× [3.49–3.95] | 4.32× [2.42–4.80] | 6.04× [4.81–6.61] | 1.63× [1.58–1.78] |
| stencil | L2 (512 KiB) | 6.47 | 5.01× [4.94–5.19] | 3.29× [3.24–3.35] | 3.31× [3.28–3.38] | 5.12× [4.70–5.18] | 1.59× [1.52–1.65] |
| stencil | LLC (5792 KiB) | 6.20 | 2.70× [2.58–2.76] | 2.46× [1.74–2.47] | 2.51× [2.45–2.58] | 2.83× [2.71–2.88] | 1.61× [1.47–1.66] |
| stencil | DRAM (1048576 KiB) | 4.65 | 1.48× [1.45–1.49] | 1.25× [1.17–1.33] | 1.33× [1.29–1.37] | 1.49× [1.40–1.52] | 1.23× [1.18–1.28] |

## 2. Measured single-core bandwidth plateaus (GiB/s, `avx512` build)

| stream | L1 | L2 | LLC | DRAM |
|---|---|---|---|---|
| read | 61.3 | 46.3 | 29.3 | 9.0 |
| write | 178.8 | 54.9 | 24.5 | 7.1 |
| **roof used in roofline** (best of read/write/saxpy/dotsimd/mul, any vector build) | 196.6 | 122.7 | 41.4 | 14.9 |
| (kernel that set the roof) | mul/avx512 | saxpy/native | saxpy/native | saxpy/avx2 |

## 3. Measured peak FLOP/s (independent FMA / mul+add chains)

| ISA | dtype | lanes | GFLOP/s | flop/cycle |
|---|---|---|---|---|
| scalar_sse | f32 | 1 | 5.5 | 1.7 |
| sse2 | f32 | 4 | 26.3 | 8.1 |
| sse2 | f64 | 2 | 13.1 | 4.1 |
| scalar_fma | f32 | 1 | 12.6 | 3.9 |
| avx2_fma | f32 | 8 | 98.9 | 30.5 |
| avx2_fma | f64 | 4 | 52.6 | 16.2 |
| avx512_fma | f32 | 16 | 165.8 | 51.1 |
| avx512_fma | f64 | 8 | 72.7 | 22.4 |

## 3b. Frequency licence: core clock right after ~30 ms of each kind of work

| preceding work | clock (GHz, median of trials) | relative to scalar |
|---|---|---|
| idle_spin | 3.26 | 1.00 |
| scalar_mul_add | 3.26 | 1.00 |
| sse2_mul_add | 3.25 | 1.00 |
| avx2_fma | 3.19 | 0.98 |
| avx512_fma | 2.60 | 0.80 |
| idle_spin_again | 3.28 | 1.01 |

## 4. Alignment: slowdown vs offset 0 (time ratio, >1 = slower)

Ratios use the **minimum** time over all samples and rounds: alignment costs are deterministic, and the minimum filters interference bursts that can hit every round of one configuration. Median-based ratios are kept in `processed/align_ratios.csv` (`ratio_median`).

|                               |    0 |    4 |      8 |     16 |   32 |     48 |     64 |
|:------------------------------|-----:|-----:|-------:|-------:|-----:|-------:|-------:|
| ('dotsimd', 'DRAM', 'avx512') | 1.00 | 0.95 | nan    | nan    | 0.92 | nan    | nan    |
| ('dotsimd', 'DRAM', 'scalar') | 1.00 | 1.01 | nan    | nan    | 1.00 | nan    | nan    |
| ('dotsimd', 'L1', 'avx2')     | 1.00 | 0.98 |   0.99 |   0.99 | 1.00 |   0.99 |   0.99 |
| ('dotsimd', 'L1', 'avx512')   | 1.00 | 1.22 |   1.19 |   1.19 | 1.19 |   1.19 |   1.00 |
| ('dotsimd', 'L1', 'native')   | 1.00 | 1.00 |   1.00 |   1.00 | 0.99 |   1.00 |   1.01 |
| ('dotsimd', 'L1', 'scalar')   | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L1', 'sse2')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'avx2')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'avx512')   | 1.00 | 2.20 |   2.20 |   2.20 | 2.21 |   2.20 |   1.00 |
| ('dotsimd', 'L2', 'native')   | 1.00 | 1.00 |   1.00 |   1.01 | 1.01 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'scalar')   | 1.00 | 0.99 |   1.00 |   1.00 | 0.99 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'sse2')     | 1.00 | 1.00 |   1.00 |   1.01 | 1.00 |   1.00 |   1.00 |
| ('saxpy', 'DRAM', 'avx512')   | 1.00 | 0.89 | nan    | nan    | 0.86 | nan    | nan    |
| ('saxpy', 'DRAM', 'scalar')   | 1.00 | 1.04 | nan    | nan    | 0.99 | nan    | nan    |
| ('saxpy', 'L1', 'avx2')       | 1.00 | 1.04 |   1.14 |   1.16 | 1.00 |   1.12 |   0.98 |
| ('saxpy', 'L1', 'avx512')     | 1.00 | 1.97 |   2.00 |   2.11 | 1.99 |   2.30 |   1.02 |
| ('saxpy', 'L1', 'native')     | 1.00 | 1.06 |   1.10 |   1.13 | 1.01 |   1.16 |   1.01 |
| ('saxpy', 'L1', 'scalar')     | 1.00 | 1.01 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('saxpy', 'L1', 'sse2')       | 1.00 | 1.00 |   1.00 |   0.99 | 1.00 |   1.00 |   1.00 |
| ('saxpy', 'L2', 'avx2')       | 1.00 | 1.65 |   1.64 |   1.64 | 1.00 |   1.66 |   1.00 |
| ('saxpy', 'L2', 'avx512')     | 1.00 | 2.09 |   2.07 |   2.13 | 2.01 |   2.10 |   0.99 |
| ('saxpy', 'L2', 'native')     | 1.00 | 1.66 |   1.66 |   1.65 | 1.00 |   1.65 |   1.00 |
| ('saxpy', 'L2', 'scalar')     | 1.00 | 0.99 |   0.99 |   0.99 | 0.99 |   0.99 |   0.99 |
| ('saxpy', 'L2', 'sse2')       | 1.00 | 1.20 |   1.19 |   0.99 | 1.00 |   1.00 |   1.00 |

## 5. Tail handling (n = 1024…1152, L1-resident): ns per call (minimum over samples)

| variant/kernel | n=1024 | max over 1025–1087 | n=1088 | worst extra ns vs n=1024 |
|---|---|---|---|---|
| avx2/saxpy | 56.2 | 62.4 | 60.6 | 6.2 |
| avx512/saxpy | 55.2 | 72.4 | 61.1 | 17.1 |
| native/mask_avx2 | 44.4 | 49.0 | 49.2 | 4.6 |
| native/mask_avx512 | 58.8 | 70.5 | 67.3 | 11.8 |
| native/saxpy | 56.4 | 63.0 | 60.3 | 6.6 |
| scalar/saxpy | 388.1 | 412.8 | 405.7 | 24.7 |
| sse2/saxpy | 128.8 | 137.3 | 136.5 | 8.5 |

## 6. Stride / gather: useful GiB/s (speedup vs scalar)

**L1**

| pattern | avx2 | native | scalar | sse2 | avx512 |
|---|---|---|---|---|---|
| s1 | 173.4 (6.20×) | 170.8 (6.11×) | 28.0 (1.00×) | 86.8 (3.10×) | 174.3 (6.23×) |
| s2 | 26.7 (0.93×) | 32.4 (1.13×) | 28.6 (1.00×) | 34.1 (1.19×) | 30.0 (1.05×) |
| s4 | 15.6 (0.57×) | 22.5 (0.82×) | 27.5 (1.00×) | 25.4 (0.92×) | 25.4 (0.92×) |
| s8 | 8.6 (0.34×) | 14.4 (0.57×) | 25.1 (1.00×) | 25.2 (1.01×) | 18.5 (0.74×) |
| s16 | 23.9 (0.84×) | 23.7 (0.83×) | 28.4 (1.00×) | 27.9 (0.98×) | 13.4 (0.47×) |
| gather-seq | 44.4 (1.41×) | 44.0 (1.39×) | 31.6 (1.00×) | 39.9 (1.26×) | 28.8 (0.91×) |
| gather-random | 43.7 (1.43×) | 43.0 (1.41×) | 30.5 (1.00×) | 40.4 (1.32×) | 29.5 (0.97×) |

**L2**

| pattern | avx2 | native | scalar | sse2 | avx512 |
|---|---|---|---|---|---|
| s1 | 122.9 (4.43×) | 125.0 (4.51×) | 27.7 (1.00×) | 70.3 (2.54×) | 108.9 (3.93×) |
| s2 | 26.2 (1.15×) | 29.1 (1.28×) | 22.8 (1.00×) | 33.2 (1.46×) | 28.1 (1.23×) |
| s4 | 15.3 (0.83×) | 21.8 (1.18×) | 18.4 (1.00×) | 16.0 (0.87×) | 23.1 (1.26×) |
| s8 | 8.1 (0.53×) | 13.7 (0.89×) | 15.3 (1.00×) | 15.6 (1.02×) | 15.1 (0.98×) |
| s16 | 8.0 (0.94×) | 8.5 (0.99×) | 8.5 (1.00×) | 8.5 (0.99×) | 6.8 (0.80×) |
| gather-seq | 40.6 (1.45×) | 41.0 (1.46×) | 28.1 (1.00×) | 39.0 (1.39×) | 27.4 (0.97×) |
| gather-random | 29.5 (1.32×) | 29.3 (1.31×) | 22.3 (1.00×) | 27.8 (1.25×) | 23.1 (1.04×) |

**LLC**

| pattern | avx2 | native | scalar | sse2 | avx512 |
|---|---|---|---|---|---|
| s1 | 36.3 (2.61×) | 39.2 (2.82×) | 13.9 (1.00×) | 32.7 (2.35×) | 35.1 (2.53×) |
| s2 | 15.1 (1.37×) | 11.1 (1.00×) | 11.0 (1.00×) | 14.7 (1.34×) | 15.9 (1.44×) |
| s4 | 6.6 (0.88×) | 9.1 (1.20×) | 7.6 (1.00×) | 7.6 (1.01×) | 8.6 (1.14×) |
| s8 | 4.5 (0.93×) | 4.2 (0.86×) | 4.9 (1.00×) | 4.7 (0.96×) | 4.3 (0.89×) |
| s16 | 2.4 (0.93×) | 2.4 (0.92×) | 2.6 (1.00×) | 2.5 (0.98×) | 2.6 (1.01×) |
| gather-seq | 22.1 (1.11×) | 22.5 (1.13×) | 20.0 (1.00×) | 22.8 (1.14×) | 19.4 (0.97×) |
| gather-random | 4.3 (1.09×) | 4.5 (1.14×) | 4.0 (1.00×) | 3.9 (1.00×) | 3.3 (0.84×) |

**DRAM**

| pattern | avx2 | native | scalar | sse2 | avx512 |
|---|---|---|---|---|---|
| s1 | 15.4 (1.26×) | 14.8 (1.21×) | 12.2 (1.00×) | 15.1 (1.23×) | 14.3 (1.16×) |
| s2 | 7.2 (0.98×) | 6.9 (0.94×) | 7.3 (1.00×) | 7.6 (1.03×) | 7.3 (1.00×) |
| s4 | 3.8 (1.02×) | 3.9 (1.04×) | 3.7 (1.00×) | 3.5 (0.93×) | 3.9 (1.04×) |
| s8 | 1.8 (1.00×) | 1.9 (1.01×) | 1.8 (1.00×) | 1.9 (1.04×) | 1.9 (1.03×) |
| s16 | 0.9 (0.95×) | 0.9 (0.95×) | 0.9 (1.00×) | 0.9 (0.96×) | 0.9 (0.97×) |
| gather-seq | 12.9 (1.01×) | 13.8 (1.08×) | 12.8 (1.00×) | 13.7 (1.07×) | 13.2 (1.03×) |
| gather-random | 1.4 (1.16×) | 1.4 (1.12×) | 1.2 (1.00×) | 1.3 (1.11×) | 1.4 (1.11×) |

## 7. Data type: speedup vs scalar and element throughput (Gelem/s)

Best-vector build = `avx512`.

| kernel | type | regime | scalar Gelem/s | avx512 Gelem/s | speedup |
|---|---|---|---|---|---|
| stencil | i32 | L1 | 1.08 | 5.48 | 5.06× |
| stencil | i32 | L2 | 1.08 | 3.72 | 3.44× |
| stencil | i32 | DRAM | 0.89 | 1.32 | 1.48× |
| mul | f64 | L1 | 2.25 | 9.04 | 4.03× |
| mul | f64 | L2 | 2.00 | 3.44 | 1.72× |
| mul | f64 | DRAM | 0.51 | 0.46 | 0.90× |
| dot | i32 | L1 | 1.94 | 15.65 | 8.05× |
| dot | i32 | L2 | 1.88 | 17.64 | 9.39× |
| dot | i32 | DRAM | 1.13 | 1.29 | 1.15× |
| stencil | f64 | L1 | 1.27 | 2.94 | 2.31× |
| stencil | f64 | L2 | 1.25 | 2.14 | 1.71× |
| stencil | f64 | DRAM | 0.63 | 0.64 | 1.02× |
| dot | f32 | L1 | 0.83 | 0.78 | 0.94× |
| dot | f32 | L2 | 0.82 | 0.77 | 0.94× |
| dot | f32 | DRAM | 0.73 | 0.69 | 0.95× |
| dotsimd | f64 | L1 | 0.85 | 7.63 | 9.02× |
| dotsimd | f64 | L2 | 0.81 | 6.06 | 7.44× |
| dotsimd | f64 | DRAM | 0.56 | 0.66 | 1.17× |
| saxpy | f32 | L1 | 2.66 | 17.34 | 6.53× |
| saxpy | f32 | L2 | 2.40 | 8.91 | 3.71× |
| saxpy | f32 | DRAM | 1.18 | 1.29 | 1.09× |
| stencil | f32 | L1 | 1.12 | 5.86 | 5.21× |
| stencil | f32 | L2 | 1.20 | 4.28 | 3.56× |
| stencil | f32 | DRAM | 0.99 | 1.32 | 1.33× |
| saxpy | i32 | L1 | 1.76 | 15.29 | 8.70× |
| saxpy | i32 | L2 | 1.76 | 10.46 | 5.93× |
| saxpy | i32 | DRAM | 1.06 | 1.33 | 1.25× |
| mul | i32 | L1 | 2.43 | 14.93 | 6.13× |
| mul | i32 | L2 | 2.09 | 7.04 | 3.36× |
| mul | i32 | DRAM | 0.94 | 0.95 | 1.02× |
| saxpy | f64 | L1 | 2.60 | 8.89 | 3.42× |
| saxpy | f64 | L2 | 2.02 | 4.54 | 2.24× |
| saxpy | f64 | DRAM | 0.65 | 0.65 | 0.99× |
| dot | f64 | L1 | 0.84 | 0.81 | 0.96× |
| dot | f64 | L2 | 0.82 | 0.77 | 0.94× |
| dot | f64 | DRAM | 0.59 | 0.57 | 0.96× |
| mul | f32 | L1 | 2.21 | 15.27 | 6.91× |
| mul | f32 | L2 | 2.21 | 6.86 | 3.11× |
| mul | f32 | DRAM | 0.91 | 0.92 | 1.00× |
| dotsimd | i32 | L1 | 1.95 | 15.52 | 7.95× |
| dotsimd | i32 | L2 | 1.96 | 17.15 | 8.74× |
| dotsimd | i32 | DRAM | 1.14 | 1.34 | 1.17× |
| dotsimd | f32 | L1 | 0.79 | 15.02 | 18.99× |
| dotsimd | f32 | L2 | 0.82 | 12.29 | 14.97× |
| dotsimd | f32 | DRAM | 0.74 | 1.25 | 1.70× |

## 8. Measurement variability

Each configuration was measured in 3 independent rounds. 7.5% of configurations had one round >1.5× slower than another (interference bursts on the host); with >= 3 rounds the median of round medians discards such a single bad round.  
Median coefficient of variation across all 2678 configurations: 6.21% (90th percentile 24.42%, worst 76.9%).  
Measured clock across all runs: median 3.271 GHz, range 3.125–3.301 GHz.

