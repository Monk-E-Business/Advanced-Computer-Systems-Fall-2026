# Methodology

The exact values for a given run (CPU, caches, OS, compiler, clock, power plan/governor, SMT, hybrid cores,
pinning) are recorded
automatically in `results/<run>/sysinfo.json` and summarised at the top of `results/<run>/summary.md`.
This document describes *how* things are measured, which is the same for every run.

## 1. What is compared

The project is C++17 compiled with **g++** (GCC). On Windows that is MSYS2's UCRT64 g++ (MinGW-w64); on
Linux, the distribution's g++. `src/kernels.cpp` contains the code under test. It is compiled once per
**build variant**, and each build is linked into its own `build/<variant>/bench[.exe]` binary:

| variant | g++ kernel flags | purpose |
|---|---|---|
| `scalar` | `-O3 -fno-tree-vectorize -fno-tree-slp-vectorize` | baseline: x86-64 (SSE2 scalar), both vectorizers off |
| `scalar_native` | `-O3 -march=native -fno-tree-vectorize -fno-tree-slp-vectorize` | same ISA as `native` (FMA, AVX encodings) but no SIMD: separates the effect of "new ISA" from "vector width" |
| `sse2` | `-O3 -fopenmp-simd` | compiler default target: 128-bit SSE2 auto-vectorization |
| `avx2` | `-O3 -march=x86-64-v3 -fopenmp-simd` | 256-bit AVX2 + FMA, generic tuning (built only if the CPU has AVX2) |
| `native` | `-O3 -march=native -fopenmp-simd` | whatever g++ chooses for this CPU. On AVX-512 Intel server parts its tuning prefers 256-bit vectors |
| `avx512` | `-O3 -march=native -mprefer-vector-width=512 -fopenmp-simd` | widest vectors actually used (built only if the CPU has AVX-512F) |

CPU features are detected from the compiler itself (`g++ -march=native -dM -E`), so the build works the
same on Windows, which has no `/proc/cpuinfo`. Common flags: `-std=c++17 -Wall -Wextra -g`. Kernels are also
compiled with **`-falign-functions=64 -falign-loops=64`**, which pins their code placement. Without it, the
address where the linker happened to put a kernel (which shifts whenever the harness changes size) changed
scalar SAXPY speed by 1.6× on the reference machine (REPORT §11). On Windows every
compile also gets `-Wa,-muse-unaligned-vector-move` and binaries are linked `-static` (§10).

`-fopenmp-simd` only enables `#pragma omp simd` (used by `dotsimd` and `read`). It does not link an
OpenMP runtime and does not start threads. Every experiment is **single-threaded**.

The harness (`src/main.cpp`) and the hand-written intrinsics (`src/manual.cpp`) are compiled with **the same
fixed flags in every binary**: `-O2 -fno-tree-vectorize -fno-tree-slp-vectorize -ffp-contract=off`. Timing loop,
data initialisation and reference checks are therefore identical across variants. Kernels are
`noinline`, live in a separate translation unit, and there is no LTO, so the compiler cannot hoist
work out of the timing loop or fold repeated calls.

Kernels are declared `extern "C"`, so compiler reports and disassembly show plain names (no C++ mangling).
An earlier pilot of this project used Clang on a different machine; it is preserved in git history only.

## 2. Kernels

| kernel | operation | flops/elem | compulsory bytes/elem (f32) | AI (flop/B) |
|---|---|---|---|---|
| `saxpy` | `y[i] = a*x[i] + y[i]` | 2 | 12 (read x, read y, write y) | 0.167 |
| `dot` | `s += x[i]*y[i]` (plain loop) | 2 | 8 | 0.25 |
| `dotsimd` | same, with `#pragma omp simd reduction(+:s)` | 2 | 8 | 0.25 |
| `mul` | `z[i] = x[i]*y[i]` | 1 | 12 (+4 write-allocate) | 0.083 |
| `stencil` | `y[i] = a*x[i-1] + b*x[i] + c*x[i+1]` | 5 | 8 (+4 write-allocate) | 0.625 |
| `read` / `write` | `s += x[i]` / `y[i] = v` | 1 / 0 | 4 / 4 | bandwidth probes |
| `saxpy_sS` | `y[i*S] = a*x[i*S] + y[i*S]`, S ∈ {1,2,4,8,16} (compile-time) | 2 | 12 useful | — |
| `gather` | `y[i] = a*x[idx[i]] + y[i]`, idx = identity or random permutation | 2 | 16 useful | — |
| `mask_avx2/512` | hand-written SAXPY with a single masked vector for the tail | 2 | 12 | — |

