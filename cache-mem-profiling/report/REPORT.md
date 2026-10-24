# Project 2 — Cache & Memory Performance Profiling

*Author:* Brendan · *Date:* ____ · *Commit of measured code:* `____` (see `bin/BUILD_INFO`)

> How to use this template: fill **§1–§2 before running anything** and commit
> (`git commit -am "pre-experiment hypothesis"`). After `./scripts/run_all.sh`, fill §3–§8 from
> `data/processed/summary.md` and `figures/`. Delete these quote blocks when done.

---

## 1. System configuration

> Copy from `data/raw/sysinfo.txt`. Every row is required by the assignment.

| Item | Value |
|---|---|
| CPU model, cores/threads | |
| Caches (L1d / L2 / LLC, per core or shared) | |
| Memory (type, speed, channels, DIMMs) → theoretical peak GB/s | |
| OS (Windows 11 edition + build) | |
| Toolchain: MSYS2 UCRT64, G++ version + flags | (from `bin/BUILD_INFO`) |
| Python / numpy / pandas / matplotlib | |
| Power plan, processor boost, min/max processor state, Power mode | (sysinfo.txt "Power / frequency policy") |
| SMT state | |
| Pinning: measurement CPU, bandwidth CPUs | |
| Isolation (process priority, background load, OneDrive/Windows Update paused?) | |
| NUMA nodes / CCDs used | |
| Large pages (Lock pages in memory granted? `huge_kb` confirmed?) | |
| Counters: AMD uProf version, event set (`UPROF_CONFIG`), event or sample counts? | |
| Memory integrity / VBS / hypervisor state while measuring | |
| Repetitions × duration per configuration | |

## 2. Pre-experiment hypotheses

> Draft predictions with the reasoning behind them. **Edit these to what you actually expect for
> your machine** (look up your CPU's documented latencies and DRAM speed) and commit before running.

**H1 – Per-level latency.** Random-chase latency forms plateaus: L1 ≈ 4–5 cycles, L2 ≈ 12–16
cycles, LLC ≈ 40–70 cycles, DRAM ≈ 70–110 ns. *Why:* fixed pipeline depth for L1/L2; LLC is
reached over the on-chip ring/mesh; DRAM adds the memory controller, row activation and CAS.
Transitions should sit at each cache's capacity but be smeared (random replacement, set conflicts,
hits in smaller levels).

**H2 – Huge pages (Windows large pages).** Above a few MiB, 4 KB pages add latency (dTLB misses → page walks, some of
whose entries themselves miss in cache); 2 MB pages remove most of it. Below the TLB's reach,
huge pages make no difference.

**H3 – Pattern.** A sequential chase at 64 B stride will look 10–30× faster than random at DRAM
sizes because the hardware prefetchers fetch ahead; 256 B still benefits partially; at 1024 B the
L2 stream prefetcher (which stops at 4 KB page boundaries and has limited lookahead) helps less.

**H4 – Granularity.** Useful bandwidth of sparse access falls in proportion to bytes used per line
(8 B of 64 B = 1/8) while line bandwidth stays roughly constant until the stride exceeds a page;
random 8 B accesses are the worst case. Random accesses of ≥ 1 KB approach sequential bandwidth.

**H5 – R/W mix.** Demanded bandwidth: 100% read > 70/30 ≈ 50/50 > 100% write with normal stores,
because each written line is first read (RFO) and later written back (2 transfers) and DRAM pays
read↔write bus turnaround. Non-temporal stores recover most of the write deficit.

**H6 – Intensity / Little's Law.** Single-core throughput rises ~linearly with outstanding misses
up to ~10–16 (L1 fill buffers) or up to the L2 superqueue limit, then flattens while latency
grows. System-wide, latency stays near idle until ~60–80% of peak bandwidth, then rises steeply
(queueing) — the knee. One core alone reaches only `limit × 64 B / latency` ≈ 10–20 GB/s, so
saturating DRAM needs several cores.

**H7 – Working-set bandwidth.** Sequential read bandwidth shows one plateau per level, decreasing
roughly 2× per level; DRAM bandwidth with all cores approaches 70–85% of theoretical peak.

**H8 – Kernel misses.** For unit stride, runtime per element will track the footprint plateaus and
correlate with LLC misses. At constant work, stride 8 (one line per access) and stride 512 (one
page per access) raise L1/LLC/dTLB misses per element and runtime by roughly an order of
magnitude; random order is the slowest.

## 3. Methodology (short)

> Summarise README §4 in your own words: pointer chase, K-chain MLP, multithreaded bandwidth with
> first-touch, loaded-latency injection, kernel locality knobs, in-process counters, huge-page
> verification, frequency calibration, statistics (n reps, 95% CI). Note any deviations from the
> defaults (env vars you set).

## 4. Correctness validation

> Paste the key lines of `data/raw/validation.txt` and the sanity-check table (summary §0).
> Explain every WARN/FAIL: fixed, or why it does not invalidate the result. Compare your L1/L2
> latencies with the vendor's published figures and, if you ran it, with Intel MLC.

## 5. Results and analysis

### 5.1 Zero-queue latency (Fig. 1, summary §1)

