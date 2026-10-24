# Results summary — my-pc

CPU: **AMD Ryzen 5 3600 6-Core Processor** · Microsoft Windows 11 Pro (build 26200) · windows (MSYS2 UCRT64) · hypervisor: n/a (native Windows)  
Caches (from sysfs): L1d 32 KiB · L2 512 KiB · LLC 16 MiB  
**Measured LLC knee: ~13 MiB.** The read stream falls to DRAM speed far below the 16 MiB that sysfs reports (shared / partitioned L3). Regimes below use the measured size.  
Measured clock (dependent-add chain): [3.9834, 3.9839, 3.9868] GHz · frequency policy: Windows power plan: Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)  
Cores: 6 physical / 12 logical · SMT active: True · hybrid (P/E cores): False · pinned CPU: 10 · timer: QueryPerformanceCounter, resolution 100.0 ns  
Compiler: g++.exe (Rev4, Built by MSYS2 project) 16.2.0

Windows details (CIM / powercfg):
```
{
 "cpu": "AMD Ryzen 5 3600 6-Core Processor              ",
 "cores": 6,
 "logical": 12,
 "max_mhz": 3593,
 "current_mhz": 3593,
 "l2_kb": 3072,
 "l3_kb": 32768,
 "os": "Microsoft Windows 11 Pro",
 "build": "26200",
 "ram_gb": 31.9,
 "battery": false,
 "on_ac": true,
 "power_plan": "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)"
}
```

All numbers are medians over samples; speedup = scalar median / variant median. Brackets are the conservative IQR-based interval.

## 1. Speedup vs scalar build, by regime (float32)

| kernel | regime (WS) | scalar GFLOP/s | avx2 | sse2 | scalar_native | native |
|---|---|---|---|---|---|---|
| saxpy | L1 (16 KiB) | 6.26 | 6.84× [6.60–6.92] | 3.02× [2.83–3.05] | 1.18× [1.15–1.19] | 6.89× [6.87–6.95] |
| saxpy | L2 (256 KiB) | 6.45 | 4.76× [4.67–4.81] | 3.06× [3.04–3.07] | 1.10× [1.04–1.11] | 4.79× [4.77–4.82] |
| saxpy | LLC (4096 KiB) | 6.50 | 3.75× [3.73–3.90] | 2.90× [2.88–2.92] | 1.03× [0.93–1.06] | 3.94× [3.93–4.01] |
| saxpy | DRAM (1048576 KiB) | 3.64 | 1.13× [0.95–1.19] | 0.88× [0.78–0.99] | 0.90× [0.73–0.94] | 1.11× [1.02–1.18] |
| dot | L1 (16 KiB) | 2.67 | 1.02× [1.01–1.02] | 1.01× [1.01–1.02] | 1.00× [1.00–1.00] | 1.02× [1.02–1.02] |
| dot | L2 (256 KiB) | 2.66 | 1.01× [1.00–1.01] | 1.01× [1.00–1.01] | 1.00× [1.00–1.00] | 1.01× [1.00–1.01] |
| dot | LLC (4096 KiB) | 2.67 | 1.00× [1.00–1.01] | 1.00× [1.00–1.00] | 0.99× [0.99–1.00] | 1.00× [1.00–1.01] |
| dot | DRAM (1048576 KiB) | 2.51 | 1.00× [0.99–1.03] | 1.02× [1.00–1.04] | 0.97× [0.93–1.00] | 0.98× [0.96–1.02] |
| dotsimd | L1 (16 KiB) | 2.69 | 8.03× [8.01–8.08] | 3.99× [3.98–4.02] | 1.00× [1.00–1.01] | 7.99× [7.93–8.06] |
| dotsimd | L2 (256 KiB) | 2.67 | 7.88× [7.87–7.92] | 3.96× [3.95–3.98] | 1.00× [1.00–1.01] | 7.92× [7.85–7.95] |
| dotsimd | LLC (4096 KiB) | 2.67 | 7.82× [7.80–7.85] | 3.96× [3.95–3.97] | 1.00× [0.99–1.00] | 7.84× [7.83–7.88] |
| dotsimd | DRAM (1048576 KiB) | 2.56 | 2.47× [2.41–2.54] | 1.92× [1.89–2.16] | 1.00× [0.96–1.01] | 2.32× [2.17–2.45] |
| mul | L1 (15 KiB) | 3.66 | 5.13× [5.13–5.16] | 2.88× [2.84–2.88] | 0.99× [0.99–1.00] | 5.15× [5.05–5.18] |
| mul | L2 (255 KiB) | 3.48 | 3.00× [2.98–3.02] | 2.95× [2.94–2.96] | 1.01× [1.00–1.01] | 3.02× [3.01–3.03] |
| mul | LLC (4095 KiB) | 3.48 | 2.34× [2.25–2.39] | 2.33× [2.32–2.48] | 1.00× [0.99–1.02] | 2.27× [2.26–2.33] |
| mul | DRAM (1048575 KiB) | 1.46 | 1.09× [1.00–1.16] | 1.09× [1.03–1.17] | 1.03× [0.98–1.10] | 1.06× [0.97–1.13] |
| stencil | L1 (16 KiB) | 8.64 | 7.42× [7.41–7.47] | 3.35× [3.32–3.38] | 1.15× [1.15–1.16] | 7.44× [7.42–7.47] |
| stencil | L2 (256 KiB) | 8.66 | 5.68× [5.60–5.69] | 3.25× [3.23–3.26] | 1.14× [1.13–1.15] | 5.68× [5.57–5.70] |
| stencil | LLC (4096 KiB) | 8.69 | 5.46× [5.44–5.50] | 3.15× [3.13–3.18] | 1.14× [1.14–1.15] | 5.42× [5.33–5.46] |
| stencil | DRAM (1048576 KiB) | 6.38 | 1.33× [1.19–1.48] | 1.31× [1.18–1.36] | 1.19× [1.05–1.22] | 1.52× [1.42–1.61] |

