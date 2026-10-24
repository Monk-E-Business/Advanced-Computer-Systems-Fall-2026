#!/usr/bin/env bash
# Record the system configuration that every result depends on:
#   data/raw/sysinfo.txt   human-readable dump (commit this with the data)
#   data/raw/sysinfo.env   key=value summary read by the analysis scripts
#   data/raw/caches.csv    cache hierarchy of the measurement CPU
source "$(dirname "$0")/lib.sh"

TXT="$RAW/sysinfo.txt"; ENV="$RAW/sysinfo.env"; CACHES="$RAW/caches.csv"
section() { printf '\n===== %s =====\n' "$1"; }
rd() { cat "$1" 2>/dev/null || echo "n/a"; }
si() { "$BIN/sysinfo" "$@" 2>&1 | tr -d '\r'; }

"$BIN/sysinfo" --caches "$CPU" | tr -d '\r' > "$CACHES"
SMT="$(echo "$TOPO" | awk -F, '{ c[$3 "," $2]++ } END { s = "off"; for (k in c) if (c[k] > 1) s = "on"; print s }')"
NOMINAL="$(si --tsc-ghz)"

{
    echo "collected: $(date '+%Y-%m-%dT%H:%M:%S%z')  host: $(hostname)  os-family: $CMP_OS"
    section "CPU / topology (bin/sysinfo)"; si --summary
    section "Logical CPUs (cpu,core,package,node,eff_class)"; si --topology
    section "Caches of measurement CPU $CPU"; cat "$CACHES"
    if is_windows; then
        section "Windows"
        pwsh '$o = Get-CimInstance Win32_OperatingSystem; "$($o.Caption) $($o.Version) build $($o.BuildNumber)"'
        pwsh '$c = Get-CimInstance Win32_ComputerSystem; "Model: $($c.Manufacturer) $($c.Model); RAM: $([math]::Round($c.TotalPhysicalMemory/1GB,1)) GiB; HypervisorPresent: $($c.HypervisorPresent)"'
        section "Memory modules (Speed = rated MT/s, ConfiguredClockSpeed = running MT/s)"
        pwsh 'Get-CimInstance Win32_PhysicalMemory | Select-Object BankLabel,DeviceLocator,Manufacturer,PartNumber,@{n="GiB";e={$_.Capacity/1GB}},Speed,ConfiguredClockSpeed,SMBIOSMemoryType | Format-Table -AutoSize | Out-String -Width 220'
        echo "Theoretical peak DRAM bandwidth = channels x MT/s x 8 B / 1000 (desktop/laptop: usually 2 channels)."
        echo "Set PEAK_GBPS=<value> before run_all.sh to enable the peak sanity check."
        section "Power / frequency policy"
        { MSYS2_ARG_CONV_EXCL='*' powercfg.exe -getactivescheme 2>/dev/null || echo "powercfg unavailable"; } | tr -d '\r'
        for s in PERFBOOSTMODE PROCTHROTTLEMIN PROCTHROTTLEMAX; do
            v="$(powercfg_ac "$s")"
            echo "$s (AC): ${v:-n/a}  $( [ -n "$v" ] && printf '(%d)' "$v" || true)"
        done
        echo "PERFBOOSTMODE: 0 = boost disabled, 2 = aggressive (default). PROCTHROTTLE*: % of max clock."
        pwsh '$p = Get-CimInstance Win32_Processor; "Win32_Processor: CurrentClockSpeed=$($p.CurrentClockSpeed) MHz MaxClockSpeed=$($p.MaxClockSpeed) MHz"'
        section "Virtualisation-based security (Hyper-V under Windows changes timing and can block counters)"
        pwsh '$g = Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard; "VBS status: $($g.VirtualizationBasedSecurityStatus) (0 off, 1 enabled not running, 2 running); services running: $($g.SecurityServicesRunning -join ",")"'
        section "Large pages"
        echo "admin terminal: $(si --is-admin)"
        echo "large pages: $(si --large-pages-check)"
        section "Pinning / isolation"
        echo "measurement CPU=$CPU  bandwidth CPUS=$CPUS  generators=$OTHERS  NUMA node=$NODE"
        echo "process priority: ${CMP_PRIORITY:-normal} (export CMP_PRIORITY=high for HIGH_PRIORITY_CLASS)"
        echo "Windows has no isolcpus: close other programs; Task Manager shows background load."
        section "Tools"
        echo "build: $(rd "$BIN/BUILD_INFO" | tr '\n' ' ')"
        (g++ --version 2>/dev/null | head -1) || true
        (make --version 2>/dev/null | head -1) || true
        echo "MSYS2: $(uname -a)"
        { pacman -Q 2>/dev/null || true; } | { grep -E 'ucrt-x86_64-(gcc|python|python-numpy|python-pandas|python-matplotlib) ' || true; }
        "$PY" --version 2>&1 || true
        "$PY" -c 'import numpy, pandas, matplotlib; print("numpy", numpy.__version__, "pandas", pandas.__version__, "matplotlib", matplotlib.__version__)' 2>/dev/null || echo "python libs missing"
        if [ -n "$UPROF_CLI" ]; then
            echo "AMD uProf: $UPROF_CLI (event sets: $UPROF_SETS)"
            { MSYS2_ARG_CONV_EXCL='*' "$UPROF_CLI" --version 2>&1 || true; } | tr -d '\r' | head -2
        else
            echo "AMD uProf: not found (counters will be NaN). Install it, or set UPROF_CLI=/c/path/to/AMDuProfCLI.exe"
        fi
        echo "counters: $COUNTERS"
        section "Load at start"
        pwsh '"CPU load: $((Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average)%"'
    else
        section "OS / kernel"; uname -a; rd /etc/os-release | head -4; echo "cmdline: $(rd /proc/cmdline)"
        section "Memory"; rd /proc/meminfo | head -5
        if command -v dmidecode >/dev/null 2>&1 && [ "$(id -u)" = 0 ]; then
            dmidecode -t memory | grep -E 'Size:|Speed:|Type:|Locator:|Rank' | grep -v 'No Module' || true
        else
            echo "DIMM details: run 'sudo dmidecode -t memory' (speed/channels give theoretical peak bandwidth)"
        fi
        section "NUMA"; (command -v numactl >/dev/null && numactl --hardware) || echo "numactl not installed"
        section "Frequency policy"
        echo "driver:   $(rd /sys/devices/system/cpu/cpu"$CPU"/cpufreq/scaling_driver)"
        echo "governor: $(rd /sys/devices/system/cpu/cpu"$CPU"/cpufreq/scaling_governor)"
        echo "intel no_turbo: $(rd /sys/devices/system/cpu/intel_pstate/no_turbo)   cpufreq boost: $(rd /sys/devices/system/cpu/cpufreq/boost)"
        section "SMT"; echo "control: $(rd /sys/devices/system/cpu/smt/control)  active: $(rd /sys/devices/system/cpu/smt/active)"
        section "Huge pages"
        echo "THP enabled: $(rd /sys/kernel/mm/transparent_hugepage/enabled)"
        echo "nr_hugepages (2M hugetlbfs): $(rd /proc/sys/vm/nr_hugepages)"
        section "Isolation / pinning plan"
        echo "isolcpus: $(grep -o 'isolcpus=[^ ]*' /proc/cmdline || echo none)"
        echo "measurement CPU=$CPU  bandwidth CPUS=$CPUS  generators=$OTHERS  NUMA node=$NODE  NUMACTL='${NUMACTL}'"
        section "Tools"
        echo "build: $(rd "$BIN/BUILD_INFO" | tr '\n' ' ')"
        (g++ --version 2>/dev/null | head -1) || true
        "$PY" --version 2>&1 || true
        "$PY" -c 'import numpy, pandas, matplotlib; print("numpy", numpy.__version__, "pandas", pandas.__version__, "matplotlib", matplotlib.__version__)' 2>/dev/null || echo "python libs missing"
        echo "perf_event_paranoid: $(rd /proc/sys/kernel/perf_event_paranoid)"
        section "Virtualisation"; (systemd-detect-virt 2>/dev/null || grep -m1 -o hypervisor /proc/cpuinfo || echo "none detected")
        section "Load at start"; (uptime 2>/dev/null || true)
    fi
} > "$TXT" 2>&1

