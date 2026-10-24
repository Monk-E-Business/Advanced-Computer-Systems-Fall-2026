# Cache & Memory Performance Profiling

Measures the L1 / L2 / LLC / DRAM hierarchy of one machine — zero-queue latency, bandwidth by
pattern, granularity and read/write mix, the throughput–latency knee, and how cache and TLB
misses drive the runtime of simple kernels — and interprets the results with Little's Law and
AMAT. Everything from raw measurement to figures is scripted, so one command reproduces it.

Primary platform: **Windows 11, built with G++ in MSYS2 (UCRT64)**, with AMD uProf for hardware
counters on AMD Ryzen CPUs. The same sources and scripts also build and run on Linux with g++.

```
# in the "MSYS2 UCRT64" terminal, opened with "Run as administrator"
make                          # G++ build -> bin/*.exe
./scripts/setup_env.sh        # boost off, CPU at 100%, large-page privilege (sign out/in once)
./scripts/uprof_probe.sh      # check AMD uProf counters before the long run
./scripts/run_all.sh          # validate -> 8 experiments -> processed tables -> figures
./scripts/restore_env.sh
```

Results land in `data/raw/` (one CSV row per repetition), `data/processed/` (statistics +
`summary.md`) and `figures/`. The write-up goes in `report/REPORT.md`. Step-by-step setup for
Windows is in **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)**.

---

## 1. Requirements

| | Windows 11 (primary) | Linux (also supported) |
|---|---|---|
| Shell / build | MSYS2, **UCRT64** terminal: `mingw-w64-ucrt-x86_64-gcc`, `make` | bash, g++ ≥ 10, make |
| Python | `mingw-w64-ucrt-x86_64-python`, `-python-numpy`, `-python-pandas`, `-python-matplotlib` | python3 + numpy, pandas, matplotlib |
| Pinning | `SetThreadGroupAffinity` (logical CPU numbers as in Task Manager) | `sched_setaffinity` |
| Huge pages | 2 MB **large pages** (`VirtualAlloc(MEM_LARGE_PAGES)`): needs the *Lock pages in memory* right (`setup_env.sh` grants it via `bin/sysinfo --grant-lock-pages`), an administrator terminal, and free contiguous memory (run soon after a reboot) | THP (`madvise`), optional hugetlbfs |
| Huge-page check | `QueryWorkingSetEx` per 2 MB → `huge_kb` column | `/proc/self/smaps` |
| Counters | **AMD uProf** CPU profiler (`AMDuProfCLI.exe`, event-based sampling), wrapped by the scripts (see §4, *Counters*). Needs Hyper-V **off** underneath Windows (Memory integrity off) | in-process `perf_event_open` |
| Frequency policy | `powercfg`: processor boost off, min/max processor state 100 % | cpufreq governor, turbo off |
| Topology / caches | `bin/sysinfo` (`GetLogicalProcessorInformationEx`) | `bin/sysinfo` (`/sys`) |

Runtime: `QUICK=1 ./scripts/run_all.sh` ≈ 5–10 min (smoke test); the full run ≈ 30–60 min,
plus ~10 min for the uProf-wrapped counter runs.

**Why MSYS2 UCRT64?** It gives a native Windows G++ (MinGW-w64) and a bash in which the
experiment scripts run unchanged. Build and run everything inside the *UCRT64* terminal. The
MSYS, MINGW64 and CLANG64 terminals use different toolchains.

## 2. Reproducing the results

1. **Write and commit your hypothesis first.** Fill section 2 of `report/REPORT.md`, then
   `git commit -am "pre-experiment hypothesis"`. The commit timestamp proves it predates the data.
2. Quiet the machine: AC power, close browsers/IDEs, `./scripts/setup_env.sh` (Windows, admin
   MSYS2 terminal) or `sudo ./scripts/setup_env.sh` (Linux).
