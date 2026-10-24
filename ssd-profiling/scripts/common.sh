#!/usr/bin/env bash
# Shared helpers, sourced by every run script (not executed directly):
#   * config loading and platform detection (Windows/MSYS2 or Linux)
#   * DATA-LOSS SAFETY CHECKS before anything touches the target
#   * run_fio: runs one fio job and records metadata, device I/O counters and
#     drive temperature before and after the run
#
# Windows (MSYS2 UCRT64 shell): fio is the native Windows build (fio.exe),
# device facts come from bin/winstat.exe (src/winstat.cpp, built with g++).
# Linux: /proc/diskstats, sysfs, lsblk.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIO_DIR="$REPO_ROOT/fio"
export PYTHONUTF8=1                      # UTF-8 file I/O for the Python analysis on Windows

log()  { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; }
die()  { printf '\n*** ERROR: %s\n\n' "$*" >&2; exit 1; }
warn() { printf '*** WARNING: %s\n' "$*" >&2; }

to_bytes() { numfmt --from=iec "${1^^}" 2>/dev/null || die "bad size '$1'"; }
jesc() { local s=${1//\\/\\\\}; s=${s//\"/\\\"}; printf '%s' "$s"; }   # JSON string escape

# ---- platform -----------------------------------------------------------------
case "${SSDPROF_PLATFORM:-$(uname -s)}" in
  MINGW*|MSYS*|CYGWIN*|windows) IS_WIN=1 ;;
  *) IS_WIN=0 ;;
esac
PLATFORM=$([[ $IS_WIN == 1 ]] && echo windows || echo linux)
EXE=$([[ $IS_WIN == 1 ]] && echo .exe || echo "")
WINSTAT="${WINSTAT:-$REPO_ROOT/bin/winstat.exe}"
REF_QD1="${REF_QD1:-$REPO_ROOT/bin/ref_qd1$EXE}"
export IS_WIN PLATFORM WINSTAT REF_QD1