## 2. Measured single-core bandwidth plateaus (GiB/s, `native` build)

| stream | L1 | L2 | LLC | DRAM |
|---|---|---|---|---|
| read | 40.5 | 39.7 | 39.7 | 20.2 |
| write | 113.2 | 117.0 | 81.9 | 10.1 |
| **roof used in roofline** (best of read/write/saxpy/dotsimd/mul, any vector build) | 253.0 | 172.6 | 141.5 | 24.0 |
| (kernel that set the roof) | saxpy/native | saxpy/native | saxpy/native | saxpy/native |

## 3. Measured peak FLOP/s (independent FMA / mul+add chains)

| ISA | dtype | lanes | GFLOP/s | flop/cycle |
|---|---|---|---|---|
| scalar_sse | f32 | 1 | 6.8 | 1.7 |
| sse2 | f32 | 4 | 63.6 | 16.0 |
| sse2 | f64 | 2 | 27.3 | 6.9 |
| scalar_fma | f32 | 1 | 16.1 | 4.1 |
| avx2_fma | f32 | 8 | 128.5 | 32.3 |
| avx2_fma | f64 | 4 | 64.3 | 16.2 |

## 3b. Frequency licence: core clock right after ~30 ms of each kind of work

| preceding work | clock (GHz, median of trials) | relative to scalar |
|---|---|---|
| idle_spin | 4.07 | 1.01 |
| scalar_mul_add | 4.03 | 1.00 |
| sse2_mul_add | 4.02 | 1.00 |
| avx2_fma | 4.02 | 1.00 |
| idle_spin_again | 4.07 | 1.01 |

## 4. Alignment: slowdown vs offset 0 (time ratio, >1 = slower)

