#!/usr/bin/env python3
"""Correctness & sanity checks -> data/processed/<run>/validation.{csv,md}

 V1 integrity       fio crc32c write+verify finished with error=0
 V2 reference       ref_qd1 (g++, one unbuffered I/O at a time) vs fio at QD=1
                    (async engine; on Linux also psync): mean latency and IOPS agree
 V3 dd              dd unbuffered 128KiB sequential read MB/s vs fio QD1 read (if dd ran)
 V4 Little's law    IOPS x mean latency ~= configured total queue depth
 V5 device bytes    OS I/O counters for the volume/device (Windows IOCTL_DISK_PERFORMANCE,
                    Linux /proc/diskstats) ~= fio's bytes x (runtime+ramp)/runtime
                    (catches file-cache hits, writes not reaching the device, hidden writes)
 V6 ceiling         no throughput above the PCIe link's raw ceiling
Runs in the 'misleading' experiment are EXPECTED to fail V4/V5 -- that failure
is the evidence the demo is built on, so they are labelled 'expected-fail'.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from fiolib import PROC, RAW, current_run, load_runs  # noqa: E402

TOL_REF_READ, TOL_REF_WRITE = 0.10, 0.20
TOL_LITTLE, TOL_DD = 0.15, 0.15


def status(ok, warn=False):
    return "PASS" if ok else ("WARN" if warn else "FAIL")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    run = current_run(ap.parse_args().run)
    raw = RAW / run
    out = PROC / run
    out.mkdir(parents=True, exist_ok=True)
    df = load_runs(run)
    rows = []

    # V1
    v = df[(df.experiment == "validation") & (df.point == "verify_crc32c")]
    if len(v):
        rows.append(dict(check="V1 integrity (crc32c verify)", item="verify_crc32c",
                         value=f"error={int(v.fio_error.iloc[0])}", expected="error=0",
                         status=status(int(v.fio_error.iloc[0]) == 0)))

    # V2
    val = df[df.experiment == "validation"]
    for refj in sorted((raw / "validation").glob("ref_*_rep*.json")):
        m = re.match(r"ref_(\w+?)_(\d+[km])_rep(\d+)\.json", refj.name)
        if not m:
            continue
        rw, bs, rep = m.group(1), m.group(2), int(m.group(3))
        ref = json.loads(refj.read_text(encoding="utf-8", errors="replace"))
        tol = TOL_REF_WRITE if "write" in rw else TOL_REF_READ
        for variant in sorted(val["VARIANT"].dropna().unique()) if "VARIANT" in val else []:
            f = val[(val.rw == rw) & (val.bs == bs) & (val.rep == rep) & (val.VARIANT == variant)]
            if f.empty:
                continue
            f = f.iloc[0]
            d_lat = f.lat_mean_us / ref["lat_mean_us"] - 1
            d_iops = f.iops / ref["iops"] - 1
            ok = abs(d_lat) <= tol and abs(d_iops) <= tol
            rows.append(dict(check="V2 fio vs reference (QD1)", item=f"{rw} {bs} rep{rep} [{variant}]",
                             value=f"lat {f.lat_mean_us:.1f} vs {ref['lat_mean_us']:.1f} us ({d_lat:+.1%}); "
                                   f"IOPS {f.iops:.0f} vs {ref['iops']:.0f} ({d_iops:+.1%})",
                             expected=f"within ±{tol:.0%}", status=status(ok, abs(d_lat) <= 2 * tol)))

    # V3
    ddf = raw / "validation" / "dd_read_128k.txt"
    if ddf.exists():
        txt = ddf.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"copied, ([\d.]+) s, ([\d.]+) ([kMG])B/s", txt)
        f = val[(val.rw == "read") & (val.bs == "128k") & val.point.str.startswith("fio_")] if len(val) else val
        if m and len(f):
            secs = float(m.group(1))
            nbytes = int(re.search(r"(\d+) bytes", txt).group(1))
            dd_mbps = nbytes / secs / 1e6
            fio_mbps = f.bw_MBps.mean()
            d = fio_mbps / dd_mbps - 1
            rows.append(dict(check="V3 dd unbuffered seq read", item="read 128k QD1",
                             value=f"fio {fio_mbps:.0f} vs dd {dd_mbps:.0f} MB/s ({d:+.1%})",
                             expected=f"within ±{TOL_DD:.0%}", status=status(abs(d) <= TOL_DD, abs(d) <= 2 * TOL_DD)))

    # V4 / V5 for every measured run
    meas = df[~df.experiment.isin(["precondition", "steady_state"]) & (df.point != "verify_crc32c")]
    for _, r in meas.iterrows():
        exp_fail = r.experiment == "misleading"
        if r.get("ioengine") not in ("psync", "sync", "pvsync") or r.qd_cfg == 1 or exp_fail:
            dev = r.qd_little / r.qd_cfg - 1 if r.qd_cfg else math.nan
            ok = abs(dev) <= TOL_LITTLE
            rows.append(dict(check="V4 Little's law", item=f"{r.experiment}/{r.point} rep{int(r.rep)}",
                             value=f"IOPS×W = {r.qd_little:.2f} vs QD {r.qd_cfg:.0f} ({dev:+.0%})",
                             expected=f"within ±{TOL_LITTLE:.0%}",
                             status=("expected-fail" if (exp_fail and not ok) else status(ok, abs(dev) <= 0.3))))
        if not math.isnan(r.dev_bytes_ratio):
            lo, hi = 0.9, r.dev_bytes_ratio_expected * 1.25 + 0.05
            ok = lo <= r.dev_bytes_ratio <= hi
            rows.append(dict(check="V5 device bytes (OS counters)", item=f"{r.experiment}/{r.point} rep{int(r.rep)}",
                             value=f"device/fio bytes = {r.dev_bytes_ratio:.2f}",
                             expected=f"{lo:.2f}–{hi:.2f}",
                             status=("expected-fail" if (exp_fail and not ok) else status(ok))))

    # V6
    si = raw / "sysinfo" / "sysinfo.json"
    ceiling = None
    if si.exists():
        ceiling = json.loads(si.read_text(encoding="utf-8", errors="replace")).get("pcie_raw_ceiling_GBps")
    if ceiling:
        mx = meas[meas.experiment != "misleading"]
        worst = mx.loc[mx.bw_MBps.idxmax()]
        ok = worst.bw_MBps / 1e3 <= ceiling
        rows.append(dict(check="V6 interface ceiling", item=f"{worst.experiment}/{worst.point}",
                         value=f"{worst.bw_MBps/1e3:.2f} GB/s vs link {ceiling:.2f} GB/s",
                         expected="≤ ceiling", status=status(ok)))

    res = pd.DataFrame(rows)
    res.to_csv(out / "validation.csv", index=False)
    counts = res.status.value_counts().to_dict() if len(res) else {}
    with open(out / "validation.md", "w", encoding="utf-8") as fh:
        fh.write(f"# Validation — {run}\n\nSummary: {counts}\n\n")
        # collapse the per-run V4/V5 rows into a compact view: show failures + one line per check
        for chk, g in res.groupby("check", sort=False):
            fh.write(f"## {chk}\n\n")
            show = g if len(g) <= 12 else g[g.status != "PASS"]
            if len(g) > 12:
                fh.write(f"{(g.status=='PASS').sum()} of {len(g)} runs PASS; non-passing rows:\n\n")
            if len(show):
                fh.write(show[["item", "value", "expected", "status"]].to_markdown(index=False) + "\n\n")
    print(f"validation: {counts}  -> {out/'validation.md'}")


if __name__ == "__main__":
    main()
