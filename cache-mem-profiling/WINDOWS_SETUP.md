# Running the project on Windows 11 with MSYS2 + G++ (AMD Ryzen)

Everything runs natively on Windows: the benchmarks are built with **G++ (MinGW-w64) from
MSYS2**, and the bash scripts run in MSYS2's **UCRT64** terminal. Hardware counters come from
**AMD uProf**.

Budget about 1 hour of setup and 1–1.5 hours of measuring.

| You need | Notes |
|---|---|
| Windows 11, AMD Ryzen CPU, an administrator account | admin is needed for large pages and uProf |
| ~3 GB free disk | MSYS2 + packages + results |
| 16 GB RAM recommended | with 8 GB, use the smaller sizes in step 12 |
| AC power | laptops clock down on battery |

---

## Part A: install the tools (once)

### 1. Install MSYS2

1. Download the installer from **https://www.msys2.org** (`msys2-x86_64-<date>.exe`).
2. Run it and keep the default folder **`C:\msys64`**. Don't install into a path with spaces.
3. Open **MSYS2 UCRT64** from the Start menu. The prompt line shows `UCRT64` in purple. Always
   use this terminal; the "MSYS", "MINGW64" and "CLANG64" ones use other toolchains.
4. Update the package database and core system:
   ```bash
   pacman -Syu
   ```
   If it says the terminal must be closed, close it, reopen **MSYS2 UCRT64**, and run
   `pacman -Su`.

### 2. Install G++, make, Python and the plotting libraries

```bash
pacman -S --needed make git unzip \
  mingw-w64-ucrt-x86_64-gcc \
  mingw-w64-ucrt-x86_64-python \
  mingw-w64-ucrt-x86_64-python-numpy \
  mingw-w64-ucrt-x86_64-python-pandas \
  mingw-w64-ucrt-x86_64-python-matplotlib
```

Check:
```bash
which g++ && g++ --version | head -1      # -> /ucrt64/bin/g++
python -c "import numpy, pandas, matplotlib; print('python OK')"
```

### 3. Install AMD uProf (for the cache/TLB counters)

1. Download the Windows installer from **https://www.amd.com/en/developer/uprof.html**
   (`AMDuProf-<version>.exe`) and run it with the defaults. It installs a driver; reboot if asked.
2. Check that the scripts can find it (in the UCRT64 terminal):
   ```bash
   ls "/c/Program Files/AMD/AMDuProf/bin/AMDuProfCLI.exe"
   ```
   If it was installed elsewhere, put this line in `~/.bashrc` with your path:
   `export UPROF_CLI="/c/path/to/AMDuProfCLI.exe"`.

> **Why the CPU profiler and not AMDuProfPcm?** uProf's counting tool `AMDuProfPcm` supports only
> EPYC server CPUs. Its CPU profiler (`AMDuProfCLI`, event-based sampling) supports Ryzen, and
> that is what the scripts use.

---

## Part B: get and build the project

### 4. Unpack the zip inside your MSYS2 home folder

Keep the project outside OneDrive-synced folders and away from paths with spaces.
```bash
cd ~
cp "$(cygpath -u "$USERPROFILE")/Downloads/cache-mem-profiling.zip" .
unzip -q cache-mem-profiling.zip
cd cache-mem-profiling
```
In File Explorer this folder is `C:\msys64\home\<your user name>\cache-mem-profiling`.

### 5. Build with G++ and run the correctness checks

```bash
make                       # builds bin/latency.exe bandwidth.exe loaded.exe kernels.exe sysinfo.exe
./bin/sysinfo --summary    # CPU, cores, caches, admin, large pages
./scripts/validate.sh      # must end with "validation passed"
```
`--summary` will say large pages are unavailable at this point; step 9 fixes that.

### 6. Write and commit your hypothesis before measuring

