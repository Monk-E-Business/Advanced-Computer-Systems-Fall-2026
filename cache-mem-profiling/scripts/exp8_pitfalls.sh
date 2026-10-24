#!/usr/bin/env bash
# Exp 8 - benchmark pitfalls / failure cases (requirement 5 + "show one pitfall").
# Each pair is "naive" vs "correct" with identical code otherwise.
#  P1 cache reuse:  "DRAM bandwidth" with a buffer that fits in the LLC
#  P2 zero page:    reading never-written memory (all pages map to one zero page)
#     first touch:  first repetition of a write test includes page faults
#  P3 prefetching:  sequential pointer chase reported as "DRAM latency"
#  P4 pinning:      unpinned threads (bandwidth) and an unpinned chaser that can
#                   share a core with a generator; SMT sibling interference
#  P5 frequency:    cold short runs converted with nominal GHz vs warmed + calibrated
# Outputs: data/raw/pitfall_bw.csv, pitfall_lat.csv, pitfall_loaded.csv
source "$(dirname "$0")/lib.sh"
show_config
L3=$(awk -F, '$1 == 3 { print $3 }' "$RAW/caches.csv" 2>/dev/null | head -1)
L3=${L3:-$(to_bytes 8M)}
SMALL=$(( L3 / (2 * NT) ))                     # NT buffers together fill half the LLC
[ "$SMALL" -lt 65536 ] && SMALL=65536
PREPS=$(( REPS * 2 ))

new_csv "$RAW/pitfall_bw.csv" "$BIN/bandwidth"
# P1
run "$BIN/bandwidth" --size "$SMALL" --threads "$NT" --cpus "$CPUS" --reps "$REPS" --ms "$MS" --label P1_llc_resident
run "$BIN/bandwidth" --size "$DRAM_SIZE" --threads "$NT" --cpus "$CPUS" --reps "$REPS" --ms "$MS" --label P1_dram_sized
# P2
run "$BIN/bandwidth" --size "$DRAM_SIZE" --threads "$NT" --cpus "$CPUS" --reps "$REPS" --ms "$MS" --no-init --label P2_read_uninitialized
run "$BIN/bandwidth" --size "$DRAM_SIZE" --threads "$NT" --cpus "$CPUS" --reps "$REPS" --ms "$MS" --label P2_read_initialized
run "$BIN/bandwidth" --size "$DRAM_SIZE" --threads 1 --cpus "$CPU" --read-pct 0 --reps "$REPS" --ms "$MS" --no-init --label P2_write_first_touch
run "$BIN/bandwidth" --size "$DRAM_SIZE" --threads 1 --cpus "$CPU" --read-pct 0 --reps "$REPS" --ms "$MS" --label P2_write_prefaulted
# P4 (bandwidth): unpinned threads, including oversubscription onto SMT siblings
ALL_LOGICAL=$(nproc)
run "$BIN/bandwidth" --size "$DRAM_SIZE" --threads "$NT" --cpus "$CPUS" --reps "$PREPS" --ms "$MS" --label P4_pinned
run "$BIN/bandwidth" --size "$DRAM_SIZE" --threads "$NT" --cpus none --reps "$PREPS" --ms "$MS" --label P4_unpinned

new_csv "$RAW/pitfall_lat.csv" "$BIN/latency"
# P3
run "$BIN/latency" --size "$CHASE_DRAM" --pattern seq --stride 64 --cpu "$CPU" --reps "$REPS" --ms "$MS" --label P3_sequential_chase
run "$BIN/latency" --size "$CHASE_DRAM" --pattern rand --cpu "$CPU" --reps "$REPS" --ms "$MS" --label P3_random_chase
# P5: idle first so the core clocks down, then a short cold run with the
# nominal clock for cycle conversion, versus the normal warmed+calibrated run.
NOM=$(grep '^nominal_ghz=' "$RAW/sysinfo.env" 2>/dev/null | cut -d= -f2)
NOM=${NOM:-2.0}
sleep 3
run "$BIN/latency" --size 16K --pattern rand --cpu "$CPU" --reps 20 --ms 2 --ghz "$NOM" --perf --label P5_cold_nominal_ghz
run "$BIN/latency" --size 16K --pattern rand --cpu "$CPU" --reps 20 --ms "$MS" --perf --label P5_warm_calibrated

new_csv "$RAW/pitfall_loaded.csv" "$BIN/loaded"
if [ "$NOTHERS" -gt 0 ]; then
    run "$BIN/loaded" --chase-cpu "$CPU" --chase-size "$CHASE_DRAM" --cpus "$OTHERS" --gen-size "$DRAM_SIZE" --pages "$PG" \
        --reps "$PREPS" --ms "$MS" --label P4_loaded_pinned
    run "$BIN/loaded" --chase-cpu -1 --chase-size "$CHASE_DRAM" --cpus none --gens "$ALL_LOGICAL" --gen-size "$DRAM_SIZE" --pages "$PG" \
        --reps "$PREPS" --ms "$MS" --label P4_loaded_unpinned_oversubscribed
fi
SIB="$(smt_sibling "$CPU")"
if [ -n "$SIB" ]; then
    OTHER1="$(echo "$OTHERS" | cut -d, -f1)"
    # same traffic, generator on the SMT sibling vs on a different physical core
    run "$BIN/loaded" --chase-cpu "$CPU" --chase-size "$CHASE_DRAM" --cpus "$SIB" --gen-size "$DRAM_SIZE" --pages "$PG" \
        --reps "$PREPS" --ms "$MS" --label P4_smt_sibling_generator
    [ -n "$OTHER1" ] && run "$BIN/loaded" --chase-cpu "$CPU" --chase-size "$CHASE_DRAM" --cpus "$OTHER1" \
        --gen-size "$DRAM_SIZE" --pages "$PG" --reps "$PREPS" --ms "$MS" --label P4_other_core_generator
else
    log "SMT off or no sibling for CPU $CPU: skipping SMT-sibling pitfall"
fi
log "exp8 done"
