#!/usr/bin/env bash
# Build one bench_<variant> binary per g++ flag set, saving the vectorization report,
# the structured optimization record and the object file for each one.
#
#   bash scripts/build.sh                 (uses g++; override with CXX=/path/to/g++)
#
# Windows: run inside the "MSYS2 UCRT64" shell (pacman -S mingw-w64-ucrt-x86_64-gcc).
# Linux:   any g++ >= 11 (for -march=x86-64-v3).
# Output: build/<variant>/{bench[.exe],kernels.o,vec_report.txt,opt_record.json.gz},
#         build/variants.txt, build/compiler.txt
set -euo pipefail
cd "$(dirname "$0")/.."

CXX=${CXX:-g++}
if [ "${MSYSTEM:-}" = "MSYS" ]; then
  echo "error: this is the plain 'MSYS' shell. Open 'MSYS2 UCRT64' from the Start menu instead"
  echo "       (its g++ produces native Windows programs)."
  exit 1
fi
command -v "$CXX" >/dev/null || {
  echo "error: '$CXX' not found."
  echo "  MSYS2 UCRT64: pacman -S --needed mingw-w64-ucrt-x86_64-gcc"
  echo "  Ubuntu/WSL:   sudo apt install g++"
  exit 1; }
if "$CXX" --version | grep -qi clang; then
  echo "warning: $CXX looks like Clang; this project is set up for GNU g++ (flags/reports may differ)"
fi

# Windows target? Decided by what the compiler produces (MSYS2 UCRT64 g++ -> x86_64-w64-mingw32).
TARGET=$("$CXX" -dumpmachine)
WIN=0
case "$TARGET" in *mingw*|*windows*|*cygwin*) WIN=1;; esac
ARCH=${TARGET%%-*}

# ISA support as the compiler sees this CPU (no /proc/cpuinfo needed, so this works on Windows)
NATIVE_MACROS=$("$CXX" -march=native -dM -E -x c++ - </dev/null 2>/dev/null || true)
has() { grep -q "#define __$1__ 1" <<<"$NATIVE_MACROS"; }

COMMON="-std=c++17 -Wall -Wextra -g"
NOVEC="-fno-tree-vectorize -fno-tree-slp-vectorize"
QUIET="-Wno-unknown-pragmas"                        # scalar builds ignore '#pragma omp simd'
REPORT="-fopt-info-vec-optimized -fopt-info-vec-missed -fsave-optimization-record"
# Pin code placement: without this, where the linker happens to put a kernel (which changes whenever
# the harness changes size) moved scalar SAXPY by 1.6x on the reference machine (REPORT §11).
KALIGN="-falign-functions=64 -falign-loops=64"
EXTRA=""; LDEXTRA=""
if [ "$WIN" = 1 ]; then
  # GCC on 64-bit Windows can assume 32/64-byte stack alignment that the Windows ABI does not
  # guarantee (GCC PR54412), which can crash AVX code that spills vectors to the stack.
  # Binutils' -muse-unaligned-vector-move rewrites aligned vector moves as unaligned ones
  # (same speed on aligned data). -static: the .exe files run without MSYS2's DLLs on PATH.
  EXTRA="-Wa,-muse-unaligned-vector-move"
  LDEXTRA="-static"
fi
# Harness/reference/intrinsics: identical in every binary. No auto-vectorization, no FP contraction.
HARNESS="-O2 $NOVEC -ffp-contract=off"

# name|kernel flags
VARIANTS=()
if [ "$ARCH" = x86_64 ]; then
  VARIANTS+=("scalar|-O3 $NOVEC")                          # x86-64 baseline, vectorizers off
  VARIANTS+=("scalar_native|-O3 -march=native $NOVEC")     # same ISA as native (FMA etc.), vectorizers off
  VARIANTS+=("sse2|-O3 -fopenmp-simd")                     # compiler default target: 128-bit SSE2
  if has AVX2 && has FMA && has BMI2; then
    VARIANTS+=("avx2|-O3 -march=x86-64-v3 -fopenmp-simd")  # 256-bit AVX2 + FMA, generic tuning
  fi
  VARIANTS+=("native|-O3 -march=native -fopenmp-simd")     # whatever g++ picks for this CPU
  if has AVX512F; then
    VARIANTS+=("avx512|-O3 -march=native -mprefer-vector-width=512 -fopenmp-simd")  # force 512-bit
  fi
elif [ "$ARCH" = aarch64 ]; then
  VARIANTS+=("scalar|-O3 $NOVEC")
  VARIANTS+=("neon|-O3 -fopenmp-simd")
  VARIANTS+=("native|-O3 -mcpu=native -fopenmp-simd")
else
  VARIANTS+=("scalar|-O3 $NOVEC")
  VARIANTS+=("native|-O3 -march=native -fopenmp-simd")
fi

mkdir -p build
: > build/variants.txt
{ echo "CXX=$CXX"; "$CXX" --version | head -1; echo "family=gcc"; echo "target=$TARGET"; echo "arch=$ARCH"; echo "windows=$WIN";
  echo "msystem=${MSYSTEM:-none}"; echo "harness_flags=$HARNESS $EXTRA"; echo "kernel_common_flags=$COMMON $KALIGN"; echo "extra_flags=$EXTRA $LDEXTRA";
  echo "assembler=$("$CXX" -print-prog-name=as) $("$("$CXX" -print-prog-name=as)" --version 2>/dev/null | head -1)"; } > build/compiler.txt

for spec in "${VARIANTS[@]}"; do
  name=${spec%%|*}; kflags=${spec#*|}
  d=build/$name; mkdir -p "$d"
  echo "[build] $name: $kflags"
  # kernels: compile once with the vectorization report (stderr) and the structured JSON record
  rm -f "$d"/*.opt-record.json.gz
  if ! "$CXX" $COMMON $QUIET $EXTRA $KALIGN $kflags $REPORT -c src/kernels.cpp -o "$d/kernels.o" 2> "$d/vec_report.txt"; then
    cat "$d/vec_report.txt"; exit 1
  fi
  rec=$(ls "$d"/*.opt-record.json.gz 2>/dev/null | head -1 || true)
  [ -n "$rec" ] && mv "$rec" "$d/opt_record.json.gz"
  "$CXX" $COMMON $HARNESS $EXTRA -c src/manual.cpp -o "$d/manual.o"
  "$CXX" $COMMON $HARNESS $EXTRA "-DVARIANT_NAME=\"$name\"" "-DVARIANT_FLAGS=\"$kflags\"" -c src/main.cpp -o "$d/main.o"
  "$CXX" "$d/main.o" "$d/kernels.o" "$d/manual.o" $LDEXTRA -o "$d/bench"
  echo "$name|$kflags" >> build/variants.txt
done
echo "[build] done: $(cut -d'|' -f1 build/variants.txt | tr '\n' ' ')"
