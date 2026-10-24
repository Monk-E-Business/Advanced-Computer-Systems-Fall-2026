#!/usr/bin/env bash
# Shared configuration and helpers, sourced by every experiment script.
# Runs in the MSYS2 UCRT64 terminal on Windows and in bash on Linux.
#
# Everything is overridable from the environment, e.g.
#   CPU=4 REPS=10 MAX_WSS=2G ./scripts/exp1_latency_wss.sh
#   QUICK=1 ./scripts/run_all.sh          # fast smoke run (small sizes, few reps)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="${BIN:-$ROOT/bin}"
RAW="${RAW:-$ROOT/data/raw}"
mkdir -p "$RAW"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

# --- operating system ------------------------------------------------------------
# CMP_OS=windows|linux overrides detection (used to test the Windows code path).
if [ -z "${CMP_OS:-}" ]; then
    case "$(uname -s)" in
        MINGW*|MSYS*|UCRT64*|CLANG64*|CLANGARM64*|CYGWIN*) CMP_OS=windows ;;
        *) CMP_OS=linux ;;
    esac
fi
is_windows() { [ "$CMP_OS" = windows ]; }

[ -x "$BIN/latency" ] || [ -x "$BIN/latency.exe" ] || die "binaries missing in $BIN: run 'make' first"

PY="${PY:-$(command -v python3 || command -v python || true)}"
export PYTHONUTF8=1   # UTF-8 file I/O for Python on Windows

# Windows path for arguments handed to native Windows tools (AMD uProf).
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else echo "$1"; fi; }
# PowerShell one-liners (Windows only), with \r stripped from the output.
# Never fails (a missing/locked-down PowerShell must not abort a run under set -e).
pwsh() { { MSYS2_ARG_CONV_EXCL='*' powershell.exe -NoProfile -NonInteractive -Command "$1" 2>/dev/null || true; } | tr -d '\r'; }
# AC value (hex, e.g. 0x00000000) of a powercfg processor setting, or empty. Never fails.
powercfg_ac() {
    { MSYS2_ARG_CONV_EXCL='*' powercfg.exe -qh SCHEME_CURRENT SUB_PROCESSOR "$1" 2>/dev/null || true; } | tr -d '\r' |
        { grep -i 'Current AC Power Setting Index' || true; } | { grep -oiE '0x[0-9a-f]+' || true; } | head -1
}

# "64K" / "1.5M" / "1G" / plain bytes -> bytes
to_bytes() {
    awk -v s="$1" 'BEGIN{
        n = s + 0; u = toupper(substr(s, length(s), 1));
        if (u == "K") n *= 1024; else if (u == "M") n *= 1048576; else if (u == "G") n *= 1073741824;
        printf "%d\n", n }'
}

# --- topology (from bin/sysinfo; MSYS2 has no lscpu or /sys) -----------------------
# CSV rows: cpu,core,package,node,eff_class
TOPO="$("$BIN/sysinfo" --topology | tr -d '\r' | tail -n +2)"
MAXEFF="$(echo "$TOPO" | awk -F, 'BEGIN{m=0} $5 > m {m = $5} END{print m}')"

# One logical CPU per physical core on NUMA node $1 (any node if empty). By
# default only the fastest core type (P-cores on hybrid CPUs); ALL_CORE_TYPES=1
# includes every core type.
phys_cpus() {
    local node="${1:-}" eff="$MAXEFF"
    [ "${ALL_CORE_TYPES:-0}" = 1 ] && eff=""
    echo "$TOPO" | awk -F, -v want="$node" -v eff="$eff" \
        '(want == "" || $4 == want) && (eff == "" || $5 == eff) && !seen[$3 "," $2]++ { print $1 }' |
        sort -n | paste -sd, -
}
node_of_cpu() { echo "$TOPO" | awk -F, -v c="$1" '$1 == c { print $4; exit }'; }
smt_sibling() {  # another hardware thread of $1's core, or nothing
    echo "$TOPO" | awk -F, -v c="$1" '$1 == c { core = $2; pkg = $3 } { r[NR] = $0 }
        END { for (i in r) { split(r[i], f, ","); if (f[2] == core && f[3] == pkg && f[1] != c) { print f[1]; exit } } }'
}

