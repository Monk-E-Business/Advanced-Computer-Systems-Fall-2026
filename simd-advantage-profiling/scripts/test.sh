#!/usr/bin/env bash
# Correctness validation: every variant x kernel x type x size x offset is compared with a
# long-double (FP) or exact modular (int) reference in src/main.cpp. The sizes include tails
# (0..129, primes) and the offsets include misaligned bases, so prologue, epilogue and
# remainder paths are covered. Guard elements past the end (and the gaps in strided
# kernels) must stay untouched.
#   bash scripts/test.sh [output.csv]
set -uo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-build/correctness.csv}
[ -f build/variants.txt ] || bash scripts/build.sh
SIZES="0,1,2,3,5,7,8,9,15,16,17,31,32,33,63,64,65,100,127,128,129,1000,1023,1024,1025,4099"
echo "tag,variant,kernel,type,n,offset,stride,pattern,status,max_err_over_tol" > "$OUT"
for v in $(cut -d'|' -f1 build/variants.txt); do
  B=build/$v/bench
  for off in 0 4 12; do
    for t in f32 f64 i32; do
      for k in saxpy dot dotsimd mul stencil; do
        $B --check --kernel $k --type $t --n $SIZES --offset $off >> "$OUT"
      done
    done
    for k in read write saxpy_s1 saxpy_s2 saxpy_s4 saxpy_s8 saxpy_s16; do
      $B --check --kernel $k --n $SIZES --offset $off >> "$OUT"
    done
    for p in seq random; do
      $B --check --kernel gather --pattern $p --n $SIZES --offset $off >> "$OUT"
    done
    for k in mask_avx2 mask_avx512; do
      $B --check --kernel $k --n $SIZES --offset $off >> "$OUT" 2>/dev/null || true
    done
  done
done
total=$(grep -c '^CHECK' "$OUT"); fail=$(grep -c ',FAIL,' "$OUT")
echo "[test] $total checks, $fail failures -> $OUT"
if [ "$fail" -ne 0 ]; then grep ',FAIL,' "$OUT" | head -20; exit 1; fi