Edit section 2 of `report/REPORT.md` (any editor, e.g. VS Code: `code report/REPORT.md`), then:
```bash
git init -q
git config user.name "Brendan"; git config user.email "you@example.com"
git add -A && git commit -qm "pre-experiment hypothesis" && git log --oneline
```

---

## Part C: prepare Windows for measuring

### 7. Turn Memory integrity off (only while measuring)

uProf's CPU profiling is disabled while Hyper-V runs underneath Windows. Many Windows 11 PCs run
it for **Memory integrity** (virtualisation-based security).

1. **Windows Security → Device security → Core isolation details → Memory integrity: Off**, then
   reboot.
2. Turn it back on when you're finished (step 14). It is a security feature.

If the uProf probe in step 10 still complains about Hyper-V or virtualisation, disable the
hypervisor completely. Open **Command Prompt as administrator** and run
`bcdedit /set hypervisorlaunchtype off`, then reboot. WSL2, Docker and Hyper-V VMs stop working
until you undo it with `bcdedit /set hypervisorlaunchtype auto` and reboot.

### 8. Open the UCRT64 terminal as administrator

Start menu → type **MSYS2 UCRT64** → right-click → **Run as administrator**. Then
`cd ~/cache-mem-profiling`. Use an admin terminal for every remaining step.

### 9. Power settings and large pages

```bash
./scripts/setup_env.sh
```
This does two things:

- **Power settings:** turns processor boost off, holds the CPU at 100 % on AC power, and saves
  your old values so step 14 can restore them.
- **Large pages:** gives your account the **Lock pages in memory** right that 2 MB large pages
  need.

The first time, it ends with *"Sign out of Windows and back in"*. Do that, reopen the UCRT64
terminal as administrator (step 8), and run `./scripts/setup_env.sh` again. It should now say
**`large pages: OK`**.

Also set **Settings → System → Power & battery → Power mode → Best performance**, and keep the
charger plugged in.

### 10. Check that uProf counters work

```bash
./scripts/uprof_probe.sh
```
It profiles one kernel at unit stride and at page stride and prints a table. Good output looks
like this:

- `cycles/elem` is close to `expected_cycles/elem`.
- At stride 512, `l1d_miss/elem` and `dtlb_miss/elem` are much higher than at stride 1.
- `llc_ref` and `llc_miss` show NaN with the default event set. That's expected; see below.

| Probe says | Do this |
|---|---|
| Hyper-V / virtualisation / not supported | Step 7, including the `bcdedit` line, then reboot |
| access denied / driver | Use an admin terminal (step 8); reinstall uProf; reboot |
| a counter is `NaN` (not found) | Open `data/raw/uprof/available_events.txt` and add the event name to `analysis/uprof_events.csv` (one regex per line), or send both files to whoever is helping you |
| `cycles check ... SAMPLE counts` | uProf reported samples, not events. Ratios between configurations are still valid, but per-element numbers are scaled by 1/interval. Say so in the report, or send the probe output for a fix |
| `uProf captured NN% of the cycles` | Normal (multiplexing): counts are scaled up by that fraction. Below ~10 % the estimate gets noisy; close other programs and rerun |

---

## Part D: measure

### 11. Smoke test (about 20–30 minutes; uProf profiles each counted run twice)

```bash
QUICK=1 ./scripts/run_all.sh
```
Then open `data/processed/summary.md` (e.g. `code data/processed/summary.md`) and read
**section 0, Sanity checks**. QUICK mode uses small sizes, so "DRAM point well beyond LLC" may
FAIL here; that's fine. Anything else marked FAIL or WARN should be fixed first.

### 12. The real run (about 1.5–2 hours with uProf counters)

Before starting:

- Reboot first. Large pages need unfragmented memory, so a fresh boot helps.
- Close the browser, Teams, Discord and games.
- Pause OneDrive sync and Windows Update (Settings → Windows Update → Pause).
- Don't use the PC during the run.