# grep exits 1 on empty output; under `set -euo pipefail` that would kill the
# caller, so these helpers always succeed.
count_list() { echo "$1" | tr ',' '\n' | grep -c . || true; }
list_without() { { echo "$1" | tr ',' '\n' | grep -vx "$2" || true; } | paste -sd, - ; }
list_head() { echo "$1" | tr ',' '\n' | head -n "$2" | paste -sd, - ; }

# --- defaults ----------------------------------------------------------------------
QUICK="${QUICK:-0}"
_ALL_PHYS="$(phys_cpus)"
# Measurement core: second physical core (CPU 0 typically services more interrupts).
if [ -z "${CPU:-}" ]; then
    CPU="$(echo "$_ALL_PHYS" | tr ',' '\n' | sed -n 2p)"
    CPU="${CPU:-0}"
fi
NODE="$(node_of_cpu "$CPU")"; NODE="${NODE:-0}"
CPUS="${CPUS:-$(phys_cpus "$NODE")}"      # bandwidth threads: physical cores, local node
NT="$(count_list "$CPUS")"
OTHERS="$(list_without "$CPUS" "$CPU")"   # load generators for loaded-latency runs
NOTHERS="$( [ -n "$OTHERS" ] && count_list "$OTHERS" || echo 0)"

if [ "$QUICK" = 1 ]; then
    REPS="${REPS:-2}"; MS="${MS:-40}"
    MAX_WSS="${MAX_WSS:-64M}"; DRAM_SIZE="${DRAM_SIZE:-32M}"; CHASE_DRAM="${CHASE_DRAM:-128M}"
    KERNEL_DRAM="${KERNEL_DRAM:-96M}"; TLB_MAX_PAGES="${TLB_MAX_PAGES:-16384}"
else
    REPS="${REPS:-5}"; MS="${MS:-200}"
    MAX_WSS="${MAX_WSS:-1G}"; DRAM_SIZE="${DRAM_SIZE:-256M}"; CHASE_DRAM="${CHASE_DRAM:-1G}"
    KERNEL_DRAM="${KERNEL_DRAM:-768M}"; TLB_MAX_PAGES="${TLB_MAX_PAGES:-262144}"
fi
# Optional NUMA binding prefix on Linux, e.g. NUMACTL="numactl --membind=0"
NUMACTL="${NUMACTL:-}"

# --- page sizes ------------------------------------------------------------------------
# Linux: 4k, thp (madvise), hugetlb (if pages reserved). Windows: 4k, large
# (needs the "Lock pages in memory" privilege; see scripts/setup_env.sh).
if is_windows; then
    HUGE_OK="$("$BIN/sysinfo" --large-pages-check >/dev/null 2>&1 && echo 1 || echo 0)"
    HUGE_MODE=large
    HUGETLB=0
else
    HUGE_OK="$(grep -qE '\[(always|madvise)\]' /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null && echo 1 || echo 0)"
    HUGE_MODE=thp
    HUGETLB="${HUGETLB:-$( [ "$(cat /proc/sys/vm/nr_hugepages 2>/dev/null || echo 0)" -gt 0 ] && echo 1 || echo 0)}"
fi
# PG: page mode for runs that should be free of TLB effects (huge pages if possible)
PG="$( [ "$HUGE_OK" = 1 ] && echo "$HUGE_MODE" || echo 4k)"

page_modes() {  # page modes worth testing on this machine
    echo 4k
    [ "$HUGE_OK" = 1 ] && echo "$HUGE_MODE"
    [ "$HUGETLB" = 1 ] && echo hugetlb
    return 0
}

