#!/usr/bin/env bash
# Experiment 4 — queue-depth / parallelism sweep -> throughput-vs-latency curve.
# For each series rw:bs:nj in $QD_SWEEP_SERIES and each TOTAL queue depth in
# $QD_LIST, iodepth = ceil(QD/nj). Points where QD < nj are skipped (would
# need fractional iodepth). Little's Law check later: QD_eff ~= IOPS * mean_lat.
source "$(dirname "$0")/common.sh"
load_config
safety_check
EXP=qd_sweep
for rep in $(seq 1 "$REPS"); do
  for s in $QD_SWEEP_SERIES; do
    IFS=: read -r rw bs nj <<< "$s"
    for qd in $QD_LIST; do
      (( qd >= nj )) || continue
      per=$(split_qd "$qd" "$nj")
      off=0; size="$TARGET_BYTES"
      if [[ "$rw" == read || "$rw" == write ]] && (( nj > 1 )); then
        # disjoint stripes so each job is a genuine sequential stream
        size=$(( TARGET_BYTES / nj / 1048576 * 1048576 )); off="$size"
      fi
      run_fio "$FIO_DIR/workload.fio" "$EXP" "${rw}_${bs}_nj${nj}_qd${qd}" "$rep" \
        RW="$rw" BS="$bs" QD="$per" NJ="$nj" SIZE="$size" OFFINC="$off" QD_TOTAL="$(( per * nj ))" SERIES="$s"
    done
  done
done
