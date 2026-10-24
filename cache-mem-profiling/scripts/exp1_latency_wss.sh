#!/usr/bin/env bash
# Exp 1 - zero-queue latency and working-set sweep (+ latency side of the
# pattern/stride sweep).
#   rand chase, 4 KB vs huge pages, 4 KB .. MAX_WSS   -> per-level latency, L1/L2/LLC/DRAM transitions
#   seq chase at strides 64/256/1024 B                 -> what prefetchers hide
# Output: data/raw/latency_wss.csv
source "$(dirname "$0")/lib.sh"
show_config
new_csv "$RAW/latency_wss.csv" "$BIN/latency"

for pages in $(page_modes); do
    for s in $(sizes 4K "$MAX_WSS"); do
        run "$BIN/latency" --size "$s" --pattern rand --pages "$pages" --cpu "$CPU" \
            --reps "$REPS" --ms "$MS" --label wss --perf
    done
done
for st in 64 256 1024; do
    for s in $(sizes 16K "$MAX_WSS"); do
        run "$BIN/latency" --size "$s" --pattern seq --stride "$st" --pages 4k --cpu "$CPU" \
            --reps "$REPS" --ms "$MS" --label "seq$st" --perf
    done
done
log "exp1 done"