# Working-set sweep: powers of two plus the 1.5x midpoints, MIN..MAX bytes.
sizes() {
    local lo hi s
    lo="$(to_bytes "$1")"; hi="$(to_bytes "$2")"; s=$lo
    while [ "$s" -le "$hi" ]; do
        echo "$s"
        [ $(( s * 3 / 2 )) -le "$hi" ] && echo $(( s * 3 / 2 ))
        s=$(( s * 2 ))
    done
}

# Thread counts for intensity sweeps: 1 2 4 6 8 ... NT (always includes NT)
thread_counts() {
    local t
    for t in 1 2 3 4 6 8 10 12 16 20 24 32 48 64 96 128; do [ "$t" -lt "$NT" ] && echo "$t"; done
    echo "$NT"
}

# --- hardware counters -------------------------------------------------------------------
# linux : in-process perf_event_open (the binaries' --perf flag)
# uprof : Windows + AMD Ryzen: each counted run is wrapped in AMD uProf's CPU profiler
#         (AMDuProfCLI collect, event-based sampling). AMDuProfPcm is EPYC-only, so it is
#         not used. EBP is disabled while Hyper-V runs underneath Windows (Memory integrity /
#         VBS): see WINDOWS_SETUP.md and scripts/uprof_probe.sh.
# none  : no counters (columns stay NaN)
UPROF_CLI="${UPROF_CLI:-}"
if [ -z "$UPROF_CLI" ] && is_windows; then
    for c in "/c/Program Files/AMD/AMDuProf/bin/AMDuProfCLI.exe" "$(command -v AMDuProfCLI 2>/dev/null || true)"; do
        [ -n "$c" ] && [ -x "$c" ] && { UPROF_CLI="$c"; break; }
    done
fi
if [ -z "${COUNTERS:-}" ]; then
    if ! is_windows; then COUNTERS=linux
    elif [ -n "$UPROF_CLI" ]; then COUNTERS=uprof
    else COUNTERS=none
    fi
fi
# Event sets, each profiled separately (two runs per set: full + setup-only).
# Default config:data_access = uProf's predefined "Investigate Data Access" set: cycles,
# instructions, L1D accesses, L2 accesses from L1D misses, demand L1D fills from L2 / L3 /
# DRAM, L1 and L2 DTLB misses - every counter column. It has 10 events for 6 hardware
# counters, so uProf multiplexes them and captures only part of each; uprof_merge.py
# corrects for that per run with the cycles the process must have used (its own runtime x
# clock, written by --meta), like perf's time_enabled/time_running scaling.
# A and B are hand-picked <= 6-event sets (-e event=...). On uProf 5.3 / Windows 11 they
# were accepted but sampled almost none of the program's own code, so they are not the
# default; try UPROF_SETS=A,B with scripts/uprof_probe.sh if a newer uProf fixes that.
UPROF_EVENTS_A="${UPROF_EVENTS_A:-pmcx076::250000 pmcx0c0::250000 pmcx029:0x07:250000 pmcx060:0xc8:25000 pmcx043:0x08:25000 pmcx045:0xf0:25000}"
UPROF_EVENTS_B="${UPROF_EVENTS_B:-pmcx076::250000 pmcx043:0x02:25000 pmcx043:0x01:25000 pmcx045:0xff:25000}"
if [ -n "${UPROF_CONFIG:-}" ] && [ -z "${UPROF_SETS:-}" ]; then   # backwards compatibility
    UPROF_SETS="$(echo "$UPROF_CONFIG" | sed 's/[^,][^,]*/config:&/g')"
fi
UPROF_SETS="${UPROF_SETS:-config:data_access}"
UPROF_SEQ=0

# AMDuProfCLI collect arguments for one set name (A, B, or config:NAME)
uprof_set_args() {
    local set="$1" spec code mask iv args=()
    case "$set" in
        config:*) echo "--config ${set#config:}"; return ;;
        A) spec="$UPROF_EVENTS_A" ;;
        B) spec="$UPROF_EVENTS_B" ;;
        *) die "unknown uProf event set '$set' (use A, B or config:NAME)" ;;
    esac
    for e in $spec; do
        IFS=: read -r code mask iv <<< "$e"
        args+=("-e" "event=$code${mask:+,umask=$mask},interval=$iv")
    done
    echo "${args[*]}"
}

