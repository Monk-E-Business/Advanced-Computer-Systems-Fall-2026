# Results summary — smoke

CPU: **AMD Ryzen 5 3600 6-Core Processor** · Microsoft Windows 11 Pro (build 26200) · windows (MSYS2 UCRT64) · hypervisor: n/a (native Windows)  
Caches (from sysfs): L1d 32 KiB · L2 512 KiB · LLC 16 MiB  
**Measured LLC knee: ~11 MiB.** The read stream falls to DRAM speed far below the 16 MiB that sysfs reports (shared / partitioned L3). Regimes below use the measured size.  
Measured clock (dependent-add chain): [3.9862, 3.9883, 3.986] GHz · frequency policy: Windows power plan: Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)  
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
| saxpy | L1 (16 KiB) | 6.34 | 6.74× [6.46–6.94] | 3.02× [2.99–3.04] | 1.17× [1.15–1.20] | 6.85× [6.80–6.90] |
| saxpy | L2 (256 KiB) | 6.49 | 4.80× [4.78–4.86] | 3.07× [3.05–3.11] | 1.09× [1.02–1.12] | 4.80× [4.65–4.86] |
| saxpy | LLC (4096 KiB) | 6.52 | 3.86× [3.74–4.02] | 2.98× [2.95–3.00] | 1.10× [1.09–1.12] | 4.06× [4.02–4.11] |
| saxpy | DRAM (1048576 KiB) | 3.73 | 1.16× [1.09–1.32] | 1.12× [1.06–1.26] | 1.00× [0.94–1.12] | 1.19× [1.12–1.33] |
| dot | L1 (16 KiB) | 2.68 | 1.02× [1.00–1.02] | 1.02× [1.01–1.02] | 1.00× [0.98–1.01] | 1.01× [1.00–1.02] |
| dot | L2 (256 KiB) | 2.67 | 1.01× [0.99–1.01] | 1.00× [0.99–1.01] | 1.00× [0.99–1.01] | 1.01× [1.00–1.01] |
| dot | LLC (4096 KiB) | 2.67 | 1.01× [0.99–1.02] | 1.01× [1.00–1.01] | 1.00× [0.99–1.01] | 1.00× [1.00–1.01] |
| dot | DRAM (1048576 KiB) | 2.58 | 1.00× [0.98–1.03] | 1.01× [0.99–1.03] | 0.96× [0.88–1.03] | 1.01× [0.99–1.04] |
| dotsimd | L1 (16 KiB) | 2.69 | 8.04× [7.98–8.10] | 4.01× [3.97–4.04] | 1.00× [0.99–1.01] | 7.99× [7.91–8.09] |
| dotsimd | L2 (256 KiB) | 2.68 | 7.92× [7.83–8.04] | 3.99× [3.94–4.02] | 1.00× [0.99–1.01] | 7.94× [7.86–8.03] |
| dotsimd | LLC (4096 KiB) | 2.68 | 7.83× [7.75–7.92] | 3.96× [3.92–4.00] | 1.00× [0.99–1.00] | 7.83× [7.79–7.94] |
| dotsimd | DRAM (1048576 KiB) | 2.58 | 2.43× [2.17–2.67] | 2.01× [1.50–2.57] | 1.00× [0.98–1.01] | 2.56× [2.51–2.66] |
| mul | L1 (15 KiB) | 3.65 | 5.15× [5.06–5.42] | 2.90× [2.85–3.06] | 1.00× [0.98–1.05] | 5.19× [5.12–5.44] |
| mul | L2 (255 KiB) | 3.48 | 3.01× [2.97–3.06] | 2.98× [2.96–3.00] | 1.01× [1.00–1.01] | 3.03× [3.01–3.05] |
| mul | LLC (4095 KiB) | 3.48 | 2.27× [2.16–2.38] | 2.58× [2.55–2.63] | 1.00× [0.99–1.01] | 2.27× [2.25–2.28] |
| mul | DRAM (1048575 KiB) | 1.52 | 1.05× [0.93–1.12] | 1.13× [1.07–1.18] | 0.98× [0.89–1.02] | 1.03× [0.93–1.13] |
| stencil | L1 (16 KiB) | 8.73 | 7.23× [6.95–7.47] | 3.34× [3.14–3.42] | 1.12× [1.07–1.16] | 7.41× [7.37–7.50] |
| stencil | L2 (256 KiB) | 8.78 | 5.64× [5.58–5.67] | 3.23× [3.16–3.28] | 1.05× [1.01–1.10] | 5.61× [5.55–5.66] |
| stencil | LLC (4096 KiB) | 8.78 | 5.45× [5.40–5.50] | 3.17× [3.13–3.22] | 1.12× [1.04–1.15] | 5.42× [5.38–5.46] |
| stencil | DRAM (1048576 KiB) | 7.36 | 1.40× [1.28–1.52] | 1.25× [1.15–1.34] | 1.00× [0.87–1.10] | 1.37× [1.25–1.53] |

