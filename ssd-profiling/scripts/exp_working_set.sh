#!/usr/bin/env bash
# Experiment 6a — working-set / LBA-range sweep for 4KiB random reads.
# Restricting the touched LBA span changes (a) the fraction of the FTL mapping
# table that must be resident in controller DRAM / host memory buffer (DRAM-less
# drives degrade on large spans), and (b) for writes, how concentrated GC is.
# All spans were fully written during preconditioning (no unmapped LBAs).
source "$(dirname "$0")/common.sh"
load_config
safety_check
EXP=working_set
for rep in $(seq 1 "$REPS"); do
  for ws in $WS_LIST; do
    if [[ "$ws" == FULL ]]; then bytes="$TARGET_BYTES"; else bytes="$(to_bytes "$ws")"; fi
    (( bytes <= TARGET_BYTES )) || { log "skip ws=$ws (> span)"; continue; }
    for qd in $WS_QDS; do
      run_fio "$FIO_DIR/workload.fio" "$EXP" "randread_4k_ws${ws}_qd${qd}" "$rep" \
        RW=randread BS=4k QD="$qd" NJ=1 SIZE="$bytes" WS_BYTES="$bytes" WS_LABEL="$ws"
    done
  done
done