All kernels exist for float32, float64 and int32 where meaningful. "int32" is stored as `uint32_t`, which
gives 32-bit integer lanes with defined wrap-around. It produces the same `vpaddd`/`vpmulld` code as
signed int but avoids signed-overflow UB in the repeated loops. Bytes are *compulsory* traffic:
write-allocate (RFO) and hardware-prefetcher overfetch are not counted. That is why `mul` and `stencil`
look slightly worse in GiB/s than the bus actually delivers.

Working-set size (WS) is the total bytes of all arrays the kernel touches. Strided kernels count the
whole span (`2·n·S·4` bytes).

## 3. Timing

* Clock: `QueryPerformanceCounter` on Windows (100 ns resolution), `clock_gettime(CLOCK_MONOTONIC)` on
  Linux, around a batch of calls. Both are wall-clock monotonic timers; the resolution is recorded in
  `sysinfo.json`.
* **Warm-up**: at least 2 calls and ≥ 20 ms before measuring. This brings data into the target cache
  level, faults in pages and lets clocks settle.
* **Calibration**: the number of calls per sample (`reps`) is increased until one sample lasts ≥ 10 ms
  (2 ms in the tail study). Timer overhead is therefore < 0.01%. Very large working sets use reps = 1.
* **Rounds and samples**: every experiment is repeated in **3 independent rounds**, each with its own
  shuffled job order and minutes apart. Each round takes 7 samples per configuration (3 for DRAM-sized
  ones, 5 in the tail study). The raw CSV stores every sample with its `round`. This design was adopted
  after the first full run showed interference bursts on the shared host that could contaminate *all*
  samples of a configuration taken in one go (found in the Clang pilot; see REPORT §11).
* **Statistics**: tables and plots show the **median of the per-round medians**. A single bad round is
  outvoted. Bands and error bars are the inter-quartile range of the round medians (between-round
  spread). Speedup uses the median ratio, with a conservative interval
  `[scalar_p25 / variant_p75, scalar_p75 / variant_p25]`. The tail and alignment studies use the
  **minimum** over all samples and rounds instead. They measure deterministic microarchitectural costs of a
  few ns per call, and the minimum is the standard estimator for "cost without interference". In the
  reference run an interference burst hit all three rounds of one alignment configuration, which the
  median could not reject (REPORT §11).
* **In-place kernels** (SAXPY) alternate the sign of `a` on every call, so `y` oscillates instead of
  growing. Values stay in normal range (no denormals, no overflow).
* **Clock / cycles**: each benchmark process measures the effective core clock with a chain of 16
  dependent register-register `add`s (1 cycle each). Register operands matter here: Golden Cove and later
  Intel cores fold `add reg, imm` chains at rename, which would overstate the clock. cycles/element =
  ns/element × measured GHz. Under heavy AVX-512 use the real clock can be lower than this estimate.
* **Order**: within each round, (variant, kernel) jobs run in a shuffled order (seeded), so slow drift
  does not consistently favour one variant.
* **Diagnostic**: `scripts/probe_interference.py` separates address-layout effects from temporal
  interference. It runs many interleaved processes over several layouts and prints each one's array addresses.
* **Pinning**: every benchmark process pins itself (`bench --cpu N`): `SetThreadAffinityMask` plus
  HIGH priority class on Windows, `sched_setaffinity` on Linux. The default CPU comes from `bench --sysinfo`.
  On Windows that is the highest-numbered logical CPU that is the *first thread* of a core in the
  highest-performance efficiency class. On hybrid Intel CPUs this means a P-core, never an E-core, and never CPU 0.

## 4. Data initialisation

