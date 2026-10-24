#!/usr/bin/env bash
# Exp 2 - DRAM bandwidth vs access pattern and granularity.
#   seq                                    (full-line streaming)
#   stride: 8 B touched every 64..4096 B   (useful bytes vs. lines moved)
#   rand:   8 B .. 4 KB contiguous chunks  (granularity of random access)
# at 1 thread (latency/concurrency-bound) and NT threads (DRAM-bound).
# Output: data/raw/bw_pattern.csv
source "$(dirname "$0")/lib.sh"
show_config
new_csv "$RAW/bw_pattern.csv" "$BIN/bandwidth"

for T in 1 "$NT"; do
    cpus="$(list_head "$CPUS" "$T")"
    common=(--size "$DRAM_SIZE" --threads "$T" --cpus "$cpus" --reps "$REPS" --ms "$MS" --pages 4k)
    run "$BIN/bandwidth" "${common[@]}" --pattern seq --gran 64 --label pattern
    for st in 64 128 256 512 1024 2048 4096; do
        run "$BIN/bandwidth" "${common[@]}" --pattern stride --gran 8 --stride "$st" --label pattern
    done
    for g in 8 64 128 256 1024 4096; do
        run "$BIN/bandwidth" "${common[@]}" --pattern rand --gran "$g" --label pattern
    done
    [ "$T" = "$NT" ] && [ "$NT" = 1 ] && break
done
log "exp2 done"
