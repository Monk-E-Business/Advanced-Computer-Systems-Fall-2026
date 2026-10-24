#!/usr/bin/env bash
# Optional: Intel Memory Latency Checker cross-check (Intel CPUs, Linux).
# Download from intel.com ("Intel Memory Latency Checker"), put `mlc` on PATH
# or set MLC=/path/to/mlc. Many modes need root (it toggles prefetchers via MSRs).
# Raw text goes to data/raw/mlc/; process.py parses idle and loaded latency.
#
# Note on R/W mixes: MLC's built-in ratios are 3:1, 2:1 and 1:1 (and
# non-temporal variants) - there is no exact 70/30. bin/bandwidth --read-pct 70
# provides the exact mix; use MLC 2:1 (67/33) and 3:1 (75/25) to bracket it.
source "$(dirname "$0")/lib.sh"
MLC="${MLC:-$(command -v mlc || true)}"
[ -n "$MLC" ] && [ -x "$MLC" ] || { log "MLC not found: skipping (optional)"; exit 0; }
D="$RAW/mlc"; mkdir -p "$D"
SUDO=""; [ "$(id -u)" != 0 ] && command -v sudo >/dev/null && SUDO="sudo -n"
m() { local name="$1"; shift; log "mlc $*"; $SUDO "$MLC" "$@" > "$D/$name.txt" 2>&1 || log "mlc $* failed (see $D/$name.txt)"; }

"$MLC" --version > "$D/version.txt" 2>&1 || true
m idle_latency    --idle_latency -c"$CPU"
m latency_matrix  --latency_matrix
m max_bandwidth   --max_bandwidth
m loaded_latency  --loaded_latency
m bandwidth_matrix --bandwidth_matrix
log "MLC output in $D"