# winstat output, without carriage returns
ws() { "$WINSTAT" "$@" | tr -d '\r'; }
# Windows-native form of a path (identity on Linux)
winpath() { if [[ $IS_WIN == 1 ]]; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
# path as fio's filename= wants it: Windows drive colons must be escaped (D\:/x)
fio_filename_for() {
  if [[ $IS_WIN == 1 && ! "$1" =~ PhysicalDrive[0-9]+$ ]]; then
    local m; m="$(cygpath -m "$1")"; printf '%s' "${m//:/\\:}"
  else
    printf '%s' "$1"
  fi
}
# native console programs (powercfg, cmd) whose /switches MSYS2 must not
# rewrite into paths
wincmd() { MSYS2_ARG_CONV_EXCL='*' "$@" 2>&1 | tr -d '\r'; }

is_admin() {
  if [[ $IS_WIN == 1 ]]; then [[ "$(ws isadmin 2>/dev/null)" == 1 ]];
  else [[ $EUID -eq 0 ]] || sudo -n true 2>/dev/null; fi
}

# A fio left running by an interrupted run keeps the target file open, and
# Windows then refuses to let the next fio delete or resize it.
check_no_stray_fio() {
  if [[ $IS_WIN == 1 ]]; then
    if tasklist.exe 2>/dev/null | tr -d '\r' | grep -qi '^fio\.exe'; then
      die "fio.exe is already running (probably left over from an interrupted run). End it in Task Manager > Details, or run:  taskkill //F //IM fio.exe"
    fi
  elif pgrep -x fio >/dev/null 2>&1; then
    die "a fio process is already running; stop it first (pkill -x fio)"
  fi
}

# "2-5,8" -> valid on this machine?
cpu_list_valid() {
  local max=$(( $(nproc) - 1 )) part a b parts
  IFS=, read -ra parts <<< "$1"
  for part in "${parts[@]}"; do
    [[ "$part" =~ ^([0-9]+)(-([0-9]+))?$ ]] || return 1
    a=${BASH_REMATCH[1]}; b=${BASH_REMATCH[3]:-$a}
    (( a <= b && b <= max )) || return 1
  done
}
first_cpu() { printf '%s' "${FIO_CPUS%%[-,]*}"; }

load_config() {
  # shellcheck disable=SC1091
  source "$REPO_ROOT/config.env"
  if [[ -f "$REPO_ROOT/config.local.env" ]]; then
    # shellcheck disable=SC1091
    source "$REPO_ROOT/config.local.env"
  fi
  if [[ "${QUICK:-0}" == "1" ]]; then
    # Smoke-test mode: exercises every code path in a few minutes. Numbers from
    # this mode are NOT meaningful measurements.
    RUNTIME=2; RAMP=0; REPS=1
    TARGET_SIZE="${QUICK_TARGET_SIZE:-512M}"
    QD_LIST="1 4 16 64"; BS_SEQ_EXTRA=""; BS_LIST="4k 64k 128k"
    MIX_READ_PCTS="100 50 0"; WS_LIST="64M 256M FULL"; MISLEAD_WS=64M
    SS_RANDWRITE_SECONDS=8; SS_SEQWRITE_SECONDS=6; TEMP_SAMPLE_SEC=1
    SS_IDLE_BEFORE_SEC=1; SS_POST_IDLE_SEC=1
  fi

  # fio binary
  if [[ -z "${FIO_BIN:-}" ]]; then
    FIO_BIN="$(command -v fio || true)"
    [[ -z "$FIO_BIN" && $IS_WIN == 1 && -x "/c/Program Files/fio/fio.exe" ]] && FIO_BIN="/c/Program Files/fio/fio.exe"
  fi
  [[ -n "$FIO_BIN" ]] || die "fio not found. Install it (Windows: the fio MSI from https://github.com/axboe/fio/releases) or set FIO_BIN in config.local.env"
  [[ $IS_WIN == 1 && "$FIO_BIN" =~ ^[A-Za-z]: ]] && FIO_BIN="$(cygpath -u "$FIO_BIN")"

  # engines: the async engine for all measurements; a synchronous engine for
  # the reference comparison and the "wrong queue depth" demo. Windows' sync
  # engines cannot do direct (unbuffered) I/O.
  if [[ $IS_WIN == 1 ]]; then
    IOENGINE="${IOENGINE:-windowsaio}"; SYNC_ENGINE="${SYNC_ENGINE:-sync}"; SYNC_DIRECT=0
  else
    IOENGINE="${IOENGINE:-io_uring}"; SYNC_ENGINE="${SYNC_ENGINE:-psync}"; SYNC_DIRECT=1
  fi

  # CPU pinning through fio's own cpus_allowed (works on both platforms)
  if [[ -z "${FIO_CPUS:-}" ]]; then
    FIO_CPUS="0-$(( $(nproc) - 1 ))"
  elif ! cpu_list_valid "$FIO_CPUS"; then
    die "FIO_CPUS='$FIO_CPUS' is not valid on this machine (logical CPUs 0-$(( $(nproc) - 1 ))). Edit config.local.env."
  fi

  if [[ $IS_WIN == 1 ]]; then
    [[ -x "$WINSTAT" ]] || die "bin/winstat.exe is missing. Run 'make build' in the UCRT64 shell first."
  fi
  [[ -x "$REF_QD1" ]] || die "bin/ref_qd1$EXE is missing. Run 'make build' first."

  RUN_ID="${RUN_ID:-$(cat "$REPO_ROOT/data/raw/CURRENT_RUN" 2>/dev/null || true)}"
  [[ -n "$RUN_ID" ]] || RUN_ID="run_$(date +%Y%m%d_%H%M%S)"
  RAW_DIR="$REPO_ROOT/data/raw/$RUN_ID"
  mkdir -p "$RAW_DIR"
  echo "$RUN_ID" > "$REPO_ROOT/data/raw/CURRENT_RUN"
  export RUN_ID RAW_DIR FIO_BIN IOENGINE SYNC_ENGINE SYNC_DIRECT FIO_CPUS
}

# ----------------------------------------------------------------------------
# Target resolution. Sets:
#   TARGET_KIND   file | device
#   TARGET_POSIX  path bash can use (empty for raw devices on Windows)
#   TARGET_WIN    native path for g++ tools (Windows: D:\..., \\.\PhysicalDriveN)
#   FIO_FILENAME  value for fio's filename=
#   DISK_ID       disk the I/O lands on (Windows: disk number; Linux: nvme0n1)
#   COUNTER_DEV   what the I/O counters are read from (Windows: the volume, or
#                 the disk for raw targets; Linux: the partition / device)
#   TARGET_BYTES  span exercised
# ----------------------------------------------------------------------------
resolve_target() {
  [[ -n "${TARGET:-}" ]] || die "TARGET is not set (edit config.local.env)"
  FREE_BYTES=""; FS_TYPE=""; DRIVE_TYPE=""; SYS_DISK=0; SYS_VOLUME=0; PARTS=0; DEV_BYTES=0; EXTENTS=1
  if [[ $IS_WIN == 1 ]]; then
    local -A R=()
    local k v
    if [[ "$TARGET" =~ PhysicalDrive([0-9]+)$ ]]; then
      TARGET_KIND=device; TARGET_WIN="\\\\.\\PhysicalDrive${BASH_REMATCH[1]}"; TARGET_POSIX=""
    else
      TARGET_KIND=file
      TARGET_POSIX="$(cygpath -u "$TARGET")"; TARGET_WIN="$(cygpath -w "$TARGET")"
      [[ -d "$(dirname "$TARGET_POSIX")" ]] || die "folder $(dirname "$TARGET_WIN") for TARGET does not exist (create it first)"
    fi
    while IFS='=' read -r k v; do if [[ -n "$k" ]]; then R[$k]="$v"; fi; done < <(ws resolve "$TARGET_WIN" || true)
    [[ -n "${R[kind]:-}" ]] || die "winstat could not resolve $TARGET_WIN"
    DISK_ID="${R[disk]}"; COUNTER_DEV="${R[counters]:-}"
    SYS_DISK="${R[system_disk]:-0}"; SYS_VOLUME="${R[system_volume]:-0}"
    FS_TYPE="${R[fs]:-}"; DRIVE_TYPE="${R[drive_type]:-}"; FREE_BYTES="${R[free]:-}"
    PARTS="${R[partitions]:-0}"; DEV_BYTES="${R[size]:-0}"; EXTENTS="${R[extents]:-1}"
  else
    if [[ -b "$TARGET" ]]; then
      TARGET_KIND=device
      COUNTER_DEV="$(basename "$(readlink -f "$TARGET")")"
      DEV_BYTES="$(blockdev --getsize64 "$TARGET" 2>/dev/null || lsblk -bdno SIZE "$TARGET")"
    else
      TARGET_KIND=file
      local dir; dir="$(dirname "$TARGET")"
      [[ -d "$dir" ]] || die "directory $dir for TARGET does not exist"
      local src; src="$(df --output=source "$dir" | tail -1)"
      if [[ -b "$src" ]]; then COUNTER_DEV="$(basename "$(readlink -f "$src")")"; else COUNTER_DEV=""; fi
      FS_TYPE="$(df --output=fstype "$dir" | tail -1)"
      FREE_BYTES="$(df --output=avail -B1 "$dir" | tail -1)"
      [[ "$(findmnt -no SOURCE /)" == "/dev/$COUNTER_DEV" ]] && SYS_VOLUME=1
    fi
    TARGET_POSIX="$TARGET"; TARGET_WIN="$TARGET"
    DISK_ID=""
    if [[ -n "$COUNTER_DEV" ]]; then
      DISK_ID="$(lsblk -no PKNAME "/dev/$COUNTER_DEV" 2>/dev/null | head -1 || true)"
      [[ -n "$DISK_ID" ]] || DISK_ID="$COUNTER_DEV"
    fi
  fi
  if [[ "$TARGET_KIND" == device ]]; then
    if [[ -n "${TARGET_SIZE:-}" ]]; then
      TARGET_BYTES="$(to_bytes "$TARGET_SIZE")"
      (( TARGET_BYTES <= DEV_BYTES )) || die "TARGET_SIZE is larger than the disk ($DEV_BYTES B)"
    else
      TARGET_BYTES="$DEV_BYTES"
    fi
  else
    TARGET_BYTES="$(to_bytes "$TARGET_SIZE")"
  fi
  FIO_FILENAME="$(fio_filename_for "$TARGET_WIN")"
  export TARGET_KIND TARGET_POSIX TARGET_WIN FIO_FILENAME DISK_ID COUNTER_DEV TARGET_BYTES
}

# ----------------------------------------------------------------------------
# DATA-LOSS SAFETY CHECK. Called before anything touches TARGET.
# ----------------------------------------------------------------------------
_confirm_destructive() {
  [[ "${ASSUME_YES:-0}" == 1 ]] && return 0
  echo "About to run DESTRUCTIVE benchmarks on $TARGET ($1)."
  read -r -p "Type the target exactly as in your config to confirm: " ans
  [[ "$ans" == "$TARGET" ]] || die "confirmation mismatch; aborting"
}

safety_check() {
  [[ "${_SAFETY_OK:-0}" == 1 ]] && return 0
  resolve_target
  if [[ "$TARGET_KIND" == device ]]; then
    [[ "${ALLOW_RAW_DEVICE:-0}" == 1 ]] || die "TARGET $TARGET is a whole disk but ALLOW_RAW_DEVICE!=1"
    [[ "${WIPE_OK:-}" == "$TARGET" ]] || die "Raw disk target requires WIPE_OK='$TARGET' (exact match)"
    if [[ $IS_WIN == 1 ]]; then
      is_admin || die "raw disk access needs an elevated shell: start MSYS2 UCRT64 with 'Run as administrator'"
      [[ "$SYS_DISK" == 0 ]] || die "$TARGET is the disk Windows is installed on"
      [[ "$PARTS" != -1 ]] || die "cannot read the partition table of $TARGET"
      [[ "$PARTS" == 0 ]] || die "$TARGET still has $PARTS partition(s). Delete them in Disk Management first (this proves the disk is empty)."
      _confirm_destructive "$(ws info "$DISK_ID" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["model"], d["size_bytes"]//10**9, "GB")' 2>/dev/null | tr -d '\r')"
    else
      local mp
      mp="$(lsblk -nro MOUNTPOINTS "$TARGET" 2>/dev/null || lsblk -nro MOUNTPOINT "$TARGET")"
      [[ -z "${mp//[[:space:]]/}" ]] || die "$TARGET (or a partition on it) is mounted at: $mp"
      local rootsrc rootdisk
      rootsrc="$(findmnt -no SOURCE / || true)"
      rootdisk="$(lsblk -no PKNAME "$rootsrc" 2>/dev/null | head -1 || true)"
      [[ "/dev/$COUNTER_DEV" != "$rootsrc" && "$COUNTER_DEV" != "$rootdisk" ]] || die "$TARGET holds the root filesystem"
      ! grep -qw "$COUNTER_DEV" /proc/swaps 2>/dev/null || die "$TARGET is used as swap"
      local holders; holders="$(ls "/sys/class/block/$COUNTER_DEV/holders" 2>/dev/null || true)"
      [[ -z "$holders" ]] || die "$TARGET has holders (LVM/MD/dm-crypt?): $holders"
      local sig; sig="$(blkid -p -o value -s TYPE "$TARGET" 2>/dev/null || true)$(blkid -p -o value -s PTTYPE "$TARGET" 2>/dev/null || true)"
      [[ -z "$sig" ]] || warn "$TARGET carries a signature ($sig). It WILL be overwritten."
      _confirm_destructive "$(lsblk -dno MODEL,SIZE "$TARGET" 2>/dev/null)"
    fi
  else
    [[ "$(basename "$TARGET_POSIX")" == *fio-scratch* ]] || \
      die "file TARGET name must contain 'fio-scratch' (got $(basename "$TARGET_POSIX"))"
    if [[ $IS_WIN == 1 ]]; then
      case "$DRIVE_TYPE" in
        fixed) ;;
        removable) warn "TARGET is on a removable drive; make sure it is the SSD you mean to test" ;;
        *) die "TARGET is on a '$DRIVE_TYPE' drive; it must be a local disk" ;;
      esac
      case "${FS_TYPE^^}" in
        NTFS|REFS) ;;
        EXFAT) warn "exFAT: results are valid, but the report assumes NTFS" ;;
        *) die "TARGET is on $FS_TYPE; use an NTFS volume (FAT32 cannot hold files over 4 GiB)" ;;
      esac
      [[ "$EXTENTS" == 1 ]] || warn "the volume spans $EXTENTS disks; per-disk results will be mixed"
    else
      case "$FS_TYPE" in
        tmpfs|ramfs|overlay|nfs*|cifs|fuse*) die "TARGET is on $FS_TYPE; need a local filesystem on the SSD under test";;
      esac
    fi
    local marker="$TARGET_POSIX.owned-by-ssd-profiling"
    if [[ -e "$TARGET_POSIX" && ! -e "$marker" ]]; then
      die "$TARGET already exists and was not created by these scripts (no $(basename "$marker")). Refusing to overwrite."
    fi
    if [[ ! -e "$TARGET_POSIX" && -n "$FREE_BYTES" ]]; then
      (( FREE_BYTES > TARGET_BYTES + 2*1024*1024*1024 )) || \
        die "not enough free space for $TARGET_SIZE plus 2 GiB headroom (free: $FREE_BYTES B)"
    fi
    [[ -n "$COUNTER_DEV" ]] || warn "could not resolve the device under $TARGET; I/O-counter checks disabled"
    if [[ "$SYS_VOLUME" == 1 ]]; then
      warn "TARGET is on the system volume; OS background I/O (and on Windows, Defender/indexing) will add noise. A separate partition is better."
    elif [[ "$SYS_DISK" == 1 ]]; then
      warn "TARGET is on the same physical SSD as the OS; background OS I/O will add some noise"
    fi
  fi
  _SAFETY_OK=1
  export _SAFETY_OK
  log "safety check passed: $TARGET ($TARGET_KIND, disk=${DISK_ID:-?}, counters=${COUNTER_DEV:-?}, span=$TARGET_BYTES B)"
}

