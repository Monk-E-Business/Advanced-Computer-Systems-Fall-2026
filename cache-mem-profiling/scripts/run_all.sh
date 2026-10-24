#!/usr/bin/env bash
# Full pipeline: build -> record system -> validate -> experiments -> process -> plot.
#
# Windows: run inside the "MSYS2 UCRT64" terminal (as administrator for large pages / uProf).
#   ./scripts/run_all.sh                 # everything (roughly 30-60 min on a desktop)
#   ./scripts/run_all.sh exp1 exp7       # only some experiments (then process + plot)
#   QUICK=1 ./scripts/run_all.sh         # ~5 min smoke test with small sizes
#   CPU=3 REPS=10 ./scripts/run_all.sh   # see scripts/lib.sh for every knob
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
make -s
S=scripts
"$S/sysinfo.sh"
"$S/validate.sh"

ALL=(exp1 exp2 exp3 exp4 exp5 exp6 exp7 exp8 mlc)
want=("$@"); [ ${#want[@]} -eq 0 ] && want=("${ALL[@]}")
# failures.txt lists configurations that failed and were skipped (see run() in lib.sh).
# A full run starts it afresh; a partial re-run drops the lines of the CSVs it rewrites.
mkdir -p data/raw
if [ $# -eq 0 ]; then rm -f data/raw/failures.txt; fi
for e in "${want[@]}"; do
    case "$e" in
        exp1) "$S/exp1_latency_wss.sh" ;;
        exp2) "$S/exp2_pattern.sh" ;;
        exp3) "$S/exp3_rwmix.sh" ;;
        exp4) "$S/exp4_intensity.sh" ;;
        exp5) "$S/exp5_wss_bw.sh" ;;
        exp6) "$S/exp6_cache_kernels.sh" ;;
        exp7) "$S/exp7_tlb.sh" ;;
        exp8) "$S/exp8_pitfalls.sh" ;;
        mlc)  "$S/exp_mlc.sh" ;;
        *) echo "unknown experiment $e"; exit 2 ;;
    esac
done
PY="${PY:-$(command -v python3 || command -v python)}"
export PYTHONUTF8=1   # Windows Python otherwise writes files in cp1252 (no Greek letters, e.g. Little's-law lambda)
echo "finished: $(date '+%Y-%m-%dT%H:%M:%S%z')" >> data/raw/sysinfo.txt
"$PY" analysis/process.py
"$PY" analysis/plot.py
echo "Done. Figures in figures/, tables in data/processed/summary.md"
