#!/usr/bin/env bash
# Exp 6 - cache-miss impact on simple kernels (z = x*y and y = a*x + y).
#  (a) footprint sweep, unit stride       -> runtime/element vs L1/LLC misses/element
#  (b) fixed DRAM footprint, same work, worse locality: element stride
#      1, 2, 4, 8 (=64 B), 16, 64, 512 (=4 KB) and random order
# Counters: Linux - perf_event_open inside the binary around the timed loop only;
# Windows + AMD - AMD uProf with the differential method (run_counted in lib.sh).
# Output: data/raw/kernels.csv
source "$(dirname "$0")/lib.sh"
show_config
new_csv "$RAW/kernels.csv" "$BIN/kernels"

for k in mul saxpy; do
    for s in $(sizes 12K "$MAX_WSS"); do
        run_counted "$BIN/kernels" --kernel "$k" --size "$s" --order seq --pages 4k --cpu "$CPU" \
            --reps "$REPS" --ms "$MS" --perf --label footprint
    done
    for st in 1 2 4 8 16 64 512; do
        run_counted "$BIN/kernels" --kernel "$k" --size "$KERNEL_DRAM" --order stride --stride "$st" --pages 4k \
            --cpu "$CPU" --reps "$REPS" --ms "$MS" --perf --label locality
    done
    run_counted "$BIN/kernels" --kernel "$k" --size "$KERNEL_DRAM" --order rand --pages 4k --cpu "$CPU" \
        --reps "$REPS" --ms "$MS" --perf --label locality
done
log "exp6 done"
