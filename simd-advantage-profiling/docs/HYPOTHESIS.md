# Pre-experiment hypothesis

*Written and committed before any measurement was taken (see `git log -- docs/HYPOTHESIS.md`;
this file's first commit is older than every file under `results/`).*

These predictions are for one modern x86-64 core (2 FMA pipes, 2–3 loads + 1–2 stores per cycle,
32–48 KiB L1D, 1–2 MiB L2, a shared LLC, single-thread DRAM bandwidth of roughly 10–25 GB/s).
The compiler is Clang at `-O3`. "Scalar" means `-fno-vectorize -fno-slp-vectorize`. All
statements are about float32 unless noted.

## H1: Speedup follows the lane count only while the data sits in L1, then drops
| Regime | Expected SIMD speedup (best ISA vs scalar), SAXPY / mul | Reason |
|---|---|---|
| L1 | ≈ lane count, capped by load/store ports: SSE2 ~3–4×, AVX2 ~6–8×, AVX-512 ~8–12× | Scalar SAXPY does about 1 element per cycle (limited by the store port). A vector does 1 *vector* per cycle. |
| L2 | ~2–4× | L2 can deliver about 32–64 B/cycle. Vector code reaches that ceiling, scalar code does not. |
| LLC | ~1.3–2× | LLC bandwidth per core is roughly 10–20 B/cycle. Scalar code gets close to that. |
| DRAM | ~1.0–1.2× | Scalar SAXPY at ~1 elem/cycle × 3 GHz × 12 B is about 36 GB/s, which is already more than one core can pull from DRAM. |

## H2: A plain FP dot product will *not* auto-vectorize, and that is the negative example
`s += x[i]*y[i]` on floats needs the compiler to reorder the additions. Strict IEEE semantics
forbid that, so Clang will not vectorize it at `-O3`. The scalar loop is then limited by
the FP-add latency (~4 cycles per element). The `#pragma omp simd reduction(+:s)` version allows
reordering, so I expect a speedup **larger than the lane count** in L1 (up to ~16× for
AVX2 and more for AVX-512). The gain comes from breaking the dependency chain with several
vector accumulators, not from vector width alone. The int32 dot product (unsigned wrap-around
addition is associative) should vectorize with no pragma.

## H3: Stencil keeps more of its advantage than SAXPY
The 3-point stencil does 5 flops per 8 compulsory bytes (AI ≈ 0.63 flop/B against 0.17 for SAXPY).
The neighbour loads hit L1. I expect it to keep a larger speedup into L2/LLC. It should still be
memory-bound (speedup ≈ 1) in DRAM.

## H4: Data type
- float64 has half the lanes, so its L1 speedup should be about half of float32's. In DRAM, GiB/s should
  match float32 and elements/s should be about half.
- int32 SAXPY/mul use `vpmulld`, which is 2 µops with ~10-cycle latency on Intel. So int32 should get a smaller
  speedup than float32 in L1 and an equal one in DRAM.

## H5: Alignment and tails
- Clang does not peel loops for alignment on x86. It uses unaligned loads instead. When the base address is
  not a multiple of the vector width, some loads cross a cache line. I expect AVX-512 (64 B vectors,
  every load splits when misaligned) to slow down by ~1.3–2× in L1, AVX2 less, and scalar not at all.
  The effect should vanish once the data comes from L2 or beyond.
- Time per call against N should be a **staircase** for vector builds, with period VF × interleave
  (e.g. 32 elements for AVX2 with an interleave of 4). This comes from the scalar remainder loop.
  A masked tail should flatten the steps.

## H6: Stride and gather
- With stride `s`, each element touches `min(s·4, 64)` bytes of cache line, so useful bandwidth
  should fall roughly as 1/s up to s = 16 (float32) and then stay flat.
- Vector code for strided or gathered loads (shuffles or `vgather`) should give little or no speedup at
  stride ≥ 4. A random gather from DRAM should be latency-bound and much slower than any streaming case.

## H7: Roofline
Every kernel here is below 1 flop/B, so all of them should sit under the bandwidth roof at every level
of the memory hierarchy except possibly L1, where the stencil may get close to the vector FMA roof.
None will come near the AVX-512 FMA peak.

---

# Addendum: G++ port (written before any G++ performance measurement)

The project was moved from Clang to **g++** (run natively on Windows via MSYS2 UCRT64). The original
hypotheses above still stand. This addendum records predictions specific to g++ and to the machine
used for the g++ reference run: a KVM guest on an Intel Xeon "Cascade Lake" core (family 6 model 85,
AVX-512, L1d 32 KiB, L2 1 MiB, LLC 33 MiB).

**What I knew when writing this.** (a) The Clang pilot results, from a *different* host (Emerald Rapids),
kept in git history. (b) g++'s own vectorization report and disassembly for every kernel. (c) Two
harness smoke tests (the peak-FLOP probe and a 3-sample SAXPY). No g++ experiment had been run.

* **G1. The plain FP `dot` stays latency-bound under g++, despite g++ reporting it "vectorized".** g++ uses an
  in-order ("fold-left") reduction: a vector multiply followed by a serial chain of scalar `vaddss`.
  Prediction: ≈ 1.0× vs the scalar build in every regime. Cascade Lake's FP add and FMA latencies are both
  4 cycles, so I also predict **no** 2× FMA slowdown of the kind the pilot machine showed (its 2-cycle adder made
  FMA contraction a pessimization).
* **G2. L1 speedups track lane count, but g++'s main loops are not unrolled** (one vector per iteration in
  the disassembly). With 2 loads + 1 store per cycle that should still allow ~1 vector/cycle, so SAXPY
  should reach ~4× (SSE2), ~7–8× (AVX2) and ~10–14× (AVX-512) in L1.
* **G3. AVX-512 gains less over AVX2 than its width suggests.** Cascade Lake lowers its clock for heavy
  512-bit work, and `-march=native` g++ tuning prefers 256-bit vectors, so `native` ≈ `avx2`.
* **G4. Strided SAXPY (stride ≥ 2):** g++ vectorizes it with permutes/shuffles and lane-wise stores.
  Prediction: no gain (0.8–1.2×) at any level, and useful bandwidth ∝ 1/stride once memory-bound (as H6).
* **G5. Gather SAXPY:** g++'s tuning for this core avoids hardware gathers and emulates them with scalar loads
  plus inserts. Prediction: modest gain (≤ 1.5×) in L1, none in DRAM, random gather latency-bound.
* **G6. Alignment:** g++ does not peel for alignment here (report: "Unknown misalignment, naturally aligned"),
  so H5's line-split pattern should hold: AVX-512 penalised at every offset that is not a multiple of 64, and AVX2
  except at 32.
