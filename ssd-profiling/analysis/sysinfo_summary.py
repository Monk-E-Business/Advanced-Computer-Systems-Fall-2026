#!/usr/bin/env python3
"""Summarise data/raw/<run>/sysinfo/ into sysinfo.json (one flat dict used by
the plots, the validation (interface ceiling) and the results tables).

usage: sysinfo_summary.py <sysinfo_dir> <platform> <target> <target_kind> <disk_id>
                          <span_bytes> <ioengine> <fio_cpus>
"""
import json
import platform as pyplatform
import re
import sys
from pathlib import Path

out = Path(sys.argv[1])
plat, target, kind, disk_id, span, engine, cpus = sys.argv[2:9]

# PCIe: GT/s per lane by generation, and line-code efficiency
GTS = {1: 2.5, 2: 5.0, 3: 8.0, 4: 16.0, 5: 32.0, 6: 64.0}


def rd(name):
    p = out / name
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def rdjson(name):
    t = rd(name).strip()
    if not t:
        return {}
    try:
        return json.loads(t[t.find("{"):] if "{" in t else t)
    except json.JSONDecodeError:
        return {}


def link_gbps(gts, width):
    """Raw per-direction link bandwidth in GB/s, before TLP/NVMe protocol overhead."""
    if not gts or not width:
        return None
    enc = 8 / 10 if gts <= 5.0 else 128 / 130          # Gen1/2: 8b/10b, Gen3+: 128b/130b
    return round(gts * enc * int(width) / 8, 3)


def last_line(name):
    lines = [x for x in rd(name).splitlines() if x.strip() and not x.startswith("$")]
    return lines[0].strip() if lines else None


info = {
    "platform": plat, "target": target, "target_kind": kind, "span_bytes": int(span), "disk": disk_id,
    "ioengine": engine, "fio_pinning": cpus, "fio": last_line("fio_version.txt"),
    "gxx": last_line("gxx_version.txt"),
}

if plat == "windows":
    w = rdjson("win_sysinfo.json")
    dev = rdjson("device.json")
    info.update({
        "os": w.get("os"),
        "cpu_model": (w.get("cpu_name") or "").strip() or None,
        "cpu_cores": w.get("cpu_cores"), "cpu_logical": w.get("cpu_logical"),
        "smt": (None if not w.get("cpu_cores") else
                ("on" if (w.get("cpu_logical") or 0) > w["cpu_cores"] else "off")),
        "cpu_max_mhz": w.get("cpu_max_mhz"), "ram_bytes": w.get("ram_bytes"),
        "model": dev.get("model"), "firmware": dev.get("firmware"), "bus": dev.get("bus"),
        "disk_size_bytes": dev.get("size_bytes"), "write_cache": dev.get("write_cache"),
        "trim_enabled": dev.get("trim_enabled"), "temp_c_at_start": dev.get("temp_c"),
        "temp_warning_c": dev.get("temp_warning_c"), "temp_critical_c": dev.get("temp_critical_c"),
        "logical_sector": dev.get("logical_sector"), "physical_sector": dev.get("physical_sector"),
        "is_admin": rd("is_admin.txt").strip() == "1",
    })
    plan = re.search(r"GUID:\s*\S+\s*\((.*?)\)", rd("power_plan.txt"))
    info["power_plan"] = plan.group(1) if plan else None
    res = dict(re.findall(r"^(\w+)=(.*)$", rd("target_resolve.txt"), re.M))
    info["filesystem"] = res.get("fs")
    info["cluster_bytes"] = res.get("cluster_bytes")
    info["volume"] = res.get("volume")
    # PCIe link of the disk under test
    for d in w.get("disks", []) or []:
        if str(d.get("index")) == str(disk_id):
            link = d.get("link") or {}
            cur_s, cur_w = link.get("CurrentLinkSpeed"), link.get("CurrentLinkWidth")
            max_s, max_w = link.get("MaxLinkSpeed"), link.get("MaxLinkWidth")
            if cur_s:
                info["pcie_link"] = f"{GTS.get(int(cur_s), '?')} GT/s x{cur_w}"
                info["pcie_link_max"] = f"{GTS.get(int(max_s), '?')} GT/s x{max_w}" if max_s else None
                info["pcie_raw_ceiling_GBps"] = link_gbps(GTS.get(int(cur_s)), cur_w)
    excl = w.get("defender_exclusions") or []
    info["defender_exclusions"] = excl
    vol = (res.get("full_path") or "").lower()
    info["defender_excludes_target"] = any(vol.startswith(str(e).lower().rstrip("\\")) for e in excl if e) if excl else None
else:
    dev = dict(re.findall(r"^(\S+)\s+(.*)$", rd("device.txt"), re.M))
    lscpu = dict(re.findall(r"^([^:\n]+):\s+(.*)$", rd("lscpu.txt"), re.M))
    cpu = dict(re.findall(r"^([^:\n]+):\s*(.*)$", rd("cpu_policy.txt"), re.M))
    m = re.search(r"([\d.]+)\s*GT/s", dev.get("current_link_speed", ""))
    width = dev.get("current_link_width", "").strip()
    info.update({
        "os": (re.search(r'PRETTY_NAME="(.*)"', rd("os_release.txt")) or [None, None])[1],
        "kernel": pyplatform.release(), "cpu_model": lscpu.get("Model name"), "cpu_logical": lscpu.get("CPU(s)"),
        "smt": cpu.get("smt_control"), "governor": cpu.get("governor(s)"),
        "model": dev.get("model"), "firmware": dev.get("firmware"), "scheduler": dev.get("scheduler"),
        "write_cache": dev.get("write_cache"),
        "pcie_link": f'{dev.get("current_link_speed", "?")} x{width or "?"}',
        "pcie_raw_ceiling_GBps": link_gbps(float(m.group(1)), width) if (m and width.isdigit()) else None,
    })

(out / "sysinfo.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
print(json.dumps(info, indent=2))
