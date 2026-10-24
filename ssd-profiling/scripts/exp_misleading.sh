#!/usr/bin/env bash
# Experiment 7 — misleading setups (negative / failure cases). Each pairs a
# "wrong" configuration with the correct one, and keeps the evidence that
# exposes it (device I/O counters, Little's Law).
#   A) Buffered I/O (direct=0) on a working set that fits in RAM: the OS file
#      cache serves reads and absorbs writes -> "IOPS" far above the device's
#      capability and microsecond latency; the device counters show ~0 bytes.
#   B) Wrong effective queue depth:
#      B1 a synchronous engine ignores iodepth=32: only one I/O is ever in
#         flight (Little's Law: IOPS x mean latency ~= 1, not 32). On Windows
#         the sync engines can't do unbuffered I/O, so B1 runs buffered over
#         the full span (mostly cache misses).
#      B2 the async engine at iodepth=32: L ~= 32 (correct).
#      B3 iodepth=32 with numjobs=4 *reported* as "QD32": the device really had
#         128 outstanding (L ~= 128).
#   C) Reading never-written blocks: a file region that was allocated but never
#      written (Windows: end-of-file set past the valid data length; Linux:
#      fallocated extents; raw Linux disk: discarded LBAs) returns zeros
#      WITHOUT device reads -> inflated read IOPS. This is why preconditioning
#      writes the whole span before any read test.
#   D) (Windows/NTFS) Random writes into such a file: NTFS zero-fills from the
#      valid data length up to each write offset before the write completes ->
#      device writes many times larger than fio's, and huge latency outliers.
# Run after the other experiments.
source "$(dirname "$0")/common.sh"
load_config
safety_check
EXP=misleading
WS="${MISLEAD_WS:-1G}"
WSB="$(to_bytes "$WS")"
memb=$(awk '/MemTotal/{print $2*1024}' /proc/meminfo)
(( WSB * 2 < memb )) || die "MISLEAD_WS=$WS must be < half of RAM for the page-cache demo"
(( WSB <= TARGET_BYTES )) || die "MISLEAD_WS=$WS is larger than the target span"
SYNC_DIRECT_OPT=$SYNC_DIRECT

for rep in $(seq 1 "$REPS"); do
  # ---- A) OS file cache -----------------------------------------------------
  drop_caches
  run_fio "$FIO_DIR/workload.fio" "$EXP" A_buffered_read_cold "$rep" \
    IOENGINE="$SYNC_ENGINE" DIRECT=0 RW=randread BS=4k QD=1 SIZE="$WSB" CASE=A VARIANT=buffered_cold \
    CACHE_PURGED="$CACHE_PURGED"
  run_fio "$FIO_DIR/workload.fio" "$EXP" A_buffered_read_warm "$rep" \
    IOENGINE="$SYNC_ENGINE" DIRECT=0 RW=randread BS=4k QD=1 SIZE="$WSB" CASE=A VARIANT=buffered_warm
  run_fio "$FIO_DIR/workload.fio" "$EXP" A_direct_read "$rep" \
    DIRECT=1 RW=randread BS=4k QD=1 SIZE="$WSB" CASE=A VARIANT=direct
  run_fio "$FIO_DIR/workload.fio" "$EXP" A_buffered_write "$rep" \
    IOENGINE="$SYNC_ENGINE" DIRECT=0 RW=randwrite BS=4k QD=1 SIZE="$WSB" CASE=A VARIANT=buffered_write
  sync
  run_fio "$FIO_DIR/workload.fio" "$EXP" A_direct_write "$rep" \
    DIRECT=1 RW=randwrite BS=4k QD=1 SIZE="$WSB" CASE=A VARIANT=direct_write

  # ---- B) wrong effective queue depth ---------------------------------------
  drop_caches
  run_fio "$FIO_DIR/workload.fio" "$EXP" B1_sync_iodepth32 "$rep" \
    IOENGINE="$SYNC_ENGINE" DIRECT="$SYNC_DIRECT_OPT" RW=randread BS=4k QD=32 CASE=B \
    VARIANT="${SYNC_ENGINE}_iodepth32" QD_TOTAL=32
  run_fio "$FIO_DIR/workload.fio" "$EXP" B2_async_iodepth32 "$rep" \
    RW=randread BS=4k QD=32 CASE=B VARIANT="${IOENGINE}_iodepth32" QD_TOTAL=32
  run_fio "$FIO_DIR/workload.fio" "$EXP" B3_async_iodepth32_nj4 "$rep" \
    RW=randread BS=4k QD=32 NJ=4 CASE=B VARIANT="iodepth32_x4jobs_reported_as_32" QD_TOTAL=32
