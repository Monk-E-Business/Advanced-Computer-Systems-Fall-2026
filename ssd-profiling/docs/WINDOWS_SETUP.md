# Running the project on Windows 11 with MSYS2 and g++

Everything runs natively on Windows:

| Piece | Comes from |
|---|---|
| bash, make, zip/unzip, git | MSYS2 (UCRT64 environment) |
| **g++** (builds `bin/ref_qd1.exe` and `bin/winstat.exe`) | MSYS2 package `mingw-w64-ucrt-x86_64-gcc` |
| Python + numpy/pandas/matplotlib/tabulate (analysis, plots) | MSYS2 UCRT64 packages |
| fio | official Windows installer (MSI) from fio's GitHub releases |

Allow about 45 minutes for setup, 5 minutes for the smoke test, and 4–5 hours
for the full run.

---

## 1. Install MSYS2 (~10 min)

1. Download the installer from <https://www.msys2.org> (`msys2-x86_64-….exe`)
   and install it to the default `C:\msys64`.
2. From the Start menu, open **"MSYS2 UCRT64"** (the icon with the yellow/brown
   background). **Always use this one.** The plain "MSYS2 MSYS" shell has a
   different g++ that doesn't build native Windows programs the way this
   project needs.
3. Update the package database:
   ```bash
   pacman -Syu
   ```
   If it asks to close the window, close it, reopen **MSYS2 UCRT64**, and run
   `pacman -Syu` again.
4. Install the tools:
   ```bash
   pacman -S --needed make zip unzip git \
     mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-python \
     mingw-w64-ucrt-x86_64-python-numpy mingw-w64-ucrt-x86_64-python-pandas \
     mingw-w64-ucrt-x86_64-python-matplotlib mingw-w64-ucrt-x86_64-python-tabulate
   ```
5. Check them:
   ```bash
   g++ --version && python3 -c "import numpy, pandas, matplotlib, tabulate; print('python ok')"
   ```

## 2. Install fio (~5 min)

1. Go to <https://github.com/axboe/fio/releases> and download the latest
   **`fio-<version>-x64.msi`** from the release's Assets.
2. Run it with the default options.
3. In the UCRT64 shell, check it. Windows programs aren't on MSYS2's PATH by
   default, so the scripts look for fio at this default location:
   ```bash
   "/c/Program Files/fio/fio.exe" --version
   ```
   If fio installed somewhere else, add that location to `config.local.env`
   in step 5, for example `FIO_BIN="C:/Tools/fio/fio.exe"`.

## 3. Make a dedicated test partition (~10 min, recommended)

Testing on its own partition keeps Windows' own I/O on C: out of the
measurements, which are taken from the test volume's counters.

1. **Back up anything important first.** Shrinking C: is a routine Windows
   operation, but it's still a disk operation.
2. Press **Win+X → Disk Management**, right-click **C:**, and choose
   **Shrink Volume**. Enter `81920` (MB) and click **Shrink**.
   * If Windows offers much less, run Disk Cleanup, run `powercfg /h off` in an
     admin PowerShell, and try again. You can also shrink less and use a
     smaller `TARGET_SIZE` (keep it ≥ 32 GB).
3. Right-click the new **Unallocated** space → **New Simple Volume** → use the
   full size. Assign a drive letter (the examples use **D:**; if D: is taken,
   use another and change `TARGET` to match). Choose **NTFS**, set the volume
   label to `SSDTEST`, and leave **Quick format** ticked.
4. Create the folder `D:\ssdtest` in File Explorer.
5. **Turn off indexing** for that drive: right-click **D:** → Properties →
   untick *"Allow files on this drive to have contents indexed…"* → Apply →
   *Apply changes to drive D:\ only*.
6. **Exclude it from Microsoft Defender**: open **Windows Security → Virus &
   threat protection → Manage settings → Exclusions → Add an exclusion → Folder**
   and pick `D:\ssdtest`. Defender otherwise scans the 64 GB test file when
   fio opens it.

*Testing a second, empty SSD instead?* See "Raw-disk target" at the end.

## 4. Prepare the machine for measuring

* Plug in the charger. Go to **Settings → System → Power & battery**, set
  **Power mode** to **Best performance**, and under *Screen, sleep &
  hibernate timeouts* set everything to **Never** while plugged in.
* Pause Windows Update for a week (**Settings → Windows Update → Pause**),
  and pause OneDrive sync.
* Close other apps for the full run.
* **Choose CPUs for fio.** Open **Task Manager → Performance → CPU** and note
  "Logical processors". Pick 4 that aren't CPU 0, e.g. `2-5`. On Intel 12th-gen
  and newer hybrid CPUs, Windows numbers the performance cores first, so low
  numbers like `2-5` are P-cores.

