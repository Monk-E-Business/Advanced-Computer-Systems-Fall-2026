#!/usr/bin/env bash
# Experiment 3 — read/write mix sweep: random $MIX_BS, total QD=$MIX_QD fixed,
# rwmixread in $MIX_READ_PCTS. All points use rw=randrw so the only knob that
# changes is the ratio. Reads that queue behind writes (program ~100s of us,
# erase ~ms) are what drive read tail latency up in mixed workloads.
source "$(dirname "$0")/common.sh"
load_config
safety_check
EXP=mix_sweep
for rep in $(seq 1 "$REPS"); do
  for pct in $MIX_READ_PCTS; do
    run_fio "$FIO_DIR/workload.fio" "$EXP" "r${pct}_${MIX_BS}" "$rep" \
      RW=randrw RWMIXREAD="$pct" BS="$MIX_BS" QD="$MIX_QD" NJ=1
  done
done
