# SSD Performance Profiling (Project #3) — Windows 11 + MSYS2 + g++

A reproducible fio-based harness that characterises an NVMe/SATA SSD's
throughput–latency behaviour: zero-queue latency, block-size, read/write-mix,
queue-depth and working-set effects, tail latency, burst vs steady state, and
setups that produce misleading numbers. One command runs everything, records
the environment, validates the measurement path, and produces plots and tables.

**Toolchain:** MSYS2 **UCRT64** shell (bash, make, Python) · **g++** for the
two compiled tools · the official **fio for Windows** (`windowsaio` engine).
Step-by-step setup: **[docs/WINDOWS_SETUP.md](docs/WINDOWS_SETUP.md)**.
(The same scripts also run unchanged on Linux.)

> ## ⚠ Data-loss warning
> These scripts **write to the target**. Use a dedicated empty partition, an
> empty second disk, or a large disposable file. Guards in `scripts/common.sh`
> run before anything touches the target:
> * **File target** (recommended): the file name must contain `fio-scratch`.
>   The scripts refuse to touch a file they did not create (tracked by a
>   `*.owned-by-ssd-profiling` marker). Network, RAM, CD and FAT32 volumes are
>   refused, and free space is checked first.
> * **Whole disk** (`\\.\PhysicalDriveN`): requires `ALLOW_RAW_DEVICE=1`
>   **and** `WIPE_OK=<same string>`, an Administrator shell, and a disk with
>   **no partitions**. The disk Windows boots from is always refused, and you
>   must retype the target to confirm.
>
> You are still responsible for pointing it at the right thing.

## Quick start (details in docs/WINDOWS_SETUP.md)

```bash
# In the "MSYS2 UCRT64" shell, ideally started with "Run as administrator":
pacman -S --needed make zip unzip git mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-python \
  mingw-w64-ucrt-x86_64-python-numpy mingw-w64-ucrt-x86_64-python-pandas \
  mingw-w64-ucrt-x86_64-python-matplotlib mingw-w64-ucrt-x86_64-python-tabulate
# + install fio from the MSI at https://github.com/axboe/fio/releases

cd ~ && unzip /c/Users/<you>/Downloads/ssd-profiling.zip && cd ssd-profiling
cat > config.local.env <<'EOF'
TARGET="D:/ssdtest/fio-scratch.bin"   # a folder on a dedicated NTFS partition
TARGET_SIZE="64G"                     # >= 2-3x the drive's SLC cache
FIO_CPUS="2-5"                        # 4 logical CPUs, not CPU 0
EOF
make build     # g++ -> bin/ref_qd1.exe, bin/winstat.exe
make smoke     # ~5 min end-to-end test (numbers meaningless)
make all       # full run, ~4-5 h
```

Re-run only the analysis at any time with `make analyze`.

## Repository layout

```
config.env              all knobs (put overrides in config.local.env, git-ignored)
Makefile                make build | smoke | all | analyze | <single experiment>
src/
  ref_qd1.cpp           g++: independent QD=1 benchmark (unbuffered ReadFile/WriteFile)
  winstat.cpp           g++: Windows device facts — I/O counters, temperature, model/
                        firmware/write cache, which disk a path lives on, file-cache
                        purge, "never-written" file creation
fio/
  workload.fio          generic parameterised job used by every sweep
  precondition.fio      sequential fill + random fill (SNIA-style)
  timeseries.fio        long logged runs for burst -> steady state
  burst.fio             short size-limited run (NTFS zero-fill demo)
  verify.fio            crc32c write+verify (I/O-path integrity)
scripts/
  common.sh             config, platform layer, SAFETY CHECKS, run_fio wrapper
  win_sysinfo.ps1       PowerShell: OS, CPU, PCIe link, disk health, Defender exclusions
  collect_sysinfo.sh    environment snapshot (calls the two above)
  prepare_target.sh     create + precondition the test span
  validate.sh           reference-implementation + integrity checks
  exp_*.sh              one script per experiment (see table below)
  run_all.sh            everything in the right order, then analysis
analysis/               parse_fio.py, validate.py, plot.py, knee.py, fiolib.py, sysinfo_summary.py
data/raw/<run>/         fio JSON + .meta.json per run, sysinfo/, logs, run.log, config used
data/processed/<run>/   per-run and summary CSVs, time series, histograms, validation
plots/<run>/            figures
docs/WINDOWS_SETUP.md   step-by-step setup and run guide
docs/REPORT.md          report template with the pre-experiment hypotheses
```

## What each experiment measures

| Requirement | Script | Fixed knobs | Varied | Output |
|---|---|---|---|---|
| Zero-queue baselines | `exp_baseline.sh` | QD=1, numjobs=1 | {4K rand, 128K seq} × {R, W} | `01_baseline_qd1.png` |
| Block-size sweep | `exp_bs_sweep.sh` | QD=32, nj=1 | bs 4K–256K (seq to 1M), pattern, dir | `02_bs_sweep.png` |
| R/W mix sweep | `exp_mix_sweep.sh` | rand 4K, QD=32 | rwmixread 100/70/50/0 | `03_mix_sweep.png` |
| QD/parallelism sweep, knee, Little's Law | `exp_qd_sweep.sh` | per series | total QD 1–256, 1 vs 4 jobs | `04_qd_curve.png`, `05_littles_law.png` |
| Max IOPS / max MB/s | `exp_peak.sh` | — | — | table "Peak capability" |
| Tail latency (mid-QD, knee) | `exp_tail.sh` | rand 4K | QD1, knee/4, knee, knee+70:30 | `06_tail_ccdf.png` |
| Working set / LBA range | `exp_working_set.sh` | rand 4K read | span 1G–full, QD 1 & 32 | `07_working_set.png` |
| Device state (burst vs steady) | `exp_steady_state.sh` | — | time | `08_steady_state.png` |
| Misleading setups (negative cases) | `exp_misleading.sh` | — | A cache, B queue depth, C unwritten reads, D NTFS zero-fill | `09_misleading.png` |
| Correctness validation | `validate.sh`, `validate.py` | — | — | `validation.md` |

