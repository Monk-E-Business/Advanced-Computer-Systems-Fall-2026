# Results summary — cloud-vm-xeon-clx-gpp-run1-code-placement

CPU: **Intel(R) Xeon(R) Processor @ 2.80GHz** · Ubuntu 24.04.5 LTS · linux  · hypervisor: KVM  
Caches (from sysfs): L1d 32 KiB · L2 1024 KiB · LLC 33 MiB  
**Measured LLC knee: ~19 MiB.** The read stream falls to DRAM speed far below the 33 MiB that sysfs reports (shared / partitioned L3). Regimes below use the measured size.  
Measured clock (dependent-add chain): [3.2879, 3.2965, 3.277] GHz · frequency policy: governor: unavailable: /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor not readable; no_turbo: unavailab  
Cores: 2 physical / 2 logical · SMT active: False · hybrid (P/E cores): False · pinned CPU: 1 · timer: clock_gettime(CLOCK_MONOTONIC), resolution 1.0 ns  
Compiler: g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0

All numbers are medians over samples; speedup = scalar median / variant median. Brackets are the conservative IQR-based interval.

## 1. Speedup vs scalar build, by regime (float32)

| kernel | regime (WS) | scalar GFLOP/s | avx2 | sse2 | avx512 | native | scalar_native |
|---|---|---|---|---|---|---|---|
| saxpy | L1 (16 KiB) | 3.21 | 9.89× [9.79–10.13] | 5.10× [4.97–5.22] | 10.36× [9.99–10.91] | 9.57× [9.34–9.99] | 1.00× [0.98–1.03] |
| saxpy | L2 (512 KiB) | 3.12 | 7.22× [7.11–7.29] | 4.13× [3.96–4.22] | 5.89× [5.82–5.97] | 6.87× [6.69–7.09] | 1.02× [0.81–1.03] |
| saxpy | LLC (5792 KiB) | 3.07 | 2.45× [2.35–2.51] | 2.27× [2.03–2.42] | 2.28× [2.20–2.35] | 2.28× [2.24–2.33] | 1.03× [1.01–1.06] |
| saxpy | DRAM (1048576 KiB) | 1.97 | 1.31× [1.25–1.35] | 1.28× [1.23–1.36] | 1.31× [1.26–1.35] | 1.47× [1.41–1.48] | 1.02× [0.99–1.06] |
| dot | L1 (16 KiB) | 1.64 | 1.03× [1.02–1.05] | 1.02× [1.01–1.05] | 0.97× [0.95–0.99] | 1.02× [1.01–1.05] | 1.02× [1.01–1.04] |
| dot | L2 (512 KiB) | 1.63 | 0.99× [0.98–1.00] | 0.99× [0.99–1.00] | 0.93× [0.92–0.94] | 1.00× [0.99–1.01] | 0.99× [0.99–1.01] |
| dot | LLC (5792 KiB) | 1.58 | 1.01× [1.00–1.04] | 1.01× [0.99–1.03] | 0.95× [0.90–0.97] | 1.02× [1.00–1.03] | 1.02× [1.00–1.03] |
| dot | DRAM (1048576 KiB) | 1.47 | 1.01× [1.00–1.03] | 1.00× [0.99–1.02] | 0.95× [0.92–0.97] | 1.02× [1.00–1.04] | 0.96× [0.95–1.00] |
| dotsimd | L1 (16 KiB) | 1.66 | 8.41× [8.16–8.44] | 4.09× [4.05–4.10] | 17.79× [15.67–17.92] | 8.78× [8.64–8.93] | 1.00× [1.00–1.01] |
| dotsimd | L2 (512 KiB) | 1.64 | 7.57× [7.37–7.81] | 3.93× [3.92–3.98] | 15.08× [15.05–15.19] | 7.95× [7.71–8.05] | 1.00× [1.00–1.01] |
| dotsimd | LLC (5792 KiB) | 1.60 | 5.14× [5.13–5.17] | 4.02× [3.89–4.04] | 4.83× [4.59–4.94] | 5.12× [4.93–5.17] | 1.01× [1.00–1.01] |
| dotsimd | DRAM (1048576 KiB) | 1.38 | 1.94× [1.86–2.07] | 2.11× [1.85–2.17] | 1.99× [1.93–2.06] | 1.95× [1.83–2.12] | 1.09× [1.05–1.11] |
| mul | L1 (15 KiB) | 2.18 | 5.44× [5.10–5.50] | 3.98× [3.96–4.07] | 7.92× [7.25–8.09] | 6.17× [6.00–6.40] | 1.02× [1.01–1.03] |
| mul | L2 (512 KiB) | 2.20 | 3.37× [3.18–3.71] | 2.59× [2.47–2.63] | 3.12× [3.02–3.17] | 3.65× [3.52–3.88] | 0.98× [0.97–1.02] |
| mul | LLC (5792 KiB) | 1.87 | 1.39× [1.35–1.77] | 1.40× [1.35–1.79] | 1.26× [1.20–1.62] | 1.37× [1.29–1.76] | 1.03× [1.02–1.31] |
| mul | DRAM (1048575 KiB) | 1.01 | 0.93× [0.88–0.95] | 0.98× [0.97–1.01] | 0.94× [0.87–0.96] | 0.92× [0.91–0.95] | 0.93× [0.91–0.99] |
| stencil | L1 (16 KiB) | 6.34 | 6.32× [6.19–6.44] | 3.57× [3.48–3.73] | 4.58× [4.19–4.68] | 6.27× [6.11–6.40] | 1.68× [1.59–1.72] |
| stencil | L2 (512 KiB) | 6.38 | 5.11× [4.92–5.23] | 3.32× [3.24–3.37] | 2.96× [2.95–3.20] | 5.26× [5.04–5.34] | 1.70× [1.69–1.71] |
| stencil | LLC (5792 KiB) | 6.21 | 2.78× [2.70–2.86] | 2.69× [2.64–2.74] | 2.61× [2.57–2.64] | 2.77× [2.56–2.88] | 1.69× [1.67–1.72] |
| stencil | DRAM (1048576 KiB) | 4.62 | 1.50× [1.41–1.59] | 1.39× [1.31–1.47] | 1.35× [1.26–1.47] | 1.48× [1.35–1.57] | 1.26× [1.12–1.29] |