# ----------------------------------------------------------------------------
# Observability helpers
# ----------------------------------------------------------------------------
read_temp_c() {
  if [[ $IS_WIN == 1 ]]; then
    [[ -n "${DISK_ID:-}" && "${DISK_ID}" != -1 ]] && { ws temp "$DISK_ID" 2>/dev/null || echo NA; return; }
    echo NA; return
  fi
  local f
  for f in /sys/block/"${DISK_ID:-none}"/device/hwmon*/temp1_input \
           /sys/block/"${DISK_ID:-none}"/device/device/hwmon*/temp1_input; do
    [[ -r "$f" ]] && { awk '{printf "%.1f", $1/1000}' "$f"; return; }
  done
  if [[ -n "${DISK_ID:-}" ]] && command -v nvme >/dev/null && [[ "$DISK_ID" == nvme* ]]; then
    local k; k="$(nvme smart-log "/dev/$DISK_ID" -o json 2>/dev/null | python3 -c 'import json,sys;print(json.load(sys.stdin)["temperature"])' 2>/dev/null || true)"
    [[ -n "$k" ]] && { awk -v k="$k" 'BEGIN{printf "%.1f", k-273.15}'; return; }
  fi
  echo "NA"
}

# Cumulative device counters in BYTES: "reads bytes_read writes bytes_written"
diskstats_line() {
  if [[ -z "${COUNTER_DEV:-}" ]]; then echo "NA NA NA NA"; return; fi
  if [[ $IS_WIN == 1 ]]; then
    ws counters "$COUNTER_DEV" 2>/dev/null || echo "NA NA NA NA"
  else
    awk -v d="$COUNTER_DEV" '$3==d{printf "%d %.0f %d %.0f\n", $4, $6*512, $8, $10*512; f=1} END{if(!f) print "NA NA NA NA"}' /proc/diskstats
  fi
}