3. Windows + AMD: `./scripts/uprof_probe.sh` and check every counter column is filled.
4. `./scripts/run_all.sh` (or `QUICK=1 ./scripts/run_all.sh` first, to check everything works).
5. Read `data/processed/summary.md` — **start with section 0, the sanity checks**. Any FAIL or
   WARN must be fixed or discussed before you interpret the numbers.
6. Commit `data/raw`, `data/processed`, `figures`. `data/raw/sysinfo.txt` records the full
   configuration that produced them.

Individual pieces: `./scripts/run_all.sh exp4 exp7` re-runs only those experiments (then
re-processes and re-plots); `python3 analysis/process.py && python3 analysis/plot.py` rebuilds
tables and figures from existing raw data.

### Knobs (environment variables, see `scripts/lib.sh`)

| Variable | Default | Meaning |
|---|---|---|
| `CPU` | 2nd physical core of the fastest core type | measurement core (avoid CPU 0, it services more interrupts). Numbers are logical CPUs as in Task Manager |
| `CPUS` | one logical CPU per physical core (fastest core type, same NUMA node) | bandwidth threads / load generators |
| `ALL_CORE_TYPES` | 0 | 1 = also use slower core types (E-cores) for bandwidth threads on hybrid CPUs |
| `REPS`, `MS` | 5, 200 | repetitions per configuration, target ms per repetition |
| `MAX_WSS` | 1G | top of the working-set sweeps — keep ≥ 8× the LLC |
| `DRAM_SIZE` | 256M | per-thread buffer for DRAM bandwidth (total ≫ LLC) |
| `CHASE_DRAM` | 1G | buffer for DRAM latency / MLP / loaded latency |
| `KERNEL_DRAM` | 768M | kernel footprint for the locality/TLB experiments |
| `TLB_MAX_PAGES` | 262144 | largest page count in the TLB sweep |
| `NUMACTL` | empty | Linux only: prefix such as `numactl --membind=0` |
| `COUNTERS` | auto | `uprof` (Windows + AMD uProf found), `linux` (perf_event_open), `none` |
| `UPROF_CLI` | `/c/Program Files/AMD/AMDuProf/bin/AMDuProfCLI.exe` | path to AMDuProfCLI if installed elsewhere |
| `UPROF_SETS` | `config:data_access` | uProf event sets to collect (two profiled runs each). The default predefined set gives every counter column; its 10 events are multiplexed on 6 counters, which `uprof_merge.py` corrects using each run's own runtime × clock (`--meta`). Hand-picked sets `A,B` (≤ 6 events) exist but sampled almost none of the program on uProf 5.3 / Windows 11 |
| `CMP_PRIORITY` | normal | `high` = run benchmarks at HIGH_PRIORITY_CLASS (Windows' nearest thing to an isolated core) |
| `PEAK_GBPS` | empty | theoretical DRAM peak (channels × MT/s × 8 B / 1000) for a sanity check |
| `QUICK` | 0 | 1 = small sizes, 2 reps (smoke test only — not for the report) |

## 3. What maps to which requirement

| Requirement | Script | Raw data | Figure / table |
|---|---|---|---|
| Zero-queue per-level latency (ns + cycles) | `exp1_latency_wss.sh` | `latency_wss.csv` | `fig1_latency_wss`, summary §1 (`latency_table.csv`) |
| Working-set sweep with L1/L2/LLC/DRAM regions | exp1, `exp5_wss_bw.sh` | `latency_wss.csv`, `bw_wss.csv` | fig1, `fig7_bw_wss` |
| Pattern & granularity sweep (seq/rand, 64/256/1024 B strides) | exp1 (latency), `exp2_pattern.sh` (bandwidth) | `latency_wss.csv`, `bw_pattern.csv` | `fig2_pattern_latency`, `fig3_pattern_bw`, §2 |
| Read/write mix: 100R, 100W, 70/30, 50/50 | `exp3_rwmix.sh`, exp4 | `bw_rwmix.csv`, `loaded.csv` | `fig4_rwmix`, fig6, §3 |
| Intensity sweep, knee, Little's Law | `exp4_intensity.sh` | `mlp.csv`, `loaded.csv` | `fig5_mlp`, `fig6_loaded_latency`, §4 |
| Cache-miss impact with counters | `exp6_cache_kernels.sh` | `kernels.csv` | `fig8_kernels_cache`, §5 (`kernel_regression.csv`) |
| TLB-miss impact, 4 KB vs huge pages | `exp7_tlb.sh` | `tlb.csv`, `kernels_tlb.csv` | `fig9_tlb`, §6 |
| Benchmark pitfalls + negative case | `exp8_pitfalls.sh` (+ TLB/MLP saturation) | `pitfall_*.csv` | `fig10_pitfalls`, §7 |
| Correctness validation | `validate.sh` | `validation.txt` | summary §0 |
| System configuration | `sysinfo.sh` | `sysinfo.txt`, `sysinfo.env`, `caches.csv` | report §1 |
| MLC cross-check (optional) | `exp_mlc.sh` | `mlc/*.txt` | overlaid on fig6 |

## 4. How each measurement works

**Latency — `bin/latency`.** A pointer chase: each cache line stores the address of the next, so
every load depends on the previous one and the time per hop is the load-to-use latency with
nothing else in flight (zero queue). `--pattern rand` links the lines into one random cycle
(Fisher–Yates order), defeating prefetchers; `seq` links them in address order at a given stride
(prefetcher-friendly, the P3 pitfall); `page` puts one line in each 4 KB page at a random offset,
in random page order, so the number of distinct pages grows while the number of lines stays small
(isolates TLB reach from cache capacity). Every run walks the full chain once first: that both
warms caches/TLB and *validates* the chain (a single cycle through all N nodes).

**Memory-level parallelism — `latency --chains K`.** K independent chains walked in lock-step.
Throughput rises ~linearly with K until K reaches the number of misses the core can track (fill
buffers); after that, latency per hop grows instead. Little's Law gives the limit:
`in-flight lines = bandwidth / 64 B × latency`.

**Bandwidth — `bin/bandwidth`.** Each thread pins itself, allocates and first-touches its own
buffer (NUMA-local), then all threads start on a barrier and run for `--ms`. Patterns: `seq`,
`stride` (`--gran` bytes every `--stride` bytes), `rand` (`--gran` contiguous bytes at a random
aligned slot). `--read-pct` sets the R/W mix exactly (reads then writes within each period of 10
accesses, so the branch is predictable). Two bandwidths are reported: **useful** (bytes the
program asked for) and **lines** (whole 64 B lines moved). Normal stores cause a read-for-ownership,
so for writes DRAM traffic ≈ 2× demanded bytes; `--nt` uses non-temporal stores that skip it.
Write loops store varying values on purpose — a constant fill would be turned into `memset`, which
switches to non-temporal stores for large sizes and silently changes the experiment.

**Loaded latency — `bin/loaded`.** One core chases a random chain over a large buffer while every
other physical core streams with `--delay` empty-loop iterations between accesses. Sweeping the
delay from 20000 to 0 traces latency vs bandwidth (the same method as Intel MLC's
`--loaded_latency`). The knee is located with a Kneedle-style criterion (point farthest below the
chord of the normalised curve).

**Kernels — `bin/kernels`.** `z[i] = x[i]*y[i]` and `y[i] = a*x[i] + y[i]` over a footprint
sweep, and at a fixed DRAM footprint with element stride 1, 2, 4, 8 (= one line), 16, 64, 512
(= one page) and random order. Every order processes each element exactly once per pass, so the
**work is constant and only locality changes**. Arrays start at different offsets modulo 4 KB to
avoid 4K-aliasing stalls. Results are checked element-wise against a plain reference loop.

**Counters (Windows + AMD Ryzen): AMD uProf, differential method.** Windows has no user-space
PMU API, and AMD's counting tool `AMDuProfPcm` supports only EPYC server CPUs, so the suite uses
uProf's **CPU profiler** (event-based sampling, EBP), which supports Ryzen. `run_counted` in
`scripts/lib.sh` profiles each counted configuration with
`AMDuProfCLI collect -e event=pmcx…,umask=…,interval=… … bin/kernels.exe …` and
`AMDuProfCLI report`, **twice per event set**: once normally and once with `--reps 0`
(identical allocation, initialisation, validation and warm-up, but no timed repetitions).
The default set is uProf's predefined `data_access` (10 events). A Zen core has 6
counters, so uProf multiplexes them and each event is captured only part of the time; the
report does not scale this back (on the test machine uProf saw 17–42 % of the cycles). The
programs therefore write their own runtime and clock (`--meta`), and the merge scales every
event of a run by expected cycles / uProf cycles before subtracting, the same correction
Linux `perf` applies to multiplexed counters. It assumes all events are captured at the same
rate; state that in the report. Hand-picked ≤ 6-event sets (`UPROF_SETS=A,B`, `-e event=…`)
avoid multiplexing, but on uProf 5.3 / Windows 11 they sampled almost none of the program's
own code.
`analysis/uprof_merge.py` reads the report's `MONITORED EVENTS` (code, unit mask, sampling
interval) and the benchmark's `PROCESS` row (other processes excluded). It converts samples ×
interval to event counts, solves the report's derived metrics (per-1000-instructions, %)
for events shown only as metrics, subtracts the setup-only run, and divides by the number of
repetitions. So the counts belong to the timed loop only. Columns map to exact
`PMCx<code>:<mask>` keys in `analysis/uprof_events.csv`. On Zen, `llc_ref` = demand L1D fills
from L3 + from DRAM (requests reaching the L3, the LLC; needs set B), and `llc_miss` = fills
from DRAM. `dtlb_miss` = L2 DTLB misses,
i.e. page walks. Sampling makes these *estimates*: with ~1 s timed loops the statistical error is
about 1–2 %. The merge cross-checks uProf's cycle count against the benchmark's own time × clock
and prints the ratio, which shows whether uProf reported event counts (ratio ≈ 1) or sample
counts (ratio ≈ 1/interval). **Run `scripts/uprof_probe.sh` first.** uProf's CPU profiling is
**disabled while Hyper-V runs underneath Windows**, which is the case on many Windows 11 PCs
because of *Memory integrity* (virtualisation-based security). WINDOWS_SETUP.md shows how to
switch it off for the measurement session and back on afterwards. Raw uProf output is kept in
`data/raw/uprof/`.

