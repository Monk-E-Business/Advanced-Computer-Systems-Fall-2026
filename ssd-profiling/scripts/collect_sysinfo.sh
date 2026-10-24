#!/usr/bin/env bash
# Record everything needed to reproduce and interpret the measurements:
# hardware, OS, tool versions, CPU power policy / SMT, the device (model,
# firmware, bus, PCIe link, write cache, temperature, health), the filesystem,
# and pinning. Output: data/raw/<run>/sysinfo/*.txt + sysinfo.json (summary).
source "$(dirname "$0")/common.sh"
load_config
resolve_target
OUT="$RAW_DIR/sysinfo"; mkdir -p "$OUT"
cap() { local f="$1"; shift; { echo "\$ $*"; "$@" 2>&1 | tr -d '\r' || true; } > "$OUT/$f.txt"; }
PY=python3

log "collecting system info into $OUT"
cap fio_version  "$FIO_BIN" --version
cap gxx_version  g++ --version
cap python       $PY -c 'import sys,numpy,pandas,matplotlib;print(sys.version);print("numpy",numpy.__version__,"pandas",pandas.__version__,"matplotlib",matplotlib.__version__)'
cap uname        uname -a
echo "fio pinned to (cpus_allowed): $FIO_CPUS" > "$OUT/pinning.txt"

if [[ $IS_WIN == 1 ]]; then
  PS="$(command -v powershell.exe || echo /c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe)"
  PCFG="$(command -v powercfg.exe || echo /c/Windows/System32/powercfg.exe)"
  "$PS" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$(cygpath -w "$REPO_ROOT/scripts/win_sysinfo.ps1")" \
     2> "$OUT/win_sysinfo.stderr" | tr -d '\r' > "$OUT/win_sysinfo.json" || true
  [[ -s "$OUT/win_sysinfo.stderr" ]] || rm -f "$OUT/win_sysinfo.stderr"
  { echo "\$ ver"; wincmd cmd.exe /c ver; } > "$OUT/os_version.txt"
  { echo "\$ powercfg /getactivescheme"; wincmd "$PCFG" /getactivescheme
    echo; echo "\$ powercfg /query SCHEME_CURRENT SUB_PROCESSOR (min/max state, boost mode)"
    wincmd "$PCFG" /query SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMIN
    wincmd "$PCFG" /query SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMAX
    wincmd "$PCFG" /query SCHEME_CURRENT SUB_PROCESSOR PERFBOOSTMODE
  } > "$OUT/power_plan.txt"
  ws isadmin > "$OUT/is_admin.txt" || true
  if [[ -n "${DISK_ID:-}" && "$DISK_ID" != -1 ]]; then
    ws info "$DISK_ID" > "$OUT/device.json" 2> "$OUT/device.stderr" || true
    [[ -s "$OUT/device.stderr" ]] || rm -f "$OUT/device.stderr"
  fi
  ws resolve "$TARGET_WIN" > "$OUT/target_resolve.txt" || true
else
  sudo_if() { if [[ $EUID -ne 0 ]] && sudo -n true 2>/dev/null; then sudo "$@"; else "$@"; fi; }
  cap os_release   cat /etc/os-release
  cap cmdline      cat /proc/cmdline
  cap lscpu        lscpu
  cap meminfo      head -5 /proc/meminfo
  cap lsblk        lsblk -o NAME,MODEL,SERIAL,SIZE,ROTA,TRAN,TYPE,FSTYPE,MOUNTPOINTS,PHY-SEC,LOG-SEC,SCHED
  cap smart_before sudo_if smartctl -a "/dev/${DISK_ID:-none}"
  {
    echo "governor(s):  $(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | sort | uniq -c | tr '\n' ' ')"
    echo "smt_control:  $(cat /sys/devices/system/cpu/smt/control 2>/dev/null)"
  } > "$OUT/cpu_policy.txt"
  if [[ -n "${DISK_ID:-}" ]]; then
    q="/sys/block/$DISK_ID/queue"
    d="$(readlink -f /sys/block/"$DISK_ID"/device/device 2>/dev/null || readlink -f /sys/block/"$DISK_ID"/device)"
    {
      for k in scheduler nr_requests max_sectors_kb logical_block_size physical_block_size write_cache; do
        printf '%-20s %s\n' "$k" "$(cat "$q/$k" 2>/dev/null)"; done
      for k in current_link_speed current_link_width max_link_speed max_link_width; do
        printf '%-20s %s\n' "$k" "$(cat "$d/$k" 2>/dev/null)"; done
      printf '%-20s %s\n' model "$(cat /sys/block/"$DISK_ID"/device/model 2>/dev/null | xargs)"
      printf '%-20s %s\n' firmware "$(cat /sys/block/"$DISK_ID"/device/firmware_rev 2>/dev/null | xargs)"
    } > "$OUT/device.txt"
  fi
fi

$PY "$REPO_ROOT/analysis/sysinfo_summary.py" "$OUT" "$PLATFORM" "$TARGET" "$TARGET_KIND" "${DISK_ID:-}" \
  "$TARGET_BYTES" "$IOENGINE" "$FIO_CPUS"