Ratios use the **minimum** time over all samples and rounds: alignment costs are deterministic, and the minimum filters interference bursts that can hit every round of one configuration. Median-based ratios are kept in `processed/align_ratios.csv` (`ratio_median`).

|                               |    0 |    4 |      8 |     16 |   32 |     48 |     64 |
|:------------------------------|-----:|-----:|-------:|-------:|-----:|-------:|-------:|
| ('dotsimd', 'DRAM', 'native') | 1.00 | 0.98 | nan    | nan    | 1.00 | nan    | nan    |
| ('dotsimd', 'DRAM', 'scalar') | 1.00 | 1.00 | nan    | nan    | 1.00 | nan    | nan    |
| ('dotsimd', 'L1', 'avx2')     | 1.00 | 1.01 |   1.01 |   1.02 | 1.00 |   1.02 |   1.00 |
| ('dotsimd', 'L1', 'native')   | 1.00 | 1.02 |   1.02 |   1.00 | 1.00 |   1.02 |   1.00 |
| ('dotsimd', 'L1', 'scalar')   | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L1', 'sse2')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'avx2')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'native')   | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'scalar')   | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'sse2')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('saxpy', 'DRAM', 'native')   | 1.00 | 1.01 | nan    | nan    | 1.01 | nan    | nan    |
| ('saxpy', 'DRAM', 'scalar')   | 1.00 | 1.00 | nan    | nan    | 1.00 | nan    | nan    |
| ('saxpy', 'L1', 'avx2')       | 1.00 | 1.59 |   1.58 |   1.58 | 1.07 |   1.58 |   1.07 |
| ('saxpy', 'L1', 'native')     | 1.00 | 1.49 |   1.49 |   1.49 | 1.00 |   1.48 |   1.00 |
| ('saxpy', 'L1', 'scalar')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('saxpy', 'L1', 'sse2')       | 1.00 | 1.00 |   1.00 |   0.99 | 1.00 |   0.99 |   0.99 |
| ('saxpy', 'L2', 'avx2')       | 1.00 | 1.31 |   1.31 |   1.30 | 1.00 |   1.31 |   1.00 |
| ('saxpy', 'L2', 'native')     | 1.00 | 1.31 |   1.31 |   1.30 | 1.00 |   1.31 |   1.00 |
| ('saxpy', 'L2', 'scalar')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('saxpy', 'L2', 'sse2')       | 1.00 | 1.17 |   1.18 |   1.00 | 1.00 |   1.00 |   1.00 |

## 5. Tail handling (n = 1024…1152, L1-resident): ns per call (minimum over samples)

| variant/kernel | n=1024 | max over 1025–1087 | n=1088 | worst extra ns vs n=1024 |
|---|---|---|---|---|
| avx2/saxpy | 60.4 | 64.2 | 62.3 | 3.7 |
| native/mask_avx2 | 35.1 | 42.1 | 37.1 | 7.0 |
| native/saxpy | 60.4 | 64.4 | 62.5 | 3.9 |
| scalar/saxpy | 333.3 | 351.8 | 352.7 | 18.5 |
| sse2/saxpy | 113.0 | 119.7 | 119.3 | 6.6 |

## 6. Stride / gather: useful GiB/s (speedup vs scalar)

**L1**

| pattern | native | avx2 | sse2 | scalar |
|---|---|---|---|---|
| s1 | 237.4 (6.76×) | 240.8 (6.86×) | 107.5 (3.06×) | 35.1 (1.00×) |
| s2 | 21.8 (0.65×) | 20.0 (0.59×) | 35.7 (1.06×) | 33.8 (1.00×) |
| s4 | 12.0 (0.41×) | 12.0 (0.41×) | 23.6 (0.80×) | 29.4 (1.00×) |
| s8 | 5.9 (0.21×) | 30.3 (1.10×) | 27.5 (1.00×) | 27.5 (1.00×) |
| s16 | 25.8 (1.05×) | 25.5 (1.04×) | 24.5 (1.00×) | 24.6 (1.00×) |
| gather-seq | 45.8 (1.43×) | 45.9 (1.43×) | 45.7 (1.42×) | 32.1 (1.00×) |
| gather-random | 45.5 (1.41×) | 45.9 (1.42×) | 45.7 (1.42×) | 32.2 (1.00×) |

