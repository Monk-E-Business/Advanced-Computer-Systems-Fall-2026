"""Shared parsing utilities: fio JSON (+meta sidecar) -> flat records, summary
statistics across repetitions, knee detection, fio log parsing.

Units used everywhere downstream:
  latency  -> microseconds (us)
  throughput -> MB/s (10^6 bytes/s) and IOPS
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "data" / "raw"
PROC = REPO / "data" / "processed"
PLOTS = REPO / "plots"

PCTS = ["50", "90", "95", "99", "99.9", "99.99"]
T95 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
       8: 2.306, 9: 2.262, 10: 2.228}


def current_run(run: str | None) -> str:
    if run:
        return run
    p = RAW / "CURRENT_RUN"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace").strip()
    runs = sorted(d.name for d in RAW.iterdir() if d.is_dir())
    if not runs:
        raise SystemExit("no runs under data/raw")
    return runs[-1]


def to_bytes(s: str) -> int:
    s = str(s).strip().lower()
    m = re.fullmatch(r"([\d.]+)\s*([kmgt]?)i?b?", s)
    if not m:
        return int(float(s))
    mult = {"": 1, "k": 1 << 10, "m": 1 << 20, "g": 1 << 30, "t": 1 << 40}[m.group(2)]
    return int(float(m.group(1)) * mult)


def load_fio_json(path: str | Path) -> dict:
    txt = Path(path).read_text(encoding="utf-8", errors="replace")
    i = txt.find("{")           # fio may print warnings before the JSON body
    return json.loads(txt[i:])


def _lat_block(d: dict) -> dict:
    """Return the latency dict that carries percentiles (lat_ns with
    lat_percentiles=1, else clat_ns)."""
    for key in ("lat_ns", "clat_ns"):
        b = d.get(key) or {}
        if b.get("percentile") or b.get("bins"):
            return b
    return d.get("lat_ns") or d.get("clat_ns") or {}


def _pct(block: dict, p: str) -> float:
    pc = block.get("percentile") or {}
    for k, v in pc.items():
        if abs(float(k) - float(p)) < 1e-6:
            return v / 1e3
    return math.nan


def _diskstats(meta: dict):
    try:
        b = [int(x) for x in meta["diskstats_before"].split()]
        a = [int(x) for x in meta["diskstats_after"].split()]
    except (KeyError, ValueError):
        return math.nan, math.nan, math.nan, math.nan
    return a[0] - b[0], a[1] - b[1], a[2] - b[2], a[3] - b[3]   # counters are in bytes


def record_from_files(meta_path: Path) -> dict | None:
    meta = json.loads(meta_path.read_text(encoding="utf-8", errors="replace"))
    jpath = Path(str(meta_path).replace(".meta.json", ".json"))
    if not jpath.exists():
        return None
    fj = load_fio_json(jpath)
    job = fj["jobs"][0]
    rec = dict(meta)
    rec["file"] = str(jpath.relative_to(REPO))
    rec["fio_error"] = job.get("error", 0)
    tot_ios, lat_sum = 0, 0.0
    for d, tag in (("read", "r"), ("write", "w")):
        dd = job.get(d, {})
        lb = _lat_block(dd)
        ios = dd.get("total_ios", 0) or 0
        rec[f"iops_{tag}"] = dd.get("iops", 0.0)
        rec[f"bw_{tag}_MBps"] = dd.get("bw_bytes", 0) / 1e6
        rec[f"io_bytes_{tag}"] = dd.get("io_bytes", 0)
        rec[f"ios_{tag}"] = ios
        mean = lb.get("mean", math.nan) / 1e3 if lb else math.nan
        rec[f"lat_mean_{tag}_us"] = mean if ios else math.nan
        rec[f"lat_std_{tag}_us"] = lb.get("stddev", math.nan) / 1e3 if (lb and ios) else math.nan
        rec[f"lat_max_{tag}_us"] = lb.get("max", math.nan) / 1e3 if (lb and ios) else math.nan
        for p in PCTS:
            rec[f"p{p}_{tag}_us"] = _pct(lb, p) if ios else math.nan
        if ios and not math.isnan(mean):
            tot_ios += ios
            lat_sum += ios * mean
    rec["iops"] = rec["iops_r"] + rec["iops_w"]
    rec["bw_MBps"] = rec["bw_r_MBps"] + rec["bw_w_MBps"]
    rec["lat_mean_us"] = lat_sum / tot_ios if tot_ios else math.nan
    # the dominant direction's percentiles as the headline columns
    dom = "r" if rec["ios_r"] >= rec["ios_w"] else "w"
    for p in PCTS:
        rec[f"p{p}_us"] = rec[f"p{p}_{dom}_us"]
    rec["cpu_usr"] = job.get("usr_cpu", math.nan)
    rec["cpu_sys"] = job.get("sys_cpu", math.nan)
    # effective queue depth: configured vs Little's law (L = lambda * W)
    qd_cfg = float(meta.get("QD_TOTAL") or (float(meta.get("qd", 1)) * float(meta.get("nj", 1))))
    rec["qd_cfg"] = qd_cfg
    rec["qd_little"] = rec["iops"] * rec["lat_mean_us"] / 1e6
    # kernel accounting for the device the I/O should land on
    r_ios, r_b, w_ios, w_b = _diskstats(meta)
    rec["dev_read_bytes"], rec["dev_write_bytes"] = r_b, w_b
    fio_b = rec["io_bytes_r"] + rec["io_bytes_w"]
    rt, ramp = float(meta.get("runtime", 0) or 0), float(meta.get("ramp", 0) or 0)
    rec["dev_bytes_ratio"] = ((r_b + w_b) / fio_b) if (fio_b and not math.isnan(r_b)) else math.nan
    rec["dev_bytes_ratio_expected"] = (rt + ramp) / rt if rt else 1.0
    rec["bs_bytes"] = to_bytes(meta.get("bs", "4k"))
    return rec


def load_runs(run: str, experiment: str | None = None) -> pd.DataFrame:
    base = RAW / run
    pat = f"{experiment}/*.meta.json" if experiment else "*/*.meta.json"
    recs = []
    for m in sorted(base.glob(pat)):
        r = record_from_files(m)
        if r is not None:
            recs.append(r)
    df = pd.DataFrame(recs)
    if not df.empty:
        for c in ("qd", "nj", "rwmixread", "rep"):
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def summarize(df: pd.DataFrame, keys=("experiment", "point")) -> pd.DataFrame:
    """Mean, std, n and 95% CI half-width (Student t) across repetitions."""
    num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c not in ("rep",)]
    const = [c for c in df.columns if c not in num and c not in keys
             and c not in ("rep", "timestamp", "file", "diskstats_before", "diskstats_after",
                           "temp_before_c", "temp_after_c")]
    g = df.groupby(list(keys), sort=False)
    out = g[num].mean()
    std = g[num].std(ddof=1)
    n = g.size()
    out["n_reps"] = n
    for c in ("iops", "bw_MBps", "lat_mean_us", "p99_us", "p99.9_us", "p95_us", "qd_little"):
        if c in std:
            t = n.map(lambda k: T95.get(int(k) - 1, 1.96) if k > 1 else math.nan)
            out[f"{c}_std"] = std[c]
            out[f"{c}_ci95"] = t * std[c] / np.sqrt(n)
    first = g[const].first()
    return pd.concat([first, out], axis=1).reset_index()


def knee(qd, thr, lat):
    """Knee of a throughput-latency curve.
    Primary: argmax of Kleinrock's 'power' P = X/R (throughput per unit delay) --
    the operating point beyond which extra queueing buys proportionally less
    throughput than it costs in latency. Secondary (reported): first QD where
    doubling QD gives <10% more throughput but >=50% more latency."""
    qd, thr, lat = map(np.asarray, (qd, thr, lat))
    o = np.argsort(qd)
    qd, thr, lat = qd[o], thr[o], lat[o]
    power = thr / lat
    k_power = qd[int(np.nanargmax(power))]
    k_marg = None
    for i in range(1, len(qd)):
        dthr = thr[i] / thr[i - 1] - 1
        dlat = lat[i] / lat[i - 1] - 1
        if dthr < 0.10 and dlat >= 0.50:
            k_marg = qd[i - 1]
            break
    return int(k_power), (int(k_marg) if k_marg is not None else None)


def read_fio_log(prefix: str, kind: str) -> pd.DataFrame:
    """fio per-interval logs: <prefix>_<kind>.<jobno>.log  rows: time_ms, value,
    ddir, bs, offset[, prio]. Aggregates jobs per 1s bucket (sum for bw/iops,
    mean for lat)."""
    frames = []
    for f in sorted(glob.glob(f"{prefix}_{kind}.*.log")):
        d = pd.read_csv(f, header=None, usecols=[0, 1, 2], names=["t_ms", "v", "ddir"],
                        skipinitialspace=True)
        d["job"] = f
        frames.append(d)
    if not frames:
        return pd.DataFrame(columns=["t_s", "value"])
    d = pd.concat(frames)
    d["t_s"] = (d["t_ms"] / 1000).round().astype(int)
    agg = "mean" if kind in ("lat", "clat", "slat") else "sum"
    per_job = d.groupby(["job", "t_s"])["v"].mean().reset_index()
    out = per_job.groupby("t_s")["v"].agg(agg).reset_index().rename(columns={"v": "value"})
    return out


def hist_from_bins(block: dict):
    """json+ latency histogram -> (lat_us sorted, counts)"""
    bins = block.get("bins") or {}
    if not bins:
        return None, None
    items = sorted((int(k), v) for k, v in bins.items())
    lat = np.array([k for k, _ in items], dtype=float) / 1e3
    cnt = np.array([v for _, v in items], dtype=float)
    return lat, cnt
