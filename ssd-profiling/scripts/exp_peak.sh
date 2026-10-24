#!/usr/bin/env bash
# Experiment 4b — peak capability: maximum small-block IOPS (4KiB random,
# several submitting threads, deep total queue) and maximum large-block
# sequential throughput (1MiB). Compared against the interface ceiling.
source "$(dirname "$0")/common.sh"
load_config
safety_check
EXP=peak
NJ_P="${PEAK_NJ:-4}"
for rep in $(seq 1 "$REPS"); do
  run_fio "$FIO_DIR/workload.fio" "$EXP" randread_4k_peak "$rep" \
    RW=randread BS=4k QD=64 NJ="$NJ_P" QD_TOTAL=$(( 64 * NJ_P ))
  run_fio "$FIO_DIR/workload.fio" "$EXP" randwrite_4k_peak "$rep" \
    RW=randwrite BS=4k QD=32 NJ="$NJ_P" QD_TOTAL=$(( 32 * NJ_P ))
  run_fio "$FIO_DIR/workload.fio" "$EXP" read_1m_peak "$rep" \
    RW=read BS=1m QD=16 NJ=2 SIZE=$(( TARGET_BYTES / 2 / 1048576 * 1048576 )) \
    OFFINC=$(( TARGET_BYTES / 2 / 1048576 * 1048576 )) QD_TOTAL=32
  run_fio "$FIO_DIR/workload.fio" "$EXP" write_1m_peak "$rep" \
    RW=write BS=1m QD=16 NJ=2 SIZE=$(( TARGET_BYTES / 2 / 1048576 * 1048576 )) \
    OFFINC=$(( TARGET_BYTES / 2 / 1048576 * 1048576 )) QD_TOTAL=32
done
