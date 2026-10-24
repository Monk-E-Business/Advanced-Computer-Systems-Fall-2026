# Running this project on Windows 11 with MSYS2 + g++

Everything runs **natively on Windows**. MSYS2's UCRT64 environment provides g++ (MinGW-w64 GCC),
binutils (`objdump`), bash and a native Windows Python. The benchmark binaries are ordinary
`bench.exe` programs. They pin themselves to one core with the Windows API and use
`QueryPerformanceCounter` for timing. No WSL or virtual machine is involved.

## 1. Install MSYS2 (one time)

1. Download the installer from <https://www.msys2.org> and install it to the default `C:\msys64`.
2. From the Start menu open **"MSYS2 UCRT64"**. The prompt shows `UCRT64` in purple. Don't use the
   plain "MSYS2 MSYS" shell: its compiler doesn't produce native Windows programs, and the build script
   refuses to run there.
3. Update the package database (the window may close itself; if so, reopen **MSYS2 UCRT64** and run it again):

   ```bash
   pacman -Syu
   ```

## 2. Install g++, Python and tools

In the **MSYS2 UCRT64** shell:

```bash
pacman -S --needed mingw-w64-ucrt-x86_64-gcc \
  mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-python-numpy \
  mingw-w64-ucrt-x86_64-python-pandas mingw-w64-ucrt-x86_64-python-matplotlib \
  mingw-w64-ucrt-x86_64-python-tabulate unzip git
g++ --version        # GCC 13 or newer; mingw-w64-ucrt-x86_64-gcc pulls in binutils (objdump, as)
python -c "import numpy, pandas, matplotlib; print('python ok')"
```

## 3. Unzip the project

Put it somewhere **without spaces** in the path. Your MSYS2 home folder (`C:\msys64\home\<you>`) is a
good choice:

```bash
cd ~
cp /c/Users/<YourWindowsName>/Downloads/simd-advantage-profiling.zip .
unzip simd-advantage-profiling.zip
cd simd-advantage-profiling
git log --oneline    # the hypothesis commits come before every results commit
```

