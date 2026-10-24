#!/usr/bin/env bash
# Exp 5 - bandwidth vs working-set size (complements the latency sweep):
#   1 thread  seq read / seq write, 8 KB .. MAX_WSS
#   NT threads seq read with the per-thread size swept (aggregate = NT x size)
# Output: data/raw/bw_wss.csv
source "$(dirname "$0")/lib.sh"
show_config
new_csv "$RAW/bw_wss.csv" "$BIN/bandwidth"

for s in $(sizes 8K "$MAX_WSS"); do
    run "$BIN/bandwidth" --size "$s" --threads 1 --cpus "$CPU" --pattern seq --read-pct 100 \
        --pages "$PG" --reps "$REPS" --ms "$MS" --label wss_read_1t
    run "$BIN/bandwidth" --size "$s" --threads 1 --cpus "$CPU" --pattern seq --read-pct 0 \
        --pages "$PG" --reps "$REPS" --ms "$MS" --label wss_write_1t
done
if [ "$NT" -gt 1 ]; then
    max_per=$(( $(to_bytes "$MAX_WSS") / NT ))
    for s in $(sizes 8K "$max_per"); do
        run "$BIN/bandwidth" --size "$s" --threads "$NT" --cpus "$CPUS" --pattern seq --read-pct 100 \
            --pages "$PG" --reps "$REPS" --ms "$MS" --label wss_read_all
    done
fi
log "exp5 done"