> Latency table (ns and cycles, raw and AMAT-corrected). Where are the transitions relative to
> the capacities? How close is the AMAT model, and where does it deviate (just past a capacity?
> large sizes with 4 KB pages?) — and why? Does H1 hold?

### 5.2 Pattern and granularity (Fig. 2, Fig. 3, summary §2)

> Latency: sequential strides vs random — quantify how much the prefetchers hide. Bandwidth:
> useful vs line bandwidth vs stride/granularity; when does line bandwidth itself drop (page
> boundary crossings, TLB, DRAM row locality)? H3/H4?

### 5.3 Read/write mix (Fig. 4, Fig. 6, summary §3)

> Throughput per mix vs threads; normal vs non-temporal stores; estimated DRAM traffic including
> RFO; loaded latency at maximum load per mix. H5?

### 5.4 Intensity, knee and Little's Law (Fig. 5, Fig. 6, summary §4)

> Single-core MLP: idle latency, peak, in-flight lines (L = λW) → what hardware structure does that
> number correspond to on your CPU? System: knee location, outstanding lines at the knee and at
> maximum, latency at maximum. Why does latency explode past the knee (queueing in controller /
> mesh)? H6?

### 5.5 Working-set sweep (Fig. 1, Fig. 7)

> Annotated L1/L2/LLC/DRAM regions; bandwidth per level; 1 thread vs all cores (why does one core
> not reach DRAM peak? Use Little's Law). H7?

### 5.6 Cache-miss impact (Fig. 8, summary §5)

> Runtime vs footprint; constant-work locality sweep with misses per element; regression
> coefficients as effective miss penalties vs the measured latencies (why smaller?). H8?

### 5.7 TLB-miss impact and huge pages (Fig. 9, summary §6)

> Latency vs pages touched for 4 KB vs 2 MB; where does the 4 KB curve break (L1 dTLB reach =
> entries × 4 KB, STLB reach)? Estimated page-walk cost per miss. Kernels: which configurations do
> huge pages help, and which not? H2?

## 6. Negative / failure case

> At least one experiment where the technique stops helping or misleads. Candidates measured:
> huge pages give no benefit inside TLB reach or for unit-stride streaming (Fig. 9a/c); adding
> outstanding misses beyond the fill-buffer limit adds latency, not throughput (Fig. 5); adding
> threads past DRAM saturation (Fig. 4a); non-temporal stores in a cache-resident case.

## 7. Benchmark pitfalls (Fig. 10, summary §7)

> P1 LLC-resident "DRAM" bandwidth; P2 reading untouched memory (zero page) and first-touch faults;
> P3 sequential chase as "DRAM latency"; P4 unpinned threads / SMT sibling; P5 frequency (cold vs
> warm, nominal vs calibrated GHz). For each: naive number, correct number, the mechanism, and how
> the suite avoids it.

## 8. Honest anomalies

> Every unexpected result with a plausible hypothesis and, ideally, a follow-up test. Examples that
> showed up while developing this suite on a cloud VM (check whether yours shows them):
>
> - **Clock calibration with `add reg, imm` reported 13–16 GHz** on a Golden Cove–class core —
>   rename-stage folding of immediate adds; fixed by using register-register adds.
> - **Windows: reading never-written memory (pitfall P2)** pays a demand-zero page fault per 4 KB
>   on the first pass, rather than Linux's cached shared zero page. Compare the first and later
>   repetitions.
> - **Counter estimates from sampling** (uProf EBP): small differences between configurations
>   may be within sampling noise; compare with the 95% CIs of the runtimes.
> - **Host clock changed mid-sweep** (L1 went 1.8 → 3.6 ns) while latency in cycles stayed ~5.4 —
>   frequency scaling; this is why the suite reports cycles from a per-run calibration.
> - **Loaded latency lower than idle latency** at light load — likely uncore/mesh frequency rising
>   under load (or package C-state exit latency at idle). Test: repeat with turbo/uncore fixed.
> - **Non-temporal write bandwidth higher than read bandwidth** with few cores — reads are limited
>   per core by fill buffers (Little's Law: buffers × 64 B / latency); streaming stores are
>   fire-and-forget and are not.
>
> Other things worth checking: steps in the latency curve that don't match a cache size (TLB
> reach, set conflicts, page coloring); transitions below the nominal LLC size (LLC shared with
> other cores, inclusive vs non-inclusive policy, code/page tables occupying it); large CI on a few
> points (interrupts, SMIs, background tasks — look at the raw per-rep rows).

## 9. Conclusions

> Three to five sentences tying latency, bandwidth, concurrency (Little's Law) and miss counters
> (AMAT) together: what limits single-thread vs multi-thread memory performance on this machine?

## Appendix: reproduction

```
git clone <repo> && cd cache-mem-profiling
pacman -S --needed make git unzip mingw-w64-ucrt-x86_64-{gcc,python,python-numpy,python-pandas,python-matplotlib}
# Windows 11, "MSYS2 UCRT64" terminal as administrator - see WINDOWS_SETUP.md
make && ./scripts/setup_env.sh && ./scripts/uprof_probe.sh && ./scripts/run_all.sh && ./scripts/restore_env.sh
```
