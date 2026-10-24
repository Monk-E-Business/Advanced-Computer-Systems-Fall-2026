#!/usr/bin/env bash
# Put the machine into a quiet, reproducible state and save the previous
# settings so scripts/restore_env.sh can undo everything.
#
# Windows (MSYS2 UCRT64 terminal opened with "Run as administrator"):
#   ./scripts/setup_env.sh
#     - current power plan, on AC power: processor boost (turbo) off,
#       minimum and maximum processor state 100%
#     - grants your account "Lock pages in memory" (for large pages) if missing;
#       you must then sign out of Windows and back in once
#   TURBO=on ./scripts/setup_env.sh      keep boost enabled
#
# Linux:  sudo ./scripts/setup_env.sh    performance governor, turbo off, THP=madvise,
#         perf counters allowed, NUMA balancing off, 1024 x 2 MB hugetlb pages
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="${BIN:-$ROOT/bin}"
TURBO="${TURBO:-off}"
case "${CMP_OS:-$(uname -s)}" in MINGW*|MSYS*|UCRT64*|CLANG64*|CYGWIN*|windows) WIN=1 ;; *) WIN=0 ;; esac

if [ "$WIN" = 1 ]; then
    BACKUP="${BACKUP:-$ROOT/data/.env_backup_windows}"
    mkdir -p "$(dirname "$BACKUP")"
    [ "$("$BIN/sysinfo" --is-admin | tr -d '\r')" = 1 ] ||
        echo "note: not an administrator terminal - power settings may still work, the large-page grant will not."
    pc() { MSYS2_ARG_CONV_EXCL='*' powercfg.exe "$@" 2>&1 | tr -d '\r'; }
    cur() {  # current AC value of a processor setting, in decimal (empty if unknown)
        local hex
        hex="$(pc -qh SCHEME_CURRENT SUB_PROCESSOR "$1" | { grep -i 'Current AC Power Setting Index' || true; } |
               { grep -oiE '0x[0-9a-f]+' || true; } | head -1)"
        [ -n "$hex" ] && printf '%d\n' "$hex" || true
    }
    if [ -s "$BACKUP" ]; then
        echo "backup $BACKUP already exists (setup was run before); keeping the original values in it"
    else
        : > "$BACKUP"
        for s in PERFBOOSTMODE PROCTHROTTLEMIN PROCTHROTTLEMAX; do
            v="$(cur "$s")"
            [ -n "$v" ] && echo "$s=$v" >> "$BACKUP"
        done
    fi
    setv() { pc -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR "$1" "$2" >/dev/null && echo "set $1 (AC) = $2"; }
    [ "$TURBO" = off ] && setv PERFBOOSTMODE 0      # 0 = boost disabled
    setv PROCTHROTTLEMIN 100                         # no clocking down between runs
    setv PROCTHROTTLEMAX 100
    pc -setactive SCHEME_CURRENT >/dev/null
    echo "active plan: $(pc -getactivescheme)"
    echo
    if "$BIN/sysinfo" --large-pages-check >/dev/null 2>&1; then
        echo "large pages: OK"
    elif [ "$("$BIN/sysinfo" --is-admin | tr -d '\r')" = 1 ]; then
        "$BIN/sysinfo" --grant-lock-pages && echo ">>> Sign out of Windows and back in, reopen MSYS2 UCRT64 as administrator, then continue."
    else
        echo "large pages: NOT available. Reopen MSYS2 UCRT64 with 'Run as administrator' and run this script again."
    fi
    echo
    echo "Also: plug in AC power; Settings > System > Power > Power mode = Best performance;"
    echo "close browsers/Teams/OneDrive sync; pause Windows Update for the run."
    echo "Undo with: ./scripts/restore_env.sh"
    exit 0
fi

[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
BACKUP="${BACKUP:-/var/tmp/cachemem_env_backup}"
HUGEPAGES="${HUGEPAGES:-1024}"
: > "$BACKUP"
save() { [ -w "$1" ] && echo "$1=$(cat "$1")" >> "$BACKUP"; }
put()  { if [ -w "$1" ]; then save "$1"; echo "$2" > "$1" && echo "set $1 = $2"; else echo "skip $1 (not present)"; fi; }

for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do put "$g" performance; done
for e in /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference; do put "$e" performance; done
if [ "$TURBO" = off ]; then
    put /sys/devices/system/cpu/intel_pstate/no_turbo 1   # Intel
    put /sys/devices/system/cpu/cpufreq/boost 0            # AMD / acpi-cpufreq
fi
put /sys/kernel/mm/transparent_hugepage/enabled madvise
put /proc/sys/kernel/perf_event_paranoid 1
put /proc/sys/kernel/numa_balancing 0
[ "$HUGEPAGES" -gt 0 ] && put /proc/sys/vm/nr_hugepages "$HUGEPAGES"
echo "backup written to $BACKUP; undo with: sudo ./scripts/restore_env.sh"
