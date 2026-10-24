#!/usr/bin/env bash
# Experiment 2 — block-size sweep at fixed QD=$BS_SWEEP_QD, numjobs=1.
# Throughput AND latency come from the same runs, so the plot shows both
# sides of the tradeoff: bigger blocks amortise per-command overhead (higher
# MB/s) but each command takes longer (higher latency) and IOPS fall.
source "$(dirname "$0")/common.sh"
load_config
safety_check
EXP=bs_sweep
for rep in $(seq 1 "$REPS"); do
  for rw in randread randwrite read write; do
    list="$BS_LIST"
    [[ "$rw" == read || "$rw" == write ]] && list="$BS_LIST ${BS_SEQ_EXTRA:-}"
    for bs in $list; do
      run_fio "$FIO_DIR/workload.fio" "$EXP" "${rw}_${bs}" "$rep" \
        RW="$rw" BS="$bs" QD="$BS_SWEEP_QD" NJ=1
    done
  done
done
