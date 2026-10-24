#!/usr/bin/env bash
# One command, whole pipeline:  build (g++) -> correctness tests -> vectorization verification
#   -> system info -> experiments -> processed data -> figures.
#
# Windows: run from the "MSYS2 UCRT64" shell (see docs/WINDOWS.md). Linux: any shell.
#
#   bash scripts/run_all.sh                 # full run (~45-60 min), results/<host>-<date>/
#   bash scripts/run_all.sh --quick         # coarse smoke run (~5 min)
#   bash scripts/run_all.sh --cpu 2 --max-ws 512M --tag my-laptop
set -euo pipefail
cd "$(dirname "$0")/.."

CPU_ARGS=(); TAG="$(hostname 2>/dev/null || echo run)-$(date +%Y%m%d-%H%M)"; EXTRA=()
while [ $# -gt 0 ]; do
  case "$1" in
    --cpu) CPU_ARGS=(--cpu "$2"); shift 2;;
    --tag) TAG=$2; shift 2;;
    --quick) EXTRA+=(--quick); shift;;
    --max-ws|--samples|--dram-samples|--min-time|--only|--rounds) EXTRA+=("$1" "$2"); shift 2;;
    *) echo "unknown option $1"; exit 2;;
  esac
done

export PYTHONUTF8=1                      # Windows: UTF-8 for all file I/O and console output
PY=${PYTHON:-}
if [ -z "$PY" ]; then
  for c in python3 python; do
    if command -v "$c" >/dev/null && "$c" -c "import sys; sys.exit(sys.version_info < (3, 8))" 2>/dev/null; then PY=$c; break; fi
  done
fi
if [ -z "$PY" ] || ! "$PY" -c "import numpy, pandas, matplotlib" 2>/dev/null; then
  echo "Python 3 with numpy, pandas and matplotlib is required."
  if [ -n "${MSYSTEM:-}" ]; then
    echo "  MSYS2 UCRT64:  pacman -S --needed mingw-w64-ucrt-x86_64-python mingw-w64-ucrt-x86_64-python-numpy \\"
    echo "                 mingw-w64-ucrt-x86_64-python-pandas mingw-w64-ucrt-x86_64-python-matplotlib mingw-w64-ucrt-x86_64-python-tabulate"
  else
    echo "  Ubuntu: sudo apt install -y python3-numpy python3-pandas python3-matplotlib python3-tabulate"
  fi
  exit 1
fi

OUT=results/$TAG
mkdir -p "$OUT/verification"
echo "== 1/7 build (g++)";  bash scripts/build.sh
echo "== 2/7 correctness";  bash scripts/test.sh "$OUT/verification/correctness.csv"
echo "== 3/7 verification"; "$PY" scripts/verify_vectorization.py "$OUT/verification"
echo "== 4/7 sysinfo";      "$PY" scripts/sysinfo.py "$OUT" "${CPU_ARGS[@]}"
echo "== 5/7 experiments (pinned; keep the machine idle and plugged in)"
"$PY" scripts/run_experiments.py --out "$OUT" "${CPU_ARGS[@]}" "${EXTRA[@]}" 2>&1 | tee "$OUT/run.log"
echo "== 6/7 analyze";      "$PY" scripts/analyze.py "$OUT"
echo "== 7/7 plot";         "$PY" scripts/plot.py "$OUT"
cp build/compiler.txt build/variants.txt "$OUT/verification/"
echo
echo "Done. Results: $OUT   (summary: $OUT/summary.md, figures: $OUT/figures/)"