## 2. Measured single-core bandwidth plateaus (GiB/s, `avx512` build)

| stream | L1 | L2 | LLC | DRAM |
|---|---|---|---|---|
| read | 60.7 | 45.1 | 29.8 | 9.2 |
| write | 175.0 | 53.0 | 23.1 | 6.9 |
| **roof used in roofline** (best of read/write/saxpy/dotsimd/mul, any vector build) | 191.2 | 124.4 | 43.8 | 15.1 |
| (kernel that set the roof) | mul/avx512 | saxpy/native | saxpy/avx2 | saxpy/avx2 |

## 3. Measured peak FLOP/s (independent FMA / mul+add chains)

| ISA | dtype | lanes | GFLOP/s | flop/cycle |
|---|---|---|---|---|
| scalar_sse | f32 | 1 | 5.5 | 1.7 |
| sse2 | f32 | 4 | 26.2 | 8.0 |
| sse2 | f64 | 2 | 13.2 | 4.0 |
| scalar_fma | f32 | 1 | 13.0 | 4.0 |
| avx2_fma | f32 | 8 | 100.6 | 30.8 |
| avx2_fma | f64 | 4 | 51.4 | 15.7 |
| avx512_fma | f32 | 16 | 165.1 | 50.5 |
| avx512_fma | f64 | 8 | 72.4 | 22.1 |

## 3b. Frequency licence: core clock right after ~30 ms of each kind of work

| preceding work | clock (GHz, median of trials) | relative to scalar |
|---|---|---|
| idle_spin | 3.25 | 0.99 |
| scalar_mul_add | 3.28 | 1.00 |
| sse2_mul_add | 3.24 | 0.99 |
| avx2_fma | 3.25 | 0.99 |
| avx512_fma | 2.58 | 0.79 |
| idle_spin_again | 3.27 | 1.00 |

## 4. Alignment: slowdown vs offset 0 (time ratio, >1 = slower)

Ratios use the **minimum** time over all samples and rounds: alignment costs are deterministic, and the minimum filters interference bursts that can hit every round of one configuration. Median-based ratios are kept in `processed/align_ratios.csv` (`ratio_median`).