Then run:
```bash
./scripts/run_all.sh
```
On a machine with 8 GB of RAM, use smaller buffers:
```bash
CHASE_DRAM=512M DRAM_SIZE=128M KERNEL_DRAM=384M ./scripts/run_all.sh
```

Optional settings (they are recorded in `data/raw/sysinfo.txt`):

- `CMP_PRIORITY=high`: runs the benchmarks at high process priority.
- `CPU=4`: picks a different measurement core. CPU numbers are logical processors as in Task
  Manager; on Ryzen, CPUs 0 and 1 are the two threads of core 0, 2 and 3 of core 1, and so on.
- On **X3D** CPUs with two CCDs, choose deliberately whether `CPU=` sits on the V-Cache CCD, and
  write that down.
- With a known memory speed, `PEAK_GBPS=<channels × MT/s × 8 / 1000>` enables the
  peak-bandwidth sanity check. For example, 2 channels of DDR5-6000 is 96.

If one experiment fails, rerun only that one: `./scripts/run_all.sh exp7`.

### 13. Look at the results

```bash
explorer.exe .               # opens the project folder in File Explorer
```
- **Figures:** `figures\fig1_latency_wss.png` … `fig10_pitfalls.png`.
- **Tables:** `data/processed/summary.md` (sanity checks, latency table, Little's Law, knees,
  counter regression, TLB, pitfalls).
- **Raw data:** `data/raw/*.csv` (one row per repetition) and `data/raw/sysinfo.txt` (the
  configuration you measured).

Commit everything:
```bash
git add -A && git commit -qm "measurement results"
```

### 14. Put Windows back

```bash
./scripts/restore_env.sh     # restores boost and processor-state settings
```

- Turn **Memory integrity** back on (step 7) and reboot.
- If you used `bcdedit`, run `bcdedit /set hypervisorlaunchtype auto` in an admin Command
  Prompt, then reboot.
- The "Lock pages in memory" right can stay. To remove it: `secpol.msc` → Local Policies → User
  Rights Assignment (Windows Pro), or ignore it on Home.

---

## Write the report

Fill sections 1 and 3–9 of `report/REPORT.md`. Each section names the figure and summary table
to use. For section 1, copy from `data/raw/sysinfo.txt`. Record the Windows-specific settings
too:

- power plan and boost state,
- Memory integrity / VBS state while measuring,
- whether large pages were active,
- the uProf version and event set.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `make: g++: No such file or directory` | You're not in the UCRT64 terminal, or step 2 is missing |
| `binaries missing in .../bin` | Run `make` in the project folder |
| `large pages unavailable: ... Lock pages in memory` | Step 9 (sign out and in after the first run), and use an admin terminal |
| `VirtualAlloc(MEM_LARGE_PAGES) failed ... (error 1450)` | Windows has run out of free 2 MB blocks of physical memory (fragmentation). Load generators and bandwidth buffers now fall back to 4 KB pages with a warning; a latency/kernel configuration that needs large pages is skipped and listed in `data/raw/failures.txt`, and the run continues. To get every point: reboot, close other programs, and re-run only the affected experiments (e.g. `./scripts/run_all.sh exp4 exp7`) |
| `warning: exit code N - this configuration is skipped` | One configuration failed (message just above it). The rest of the run continues; the summary's sanity checks show a FAIL listing `data/raw/failures.txt`. Re-run that experiment after fixing the cause |
| uProf counters NaN in every row | Run `./scripts/uprof_probe.sh` and follow its table (usually Memory integrity / Hyper-V) |
| Numbers jump around between repetitions | Background activity: check Task Manager, pause OneDrive/Windows Update, set Power mode to Best performance, use `CMP_PRIORITY=high` |
| `python: command not found` | Step 2 (UCRT64 Python packages) |
| A script stops with `$'\r': command not found` | The `.sh` file got Windows line endings from an editor. Run `sed -i 's/\r$//' scripts/*.sh` |