## Methodology choices (and why)

* **Unbuffered I/O everywhere** (`direct=1` → Windows `FILE_FLAG_NO_BUFFERING`),
  so the Windows file cache never serves or absorbs I/O. Misleading case A
  shows what happens otherwise.
* **Engine:** `windowsaio` (I/O completion ports), so `iodepth` really means
  outstanding I/Os. Windows' synchronous engines can't do unbuffered I/O, so
  they appear only in the misleading demos.
* **Effective queue depth** = `iodepth × numjobs` ("total QD" in every plot).
  Sequential multi-job runs give each job a disjoint stripe (`offset_increment`).
  Otherwise N jobs read the same LBAs and the device sees one stream.
* **CPU pinning:** fio's `cpus_allowed=$FIO_CPUS`. The reference tool pins
  itself with `SetThreadAffinityMask` to the first CPU in that list.
* **Data pattern:** incompressible (`refill_buffers=1`,
  `buffer_compress_percentage=0`), constant across all runs.
* **Random offsets:** aligned to the block size, `norandommap`,
  `randrepeat=0` → independent uniform offsets each rep.
* **Latency metric:** fio `lat` (submission → completion), percentiles
  1–99.99. Tail runs use `json+` full histograms for the CCDF.
* **Warm-up:** `ramp_time` discarded each run; `time_based` runs.
* **Preconditioning:** `PRECOND_SEQ_LOOPS` (2) full sequential fills, then
  `PRECOND_RAND_MULT` (1×) span of 4K random writes. The sequential fill also
  moves NTFS's *valid data length* to the end of the file, so later random
  writes never trigger NTFS zero-fill (misleading case D).
* **Device counters:** `winstat counters` reads `IOCTL_DISK_PERFORMANCE` from
  the **volume** holding the test file (whole disk for raw targets). That
  excludes I/O on C: even when both are on one SSD, but includes everything
  NTFS itself issues on that volume.
* **Order:** prepare → validate → read/write experiments → misleading → steady
  state last (it leaves the drive maximally fragmented).
* **Knee:** argmax of Kleinrock's power (throughput / mean latency), plus a
  marginal criterion (doubling QD gives <10% throughput for ≥50% latency).
* **Error bars:** 95% CI across reps (Student t). Tables carry `_ci95` columns.

## Correctness validation

`scripts/validate.sh` + `analysis/validate.py` → `data/processed/<run>/validation.md`

| Check | What it catches |
|---|---|
| V1 crc32c write+verify (fio `verify`) | broken I/O path, wrong offsets |
| V2 `bin/ref_qd1.exe` vs fio at QD1 | fio misconfiguration; engine overhead |
| V3 `dd iflag=direct` vs fio 128K seq read (if dd can open the file unbuffered) | second bandwidth reference |
| V4 Little's Law: IOPS × mean latency ≈ total QD, every run | queue not actually full (CPU-bound submitter, sync engine) |
| V5 volume byte counters ≈ fio bytes × (runtime+ramp)/runtime | cache hits, writes not reaching the device, hidden writes |
| V6 throughput ≤ PCIe link raw ceiling (from the PnP device properties) | impossible numbers (cache, compression, wrong units) |

Runs in the misleading experiment are labelled `expected-fail` when they fail
V4/V5, because that failure is the evidence.

## Windows-specific cautions

* **Microsoft Defender** scans files as they're opened. Exclude the test folder
  (`D:\ssdtest`) or it can read your 64 GB file behind fio's back.
  `sysinfo.json` records whether the exclusion is present (elevated shell only).
* **Indexing, Windows Update, OneDrive, backups** add I/O. Pause what you can,
  and put the target on its own partition, not C:.
* **Elevation:** an Administrator shell is needed for the cold-cache part of
  case A (purging the standby list) and for raw-disk targets. Everything else
  works without it.
* **Ctrl+C** may not reach the native fio.exe from MSYS2's terminal. To abort,
  close the window and end `fio.exe` in Task Manager.
* **Power:** stay plugged in, Power mode = *Best performance*, and sleep
  disabled for the duration.

## Runtime (defaults)

About 105 measured points × 3 reps × 35 s ≈ 3.1 h. Add about 20 min of tail
runs and about 48 min for the steady-state phase (5 min idle, 10 min
sequential write, 30 min random write). Preconditioning (2 × 64 GiB
sequential + 64 GiB random) takes minutes to roughly 30 min depending on the
drive. For a faster pass, lower `RUNTIME` to 15–20 s or `REPS` to 2.

## Things to watch for

* **128 KiB QD1 writes may fall short of Little's Law** (IOPS × W ≈ 0.75 rather
  than 1) and run slower than the reference tool. With `refill_buffers=1`, fio
  regenerates 128 KiB of random data before each submit, and at QD1 the device
  idles meanwhile. This is a host-side effect that disappears at higher QD.
* **Single-job vs multi-job QD sweeps diverge at high QD** when one submitting
  thread becomes CPU-bound before the device saturates. Compare `cpu_sys`/`cpu_usr`.
