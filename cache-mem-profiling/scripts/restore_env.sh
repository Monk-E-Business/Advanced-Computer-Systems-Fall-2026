#!/usr/bin/env bash
# Undo scripts/setup_env.sh using the saved backup.
#   Windows (MSYS2):  ./scripts/restore_env.sh
#   Linux:            sudo ./scripts/restore_env.sh
# The "Lock pages in memory" right is left in place (harmless); remove it in
# secpol.msc > Local Policies > User Rights Assignment if you want to.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
case "${CMP_OS:-$(uname -s)}" in MINGW*|MSYS*|UCRT64*|CLANG64*|CYGWIN*|windows) WIN=1 ;; *) WIN=0 ;; esac

if [ "$WIN" = 1 ]; then
    BACKUP="${BACKUP:-$ROOT/data/.env_backup_windows}"
    [ -r "$BACKUP" ] || { echo "no backup at $BACKUP"; exit 1; }
    while IFS='=' read -r name val; do
        [ -n "$name" ] || continue
        MSYS2_ARG_CONV_EXCL='*' powercfg.exe -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR "$name" "$val" >/dev/null &&
            echo "restored $name (AC) = $val"
    done < "$BACKUP"
    # Older setup runs could not read the hidden boost setting, so it is missing from the
    # backup: put back the Windows default (2 = Aggressive) instead of leaving boost off.
    if ! grep -q '^PERFBOOSTMODE=' "$BACKUP"; then
        MSYS2_ARG_CONV_EXCL='*' powercfg.exe -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PERFBOOSTMODE 2 >/dev/null &&
            echo "restored PERFBOOSTMODE (AC) = 2 (Windows default; original value was not recorded)"
    fi
    MSYS2_ARG_CONV_EXCL='*' powercfg.exe -setactive SCHEME_CURRENT >/dev/null
    rm -f "$BACKUP"
    exit 0
fi

[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
BACKUP="${BACKUP:-/var/tmp/cachemem_env_backup}"
[ -r "$BACKUP" ] || { echo "no backup at $BACKUP"; exit 1; }
tac "$BACKUP" | while IFS='=' read -r path val; do
    case "$val" in *\[*) val="$(echo "$val" | grep -oE '\[[a-z]+\]' | tr -d '[]')";; esac
    echo "$val" > "$path" 2>/dev/null && echo "restored $path = $val"
done
