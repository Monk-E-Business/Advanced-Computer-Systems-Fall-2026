#!/usr/bin/env bash
# Exp 4 - access intensity: throughput vs latency, the knee, Little's Law.
#  (a) single-core memory-level parallelism: K independent random chains over a
#      DRAM-sized buffer, K = 1..32  -> per-core outstanding-miss limit
#  (b) loaded latency: chase on $CPU while every other physical core streams
#      with injected delay (large -> 0), for each R/W mix -> system knee
# Outputs: data/raw/mlp.csv, data/raw/loaded.csv
source "$(dirname "$0")/lib.sh"
show_config
# PG (from lib.sh) = huge pages when available: keeps TLB misses out of the latency

new_csv "$RAW/mlp.csv" "$BIN/latency"
for k in 1 2 3 4 5 6 7 8 10 12 14 16 20 24 28 32; do
    run "$BIN/latency" --size "$CHASE_DRAM" --pattern rand --pages "$PG" --chains "$k" \
        --cpu "$CPU" --reps "$REPS" --ms "$MS" --label mlp
done

new_csv "$RAW/loaded.csv" "$BIN/loaded"
LREPS=$(( REPS < 3 ? REPS : 3 ))
# Only the chase buffer uses $PG; the generators' buffers use 4 KB pages (loaded's
# --gen-pages default): they just make traffic, and 5 x DRAM_SIZE of large pages
# would exhaust Windows' contiguous memory (VirtualAlloc error 1450).
# idle reference point (no generators)
run "$BIN/loaded" --chase-cpu "$CPU" --chase-size "$CHASE_DRAM" --pages "$PG" \
    --reps "$LREPS" --ms "$MS" --label idle
if [ "$NOTHERS" -gt 0 ]; then
    for mix in 100 70 50 0; do
        for d in 20000 10000 5000 2500 1200 600 300 150 80 40 20 10 5 0; do
            run "$BIN/loaded" --chase-cpu "$CPU" --chase-size "$CHASE_DRAM" --cpus "$OTHERS" \
                --gen-size "$DRAM_SIZE" --pattern seq --gran 64 --read-pct "$mix" --delay "$d" \
                --pages "$PG" --reps "$LREPS" --ms "$MS" --label "loaded_r$mix"
        done
    done
else
    log "only one core available: skipping loaded-latency sweep"
fi
log "exp4 done"