`ls /c/Users` lists the Windows user folder names. In MSYS2, `C:\` is `/c/`.

## 4. (Optional) Make the hypothesis yours

`docs/HYPOTHESIS.md` was committed before any measurement. Its g++ addendum predicts behaviour for the
reference machine. To make predictions for *your* CPU, edit the file and commit it **before** you run:

```bash
nano docs/HYPOTHESIS.md      # or: notepad docs/HYPOTHESIS.md (save as UTF-8)
git add docs/HYPOTHESIS.md && git commit -m "Hypothesis for my machine (pre-measurement)"
```

## 5. Prepare Windows for measuring

1. **Plug in the charger** (laptops). The scripts record whether you are on AC power.
2. Settings → System → Power & battery → **Power mode: Best performance**. The active power plan is recorded.
3. Close browsers, chat apps, games, etc. Pause OneDrive and don't let Windows Update run.
4. Don't use the PC while the run is going.
5. Optional: add the project folder to Windows Security's exclusions (Virus & threat protection → Manage
   settings → Exclusions). Real-time scanning of the many short `bench.exe` launches adds startup delay
   (not timing noise), which makes the run slower.

The harness pins itself to one logical CPU (`SetThreadAffinityMask`) and raises its priority class to
HIGH while measuring. On **hybrid Intel CPUs** (12th gen and later: P-cores + E-cores), `sysinfo.py` asks
Windows which logical CPUs belong to the highest-performance core class and pins to one of those
automatically. The choice is printed and recorded in `sysinfo.json`.

## 6. Run

Smoke test first (about 5 minutes):

```bash
bash scripts/run_all.sh --quick --tag smoke
```

This builds six variants with g++ (`scalar`, `scalar_native`, `sse2`, `avx2`, `native`, and `avx512` if
your CPU has AVX-512), runs ~12,000 correctness checks, verifies vectorization from g++'s report and the
disassembly, records system info, runs every experiment on a coarse grid, and writes processed data and
figures to `results/smoke/`.

Then the real run (about 45–60 minutes; every experiment is repeated in 3 rounds):

```bash
bash scripts/run_all.sh --tag my-pc
```

| option | meaning |
|---|---|
| `--cpu N` | logical CPU to pin to (default: chosen by sysinfo, a performance core on hybrid CPUs) |
| `--max-ws 512M` | largest working set (default 1G; it needs about 1.2 GB of free RAM) |
| `--rounds 5` | more independent rounds (slower, more robust medians) |
| `--quick` | coarse grid, 1 round |

## 7. Look at the results

* Every key number: `results/my-pc/summary.md`
* Figures: `results/my-pc/figures/*.png`. Open the folder in Explorer with
  `explorer.exe "$(cygpath -w results/my-pc/figures)"`
  (or browse to `C:\msys64\home\<you>\simd-advantage-profiling\results\my-pc\figures`).
* Vectorization evidence: `results/my-pc/verification/vectorization_summary.md` and `hot_loops.md`
* Environment record: `results/my-pc/sysinfo.json` (CPU, cores/threads, hybrid, caches, power plan, AC power,
  g++ version and flags, timer)

## 7b. Notes for AMD Ryzen CPUs

What your results will look like depends on the Zen generation. `sysinfo.json` (and Task Manager → CPU) shows the model.

| CPU | AVX-512? | what to expect |
|---|---|---|
| Ryzen 1000–5000 (Zen 1–3) | no | no `avx512` build. `native` = AVX2 (`-march=znver1..3`); compare `sse2` → `avx2`/`native` |
| Ryzen 7000 / 8000 (Zen 4) | yes | `avx512` is built, but Zen 4 runs 512-bit operations as two 256-bit halves, so peak FLOP/s (`bench --peak`) is about the same for AVX2 and AVX-512. Any AVX-512 advantage comes from fewer instructions, masking, etc., not from doubled arithmetic width |
| Ryzen 9000 (Zen 5) desktop | yes | full 512-bit datapaths: the AVX-512 peak should be about 2× AVX2. Mobile Zen 5 parts (Ryzen AI 300) use 256-bit datapaths like Zen 4 |

Other AMD specifics:

* **SMT** (two threads per core) is normally on. The harness pins to the first thread of a core, but the
  sibling thread can still run other work. Close background apps, or disable SMT in the BIOS for the cleanest
  numbers, and record which you did.
* **L3 is per CCD/CCX.** On multi-CCD parts (Ryzen 9) one core only sees its own CCD's L3 (e.g. 32 MiB), not
  the total on the box. The analysis measures the effective LLC knee from the bandwidth curve, so the plots
  are right either way. Quote the per-CCD size in the write-up.
* **X3D parts** (extra V-Cache): the LLC knee moves out to ~96 MiB on the V-Cache CCD. Use `--max-ws 2G` so
  the DRAM points are really in DRAM.
* **Counters**: AMD uProf (free) can sample `build/<variant>/bench.exe` if you want instruction/cache-miss
  counts. The scripts don't need it.
* **Frequency**: Ryzen boosts aggressively and drops under all-core load or heat. Stay on AC power with the
  *Best performance* power mode. The measured clock is recorded in every run.

## 8. Update the report

`REPORT.md` interprets the **reference run** (`results/cloud-vm-xeon-clx-gpp/`, measured with g++ on a
Linux cloud VM with an AVX-512 Xeon). For your submission, point its figure links at your run folder and
update the numbers from your `summary.md`. Keep the explanations where your CPU behaves the same and
change them where it doesn't. Typical differences: most Intel laptop/desktop CPUs from 12th gen on have no
AVX-512 (so no `avx512` build); AMD Zen 4/5 do have it; and the cache sizes differ.

## 9. Put it on GitHub

Create an **empty** repository on github.com (no README or license). Then, in the UCRT64 shell:

```bash
git config user.name  "Your Name"
git config user.email "you@example.com"
git add -A && git commit -m "Results from my PC"
git remote add origin https://github.com/<you>/simd-advantage-profiling.git
git push -u origin main
```

GitHub doesn't accept account passwords for `git push`. When asked for a password, paste a personal
access token (github.com → Settings → Developer settings → Personal access tokens). Alternatively, push
from GitHub Desktop or VS Code, which handle sign-in for you.

## Troubleshooting

| symptom | fix |
|---|---|
| `error: this is the plain 'MSYS' shell` | Open **MSYS2 UCRT64** from the Start menu instead. |
| `g++: command not found` | You are not in the UCRT64 shell, or step 2 was skipped. |
| `Python 3 with numpy, pandas and matplotlib is required` | Run the `pacman -S` line in step 2. A Python installed from python.org is ignored; use MSYS2's. |
| `$'\r': command not found` | A script got Windows line endings (edited in an old editor, or extracted by a tool that converts them). Run `pacman -S dos2unix && dos2unix scripts/*.sh`, or re-unzip with `unzip` as in step 3. |
| No `avx512` variant | Your CPU has no AVX-512. That's expected on most recent Intel client CPUs: `native` is then your widest build. |
| A `bench.exe` crashes with an access violation in AVX code | Make sure binutils is current (`pacman -Syu`). The build passes `-Wa,-muse-unaligned-vector-move` to work around GCC's Windows stack-alignment bug (PR54412); it needs binutils ≥ 2.38. |
| Very wide error bars / bimodal timings | Close background apps, stay on AC power and Best performance, and re-run. On a hybrid CPU, check which CPU was pinned (`sysinfo.json` → `pinned_cpu`, `top_class_cpus`). |
| `perf` step says SKIPPED | Expected on Windows. Vectorization is verified from g++'s report and the disassembly. Intel VTune or AMD uProf can read hardware counters for `build/<variant>/bench.exe` if you want them. |
| Out of memory at large sizes | Use `--max-ws 512M`. |
| Windows on ARM (Snapdragon) | MSYS2 has no native g++ for ARM64. This project needs an x86-64 PC (or WSL/Linux with g++). |