**L2**

| pattern | native | avx2 | sse2 | scalar |
|---|---|---|---|---|
| s1 | 174.5 (4.80×) | 173.5 (4.78×) | 111.5 (3.07×) | 36.3 (1.00×) |
| s2 | 21.5 (0.61×) | 20.8 (0.59×) | 36.5 (1.04×) | 35.1 (1.00×) |
| s4 | 12.0 (0.41×) | 11.9 (0.41×) | 24.5 (0.84×) | 29.1 (1.00×) |
| s8 | 5.9 (0.27×) | 21.9 (1.01×) | 21.8 (1.00×) | 21.8 (1.00×) |
| s16 | 11.0 (0.99×) | 11.1 (1.00×) | 11.1 (1.00×) | 11.1 (1.00×) |
| gather-seq | 45.9 (1.42×) | 46.0 (1.42×) | 45.7 (1.41×) | 32.4 (1.00×) |
| gather-random | 28.4 (1.16×) | 28.5 (1.16×) | 28.3 (1.16×) | 24.5 (1.00×) |

**LLC**

| pattern | native | avx2 | sse2 | scalar |
|---|---|---|---|---|
| s1 | 139.2 (3.86×) | 138.7 (3.85×) | 107.4 (2.98×) | 36.0 (1.00×) |
| s2 | 22.3 (0.64×) | 20.6 (0.59×) | 36.1 (1.04×) | 34.8 (1.00×) |
| s4 | 11.8 (0.41×) | 11.9 (0.42×) | 23.7 (0.83×) | 28.6 (1.00×) |
| s8 | 5.8 (0.33×) | 17.6 (0.99×) | 18.1 (1.02×) | 17.7 (1.00×) |
| s16 | 8.2 (1.00×) | 8.2 (1.00×) | 8.3 (1.01×) | 8.2 (1.00×) |
| gather-seq | 45.6 (1.41×) | 45.6 (1.41×) | 45.4 (1.41×) | 32.3 (1.00×) |
| gather-random | 22.1 (1.09×) | 21.9 (1.08×) | 21.8 (1.08×) | 20.3 (1.00×) |

**DRAM**

| pattern | native | avx2 | sse2 | scalar |
|---|---|---|---|---|
| s1 | 23.9 (1.15×) | 23.6 (1.13×) | 23.6 (1.13×) | 20.9 (1.00×) |
| s2 | 10.6 (1.01×) | 10.4 (0.99×) | 11.3 (1.08×) | 10.5 (1.00×) |
| s4 | 5.2 (0.92×) | 5.1 (0.90×) | 5.7 (1.01×) | 5.7 (1.00×) |
| s8 | 2.6 (0.90×) | 3.0 (1.02×) | 3.1 (1.06×) | 2.9 (1.00×) |
| s16 | 1.4 (1.01×) | 1.5 (1.03×) | 1.4 (0.99×) | 1.4 (1.00×) |
| gather-seq | 21.8 (0.96×) | 22.8 (1.01×) | 20.8 (0.92×) | 22.7 (1.00×) |
| gather-random | 3.5 (1.12×) | 3.5 (1.12×) | 3.4 (1.10×) | 3.1 (1.00×) |

## 7. Data type: speedup vs scalar and element throughput (Gelem/s)

Best-vector build = `native`.

