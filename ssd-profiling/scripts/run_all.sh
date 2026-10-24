#!/usr/bin/env bash
# Full pipeline. Starts a new run directory data/raw/run_<timestamp>/ unless
# RESUME=1 (then continues CURRENT_RUN). Order matters:
#   prepare (fill + random precondition) -> validate -> read/write experiments
#   -> misleading demos -> steady state (most destructive to device state) -> analysis
# Skip steps with SKIP="steady misleading" etc.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
[[ "${RESUME:-0}" == 1 ]] || rm -f "$REPO/data/raw/CURRENT_RUN"
source "$HERE/common.sh"
load_config
safety_check            # confirm once; exported state is inherited by children
check_no_stray_fio
# Elevated rights unlock: the cold-cache demo (purging the OS file cache),
# raw-disk targets, and on Linux SMART queries.
if [[ $IS_WIN == 1 ]]; then
  if is_admin; then log "running elevated (Administrator)"
  else warn "not elevated: the cold-cache part of the misleading-setup demo will be partly warm. For the full run, start MSYS2 UCRT64 with 'Run as administrator'."; fi
elif [[ $EUID -ne 0 ]] && command -v sudo >/dev/null; then
  log "asking for sudo once (page-cache drop, SMART)"
  if sudo -v; then
    ( while kill -0 $$ 2>/dev/null; do sudo -n true 2>/dev/null; sleep 50; done ) &
  else
    warn "no sudo: page-cache drop and SMART queries will be skipped"
  fi
fi
cp "$REPO/config.env" "$RAW_DIR/config.env.used"
[[ -f "$REPO/config.local.env" ]] && cp "$REPO/config.local.env" "$RAW_DIR/config.local.env.used"
(cd "$REPO" && git rev-parse HEAD 2>/dev/null || echo "not a git checkout") > "$RAW_DIR/git_commit.txt"
exec > >(tee -a "$RAW_DIR/run.log") 2>&1
log "run $RUN_ID  QUICK=${QUICK:-0}  target=$TARGET"

skip() { [[ " ${SKIP:-} " == *" $1 "* ]]; }
step() { local name="$1" script="$2"; if skip "$name"; then log "== skip $name"; return; fi
         log "== $name"; local t=$SECONDS; "$HERE/$script"; log "== $name done in $((SECONDS-t))s"; }

step sysinfo    collect_sysinfo.sh
step prepare    prepare_target.sh
step validate   validate.sh
step baseline   exp_baseline.sh
step bs         exp_bs_sweep.sh
step mix        exp_mix_sweep.sh
step qd         exp_qd_sweep.sh
step peak       exp_peak.sh
step tail       exp_tail.sh
step ws         exp_working_set.sh
step misleading exp_misleading.sh
step steady     exp_steady_state.sh

if ! skip analyze; then
  log "== analysis"
  python3 "$REPO/analysis/parse_fio.py" --run "$RUN_ID"
  python3 "$REPO/analysis/validate.py" --run "$RUN_ID"
  python3 "$REPO/analysis/plot.py" --run "$RUN_ID"
fi
log "finished $RUN_ID"