## 2. Measured single-core bandwidth plateaus (GiB/s, `native` build)

| stream | L1 | L2 | LLC | DRAM |
|---|---|---|---|---|
| read | 40.7 | 39.6 | 39.8 | 21.7 |
| write | 113.8 | 117.5 | 82.4 | 10.8 |
| **roof used in roofline** (best of read/write/saxpy/dotsimd/mul, any vector build) | 242.5 | 173.7 | 144.9 | 24.6 |
| (kernel that set the roof) | saxpy/native | saxpy/avx2 | saxpy/native | dotsimd/avx2 |

## 3. Measured peak FLOP/s (independent FMA / mul+add chains)

| ISA | dtype | lanes | GFLOP/s | flop/cycle |
|---|---|---|---|---|
| scalar_sse | f32 | 1 | 6.8 | 1.7 |
| sse2 | f32 | 4 | 63.7 | 16.0 |
| sse2 | f64 | 2 | 27.4 | 6.9 |
| scalar_fma | f32 | 1 | 16.1 | 4.0 |
| avx2_fma | f32 | 8 | 128.5 | 32.2 |
| avx2_fma | f64 | 4 | 64.3 | 16.1 |

## 3b. Frequency licence: core clock right after ~30 ms of each kind of work

| preceding work | clock (GHz, median of trials) | relative to scalar |
|---|---|---|
| idle_spin | 4.07 | 1.02 |
| scalar_mul_add | 4.00 | 1.00 |
| sse2_mul_add | 4.03 | 1.01 |
| avx2_fma | 4.02 | 1.01 |
| idle_spin_again | 4.07 | 1.02 |

## 4. Alignment: slowdown vs offset 0 (time ratio, >1 = slower)

Ratios use the **minimum** time over all samples and rounds: alignment costs are deterministic, and the minimum filters interference bursts that can hit every round of one configuration. Median-based ratios are kept in `processed/align_ratios.csv` (`ratio_median`).

|                               |    0 |    4 |      8 |     16 |   32 |     48 |     64 |
|:------------------------------|-----:|-----:|-------:|-------:|-----:|-------:|-------:|
| ('dotsimd', 'DRAM', 'native') | 1.00 | 0.96 | nan    | nan    | 0.97 | nan    | nan    |
| ('dotsimd', 'DRAM', 'scalar') | 1.00 | 0.99 | nan    | nan    | 1.00 | nan    | nan    |
| ('dotsimd', 'L1', 'avx2')     | 1.00 | 1.01 |   1.01 |   1.01 | 0.99 |   1.02 |   1.00 |
| ('dotsimd', 'L1', 'native')   | 1.00 | 1.03 |   1.02 |   1.01 | 1.00 |   1.02 |   1.00 |
| ('dotsimd', 'L1', 'scalar')   | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L1', 'sse2')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'avx2')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'native')   | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('dotsimd', 'L2', 'scalar')   | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.01 |
| ('dotsimd', 'L2', 'sse2')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('saxpy', 'DRAM', 'native')   | 1.00 | 1.00 | nan    | nan    | 1.00 | nan    | nan    |
| ('saxpy', 'DRAM', 'scalar')   | 1.00 | 0.97 | nan    | nan    | 1.01 | nan    | nan    |
| ('saxpy', 'L1', 'avx2')       | 1.00 | 1.49 |   1.49 |   1.49 | 1.00 |   1.49 |   1.00 |
| ('saxpy', 'L1', 'native')     | 1.00 | 1.49 |   1.49 |   1.49 | 1.00 |   1.48 |   1.00 |
| ('saxpy', 'L1', 'scalar')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('saxpy', 'L1', 'sse2')       | 1.00 | 1.01 |   1.00 |   1.00 | 1.00 |   1.01 |   1.00 |
| ('saxpy', 'L2', 'avx2')       | 1.00 | 1.30 |   1.30 |   1.30 | 1.00 |   1.30 |   1.00 |
| ('saxpy', 'L2', 'native')     | 1.00 | 1.31 |   1.31 |   1.30 | 1.00 |   1.30 |   1.00 |
| ('saxpy', 'L2', 'scalar')     | 1.00 | 1.00 |   1.00 |   1.00 | 1.00 |   1.00 |   1.00 |
| ('saxpy', 'L2', 'sse2')       | 1.00 | 1.17 |   1.17 |   1.00 | 1.00 |   1.00 |   1.00 |