Arrays are allocated 4 KiB-aligned (`_aligned_malloc` on Windows, `posix_memalign` on Linux) plus a
deliberate byte offset (alignment study). They
are filled by a deterministic xorshift64 generator, seeded per size: floats uniform in [−1, 1], ints in
[−8, 8]. Filling also performs the first touch, outside the timed region. 64 sentinel elements after each
array detect out-of-bounds writes.

## 5. Correctness validation (`scripts/test.sh`)

Every variant × kernel × type is run once at 26 sizes (0, 1, 2, 3, 5, 7, 8, 9, 15, 16, 17, 31, 32, 33,
63, 64, 65, 100, 127, 128, 129, 1000, 1023, 1024, 1025, 4099) and 3 base offsets (0, 4, 12 bytes). That
exercises vector bodies, remainders, vectorized epilogues and misaligned starts. Each result is compared
with a reference computed in the harness (vectorization off) in `long double`:

* element-wise FP kernels: |got − ref| ≤ 2u·(|a·x| + |y|) per element (4u·Σ|terms| for the stencil),
  with u = 2⁻²⁴ (f32) or 2⁻⁵³ (f64). This admits FMA contraction (≤ 0.5 ulp) and separate mul+add rounding.
* reductions: |got − ref| ≤ (n+2)·u·Σ|xᵢyᵢ|. This is the standard worst-case bound for *any* summation
  order, which a vectorized reduction needs.
* int32: exact equality (modular arithmetic).
* untouched memory: guard elements, the gaps in strided kernels and the stencil boundary must be
  bit-identical to their initial values.

A mutation test (an injected off-by-one write, a perturbed product) was run during development to
confirm the checker fails loudly. **Limitation**: the reduction bound is the rigorous worst case, so a
small perturbation of a single term in a long FP dot product can still pass. Integer and element-wise
checks have no such slack.

## 6. Vectorization verification (`scripts/verify_vectorization.py`)

There are two independent sources of evidence, per function and per variant:

1. **Compiler report**: g++ `-fopt-info-vec-optimized -fopt-info-vec-missed` text (`vec_report.txt`)
   plus the structured `-fsave-optimization-record` file (gzipped JSON). The JSON attributes each remark to
   a function even inside macro-generated code. It gives the vector size(s) used for the main loop and
   epilogue ("loop vectorized using 64 byte vectors") or the reason vectorization failed. A "vectorized"
   verdict is not the end of the story: g++ also reports in-order FP reductions as vectorized even
   though their add chain stays serial (REPORT §10).
2. **Disassembly**: `objdump` (binutils; MSYS2 ships it with g++) of each `kernels.o`, ELF or PE/COFF. The script finds the main vector loop (backward branch
   with the widest vector registers, innermost) and counts packed vs scalar FP ops, integer vector ops,
   gathers/scatters, masked ops and shuffles. This is the ground truth.
   `hot_loops.md` keeps short excerpts (≤ 24 lines) of key loops, not full dumps.

## 7. Bandwidth, peak FLOP/s and the roofline

* **Peak FLOP/s** (`bench --peak`): independent accumulator chains (12 for SSE/AVX2, 24 for AVX-512) of
  `acc = acc*m + c`. They are written with intrinsics and empty `asm` barriers so the compiler cannot
  simplify or spill them. Variants: scalar mul+add (what the scalar build can reach), SSE2 4-wide,
  scalar FMA, AVX2 FMA, AVX-512 FMA.
* **Frequency licence** (`bench --license`): runs ~30 ms of scalar, SSE2, AVX2-FMA or AVX-512-FMA work, then
  *immediately* measures the clock with a short (~0.5 ms) dependent-add chain, before the core can return to
  its normal frequency (Intel holds a licence for ~1-2 ms after the last heavy instruction). Median of 7 trials,
  3 repetitions. It shows how much clock wide vectors cost on this CPU, which the normal per-process clock
  estimate (taken before any vector work) cannot see.
* **Effective LLC size**: measured, not taken from sysfs. It is the first size beyond 4×L2 where the
  read stream drops below 75% of its early-LLC plateau. In VMs and on partitioned caches this can be far
  smaller than the reported L3 (in the Clang pilot: 54 MiB measured against 260 MiB reported). Regime
  labels, roofs and plot markers use the measured size.
