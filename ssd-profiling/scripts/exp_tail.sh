#!/usr/bin/env bash
# Experiment 5 — tail-latency characterisation at a mid queue depth and at the
# knee of the 4KiB random-read curve. Runs are TAIL_RUNTIME_MULT x longer and
# use fio's json+ output (full latency histogram), so the CCDF can be plotted
# down to p99.99 from >=1e5-1e6 samples rather than from a handful of
# percentiles. Also runs a 70/30 mix at the knee to show write interference.
# Knee QDs are taken from the QD sweep (analysis/knee.py) unless overridden.
source "$(dirname "$0")/common.sh"
load_config
safety_check
EXP=tail
# tr: native Windows Python ends lines with \r\n, and a stray \r breaks bash arithmetic
read -r auto_mid auto_knee auto_nj < <( { python3 "$REPO_ROOT/analysis/knee.py" "$RAW_DIR" 2>/dev/null || echo "8 32 1"; } | tr -d '\r')
MID="${TAIL_QD_MID:-$auto_mid}"; KNEE="${TAIL_QD_KNEE:-$auto_knee}"; NJ_T="${auto_nj:-1}"
log "tail experiment at QD_mid=$MID QD_knee=$KNEE (numjobs=$NJ_T)"
echo "mid=$MID knee=$KNEE nj=$NJ_T" > "$RAW_DIR/tail_qds.txt"
RT=$(( RUNTIME * TAIL_RUNTIME_MULT ))
for rep in $(seq 1 "$REPS"); do
  for pair in "base:1" "mid:$MID" "knee:$KNEE"; do
    role="${pair%%:*}"; qd="${pair##*:}"
    nj=$NJ_T; (( qd < nj )) && nj=1
    per=$(split_qd "$qd" "$nj")
    FIO_JSONPLUS=1 RUNTIME=$RT run_fio "$FIO_DIR/workload.fio" "$EXP" "randread_4k_${role}_qd${qd}" "$rep" \
      RW=randread BS=4k QD="$per" NJ="$nj" QD_TOTAL="$(( per * nj ))" ROLE="$role"
  done
  nj=$NJ_T; per=$(split_qd "$KNEE" "$nj")
  FIO_JSONPLUS=1 RUNTIME=$RT run_fio "$FIO_DIR/workload.fio" "$EXP" "randrw70_4k_qd${KNEE}" "$rep" \
    RW=randrw RWMIXREAD=70 BS=4k QD="$per" NJ="$nj" QD_TOTAL="$(( per * nj ))" ROLE=knee_mix70
done