## 5. Unpack and configure the project

Open **MSYS2 UCRT64 with "Run as administrator"** (right-click the Start-menu
entry). It works without elevation too, but then the cold-cache part of one
demo is skipped.

```bash
cd ~
unzip /c/Users/YourName/Downloads/ssd-profiling.zip     # replace YourName
cd ssd-profiling

cat > config.local.env <<'EOF'
TARGET="D:/ssdtest/fio-scratch.bin"
TARGET_SIZE="64G"
FIO_CPUS="2-5"
EOF

make build
```
`make build` compiles the two g++ tools into `bin\`. `~` is
`C:\msys64\home\<you>`, so the project folder is visible in File Explorer
there.

**Recommended: lock in your hypotheses.** Read §2 of `docs/REPORT.md` and edit
the predictions so they're the ones you actually believe (VS Code or
`nano docs/REPORT.md`). Then commit:
```bash
git init -q && git add -A
git -c user.name="Brendan" -c user.email="you@example.com" commit -qm "Harness + pre-experiment hypotheses"
```

## 6. Run

```bash
make smoke
```
This takes about 5 minutes with tiny sizes; the numbers mean nothing. Then
check the results:
```bash
cat "data/processed/$(cat data/raw/CURRENT_RUN)/validation.md" | head -40
explorer.exe "plots\\$(cat data/raw/CURRENT_RUN)"
```
V1 should be PASS, and nearly everything else PASS or `expected-fail`.
Expected warnings: "same physical SSD as the OS" (fine with a separate
partition) and, if not elevated, "cannot purge the Windows file cache".

```bash
make all
```
This takes about 4–5 hours; leave the machine alone. The full log is in
`data/raw/<run>/run.log`.

**If it's interrupted**, resume the same run and skip the steps that
`run.log` shows as "== … done":
```bash
RESUME=1 SKIP="sysinfo prepare validate baseline" scripts/run_all.sh
```

**To abort:** Ctrl+C may not stop the native `fio.exe`. Close the UCRT64
window and end `fio.exe` in Task Manager.

## 7. Write the report

* Numbers: `docs/results_tables.md`. Figures: `plots/<run>/`. Checks:
  `data/processed/<run>/validation.md`. System facts:
  `data/raw/<run>/sysinfo/sysinfo.json`.
* Fill every `[[FILL …]]` in `docs/REPORT.md`.
* After changing plotting code, `make analyze` re-parses and re-plots from the
  raw JSON. It doesn't touch the SSD.

## 8. Clean up

1. Delete `D:\ssdtest\fio-scratch.bin` and its `.owned-by-ssd-profiling` marker.
2. Run **Defragment and Optimize Drives → D: → Optimize** to TRIM the freed
   blocks.
3. To give the space back: in **Disk Management**, right-click D: →
   **Delete Volume**, then right-click C: → **Extend Volume** → maximum.
   Remove the Defender exclusion.

---

## Raw-disk target (a second, empty SSD)

1. In Disk Management, delete every volume on that disk until it shows only
   "Unallocated". The scripts refuse any disk that still has partitions, and
   always refuse the disk Windows runs from.
2. Note its disk number (the "Disk 1" label in Disk Management).
3. Use an **Administrator** UCRT64 shell, and put this in `config.local.env`:
   ```bash
   TARGET='\\.\PhysicalDrive1'
   ALLOW_RAW_DEVICE=1
   WIPE_OK='\\.\PhysicalDrive1'
   TARGET_SIZE="200G"     # or empty for the whole disk
   ```
4. `make all` asks you to retype the target before writing anything.
   Misleading cases C/D need a file target, so they're skipped in this mode.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `fio not found` | Install the MSI (step 2) or set `FIO_BIN` |
| `bin/winstat.exe is missing` | Run `make build` in the **UCRT64** shell |
| `g++: command not found` | You're in the MSYS shell, not UCRT64; or step 1.4 didn't run |
| `$'\r': command not found` | A script got Windows line endings (edited in an old editor). Re-unzip, or `sed -i 's/\r$//' scripts/*.sh *.env` |
| `folder D:\ssdtest … does not exist` | Create it, or fix `TARGET` |
| `TARGET is on FAT32` | Use an NTFS volume (FAT32 can't hold files > 4 GiB) |
| `FIO_CPUS='…' is not valid` | Check "Logical processors" in Task Manager and edit `config.local.env` |
| Temperature shows `NA` | Some drivers don't report it; fine, just note it in the report |
| fio error mentioning the filename | Use forward slashes in `TARGET` (`D:/ssdtest/…`) |