done

# ---- C/D) never-written regions ----------------------------------------------
if [[ "$TARGET_KIND" == file ]]; then
  UNW="$(dirname "$TARGET_POSIX")/fio-scratch-unwritten.bin"
  if [[ -e "$UNW" && ! -e "$UNW.owned-by-ssd-profiling" ]]; then die "$UNW exists and is not ours"; fi
  touch "$UNW.owned-by-ssd-profiling"
  make_unwritten() {
    rm -f "$UNW"
    if [[ $IS_WIN == 1 ]]; then ws mkunwritten "$(winpath "$UNW")" "$WSB" >/dev/null
    else fallocate -l "$WSB" "$UNW" || die "fallocate not supported on this filesystem"; fi
  }
  for rep in $(seq 1 "$REPS"); do
    make_unwritten
    run_fio "$FIO_DIR/workload.fio" "$EXP" C_unwritten_read "$rep" \
      FILE_OVERRIDE="$(winpath "$UNW")" RW=randread BS=4k QD=32 SIZE="$WSB" CASE=C VARIANT=unwritten
    run_fio "$FIO_DIR/workload.fio" "$EXP" C_written_read "$rep" \
      RW=randread BS=4k QD=32 SIZE="$WSB" CASE=C VARIANT=written
    if [[ $IS_WIN == 1 ]]; then
      make_unwritten
      run_fio "$FIO_DIR/burst.fio" "$EXP" D_unwritten_write "$rep" \
        FILE_OVERRIDE="$(winpath "$UNW")" RW=randwrite BS=4k QD=1 SIZE="$WSB" IOSIZE=$((16 * 1048576)) \
        RUNTIME=0 RAMP=0 CASE=D VARIANT=unwritten
      run_fio "$FIO_DIR/burst.fio" "$EXP" D_written_write "$rep" \
        RW=randwrite BS=4k QD=1 SIZE="$WSB" IOSIZE=$((16 * 1048576)) RUNTIME=0 RAMP=0 CASE=D VARIANT=written
    fi
  done
  rm -f "$UNW" "$UNW.owned-by-ssd-profiling"
elif [[ $IS_WIN == 0 ]]; then
  off=$(( TARGET_BYTES - WSB ))
  log "discarding last $WS of the span on $TARGET (offset $off) for case C"
  if blkdiscard -o "$off" -l "$WSB" "$TARGET" 2>/dev/null || sudo -n blkdiscard -o "$off" -l "$WSB" "$TARGET"; then
    for rep in $(seq 1 "$REPS"); do
      run_fio "$FIO_DIR/workload.fio" "$EXP" C_unwritten_read "$rep" \
        RW=randread BS=4k QD=32 SIZE="$WSB" OFFSET="$off" CASE=C VARIANT=discarded_lbas
      run_fio "$FIO_DIR/workload.fio" "$EXP" C_written_read "$rep" \
        RW=randread BS=4k QD=32 SIZE="$WSB" OFFSET=0 CASE=C VARIANT=written
    done
  else
    warn "blkdiscard failed; skipping case C"
  fi
else
  log "raw-disk target on Windows: cases C/D need a file target; skipped"
fi