**Counters (Linux).** `perf_event_open` (user-space only, generic events: cycles, instructions,
L1D read misses, LLC read references/misses, dTLB read references/misses) is enabled around the
timed loop *inside* the process, so set-up, initialisation and page faults are not counted.

**Huge pages.** Windows: `--pages large` allocates with `VirtualAlloc(MEM_LARGE_PAGES)` after
enabling `SeLockMemoryPrivilege` in the process token. Large pages are locked in RAM and need
physically contiguous memory, so allocations can fail after long uptime (error 1450). Reboot, then run.
Only the buffer being measured uses `$PG`: `loaded`'s generators default to 4 KB (`--gen-pages`), and
generator/bandwidth buffers fall back to 4 KB with a warning if large pages run out (`huge_kb` shows it,
and a sanity check flags it). A latency or kernel run that cannot get large pages fails instead; the
scripts skip it, list it in `data/raw/failures.txt`, and carry on. Windows
never uses large pages implicitly, so `4k` runs really are 4 KB. Every row records `huge_kb`, the
amount actually backed by large pages, read back with `QueryWorkingSetEx`. Linux: `4k` calls
`madvise(MADV_NOHUGEPAGE)` (otherwise THP=`always` would silently make "4 KB" runs huge), `thp`
calls `MADV_HUGEPAGE`, `hugetlb` uses `MAP_HUGETLB`, and `huge_kb` comes from `/proc/self/smaps`.
The scripts use `large` on Windows and `thp` on Linux automatically.