|                               |    0 |    4 |      8 |     16 |   32 |     48 |     64 |
|:------------------------------|-----:|-----:|-------:|-------:|-----:|-------:|-------:|
| ('dotsimd', 'DRAM', 'avx512') | 1.00 | 0.92 | nan    | nan    | 0.88 | nan    | nan    |
| ('dotsimd', 'DRAM', 'scalar') | 1.00 | 1.00 | nan    | nan    | 1.01 | nan    | nan    |
| ('dotsimd', 'L1', 'avx2')     | 1.00 | 0.99 |   1.01 |   0.99 | 0.99 |   0.99 |   1.00 |
| ('dotsimd', 'L1', 'avx512')   | 1.00 | 1.20 |   1.20 |   1.21 | 1.22 |   1.21 |   1.01 |
| ('dotsimd', 'L1', 'native')   | 1.00 | 1.01 |   1.02 |   1.02 | 1.00 |   1.00 |   1.02 |
| ('dotsimd', 'L1', 'scalar')   | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L1', 'sse2')     | 1.00 | 0.99 |   0.99 |   1.00 | 1.00 |   0.99 |   1.01 |
| ('dotsimd', 'L2', 'avx2')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'avx512')   | 1.00 | 2.20 |   2.20 |   2.20 | 2.20 |   2.20 |   1.00 |
| ('dotsimd', 'L2', 'native')   | 1.00 | 1.01 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'scalar')   | 1.00 | 1.00 |   1.00 |   1.01 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'sse2')     | 1.00 | 1.00 |   1.01 |   1.01 | 1.00 |   1.00 |   1.01 |
| ('saxpy', 'DRAM', 'avx512')   | 1.00 | 0.84 | nan    | nan    | 0.88 | nan    | nan    |
| ('saxpy', 'DRAM', 'scalar')   | 1.00 | 1.00 | nan    | nan    | 1.00 | nan    | nan    |
| ('saxpy', 'L1', 'avx2')       | 1.00 | 1.06 |   1.12 |   1.17 | 1.01 |   1.16 |   1.01 |
| ('saxpy', 'L1', 'avx512')     | 1.00 | 2.01 |   2.42 |   2.22 | 2.35 |   2.04 |   1.17 |
| ('saxpy', 'L1', 'native')     | 1.00 | 1.04 |   1.12 |   1.16 | 0.99 |   1.09 |   1.00 |
| ('saxpy', 'L1', 'scalar')     | 1.00 | 0.99 |   1.00 |   0.99 | 0.99 |   0.99 |   1.00 |
| ('saxpy', 'L1', 'sse2')       | 1.00 | 1.00 |   0.99 |   0.99 | 1.00 |   0.99 |   1.00 |
| ('saxpy', 'L2', 'avx2')       | 1.00 | 1.66 |   1.65 |   1.65 | 1.00 |   1.65 |   1.00 |
| ('saxpy', 'L2', 'avx512')     | 1.00 | 1.96 |   1.93 |   1.99 | 1.94 |   1.95 |   0.94 |
| ('saxpy', 'L2', 'native')     | 1.00 | 1.65 |   1.65 |   1.66 | 1.00 |   1.65 |   1.01 |
| ('saxpy', 'L2', 'scalar')     | 1.00 | 1.00 |   1.02 |   1.00 | 1.00 |   1.01 |   1.00 |
| ('saxpy', 'L2', 'sse2')       | 1.00 | 1.18 |   1.18 |   0.99 | 0.99 |   0.99 |   0.99 |

## 5. Tail handling (n = 1024…1152, L1-resident): ns per call (minimum over samples)

| variant/kernel | n=1024 | max over 1025–1087 | n=1088 | worst extra ns vs n=1024 |
|---|---|---|---|---|
| avx2/saxpy | 56.1 | 65.5 | 60.1 | 9.3 |
| avx512/saxpy | 55.9 | 65.9 | 72.3 | 10.0 |
| native/mask_avx2 | 44.1 | 49.2 | 48.8 | 5.0 |
| native/mask_avx512 | 66.5 | 69.3 | 64.9 | 2.8 |
| native/saxpy | 56.1 | 61.6 | 59.7 | 5.4 |
| scalar/saxpy | 625.8 | 665.9 | 675.2 | 40.1 |
| sse2/saxpy | 130.9 | 139.3 | 139.1 | 8.3 |

## 6. Stride / gather: useful GiB/s (speedup vs scalar)

**L1**

