#!/usr/bin/env python3
"""Record the measurement environment: hardware, OS, compiler, frequency policy, SMT, pinning.

usage: python scripts/sysinfo.py <results_dir> [--cpu N]
Writes <results_dir>/sysinfo.json and <results_dir>/sysinfo.txt.

Works natively on Windows (MSYS2 UCRT64) and on Linux:
  * topology / caches / CPU brand / timer: `bench --sysinfo` (Windows API or sysfs, see src/platform.hpp)
  * Windows: CPU name, cores, clock, OS build, active power plan via PowerShell (CIM) and powercfg
  * Linux:   lscpu, cpufreq governor, turbo, SMT control, THP, isolcpus
Anything that cannot be read is recorded as "unavailable: <why>" instead of being omitted.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time

from simdlib import BUILD, IS_WINDOWS, ROOT, bench_path, uopen, variants


def run(cmd, timeout=60, stdin_text=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                           input=stdin_text)
        out = (r.stdout or "").replace("\r", "").strip()
        return out if r.returncode == 0 and out else f"unavailable: {(r.stderr or out or 'rc=' + str(r.returncode)).strip()[:200]}"
    except Exception as e:  # noqa: BLE001
        return f"unavailable: {e}"


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:  # noqa: BLE001
        return f"unavailable: {path} not readable"


def powershell():
    ps = shutil.which("powershell") or shutil.which("powershell.exe")
    if not ps:
        root = os.environ.get("SystemRoot", r"C:\Windows")
        cand = os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        ps = cand if os.path.exists(cand) else None
    return ps


def windows_info():
    ps = powershell()
    info = {}
    if ps:
        cmd = ("$c=Get-CimInstance Win32_Processor | Select-Object -First 1; $o=Get-CimInstance Win32_OperatingSystem; "
               "$b=Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue; "
               "[pscustomobject]@{cpu=$c.Name; cores=$c.NumberOfCores; logical=$c.NumberOfLogicalProcessors; "
               "max_mhz=$c.MaxClockSpeed; current_mhz=$c.CurrentClockSpeed; l2_kb=$c.L2CacheSize; l3_kb=$c.L3CacheSize; "
               "os=$o.Caption; build=$o.BuildNumber; ram_gb=[math]::Round($o.TotalVisibleMemorySize/1MB,1); "
               "battery=($b -ne $null); on_ac=(($b -eq $null) -or ($b.BatteryStatus -eq 2))} | ConvertTo-Json -Compress")
        out = run([ps, "-NoProfile", "-NonInteractive", "-Command", cmd])
        try:
            info = json.loads(out)
        except Exception:  # noqa: BLE001
            info = {"error": out}
    else:
        info = {"error": "powershell.exe not found"}
    info["power_plan"] = run(["powercfg", "/getactivescheme"]) if shutil.which("powercfg") else run(
        [os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "powercfg.exe"), "/getactivescheme"])
    return info


def main():
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    want_cpu = int(sys.argv[sys.argv.index("--cpu") + 1]) if "--cpu" in sys.argv else None

    native = "native" if os.path.isdir(os.path.join(BUILD, "native")) else variants()[0][0]
    topo = json.loads(run([bench_path(native), "--sysinfo"]))
    cpu = want_cpu if want_cpu is not None else topo["suggested_cpu"]
    ghz = []
    for _ in range(3):
        try:
            ghz.append(float(run([bench_path(native), "--cpu", str(cpu), "--ghz"])))
        except ValueError:
            pass
    macros = run(["g++", "-march=native", "-dM", "-E", "-x", "c++", "-"], stdin_text="")
    isa = ["SSE2", "SSE4_2", "AVX", "AVX2", "FMA", "AVX512F", "AVX512VL", "AVX512BW", "AVX512DQ", "AVX512VNNI",
           "AVX512FP16", "AVX512BF16", "AMX_TILE"]
    info = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "hostname": platform.node(),
        "platform": "windows" if IS_WINDOWS else sys.platform,
        "msystem": os.environ.get("MSYSTEM", "none"),
        "cpu_model": topo["cpu_brand"],
        "arch": platform.machine(),
        "logical_cpus": topo["logical_cpus"],
        "physical_cores": topo["physical_cores"],
        "smt_active": bool(topo["smt"]),
        "hybrid_cpu": bool(topo["hybrid"]),
        "top_class_cpus": topo["top_class_cpus"],
        "caches": {k: {"bytes": v} for k, v in topo["caches"].items()},
        "pinned_cpu": cpu,
        "timer": f"{topo['timer']}, resolution {topo['timer_resolution_ns']:.1f} ns",
        "measured_ghz_dependent_add_chain": ghz,
        "isa_flags": {f.lower(): f"#define __{f}__ 1" in macros for f in isa},
        "compiler": read(os.path.join(BUILD, "compiler.txt")),
        "variants": {n: f for n, f in variants()},
        "python": platform.python_version(),
    }
    raw_text = ""
    if IS_WINDOWS:
        w = windows_info()
        info.update({
            "os": f"{w.get('os', platform.platform())} (build {w.get('build', '?')})",
            "kernel": platform.version(),
            "wsl2": False,
            "hypervisor": "n/a (native Windows)",
            "frequency_policy": "Windows power plan: " + str(w.get("power_plan", "?")),
            "on_ac_power": w.get("on_ac", "?"),
            "cpu_max_mhz_reported": w.get("max_mhz", "?"),
            "windows_host": w,
            "isolation": "none (Windows); process priority class HIGH while pinned",
            "perf": "not available on Windows (use Intel VTune / AMD uProf for counters)",
            "mem_total": f"{w.get('ram_gb', '?')} GB",
        })
        if w.get("cpu"):
            info["cpu_model"] = w["cpu"].strip()
        raw_text = json.dumps(w, indent=2)
    else:
        lscpu = run(["lscpu"])
        hyper = re.search(r"Hypervisor vendor:\s*(.+)", lscpu)
        gov = f"/sys/devices/system/cpu/cpu{cpu}/cpufreq"
        procver = read("/proc/version")
        info.update({
            "os": (re.search(r'PRETTY_NAME="([^"]+)"', read("/etc/os-release")) or [None, platform.platform()])[1],
            "kernel": platform.release(),
            "wsl2": "microsoft" in procver.lower(),
            "hypervisor": hyper.group(1).strip() if hyper else "none reported",
            "frequency_policy": f"governor: {read(gov + '/scaling_governor')}; no_turbo: "
                                f"{read('/sys/devices/system/cpu/intel_pstate/no_turbo')}",
            "smt_control": read("/sys/devices/system/cpu/smt/control"),
            "isolation": f"isolcpus: {read('/sys/devices/system/cpu/isolated') or 'none'}",
            "thp": read("/sys/kernel/mm/transparent_hugepage/enabled"),
            "perf": run(["perf", "--version"]) if shutil.which("perf") else "not installed",
            "mem_total": (re.search(r"MemTotal:\s*(.+)", read("/proc/meminfo")) or [None, "?"])[1],
        })
        raw_text = "### lscpu\n" + lscpu + "\n\n### uname -a\n" + run(["uname", "-a"])
    for mod in ("numpy", "pandas", "matplotlib"):
        try:
            info[mod] = __import__(mod).__version__
        except Exception:  # noqa: BLE001
            info[mod] = "not installed"
    with uopen(os.path.join(outdir, "sysinfo.json"), "w") as f:
        json.dump(info, f, indent=2)
    with uopen(os.path.join(outdir, "sysinfo.txt"), "w") as f:
        f.write(raw_text + "\n\n### compiler\n" + info["compiler"] + "\n\n### g++ -v\n" + run(["g++", "-v"]) + "\n")
    c = topo["caches"]
    print(f"[sysinfo] {info['cpu_model']} | {info['os']} | L1d {c['L1d'] >> 10} KiB, L2 {c['L2'] >> 10} KiB, "
          f"L3 {c['L3'] >> 20} MiB | SMT={info['smt_active']} hybrid={info['hybrid_cpu']} | pin CPU {cpu} | "
          f"~{max(ghz) if ghz else '?'} GHz")
    print(f"[sysinfo] frequency policy: {info['frequency_policy'][:120]}")
    if info["hybrid_cpu"]:
        print(f"[sysinfo] hybrid CPU: performance-core logical CPUs = {info['top_class_cpus']}; pinned to {cpu}")


if __name__ == "__main__":
    main()