**Output on Windows.** The programs switch stdout to binary mode, so CSV lines end in `\n`, not
`\r\n`. A stray `\r` would silently break the bash scripts' comparisons.

**Frequency.** Each process measures its own core clock with a chain of dependent
register-register adds (1 cycle each) and converts ns → cycles with it. Register-register on
purpose: newer Intel cores (Golden Cove and later) fold dependent `add reg, imm` chains at rename,
which would over-report the clock ~4–5×. When counters are available, `perf_cycles` in the latency
table cross-checks the conversion.

**Statistics.** Every configuration is repeated `REPS` times; tables report mean, std, median,
min, max and the 95% confidence interval (Student-t); figures show the CI as error bars.

## 5. Correctness validation (`scripts/validate.sh`)

- every pointer chain (all patterns, strides, chain counts, page modes) is one cycle over all nodes
- bandwidth code paths reproduce closed-form checksums (Σi over a buffer holding w[i] = i), the
  stride path touches exactly the expected words, writes and NT writes store the expected values,
  and the 70/30 and 50/50 mixes write exactly 30% / 50% of blocks
- kernels equal a reference loop in every order and page mode
- `4k` buffers get 0 kB of huge pages; `large`/`thp` buffers get ~100% (else validation fails)
- **loop ceiling**: the generic strided/mixed loop is timed on an L2-resident buffer; a DRAM
  result close to that number would mean the loop, not memory, was the limit
