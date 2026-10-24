#!/usr/bin/env bash
# Correctness validation (requirement 3). Exits non-zero if anything fails.
#  - every pointer chain is a single cycle covering every node exactly once
#  - bandwidth code paths reproduce closed-form checksums and exact R/W ratios
#  - kernels match a plain reference loop in every access order and page mode
#  - generic-loop ceiling: proves the mixed/strided loop is not the bottleneck
source "$(dirname "$0")/lib.sh"
OUTF="$RAW/validation.txt"
fails=0
check() { if "$@" >> "$OUTF" 2>&1; then :; else fails=$((fails + 1)); echo "FAILED: $*" >> "$OUTF"; fi; }
: > "$OUTF"
log "validation -> $OUTF"

check "$BIN/bandwidth" --check
for pat in rand seq page; do
    for s in 64K 8M; do check "$BIN/latency" --size "$s" --pattern "$pat" --check; done
done
for st in 256 1024; do check "$BIN/latency" --size 1M --pattern seq --stride "$st" --check; done
for k in 1 4 16 32; do check "$BIN/latency" --size 4M --chains "$k" --check; done
for pages in $(page_modes); do
    check "$BIN/latency" --size 8M --pages "$pages" --check
    for k in mul saxpy; do
        for o in "seq" "stride --stride 8" "stride --stride 512" "rand"; do
            # shellcheck disable=SC2086
            check "$BIN/kernels" --size 6M --kernel "$k" --order $o --pages "$pages" --check
        done
    done
done

# Huge pages actually granted? (Linux madvise is only a hint; Windows needs a privilege)
if [ "$HUGE_OK" = 1 ]; then
    hk="$("$BIN/latency" --size 64M --pages "$HUGE_MODE" --reps 1 --ms 5 --cpu "$CPU" | cut -d, -f16)"
    echo "$HUGE_MODE check: 64 MiB buffer backed by ${hk} kB of huge pages (expect ~65536)" >> "$OUTF"
    [ "${hk:-0}" -ge 60000 ] || { echo "FAILED: $HUGE_MODE buffer is not backed by huge pages" >> "$OUTF"; fails=$((fails + 1)); }
    hk4="$("$BIN/latency" --size 64M --pages 4k --reps 1 --ms 5 --cpu "$CPU" | cut -d, -f16)"
    echo "4K check:  64 MiB buffer backed by ${hk4} kB of huge pages (expect 0)" >> "$OUTF"
    [ "${hk4:-1}" = 0 ] || { echo "FAILED: 4k mode got huge pages" >> "$OUTF"; fails=$((fails + 1)); }
fi

# Ceiling of the generic (strided/mixed) loop in L2: if a DRAM result comes
# close to this number, the loop - not memory - is the limit.
for r in 100 70 50 0; do
    g="$("$BIN/bandwidth" --size 256K --threads 1 --cpus "$CPU" --reps 3 --ms 50 \
         --pattern stride --gran 64 --stride 64 --read-pct "$r" | cut -d, -f16 | sort -n | tail -1)"
    echo "generic-loop ceiling (L2-resident, 1 thread) read_pct=$r: $g GB/s" >> "$OUTF"
done

# Timer sanity: the monotonic clock (Linux CLOCK_MONOTONIC, Windows QueryPerformanceCounter,
# used by std::chrono::steady_clock) resolves far below the ~ms repetitions
"$PY" - >> "$OUTF" 2>&1 <<'PYEOF' || true
import time
i = time.get_clock_info("monotonic")
print("monotonic clock:", i.implementation, "resolution", i.resolution, "s")
PYEOF

cat "$OUTF" >&2
if [ "$fails" -gt 0 ]; then log "VALIDATION FAILED ($fails)"; exit 1; fi
log "validation passed"
