#!/usr/bin/env bash
# Exp 3 - read/write mix: 100% read, 100% write, 70/30, 50/50.
#   thread sweep 1..NT for each mix (sequential, 64 B granularity)
#   normal (write-allocate / RFO) stores vs non-temporal stores at NT threads
#   random 64 B accesses at NT threads for each mix
# Latency under each mix comes from exp4 (loaded latency per mix).
# Output: data/raw/bw_rwmix.csv
source "$(dirname "$0")/lib.sh"
show_config
new_csv "$RAW/bw_rwmix.csv" "$BIN/bandwidth"

for mix in 100 70 50 0; do
    for T in $(thread_counts); do
        run "$BIN/bandwidth" --size "$DRAM_SIZE" --threads "$T" --cpus "$(list_head "$CPUS" "$T")" \
            --pattern seq --gran 64 --read-pct "$mix" --reps "$REPS" --ms "$MS" --label rwmix
    done
    if [ "$mix" -lt 100 ]; then
        run "$BIN/bandwidth" --size "$DRAM_SIZE" --threads "$NT" --cpus "$CPUS" \
            --pattern seq --gran 64 --read-pct "$mix" --nt --reps "$REPS" --ms "$MS" --label rwmix_nt
    fi
    run "$BIN/bandwidth" --size "$DRAM_SIZE" --threads "$NT" --cpus "$CPUS" \
        --pattern rand --gran 64 --read-pct "$mix" --reps "$REPS" --ms "$MS" --label rwmix_rand
done
log "exp3 done"