| kernel | type | regime | scalar Gelem/s | native Gelem/s | speedup |
|---|---|---|---|---|---|
| dotsimd | f64 | L1 | 1.35 | 5.43 | 4.03× |
| dotsimd | f64 | L2 | 1.34 | 5.30 | 3.96× |
| dotsimd | f64 | DRAM | 1.15 | 1.61 | 1.40× |
| mul | f64 | L1 | 3.41 | 9.49 | 2.78× |
| mul | f64 | L2 | 3.10 | 5.25 | 1.69× |
| mul | f64 | DRAM | 0.82 | 0.83 | 1.01× |
| dot | f64 | L1 | 1.35 | 1.38 | 1.02× |
| dot | f64 | L2 | 1.34 | 1.34 | 1.00× |
| dot | f64 | DRAM | 1.16 | 1.20 | 1.03× |
| saxpy | f32 | L1 | 3.15 | 21.78 | 6.92× |
| saxpy | f32 | L2 | 3.26 | 15.61 | 4.79× |
| saxpy | f32 | DRAM | 1.80 | 2.17 | 1.21× |
| stencil | f32 | L1 | 1.74 | 12.94 | 7.43× |
| stencil | f32 | L2 | 1.75 | 9.89 | 5.65× |
| stencil | f32 | DRAM | 1.43 | 2.21 | 1.54× |
| dotsimd | i32 | L1 | 2.72 | 15.70 | 5.77× |
| dotsimd | i32 | L2 | 2.75 | 15.65 | 5.69× |
| dotsimd | i32 | DRAM | 2.11 | 3.20 | 1.52× |
| stencil | i32 | L1 | 1.32 | 5.28 | 3.99× |
| stencil | i32 | L2 | 1.32 | 5.28 | 3.99× |
| stencil | i32 | DRAM | 1.21 | 2.12 | 1.75× |
| dot | f32 | L1 | 1.35 | 1.36 | 1.01× |
| dot | f32 | L2 | 1.34 | 1.35 | 1.01× |
| dot | f32 | DRAM | 1.28 | 1.30 | 1.01× |
| mul | f32 | L1 | 3.65 | 19.01 | 5.21× |
| mul | f32 | L2 | 3.49 | 10.53 | 3.01× |
| mul | f32 | DRAM | 1.55 | 1.63 | 1.05× |
| dot | i32 | L1 | 2.72 | 15.69 | 5.77× |
| dot | i32 | L2 | 2.75 | 15.66 | 5.70× |
| dot | i32 | DRAM | 2.12 | 3.04 | 1.43× |
| saxpy | f64 | L1 | 3.03 | 10.86 | 3.58× |
| saxpy | f64 | L2 | 3.14 | 7.80 | 2.48× |
| saxpy | f64 | DRAM | 0.94 | 1.09 | 1.16× |
| saxpy | i32 | L1 | 2.41 | 15.70 | 6.52× |
| saxpy | i32 | L2 | 2.40 | 15.55 | 6.47× |
| saxpy | i32 | DRAM | 1.71 | 2.14 | 1.25× |
| dotsimd | f32 | L1 | 1.35 | 10.76 | 8.00× |
| dotsimd | f32 | L2 | 1.34 | 10.58 | 7.92× |
| dotsimd | f32 | DRAM | 1.29 | 3.13 | 2.43× |
| mul | i32 | L1 | 2.32 | 15.82 | 6.81× |
| mul | i32 | L2 | 2.43 | 10.55 | 4.35× |
| mul | i32 | DRAM | 1.49 | 1.60 | 1.08× |
| stencil | f64 | L1 | 1.73 | 6.58 | 3.81× |
| stencil | f64 | L2 | 1.75 | 4.94 | 2.82× |
| stencil | f64 | DRAM | 0.91 | 1.11 | 1.22× |

## 8. Measurement variability

Each configuration was measured in 3 independent rounds. 0.5% of configurations had one round >1.5× slower than another (interference bursts on the host); with >= 3 rounds the median of round medians discards such a single bad round.  
Median coefficient of variation across all 2134 configurations: 4.52% (90th percentile 16.20%, worst 69.3%).  
Measured clock across all runs: median 4.006 GHz, range 3.965–4.045 GHz.