- known-answer checks run on the data (summary §0): L1 = 3–7 cycles, monotonic latency per level,
  DRAM working set ≥ 4× LLC, stable clock, huge pages granted, bandwidth below theoretical peak

## 6. Interpreting with Little's Law and AMAT

- **Little's Law**, L = λ·W: requests in flight = throughput × latency. With 64 B lines,
  `lines in flight = (GB/s ÷ 64) × ns`. At the MLP saturation point this is the per-core miss
  limit; along the loaded-latency curve it is the system-wide concurrency. One core can never
  exceed `limit × 64 B / latency` — that is why a single thread cannot saturate DRAM.
- **AMAT**: `AMAT = Σ_level (fraction served by level × level latency)`. For a uniformly random
  working set S and inclusive caches, the fraction hitting a cache of capacity C is ≈ min(1, C/S).
  `process.py` uses this to (a) correct the plateau latencies for accesses that still hit a
  smaller level and (b) predict the entire working-set curve (dotted lines in Fig. 1). Where the
  model misses — just past each capacity, with 4 KB pages at large sizes, on AMD's exclusive
  (victim) L3 — is worth discussing.
- **Kernel regression**: `ns/element ≈ a + b₁·L1miss/elem + b₂·LLCmiss/elem + b₃·dTLBmiss/elem`.
  The b's are *effective* miss penalties; they come out well below idle latencies because
  prefetching and MLP overlap misses — compare them with the Fig. 1 latencies.

## 7. Caveats

- **Hybrid CPUs** (Intel 12th gen+): P- and E-cores have different caches and latencies. Pin with
  `CPU=` to a P-core and use `CPUS=` with P-cores only, or report both.
- **AMD Ryzen**: the L3 is shared per CCD (or per CCX on Zen 2) and is a *victim* cache of L2
  (mostly exclusive), so the effective capacity for one core is roughly L2 + L3 and the AMAT
  inclusive model is an approximation. Discuss where it deviates. On two-CCD parts (e.g. 7950X)
  each CCD has its own L3; all bandwidth threads still share the same DRAM. X3D parts have one
  CCD with 3D V-Cache (96 MB) and possibly one without: pin `CPU=` to the V-Cache CCD or to the
  other one deliberately, and say which.
- **Windows specifics**: (1) with *Memory integrity* / virtualisation-based security on, Windows
  itself runs on Hyper-V. This adds small timing overheads and disables uProf's event-based
  profiling (sysinfo records the VBS status). Turn off Core isolation → Memory integrity (and, if
  needed, `bcdedit /set hypervisorlaunchtype off`), reboot, measure, and turn it back on when
  done. Record the state you measured in. (2) There are no
  isolated cores: close other programs, pause OneDrive sync and Windows Update, consider
  `CMP_PRIORITY=high`. (3) Pitfall P2 behaves differently from Linux: Windows has no shared zero
  page, so reading never-written memory pays a demand-zero fault per page on the first pass,
  rather than reading one cached zero page. (4) The timer is `QueryPerformanceCounter` (via
  `std::chrono::steady_clock`, ~100 ns resolution), negligible against ~200 ms repetitions.