* **Memory roofs**: the best sustained GiB/s demonstrated at each level by any streaming kernel
  (read-only, write-only, SAXPY, dotsimd, mul) in any vector build. Not just the widest: on the reference CPU
  the AVX-512 build runs at a 20% lower clock and underestimates the L2/LLC roofs. The plateau is the median over sizes
  that sit clearly inside the level: L1 ≤ 0.75·L1d, L2 between 2·L1d and 0.75·L2, LLC between 2·L2 and
  0.5·LLC, DRAM ≥ 2·LLC, using the measured LLC size. The pure read probe is reported too. In L1 it under-reports, because its
  4-accumulator reduction is add-latency-bound.
* Single-thread DRAM bandwidth is limited by how many outstanding misses one core can keep in flight. It
  is well below the socket's peak, and that is the bandwidth that matters for a single-threaded kernel.

## 8. Hardware counters

On Linux, `run_experiments.py --only perf` collects `perf stat` counters (cycles, instructions, L1/LLC
misses, and on Intel the `fp_arith_inst_retired.*` scalar/128/256/512 events that count vector instructions
directly) when the PMU is accessible. `perf` does not exist on Windows. There the step records `SKIPPED`
and suggests Intel VTune / AMD uProf for manual counter collection. The cloud VM used for the reference run
exposes no PMU either. Disassembly and the compiler report remain the vectorization evidence.

## 9. Known threats to validity

* **Virtualisation (reference run)**: the reference run is in a KVM guest with 2 vCPUs, no cpufreq control
  and a shared host (noisy neighbours). A native MSYS2 run on your own PC avoids this layer: pinning there
  binds to a real logical CPU.
* **Windows background activity**: Defender scans, indexing and updates can interrupt a run. The HIGH
  priority class and the 3-round median limit their effect. Close other apps and stay on AC power.
* **Turbo/thermal**: frequency is not fixed. It is measured and recorded per process instead.
* **AVX-512 frequency licence**: on some Intel parts heavy 512-bit use lowers the clock. The cycles
  estimate does not capture this, but wall-time speedups do.
* **Compulsory-byte model**: write-allocate and prefetch traffic are not modelled. Reported GiB/s is a
  lower bound on real bus traffic.

## 10. Windows / MSYS2 specifics

* **Toolchain**: MSYS2 **UCRT64** environment, `mingw-w64-ucrt-x86_64-gcc` (g++ plus binutils). The build
  refuses the plain `MSYS` shell, whose compiler targets the POSIX emulation layer, not native Windows.
  Whether the build is for Windows is decided by `g++ -dumpmachine` (`x86_64-w64-mingw32`).
* **AVX stack-alignment workaround**: GCC on 64-bit Windows may assume 32/64-byte stack alignment for
  spilled AVX/AVX-512 values, but the Windows ABI only guarantees 16 bytes (GCC bug 54412). Aligned moves
  (`vmovaps`) to such slots can then fault. Every Windows compile therefore passes
  `-Wa,-muse-unaligned-vector-move` (binutils ≥ 2.38), which encodes them as unaligned moves. That costs
  nothing on aligned data. A side effect for the reader of `hot_loops.md`: on Windows every vector move
  appears as `vmovups`/`vmovdqu`, even where g++ proved alignment.
* **Static linking**: `-static`, so `bench.exe` does not depend on MSYS2's DLLs being on `PATH`.
* **Line endings**: `bench.exe` puts stdout in binary mode, so CSV output uses `\n`. Python writes all files
  as UTF-8 (`PYTHONUTF8=1` plus explicit encodings), because the Windows default code page cannot encode
  `×`, `≈` or `→`.
* **System information**: CPU name, core/thread counts, clock, OS build and battery/AC state come from
  PowerShell CIM queries. The active power plan comes from `powercfg /getactivescheme`. Caches and the
  core-class topology come from `GetLogicalProcessorInformationEx` inside `bench.exe`.
* **Validation of the Windows build**: the Windows binaries were cross-compiled with MinGW-w64 g++ 13 and run
  under Wine on the reference machine. They pass all 12,168 correctness checks, report the right
  topology (QueryPerformanceCounter, 100 ns), and run the AVX-512 kernels without faults.