| pattern | avx2 | native | scalar | sse2 | avx512 |
|---|---|---|---|---|---|
| s1 | 128.6 (4.33×) | 134.4 (4.53×) | 29.7 (1.00×) | 65.1 (2.19×) | 175.0 (5.90×) |
| s2 | 24.8 (1.70×) | 31.8 (2.18×) | 14.6 (1.00×) | 33.8 (2.32×) | 30.1 (2.07×) |
| s4 | 15.5 (0.89×) | 22.6 (1.30×) | 17.4 (1.00×) | 24.5 (1.41×) | 25.7 (1.48×) |
| s8 | 8.6 (0.34×) | 14.1 (0.56×) | 25.2 (1.00×) | 25.2 (1.00×) | 19.0 (0.76×) |
| s16 | 24.9 (0.88×) | 17.2 (0.61×) | 28.3 (1.00×) | 28.4 (1.01×) | 13.5 (0.48×) |
| gather-seq | 43.3 (1.36×) | 27.2 (0.85×) | 31.9 (1.00×) | 39.4 (1.24×) | 30.6 (0.96×) |
| gather-random | 43.8 (1.39×) | 43.3 (1.37×) | 31.6 (1.00×) | 39.6 (1.26×) | 30.2 (0.96×) |

**L2**

| pattern | avx2 | native | scalar | sse2 | avx512 |
|---|---|---|---|---|---|
| s1 | 124.5 (4.16×) | 123.6 (4.13×) | 29.9 (1.00×) | 71.6 (2.39×) | 99.9 (3.34×) |
| s2 | 26.2 (1.23×) | 28.8 (1.36×) | 21.2 (1.00×) | 33.1 (1.56×) | 28.8 (1.36×) |
| s4 | 15.3 (0.85×) | 21.8 (1.22×) | 18.0 (1.00×) | 16.3 (0.90×) | 23.5 (1.31×) |
| s8 | 8.3 (0.53×) | 13.8 (0.88×) | 15.7 (1.00×) | 15.7 (1.00×) | 15.4 (0.98×) |
| s16 | 8.5 (1.00×) | 8.4 (1.00×) | 8.5 (1.00×) | 8.6 (1.01×) | 7.8 (0.92×) |
| gather-seq | 41.5 (1.47×) | 41.3 (1.47×) | 28.2 (1.00×) | 36.0 (1.28×) | 27.3 (0.97×) |
| gather-random | 29.2 (1.27×) | 28.9 (1.26×) | 23.0 (1.00×) | 26.6 (1.16×) | 22.2 (0.96×) |

**LLC**

| pattern | avx2 | native | scalar | sse2 | avx512 |
|---|---|---|---|---|---|
| s1 | 32.9 (2.06×) | 39.9 (2.49×) | 16.0 (1.00×) | 26.4 (1.65×) | 34.6 (2.16×) |
| s2 | 14.6 (0.98×) | 14.1 (0.94×) | 14.9 (1.00×) | 10.8 (0.72×) | 11.0 (0.73×) |
| s4 | 8.6 (1.56×) | 8.7 (1.57×) | 5.5 (1.00×) | 6.3 (1.14×) | 9.0 (1.63×) |
| s8 | 4.5 (0.94×) | 5.0 (1.04×) | 4.8 (1.00×) | 4.9 (1.01×) | 4.9 (1.02×) |
| s16 | 2.5 (0.98×) | 2.2 (0.87×) | 2.5 (1.00×) | 2.6 (1.03×) | 2.3 (0.89×) |
| gather-seq | 21.0 (1.03×) | 29.5 (1.45×) | 20.3 (1.00×) | 24.3 (1.19×) | 20.4 (1.00×) |
| gather-random | 3.8 (1.00×) | 4.1 (1.08×) | 3.8 (1.00×) | 3.9 (1.01×) | 3.2 (0.84×) |

**DRAM**

| pattern | avx2 | native | scalar | sse2 | avx512 |
|---|---|---|---|---|---|
| s1 | 15.2 (1.29×) | 14.5 (1.23×) | 11.8 (1.00×) | 14.7 (1.24×) | 14.0 (1.19×) |
| s2 | 7.4 (1.10×) | 7.4 (1.10×) | 6.7 (1.00×) | 6.9 (1.03×) | 6.7 (1.00×) |
| s4 | 3.6 (1.00×) | 4.1 (1.15×) | 3.5 (1.00×) | 3.6 (1.03×) | 3.9 (1.11×) |
| s8 | 1.9 (1.05×) | 1.8 (1.01×) | 1.8 (1.00×) | 1.9 (1.04×) | 1.9 (1.05×) |
| s16 | 0.9 (0.94×) | 0.9 (0.95×) | 0.9 (1.00×) | 0.9 (1.00×) | 0.9 (0.97×) |
| gather-seq | 10.8 (0.81×) | 13.8 (1.03×) | 13.4 (1.00×) | 13.2 (0.99×) | 13.0 (0.97×) |
| gather-random | 1.4 (1.10×) | 1.4 (1.10×) | 1.3 (1.00×) | 1.4 (1.06×) | 1.3 (1.04×) |