- **Turbo / uncore scaling**: with turbo on, the core clock changes with load; uncore/mesh
  frequency can rise under load, which can make *loaded* latency lower than *idle* latency on some
  systems. Turn turbo off for the main runs, or discuss it.
- **SMT**: keep the setting constant; record it (sysinfo does). The P4 pitfall compares a
  generator on the SMT sibling with one on another core.
- Counters: Linux generic perf events map to different hardware events per vendor; on Windows
  the uProf event mapping is in `analysis/uprof_events.csv`. Multiplexing adds noise.

## 8. Repository layout

```
Makefile                 G++ build (Windows/MSYS2 -> static .exe, or Linux); `make test` runs validation
WINDOWS_SETUP.md         step-by-step: MSYS2, G++, large pages, AMD uProf, running, results
src/platform.[ch]pp      the only OS-specific code: timing, pinning, large/huge-page allocation and
                         verification, privileges, topology and caches (Win32 / Linux)
src/common.[ch]pp        option parsing, GHz calibration, Linux perf_event_open counters
src/chase.[ch]pp         pointer-chain construction/validation, K-chain chase loops
src/latency.cpp          latency + MLP program
src/bwkern.[ch]pp        per-thread traffic kernel (patterns, granularity, mixes, NT, delay) + self-test
src/bandwidth.cpp        multi-thread bandwidth program
src/loaded.cpp           loaded-latency program
src/kernels.cpp          z=x*y / saxpy with locality knobs, counters and reference check
src/sysinfo.cpp          topology, caches, large-page check/grant, admin check (replaces lscpu)
src/threads.hpp          portable barrier
scripts/lib.sh           shared config (all knobs), OS detection, uProf wrapper (run_counted)
scripts/sysinfo.sh       system configuration capture (PowerShell/powercfg on Windows)
scripts/setup_env.sh     quiet-machine settings; restore_env.sh undoes them
scripts/uprof_probe.sh   checks AMD uProf counter collection before the long run
scripts/validate.sh      correctness checks
scripts/exp1..8_*.sh     experiments; exp_mlc.sh optional MLC cross-check
scripts/run_all.sh       whole pipeline
analysis/process.py      raw -> processed statistics, latency table, AMAT, Little's Law, regression, checks
analysis/plot.py         figures
analysis/common.py       shared helpers
analysis/uprof_merge.py  fills counter columns from uProf dumps (full run - setup-only run)
analysis/uprof_events.csv  uProf event-name -> counter-column mapping (editable)
data/raw/                raw CSVs (one row per repetition) + system info
data/processed/          per-configuration statistics + summary.md
figures/                 PNG figures
report/REPORT.md         report template: hypothesis, results, analysis, anomalies, pitfalls
examples/vm-smoke-run/   what the outputs look like (QUICK run on a Linux cloud VM - not report data)
```

### Raw CSV columns (main ones)

- **latency / mlp / tlb**: `pattern, pages, size_bytes, stride, chains, rep, accesses, lat_ns,
  lat_cycles, ghz, gbps, huge_kb, chain_ok` + 7 counter totals for the timed loop.
- **bandwidth**: `pattern, gran, stride, read_pct, nt, delay, threads, pinned, rep, gbps
  (useful), line_gbps, gbps_min_thread, gbps_max_thread, huge_kb, init, ghz`.
- **loaded**: `read_pct, nt, delay, gens, rep, lat_ns, lat_cycles, gen_gbps, gen_line_gbps`.
- **kernels**: `kernel, order, stride, pages, footprint_bytes, n, rep, passes, ns_per_elem, gbps,
  check_ok` + counters.
