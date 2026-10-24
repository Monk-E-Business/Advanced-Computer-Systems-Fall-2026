#!/usr/bin/env bash
# Experiment 1 — zero-queue baselines (QD=1, numjobs=1):
#   4KiB random read / random write, 128KiB sequential read / sequential write.
# At QD=1 there is never more than one command outstanding, so latency is pure
# service time (host stack + PCIe + controller + NAND/cache), with no queueing.
source "$(dirname "$0")/common.sh"
load_config
safety_check
EXP=baseline_qd1
cases=("randread:4k" "randwrite:4k" "read:128k" "write:128k")
for rep in $(seq 1 "$REPS"); do           # reps outermost: drift spreads over all points
  for c in "${cases[@]}"; do
    rw="${c%%:*}"; bs="${c##*:}"
    run_fio "$FIO_DIR/workload.fio" "$EXP" "${rw}_${bs}" "$rep" RW="$rw" BS="$bs" QD=1 NJ=1
  done
done