TEMP_MON_PID=""
start_temp_monitor() {  # $1 = output csv
  local out="$1"
  echo "epoch_s,temp_c" > "$out"
  ( while true; do echo "$(date +%s.%N),$(read_temp_c)" >> "$out"; sleep "$TEMP_SAMPLE_SEC"; done ) &
  TEMP_MON_PID=$!
}
stop_temp_monitor() { [[ -n "$TEMP_MON_PID" ]] && kill "$TEMP_MON_PID" 2>/dev/null || true; TEMP_MON_PID=""; }

# Empty the OS file cache. Sets CACHE_PURGED=1 on success, 0 otherwise.
drop_caches() {
  sync
  CACHE_PURGED=0
  if [[ $IS_WIN == 1 ]]; then
    if ws purge-standby >/dev/null 2>&1; then CACHE_PURGED=1
    else warn "cannot purge the Windows file cache (needs 'Run as administrator'); the 'cold' run will be partly warm"; fi
  elif [[ -w /proc/sys/vm/drop_caches ]]; then echo 3 > /proc/sys/vm/drop_caches; CACHE_PURGED=1
  elif sudo -n true 2>/dev/null; then echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null; CACHE_PURGED=1
  else warn "cannot drop page cache (not root)"; fi
}

# ----------------------------------------------------------------------------
# run_fio <jobfile> <experiment> <point-name> <rep> [KEY=VAL ...]
#   KEY=VAL pairs are exported for ${VAR} substitution in the job file and are
#   recorded verbatim in the run's .meta.json. FILE_OVERRIDE=<path> runs the
#   job against a different file than TARGET.
#   Output: $RAW_DIR/<experiment>/<point>_rep<rep>.json (+ .meta.json)
# ----------------------------------------------------------------------------
run_fio() { safety_check; _run_fio_impl "$@"; }
# Subshell body: KEY=VAL overrides (e.g. IOENGINE=sync) must not leak into later runs.
_run_fio_impl() (
  local job="$1" exp="$2" name="$3" rep="$4"; shift 4
  local outdir="$RAW_DIR/$exp"; mkdir -p "$outdir"
  local stem="${name}_rep${rep}"

  # defaults for every substitution variable used by the job files
  export FIO_FILENAME IOENGINE RUNTIME RAMP COMPRESS_PCT FIO_CPUS
  export DIRECT=1 RW=randread BS=4k QD=1 NJ=1 RWMIXREAD=50 OFFSET=0 OFFINC=0 INVALIDATE=1
  export SIZE="$TARGET_BYTES" LOGPREFIX="$stem" LOGMS=1000 IOSIZE="$TARGET_BYTES" LOOPS=1
  local kv meta_kv=""
  for kv in "$@"; do
    export "${kv?}"
    meta_kv+=$(printf ', "%s": "%s"' "$(jesc "${kv%%=*}")" "$(jesc "${kv#*=}")")
  done
  if [[ -n "${FILE_OVERRIDE:-}" ]]; then FIO_FILENAME="$(fio_filename_for "$FILE_OVERRIDE")"; fi

  local fmt="json"; [[ "${FIO_JSONPLUS:-0}" == 1 ]] && fmt="json+"
  local extra=(); read -ra extra <<< "${FIO_EXTRA_ARGS:-}"
  local ds0 ds1 t0 t1 ts
  cd "$outdir"   # outputs and logs use relative names: no drive letters for fio to parse
  # Fill in the job file here and give fio the finished copy (saved with the
  # results). Nothing reaches fio through environment variables, which MSYS2
  # rewrites when they look like paths (it mangled "D\:/ssdtest/...").
  render_job "$job" "$stem.fio"
  ds0="$(diskstats_line)"; t0="$(read_temp_c)"; ts="$(date -Is)"
  log "$exp/$name rep$rep  (rw=$RW bs=$BS qd=$QD nj=$NJ mix=$RWMIXREAD direct=$DIRECT engine=$IOENGINE)"
  if ! MSYS2_ARG_CONV_EXCL='*' "$FIO_BIN" --eta=never "${extra[@]}" --output-format="$fmt" \
         --output="$stem.json" "$stem.fio" 2> "$stem.stderr"; then
    cat "$stem.stderr" >&2; die "fio failed for $outdir/$stem (see $stem.stderr)"
  fi
  [[ -s "$stem.stderr" ]] || rm -f "$stem.stderr"
  ds1="$(diskstats_line)"; t1="$(read_temp_c)"
  cat > "$stem.meta.json" <<EOF
{"experiment": "$exp", "point": "$name", "rep": $rep, "timestamp": "$ts", "platform": "$PLATFORM",
 "jobfile": "$(basename "$job")", "target": "$(jesc "$TARGET")", "fio_filename": "$(jesc "$FIO_FILENAME")",
 "target_kind": "$TARGET_KIND", "disk_id": "$(jesc "${DISK_ID:-}")", "counter_dev": "$(jesc "${COUNTER_DEV:-}")",
 "span_bytes": $TARGET_BYTES, "ioengine": "$IOENGINE", "direct": "$DIRECT", "rw": "$RW", "bs": "$BS",
 "qd": "$QD", "nj": "$NJ", "rwmixread": "$RWMIXREAD", "size": "$SIZE", "runtime": "$RUNTIME", "ramp": "$RAMP",
 "compress_pct": "$COMPRESS_PCT", "fio_cpus": "$FIO_CPUS", "quick": "${QUICK:-0}",
 "diskstats_before": "$ds0", "diskstats_after": "$ds1", "temp_before_c": "$t0", "temp_after_c": "$t1"$meta_kv}
EOF
)

# render_job <template.fio> <out.fio>: replace every ${NAME} with the value of
# the shell variable NAME (empty if unset). Pure bash, so values such as
# D\:/ssdtest/fio-scratch.bin are written exactly as they are.
render_job() {
  local line name val
  while IFS= read -r line || [[ -n "$line" ]]; do
    while [[ "$line" =~ \$\{([A-Za-z_][A-Za-z0-9_]*)\} ]]; do
      name="${BASH_REMATCH[1]}"; val="${!name-}"
      line="${line//"\${$name}"/"$val"}"
    done
    printf '%s\n' "$line"
  done < "$1" > "$2"
}

# Effective-QD helper: split total QD over NJ jobs (rounding up, min 1).
split_qd() { local qd=$1 nj=$2; echo $(( (qd + nj - 1) / nj )); }
