"""Shared helpers for process.py and plot.py."""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = Path(os.environ.get("RAW", ROOT / "data" / "raw"))
PROC = Path(os.environ.get("PROC", ROOT / "data" / "processed"))
FIG = Path(os.environ.get("FIG", ROOT / "figures"))
PROC.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

HUGE_MODES = ("large", "thp", "hugetlb")  # Windows large pages, Linux THP, Linux hugetlbfs
PAGE_LABEL = {"4k": "4 KB pages", "large": "2 MB large pages", "thp": "2 MB pages (THP)", "hugetlb": "2 MB pages (hugetlbfs)"}


def huge_mode(modes) -> str | None:
    """The huge-page mode present in a set of page-mode names, if any."""
    for m in HUGE_MODES:
        if m in set(modes):
            return m
    return None


def counter_hint(env: dict) -> str:
    """How to get hardware counters on this system (for 'unavailable' messages)."""
    if env.get("os_family") == "windows":
        if "AMD" in env.get("cpu_vendor", ""):
            return "install AMD uProf and run scripts/uprof_probe.sh (counters come from AMDuProfCLI; turn Memory integrity off)"
        return "Windows has no built-in counter API: use Intel VTune / AMD uProf, or Linux"
    return "enable with `sudo sysctl kernel.perf_event_paranoid=1` on bare metal (VMs usually hide the PMU)"


PERF = ["cycles", "instructions", "l1d_miss", "llc_ref", "llc_miss", "dtlb_ref", "dtlb_miss"]
LINE = 64


def load(name: str) -> pd.DataFrame | None:
    """Load data/raw/<name>.csv, or None if missing/empty."""
    p = RAW / f"{name}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    return df if len(df) else None


def load_proc(name: str) -> pd.DataFrame | None:
    p = PROC / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else None


def sysenv() -> dict:
    env = {}
    p = RAW / "sysinfo.env"
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def caches() -> dict:
    """{'L1': bytes, 'L2': bytes, 'L3': bytes} for the measurement CPU."""
    out = {}
    p = RAW / "caches.csv"
    if not p.exists():
        return out
    df = pd.read_csv(p)
    for _, r in df.iterrows():
        if str(r["type"]).lower() in ("data", "unified"):
            out[f"L{int(r['level'])}"] = int(r["size_bytes"])
    return out


_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
         9: 2.262, 10: 2.228, 12: 2.179, 15: 2.131, 20: 2.086, 25: 2.060, 30: 2.042}


def t975(dof: int) -> float:
    """Two-sided 95% Student-t critical value."""
    if dof <= 0:
        return float("nan")
    if dof in _T975:
        return _T975[dof]
    keys = sorted(_T975)
    for k in keys:
        if k > dof:
            return _T975[k]
    return 1.96


def agg(df: pd.DataFrame, keys: list[str], vals: list[str]) -> pd.DataFrame:
    """Per-configuration statistics over repetitions: mean, std, median, min,
    max, n and the 95% CI half-width (t-distribution) for each value column."""
    vals = [v for v in vals if v in df.columns]
    g = df.groupby(keys, dropna=False, sort=False)
    parts = []
    for v in vals:
        s = g[v].agg(["mean", "std", "median", "min", "max", "count"])
        s.columns = [f"{v}_{c}" if c != "count" else f"{v}_n" for c in s.columns]
        n = s[f"{v}_n"]
        s[f"{v}_ci95"] = [t975(int(k) - 1) * sd / math.sqrt(k) if k > 1 else float("nan")
                          for k, sd in zip(n, s[f"{v}_std"])]
        parts.append(s)
    out = pd.concat(parts, axis=1).reset_index()
    return out


def add_per_access(df: pd.DataFrame, denom_col: str, suffix: str = "_pa") -> pd.DataFrame:
    """counter / denom for every perf counter column present."""
    df = df.copy()
    for c in PERF:
        if c in df.columns:
            df[c + suffix] = pd.to_numeric(df[c], errors="coerce") / df[denom_col]
    return df


def has_perf(df: pd.DataFrame | None, col: str = "cycles") -> bool:
    return df is not None and col in df.columns and pd.to_numeric(df[col], errors="coerce").notna().any()


def fmt_bytes(b: float) -> str:
    for unit, div in (("GiB", 1 << 30), ("MiB", 1 << 20), ("KiB", 1 << 10)):
        if b >= div:
            v = b / div
            return f"{v:.0f} {unit}" if v >= 10 or v == int(v) else f"{v:.1f} {unit}"
    return f"{int(b)} B"


def knee(x: np.ndarray, y: np.ndarray) -> int:
    """Kneedle-style knee of an increasing, convex latency-vs-throughput curve:
    the point farthest below the chord after normalising both axes to [0, 1]."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if len(x) < 3:
        return int(np.argmax(x)) if len(x) else 0
    xn = (x - x.min()) / max(x.max() - x.min(), 1e-12)
    yn = (y - y.min()) / max(y.max() - y.min(), 1e-12)
    return int(np.argmax(xn - yn))


def md_table(df: pd.DataFrame, floatfmt: str = ".2f") -> str:
    """Minimal markdown table (no tabulate dependency)."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else format(v, floatfmt))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