# --- running ---------------------------------------------------------------------------
# Run a benchmark, appending its CSV rows to $OUT. Progress goes to stderr.
# A failing configuration (e.g. large pages not available) does not stop the
# experiment: it is logged, recorded in data/raw/failures.txt, and skipped.
run() {
    log "$(basename "$1") ${*:2}"
    local rc=0
    if [ -n "$NUMACTL" ] && ! is_windows; then $NUMACTL "$@" >> "$OUT" || rc=$?; else "$@" >> "$OUT" || rc=$?; fi
    if [ "$rc" != 0 ]; then
        log "warning: exit code $rc - this configuration is skipped (listed in data/raw/failures.txt)"
        printf '%s\t%s\texit %s\t%s\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$(basename "$OUT")" "$rc" "$(basename "$1") ${*:2}" \
            >> "$RAW/failures.txt"
    fi
    return 0
}

# Like run(), but fills the counter columns. On Windows with AMD uProf:
# differential measurement - the same command is profiled twice, once normally
# and once with --reps 0 (allocation, init, validation, warm-up only); the
# difference is what the timed repetitions alone caused, split evenly per rep.
run_counted() {
    if [ "$COUNTERS" != uprof ]; then run "$@"; return; fi
    local bin="$1"; shift
    local d="$RAW/uprof" tag cfg
    mkdir -p "$d"
    UPROF_SEQ=$((UPROF_SEQ + 1))
    tag="$(basename "$OUT" .csv)_$(printf '%04d' "$UPROF_SEQ")"
    local rows="$d/$tag.rows.csv" fulls=() bases=()
    rm -f "$rows"
    log "uprof[$UPROF_SETS] $(basename "$bin") $*"
    for cfg in ${UPROF_SETS//,/ }; do
        # rows are kept from the first config only; later configs only add events
        if [ ${#fulls[@]} -eq 0 ]; then
            uprof_run "$d/$tag.${cfg#config:}.full" "$cfg" "$bin" "$@" --out "$(winpath "$rows")" \
                --meta "$(winpath "$d/$tag.${cfg#config:}.full.meta")"
        else
            uprof_run "$d/$tag.${cfg#config:}.full" "$cfg" "$bin" "$@" --meta "$(winpath "$d/$tag.${cfg#config:}.full.meta")"
        fi
        uprof_run "$d/$tag.${cfg#config:}.base" "$cfg" "$bin" "$@" --reps 0 \
            --meta "$(winpath "$d/$tag.${cfg#config:}.base.meta")"
        fulls+=("$d/$tag.${cfg#config:}.full"); bases+=("$d/$tag.${cfg#config:}.base")
    done
    if [ -s "$rows" ]; then
        local IFS=,
        "$PY" "$ROOT/analysis/uprof_merge.py" --rows "$rows" --full "${fulls[*]}" --base "${bases[*]}" \
            --exe "$(basename "$bin")" --events "$ROOT/analysis/uprof_events.csv" >> "$OUT" ||
            { log "warning: counter merge failed for $tag; keeping rows without counters"; cat "$rows" >> "$OUT"; }
    else
        log "warning: no rows from $tag under uProf (see $d/$tag.*.log); running without counters"
        run "$bin" "$@"
    fi
}

# uprof_run PREFIX SET BINARY ARGS...  -> PREFIX.d/ (session + report CSVs), PREFIX.log
uprof_run() {
    local prefix="$1" cfg="$2" exe="$3" session setargs; shift 3
    # shellcheck disable=SC2207
    setargs=($(uprof_set_args "$cfg"))
    [ -x "$exe.exe" ] && exe="$exe.exe"
    rm -rf "$prefix.d"; mkdir -p "$prefix.d"
    local rc=0
    log "  $(basename "$prefix"): collect"
    # no keyboard input (a hidden prompt must not hang the run) and a time limit
    MSYS2_ARG_CONV_EXCL='*' timeout "${UPROF_TIMEOUT:-900}" "$UPROF_CLI" collect "${setargs[@]}" \
        -o "$(winpath "$prefix.d")" "$(winpath "$exe")" "$@" < /dev/null > "$prefix.log" 2>&1 || rc=$?
    [ "$rc" = 124 ] && log "warning: AMDuProfCLI collect timed out after ${UPROF_TIMEOUT:-900}s (see $prefix.log)"
    if [ "$rc" != 0 ] && [ "$rc" != 124 ]; then
        log "warning: AMDuProfCLI collect returned error $rc. Its last lines ($prefix.log):"
        tr -d '\r' < "$prefix.log" | tail -6 | sed 's/^/     | /' >&2
    fi
    # Session directory: the path uProf prints, else the newest directory it created inside
    # PREFIX.d or next to it (older uProf treats -o as a base name).
    session="$(tr -d '\r' < "$prefix.log" | sed -n 's/.*[Gg]enerated data files path: *//p' | tail -1)"
    [ -n "$session" ] && command -v cygpath >/dev/null 2>&1 && session="$(cygpath -u "$session")"
    if [ -z "$session" ] || [ ! -d "$session" ]; then
        session="$( { find "$prefix.d" -mindepth 1 -maxdepth 1 -type d; ls -d "$prefix".d?* 2>/dev/null; } |
                    sort | tail -1 || true)"
    fi
    [ -n "$session" ] || session="$prefix.d"
    log "  $(basename "$prefix"): report"
    rc=0
    MSYS2_ARG_CONV_EXCL='*' timeout "${UPROF_TIMEOUT:-900}" "$UPROF_CLI" report -i "$(winpath "$session")" \
        < /dev/null >> "$prefix.log" 2>&1 || rc=$?
    [ "$rc" = 124 ] && log "warning: AMDuProfCLI report timed out after ${UPROF_TIMEOUT:-900}s (see $prefix.log)"
    [ "$rc" != 0 ] && [ "$rc" != 124 ] && log "warning: AMDuProfCLI report returned error $rc (see $prefix.log)"
    # Collect every CSV the report mentions (it may write outside PREFIX.d) and the session's own.
    local f
    { tr -d '\r' < "$prefix.log" | grep -oE '[A-Za-z]:[\\/][^"<>|]*\.csv|/[^ "<>|]*\.csv' || true; } | sort -u |
        while IFS= read -r f; do
            command -v cygpath >/dev/null 2>&1 && f="$(cygpath -u "$f")"
            [ -f "$f" ] && cp -f "$f" "$prefix.d/" 2>/dev/null || true
        done
    [ "$session" != "$prefix.d" ] && [ -d "$session" ] && case "$session" in "$prefix.d"/*) ;; *)
        find "$session" -name '*.csv' -exec cp -f {} "$prefix.d/" \; 2>/dev/null || true ;; esac
    return 0
}

new_csv() {  # new_csv FILE BINARY  -> writes the binary's header
    OUT="$1"
    "$2" --header-only | tr -d '\r' > "$OUT"
    # forget earlier failures recorded for this file (it is being rewritten)
    if [ -f "$RAW/failures.txt" ]; then
        awk -F'\t' -v f="$(basename "$OUT")" '$2 != f' "$RAW/failures.txt" > "$RAW/failures.txt.tmp" &&
            mv "$RAW/failures.txt.tmp" "$RAW/failures.txt"
    fi
    log "writing $OUT"
}

show_config() {
    log "OS=$CMP_OS CPU=$CPU NODE=$NODE CPUS=$CPUS (NT=$NT) OTHERS=${OTHERS:-<none>} QUICK=$QUICK REPS=$REPS MS=$MS"
    log "MAX_WSS=$MAX_WSS DRAM_SIZE=$DRAM_SIZE CHASE_DRAM=$CHASE_DRAM huge pages=$HUGE_MODE ok=$HUGE_OK counters=$COUNTERS${UPROF_CLI:+ (sets $UPROF_SETS)}"
}
