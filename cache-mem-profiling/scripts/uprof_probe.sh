#!/usr/bin/env bash
# Check AMD uProf counter collection BEFORE the long run (Windows + AMD Ryzen).
#   ./scripts/uprof_probe.sh
# 1. records uProf's version, predefined configs and PMU events,
# 2. runs one kernel at unit stride and at page stride under uProf (differential method),
# 3. prints which uProf event feeds each counter column, the per-element values, and
#    a cycles cross-check that tells whether uProf reports event counts or sample counts.
# Diagnoses the usual blocker: uProf's CPU profiling (EBP) is disabled while Hyper-V
# runs underneath Windows (Memory integrity / virtualisation-based security).
( cd "$(dirname "$0")/.." && make -s ) || { echo "build failed: run make"; exit 1; }   # binaries need --meta
source "$(dirname "$0")/lib.sh"
[ "$COUNTERS" = uprof ] || die "uProf not in use (COUNTERS=$COUNTERS). Install AMD uProf, or set UPROF_CLI=/c/path/to/AMDuProfCLI.exe"
D="$RAW/uprof"; mkdir -p "$D"
rm -f "$D/available_events.txt"
# Run AMDuProfCLI with no keyboard input (a hidden prompt would otherwise wait forever)
# and a time limit; its output goes to a file whose first lines are then shown.
cli_to() {  # cli_to FILE SECONDS ARGS...
    local f="$1" t="$2" rc=0; shift 2
    MSYS2_ARG_CONV_EXCL='*' timeout "$t" "$UPROF_CLI" "$@" < /dev/null > "$f" 2>&1 || rc=$?
    sed -i 's/\r$//' "$f" 2>/dev/null || true
    if [ "$rc" = 124 ]; then
        log "  !! 'AMDuProfCLI $*' did not finish within ${t}s and was stopped. Its output so far:"
        head -15 "$f" | sed 's/^/     | /' >&2
        log "     If it shows a question (licence, driver, ...), run AMDuProfCLI once by hand to answer it:"
        log "       \"$UPROF_CLI\" $*"
    fi
    return 0
}
log "AMDuProfCLI: $UPROF_CLI   admin: $("$BIN/sysinfo" --is-admin | tr -d '\r')"
log "step 1/3: uProf version and event lists (each limited to ${UPROF_INFO_TIMEOUT:-90}s)"
cli_to "$D/version.txt" 60 --version; head -3 "$D/version.txt"
cli_to "$D/collect_configs.txt" "${UPROF_INFO_TIMEOUT:-90}" info --list collect-configs
log "  predefined configs -> $D/collect_configs.txt ($(wc -l < "$D/collect_configs.txt") lines). First lines:"
head -6 "$D/collect_configs.txt" | sed 's/^/     | /' >&2
cli_to "$D/pmu_events.txt" "${UPROF_INFO_TIMEOUT:-90}" info --list pmu-events
log "  PMU events -> $D/pmu_events.txt ($(wc -l < "$D/pmu_events.txt") lines)"
log "step 2/3: profiling one kernel at stride 1 and stride 512, event sets $UPROF_SETS (~1-4 min)"

OUT="$D/probe.csv"
"$BIN/kernels" --header-only | tr -d '\r' > "$OUT"
for st in 1 512; do
    run_counted "$BIN/kernels" --kernel mul --size 256M --order stride --stride "$st" --cpu "$CPU" --reps 2 --ms 300 --label probe
done
if grep -qiE "hyper-?v|virtuali[sz]ation|not supported|unsupported|access denied|driver" "$D"/probe_*.log 2>/dev/null; then
    echo
    echo ">>> uProf reported a problem (see $D/probe_*.log):"
    grep -hiE "hyper-?v|virtuali[sz]ation|not supported|unsupported|access denied|driver" "$D"/probe_*.log | sort -u | head -5
    echo ">>> If it mentions Hyper-V/virtualisation: Windows Security > Device security > Core isolation >"
    echo "    Memory integrity = Off, reboot, rerun this probe. Still blocked? In an admin Command Prompt:"
    echo "    bcdedit /set hypervisorlaunchtype off, reboot (undo later: bcdedit /set hypervisorlaunchtype auto)."
fi
echo
log "step 3/3: results"
"$PY" - "$OUT" <<'EOF'
import sys, pandas as pd
d = pd.read_csv(sys.argv[1])
d["elems"] = d.passes * d.n
cols = ["cycles", "instructions", "l1d_miss", "llc_ref", "llc_miss", "dtlb_ref", "dtlb_miss"]
for c in cols:
    d[c + "/elem"] = pd.to_numeric(d[c], errors="coerce") / d.elems
d["expected_cycles/elem"] = d.ns_per_elem * d.ghz
print(d.groupby("stride")[["ns_per_elem", "expected_cycles/elem"] + [c + "/elem" for c in cols]].mean().T.to_string())
print("\nWhat good looks like:")
print(" * cycles/elem close to expected_cycles/elem (otherwise uProf gave SAMPLE counts - see WINDOWS_SETUP.md)")
print(" * stride 512 has far more l1d_miss/elem and dtlb_miss/elem than stride 1")
print(" * NaN = event not found: compare available_events.txt with analysis/uprof_events.csv")
print(" * the 'uprof counters' lines above say what fraction uProf captured; counts are scaled up by it")
EOF
echo "Event names seen: $D/available_events.txt"
