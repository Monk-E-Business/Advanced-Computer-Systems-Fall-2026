#!/usr/bin/env bash
# Experiment 6b — device state: burst vs steady state (run LAST; it leaves the
# drive heavily fragmented).
#   A) after an idle period (SLC cache flushed), sustained 128KiB sequential
#      write, logged per second  -> the SLC write-cache cliff
#   B) sustained 4KiB random write, logged per second -> FOB burst decaying to
#      GC-bound steady state (write amplification)
#   C) 4KiB random read immediately after B (GC still running) and again after
#      an idle period -> background GC interference with reads
# Drive temperature is sampled throughout (thermal throttling shows up as a
# throughput drop coinciding with a temperature plateau near the drive's
# warning composite temperature).
source "$(dirname "$0")/common.sh"
load_config
safety_check
EXP=steady_state
mkdir -p "$RAW_DIR/$EXP"
idle="${SS_IDLE_BEFORE_SEC:-300}"; post_idle="${SS_POST_IDLE_SEC:-120}"

start_temp_monitor "$RAW_DIR/$EXP/temperature.csv"
trap stop_temp_monitor EXIT
date +%s.%N > "$RAW_DIR/$EXP/t0_epoch"

log "idling ${idle}s so the drive can flush its SLC cache"
sleep "$idle"
run_fio "$FIO_DIR/timeseries.fio" "$EXP" seqwrite_128k_qd32 1 \
  RW=write BS=128k QD=32 NJ=1 RUNTIME="$SS_SEQWRITE_SECONDS" PHASE=A_slc_cliff

run_fio "$FIO_DIR/timeseries.fio" "$EXP" randwrite_4k_qd128 1 \
  RW=randwrite BS=4k QD=32 NJ=4 RUNTIME="$SS_RANDWRITE_SECONDS" PHASE=B_steady_state

run_fio "$FIO_DIR/workload.fio" "$EXP" randread_4k_qd32_postwrite 1 \
  RW=randread BS=4k QD=32 NJ=1 PHASE=C_read_during_gc
log "idling ${post_idle}s to let background GC drain"
sleep "$post_idle"
run_fio "$FIO_DIR/workload.fio" "$EXP" randread_4k_qd32_postidle 1 \
  RW=randread BS=4k QD=32 NJ=1 PHASE=C_read_after_idle

stop_temp_monitor
mkdir -p "$RAW_DIR/sysinfo"
if [[ $IS_WIN == 1 ]]; then
  [[ -n "${DISK_ID:-}" && "$DISK_ID" != -1 ]] && { ws info "$DISK_ID" > "$RAW_DIR/sysinfo/device_after.json" || true; }
elif [[ -n "${DISK_ID:-}" ]]; then
  { sudo -n smartctl -a "/dev/$DISK_ID" 2>&1 || smartctl -a "/dev/$DISK_ID" 2>&1 || true; } > "$RAW_DIR/sysinfo/smart_after.txt"
fi