## 5. Tail handling (n = 1024…1152, L1-resident): ns per call (minimum over samples)

| variant/kernel | n=1024 | max over 1025–1087 | n=1088 | worst extra ns vs n=1024 |
|---|---|---|---|---|
| avx2/saxpy | 61.2 | 63.8 | nan | 2.6 |
| native/mask_avx2 | 35.3 | 42.0 | nan | 6.7 |
| native/saxpy | 60.9 | 64.8 | nan | 3.8 |
| scalar/saxpy | 334.6 | 351.7 | nan | 17.0 |
| sse2/saxpy | 113.0 | 120.0 | nan | 7.0 |

## 6. Stride / gather: useful GiB/s (speedup vs scalar)

**L1**

| pattern | native | avx2 | scalar | sse2 |
|---|---|---|---|---|
| s1 | 241.4 (6.84×) | 241.9 (6.85×) | 35.3 (1.00×) | 108.4 (3.07×) |
| s2 | 22.0 (0.65×) | 20.1 (0.59×) | 33.9 (1.00×) | 35.9 (1.06×) |
| s4 | 12.1 (0.39×) | 12.0 (0.38×) | 31.5 (1.00×) | 24.0 (0.76×) |
| s8 | 5.9 (0.21×) | 30.6 (1.10×) | 27.8 (1.00×) | 27.8 (1.00×) |
| s16 | 25.8 (1.06×) | 25.7 (1.05×) | 24.4 (1.00×) | 24.5 (1.01×) |
| gather-seq | 46.1 (1.43×) | 46.0 (1.42×) | 32.3 (1.00×) | 46.0 (1.42×) |
| gather-random | 46.1 (1.44×) | 45.9 (1.43×) | 32.0 (1.00×) | 45.9 (1.43×) |

**L2**

| pattern | native | avx2 | scalar | sse2 |
|---|---|---|---|---|
| s1 | 174.6 (4.78×) | 174.2 (4.77×) | 36.5 (1.00×) | 112.4 (3.08×) |
| s2 | 21.2 (0.60×) | 20.5 (0.58×) | 35.3 (1.00×) | 36.5 (1.03×) |
| s4 | 12.0 (0.41×) | 12.0 (0.41×) | 29.1 (1.00×) | 24.5 (0.84×) |
| s8 | 5.9 (0.27×) | 22.0 (1.00×) | 21.9 (1.00×) | 21.9 (1.00×) |
| s16 | 11.1 (1.01×) | 11.2 (1.01×) | 11.0 (1.00×) | 11.1 (1.01×) |
| gather-seq | 45.9 (1.41×) | 46.1 (1.42×) | 32.5 (1.00×) | 46.0 (1.41×) |
| gather-random | 28.7 (1.16×) | 28.5 (1.15×) | 24.7 (1.00×) | 28.4 (1.15×) |

**LLC**

| pattern | native | avx2 | scalar | sse2 |
|---|---|---|---|---|
| s1 | 139.5 (3.90×) | 143.3 (4.00×) | 35.8 (1.00×) | 108.0 (3.02×) |
| s2 | 22.4 (0.64×) | 20.8 (0.59×) | 35.1 (1.00×) | 36.0 (1.03×) |
| s4 | 11.9 (0.41×) | 11.9 (0.41×) | 28.9 (1.00×) | 24.0 (0.83×) |
| s8 | 5.8 (0.32×) | 17.0 (0.94×) | 18.1 (1.00×) | 17.5 (0.97×) |
| s16 | 8.4 (1.03×) | 8.3 (1.02×) | 8.2 (1.00×) | 8.5 (1.04×) |
| gather-seq | 43.3 (1.34×) | 45.7 (1.41×) | 32.4 (1.00×) | 45.7 (1.41×) |
| gather-random | 22.1 (1.09×) | 22.1 (1.09×) | 20.2 (1.00×) | 21.8 (1.08×) |

**DRAM**

| pattern | native | avx2 | scalar | sse2 |
|---|---|---|---|---|
| s1 | 24.4 (1.19×) | 23.9 (1.16×) | 20.6 (1.00×) | 23.6 (1.15×) |
| s2 | 10.0 (0.95×) | 10.6 (1.01×) | 10.5 (1.00×) | 10.3 (0.99×) |
| s4 | 5.2 (0.84×) | 5.0 (0.81×) | 6.2 (1.00×) | 5.9 (0.95×) |
| s8 | 2.7 (0.86×) | 3.1 (0.99×) | 3.1 (1.00×) | 3.1 (0.98×) |
| s16 | 1.4 (0.99×) | 1.4 (0.99×) | 1.4 (1.00×) | 1.5 (1.04×) |
| gather-seq | 23.0 (1.01×) | 23.6 (1.03×) | 22.9 (1.00×) | 22.7 (0.99×) |
| gather-random | 3.6 (1.14×) | 3.6 (1.16×) | 3.1 (1.00×) | 3.6 (1.15×) |