if is_windows; then
    POLICY="$({ MSYS2_ARG_CONV_EXCL='*' powercfg.exe -getactivescheme 2>/dev/null || true; } | tr -d '\r' | sed -n 's/.*(\(.*\)).*/\1/p')"
    BOOST="$(powercfg_ac PERFBOOSTMODE)"
    GOV="plan=${POLICY:-?} boost=$( [ -n "$BOOST" ] && printf '%d' "$BOOST" || echo '?')"
    OSV="$(pwsh '$o = Get-CimInstance Win32_OperatingSystem; "$($o.Caption) build $($o.BuildNumber)"')"
    OSV="${OSV:-$(si --os)}"
    PAGES="large pages $( [ "$HUGE_OK" = 1 ] && echo ok || echo unavailable)"
else
    GOV="$(rd /sys/devices/system/cpu/cpu"$CPU"/cpufreq/scaling_governor)"
    OSV="$(uname -r)"
    PAGES="thp $(rd /sys/kernel/mm/transparent_hugepage/enabled | grep -oE '\[[a-z]+\]' | tr -d '[]')"
fi
{
    echo "cpu_model=$(si --brand)"
    echo "cpu_vendor=$(si --vendor)"
    echo "os_family=$CMP_OS"
    echo "cpu=$CPU"; echo "cpus=$CPUS"; echo "nt=$NT"; echo "node=$NODE"
    echo "nominal_ghz=$NOMINAL"
    echo "governor=$GOV"
    echo "smt=$SMT"
    echo "thp=$PAGES"
    echo "huge_mode=$HUGE_MODE"
    echo "kernel=$OSV"
    echo "compiler=$(sed -n 4p "$BIN/BUILD_INFO" 2>/dev/null || true)"
    echo "counters=$COUNTERS"
    echo "quick=$QUICK"; echo "reps=$REPS"; echo "ms=$MS"
    echo "peak_gbps=${PEAK_GBPS:-}"
} > "$ENV"
log "wrote $TXT, $ENV, $CACHES"

# Loud warnings for things that invalidate measurements
if is_windows; then
    [ "$HUGE_OK" = 1 ] || log "WARNING: large pages unavailable - huge-page comparisons will be skipped (see scripts/setup_env.sh)"
    [ "$COUNTERS" = uprof ] || log "WARNING: no AMD uProf - cache/TLB counter columns will be NaN"
    [ "${BOOST:-}" = "0x00000000" ] || log "WARNING: processor boost is on - run scripts/setup_env.sh for stable clocks"
else
    gov="$(rd /sys/devices/system/cpu/cpu"$CPU"/cpufreq/scaling_governor)"
    [ "$gov" != "performance" ] && [ "$gov" != "n/a" ] && log "WARNING: governor is '$gov' (not performance). See scripts/setup_env.sh"
    grep -q hypervisor /proc/cpuinfo && log "WARNING: running in a VM: vCPU pinning is not physical pinning and the PMU may be hidden"
fi
true
