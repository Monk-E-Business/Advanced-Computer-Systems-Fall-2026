#!/usr/bin/env bash
# Correctness validation, run BEFORE trusting any performance number:
#  1) data-path integrity: fio crc32c write+verify over VERIFY_SIZE bytes
#  2) independent reference: bin/ref_qd1 (g++; one unbuffered read/write at a
#     time) vs fio at QD=1 for the four baseline cases. fio is run with the
#     async engine ($IOENGINE) and, on Linux, also the synchronous psync engine
#     (Windows' synchronous engines cannot do unbuffered I/O, so they are skipped)
#  3) dd unbuffered sequential read as a second independent bandwidth reference
#     (best effort; skipped if dd cannot open the target unbuffered)
# analysis/validate.py turns these + Little's Law + device byte accounting +
# interface-ceiling checks into a PASS/FAIL table.
source "$(dirname "$0")/common.sh"
load_config
safety_check
EXP=validation
OUT="$RAW_DIR/$EXP"; mkdir -p "$OUT"

VSIZE="${VERIFY_SIZE:-256M}"; [[ "${QUICK:-0}" == 1 ]] && VSIZE=16M
log "1) integrity: crc32c write+verify over $VSIZE"
run_fio "$FIO_DIR/verify.fio" "$EXP" verify_crc32c 1 SIZE="$(to_bytes "$VSIZE")"
log "   verify passed (fio exits non-zero on any mismatch with verify_fatal=1)"

variants=("$IOENGINE")
(( SYNC_DIRECT == 1 )) && variants+=("$SYNC_ENGINE")
cases=("randread:4k" "randwrite:4k" "read:128k" "write:128k")
for rep in $(seq 1 "$REPS"); do
  for c in "${cases[@]}"; do
    rw="${c%%:*}"; bs="${c##*:}"; bsb="$(to_bytes "$bs")"
    log "2) reference ref_qd1 $rw $bs rep$rep"
    "$REF_QD1" "$TARGET_WIN" "$rw" "$bsb" "$TARGET_BYTES" "$RUNTIME" 0 "$(first_cpu)" \
      | tr -d '\r' > "$OUT/ref_${rw}_${bs}_rep${rep}.json"
    for eng in "${variants[@]}"; do
      run_fio "$FIO_DIR/workload.fio" "$EXP" "fio_${eng}_${rw}_${bs}" "$rep" \
        IOENGINE="$eng" RW="$rw" BS="$bs" QD=1 NJ=1 VARIANT="$eng"
    done
  done
done

if [[ -n "$TARGET_POSIX" ]]; then
  log "3) dd unbuffered sequential read reference (128KiB, QD1)"
  cnt=$(( RUNTIME * 2000 )); maxcnt=$(( TARGET_BYTES / 131072 )); (( cnt > maxcnt )) && cnt=$maxcnt
  if dd if="$TARGET_POSIX" of=/dev/null bs=128k count="$cnt" iflag=direct 2> "$OUT/dd_read_128k.txt"; then
    cat "$OUT/dd_read_128k.txt" >&2
  else
    warn "dd could not read the target unbuffered here; check V3 is skipped"
    rm -f "$OUT/dd_read_128k.txt"
  fi
fi