## 7. Data type: speedup vs scalar and element throughput (Gelem/s)

Best-vector build = `native`.

| kernel | type | regime | scalar Gelem/s | native Gelem/s | speedup |
|---|---|---|---|---|---|
| stencil | i32 | L1 | 1.32 | 5.31 | 4.02× |
| stencil | i32 | L2 | 1.32 | 5.29 | 4.00× |
| stencil | i32 | DRAM | 1.20 | 2.21 | 1.84× |
| saxpy | f64 | L1 | 3.03 | 10.88 | 3.59× |
| saxpy | f64 | L2 | 3.14 | 7.80 | 2.49× |
| saxpy | f64 | DRAM | 0.98 | 1.06 | 1.09× |
| saxpy | f32 | L1 | 3.16 | 21.78 | 6.89× |
| saxpy | f32 | L2 | 3.26 | 15.62 | 4.79× |
| saxpy | f32 | DRAM | 1.76 | 2.08 | 1.18× |
| dot | f64 | L1 | 1.35 | 1.37 | 1.01× |
| dot | f64 | L2 | 1.34 | 1.33 | 0.99× |
| dot | f64 | DRAM | 1.18 | 1.21 | 1.03× |
| stencil | f64 | L1 | 1.73 | 6.56 | 3.79× |
| stencil | f64 | L2 | 1.76 | 4.94 | 2.81× |
| stencil | f64 | DRAM | 0.90 | 1.08 | 1.20× |
| stencil | f32 | L1 | 1.74 | 13.04 | 7.48× |
| stencil | f32 | L2 | 1.76 | 9.89 | 5.62× |
| stencil | f32 | DRAM | 1.44 | 2.15 | 1.49× |
| dotsimd | i32 | L1 | 2.71 | 15.82 | 5.83× |
| dotsimd | i32 | L2 | 2.73 | 15.72 | 5.76× |
| dotsimd | i32 | DRAM | 2.03 | 3.33 | 1.64× |
| saxpy | i32 | L1 | 2.42 | 15.78 | 6.53× |
| saxpy | i32 | L2 | 2.40 | 15.54 | 6.49× |
| saxpy | i32 | DRAM | 1.73 | 2.17 | 1.25× |
| dot | i32 | L1 | 2.73 | 15.64 | 5.72× |
| dot | i32 | L2 | 2.76 | 15.69 | 5.68× |
| dot | i32 | DRAM | 2.16 | 3.31 | 1.53× |
| mul | i32 | L1 | 2.32 | 15.76 | 6.78× |
| mul | i32 | L2 | 2.43 | 10.57 | 4.35× |
| mul | i32 | DRAM | 1.48 | 1.62 | 1.10× |
| mul | f64 | L1 | 3.42 | 9.34 | 2.73× |
| mul | f64 | L2 | 3.11 | 5.29 | 1.70× |
| mul | f64 | DRAM | 0.83 | 0.78 | 0.94× |
| dotsimd | f64 | L1 | 1.35 | 5.48 | 4.05× |
| dotsimd | f64 | L2 | 1.34 | 5.32 | 3.97× |
| dotsimd | f64 | DRAM | 1.13 | 1.66 | 1.47× |
| mul | f32 | L1 | 3.67 | 18.98 | 5.18× |
| mul | f32 | L2 | 3.50 | 10.50 | 3.00× |
| mul | f32 | DRAM | 1.49 | 1.68 | 1.13× |
| dot | f32 | L1 | 1.35 | 1.36 | 1.01× |
| dot | f32 | L2 | 1.34 | 1.34 | 1.00× |
| dot | f32 | DRAM | 1.29 | 1.30 | 1.01× |
| dotsimd | f32 | L1 | 1.35 | 10.84 | 8.04× |
| dotsimd | f32 | L2 | 1.34 | 10.61 | 7.94× |
| dotsimd | f32 | DRAM | 1.28 | 3.24 | 2.54× |

## 8. Measurement variability

Median coefficient of variation across all 1182 configurations: 1.12% (90th percentile 7.44%, worst 53.4%).  
Measured clock across all runs: median 4.025 GHz, range 3.963–4.054 GHz.