## 7. Data type: speedup vs scalar and element throughput (Gelem/s)

Best-vector build = `avx512`.

| kernel | type | regime | scalar Gelem/s | avx512 Gelem/s | speedup |
|---|---|---|---|---|---|
| stencil | i32 | L1 | 1.08 | 5.41 | 4.99× |
| stencil | i32 | L2 | 1.08 | 3.63 | 3.37× |
| stencil | i32 | DRAM | 0.85 | 1.26 | 1.49× |
| mul | f64 | L1 | 2.16 | 7.72 | 3.57× |
| mul | f64 | L2 | 1.98 | 3.44 | 1.74× |
| mul | f64 | DRAM | 0.50 | 0.44 | 0.89× |
| dot | i32 | L1 | 1.59 | 15.34 | 9.64× |
| dot | i32 | L2 | 1.56 | 17.74 | 11.39× |
| dot | i32 | DRAM | 1.11 | 1.29 | 1.16× |
| stencil | f64 | L1 | 1.29 | 3.07 | 2.38× |
| stencil | f64 | L2 | 1.29 | 2.03 | 1.57× |
| stencil | f64 | DRAM | 0.61 | 0.61 | 1.01× |
| dot | f32 | L1 | 0.83 | 0.79 | 0.95× |
| dot | f32 | L2 | 0.82 | 0.77 | 0.94× |
| dot | f32 | DRAM | 0.74 | 0.68 | 0.92× |
| dotsimd | f64 | L1 | 0.84 | 8.22 | 9.73× |
| dotsimd | f64 | L2 | 0.81 | 6.12 | 7.55× |
| dotsimd | f64 | DRAM | 0.56 | 0.68 | 1.20× |
| saxpy | f32 | L1 | 1.60 | 17.87 | 11.15× |
| saxpy | f32 | L2 | 1.61 | 9.07 | 5.63× |
| saxpy | f32 | DRAM | 1.03 | 1.26 | 1.23× |
| stencil | f32 | L1 | 1.27 | 5.95 | 4.70× |
| stencil | f32 | L2 | 1.24 | 4.30 | 3.48× |
| stencil | f32 | DRAM | 0.95 | 1.32 | 1.39× |
| saxpy | i32 | L1 | 1.74 | 15.00 | 8.60× |
| saxpy | i32 | L2 | 1.76 | 10.34 | 5.87× |
| saxpy | i32 | DRAM | 1.06 | 1.27 | 1.20× |
| mul | i32 | L1 | 1.60 | 14.66 | 9.14× |
| mul | i32 | L2 | 1.60 | 7.01 | 4.39× |
| mul | i32 | DRAM | 0.91 | 0.89 | 0.97× |
| saxpy | f64 | L1 | 1.58 | 8.95 | 5.67× |
| saxpy | f64 | L2 | 1.57 | 4.78 | 3.05× |
| saxpy | f64 | DRAM | 0.63 | 0.62 | 0.97× |
| dot | f64 | L1 | 0.83 | 0.77 | 0.93× |
| dot | f64 | L2 | 0.80 | 0.76 | 0.95× |
| dot | f64 | DRAM | 0.56 | 0.57 | 1.01× |
| mul | f32 | L1 | 2.15 | 14.92 | 6.92× |
| mul | f32 | L2 | 2.21 | 6.88 | 3.11× |
| mul | f32 | DRAM | 0.93 | 0.87 | 0.93× |
| dotsimd | i32 | L1 | 1.56 | 15.13 | 9.71× |
| dotsimd | i32 | L2 | 1.58 | 17.79 | 11.27× |
| dotsimd | i32 | DRAM | 1.09 | 1.33 | 1.22× |
| dotsimd | f32 | L1 | 0.83 | 14.51 | 17.41× |
| dotsimd | f32 | L2 | 0.81 | 12.06 | 14.80× |
| dotsimd | f32 | DRAM | 0.70 | 1.36 | 1.93× |

## 8. Measurement variability

Each configuration was measured in 3 independent rounds. 8.0% of configurations had one round >1.5× slower than another (interference bursts on the host); with >= 3 rounds the median of round medians discards such a single bad round.  
Median coefficient of variation across all 2678 configurations: 6.46% (90th percentile 24.09%, worst 82.2%).  
Measured clock across all runs: median 3.271 GHz, range 3.120–3.304 GHz.

