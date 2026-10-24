#!/usr/bin/env bash
# Create (file mode) and precondition the test span.
#   1) PRECOND_SEQ_LOOPS full sequential 128KiB fills  -> every LBA mapped, and
#      (Windows/NTFS) the file's valid data length reaches its end, so later
#      random writes never trigger NTFS zero-fill
#   2) PRECOND_RAND_MULT x span of random 4KiB writes  -> fragmented FTL, GC active
# Usage: prepare_target.sh [seq|rand|all]   (default all)
source "$(dirname "$0")/common.sh"
load_config
safety_check
phase="${1:-all}"

check_no_stray_fio
# A file smaller than the span is left over from an interrupted run (it is
# ours: safety_check verified the marker). Remove it so fio can lay it out again.
if [[ "$TARGET_KIND" == file && -e "$TARGET_POSIX" ]] && (( $(stat -c %s "$TARGET_POSIX") < TARGET_BYTES )); then
  log "removing incomplete $TARGET from an earlier, interrupted run"
  rm -f "$TARGET_POSIX" 2>/dev/null || die "cannot delete $TARGET: another program has it open. \
Usually a leftover fio.exe (Task Manager > Details > fio.exe > End task) or Microsoft Defender \
scanning it (add a Defender folder exclusion for $(dirname "$TARGET_WIN")). Then run make again."
fi
if [[ "$TARGET_KIND" == file && ! -e "$TARGET_POSIX" ]]; then
  log "creating $TARGET ($TARGET_SIZE); the sequential fill writes all of it"
  touch "$TARGET_POSIX.owned-by-ssd-profiling"
  # Windows: fio creates the file itself; never pre-extend it with
  # SetEndOfFile/truncate (see misleading case D).
  # Linux: fallocate reserves extents (unwritten until the fill below).
  if [[ $IS_WIN == 0 ]]; then
    fallocate -l "$TARGET_BYTES" "$TARGET_POSIX" 2>/dev/null || true
  fi
fi

loops="${PRECOND_SEQ_LOOPS:-2}"; mult="${PRECOND_RAND_MULT:-1}"
[[ "${QUICK:-0}" == 1 ]] && { loops=1; mult=0.25; }
iosize=$(python3 -c "print(int($TARGET_BYTES*$mult)//4096*4096)" | tr -d '\r')

if [[ "$phase" == seq || "$phase" == all ]]; then
  log "sequential fill x$loops of $TARGET_BYTES bytes"
  FIO_EXTRA_ARGS="--section=seqfill" run_fio "$FIO_DIR/precondition.fio" precondition seqfill 1 \
    LOOPS="$loops" IOSIZE="$iosize" RW=write BS=128k QD=32
fi
if [[ "$phase" == rand || "$phase" == all ]]; then
  if (( iosize > 0 )); then
    log "random 4k fill: $iosize bytes"
    FIO_EXTRA_ARGS="--section=randfill" run_fio "$FIO_DIR/precondition.fio" precondition randfill 1 \
      LOOPS=1 IOSIZE="$iosize" RW=randwrite BS=4k QD=32
  fi
fi
date -Is > "$RAW_DIR/precondition/DONE"
log "preconditioning complete"
