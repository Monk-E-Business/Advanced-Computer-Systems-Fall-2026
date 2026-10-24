#!/usr/bin/env python3
"""Plots + markdown result tables from data/processed/<run>/.

plots/<run>/
  01_baseline_qd1.png       QD=1 latency (mean, p50, p95, p99, p99.9) for 4 cases
  02_bs_sweep.png           MB/s, IOPS and latency vs block size (same runs)
  03_mix_sweep.png          throughput and read/write latency vs % reads
  04_qd_curve.png           throughput-vs-latency curves with knee + QD labels
  05_littles_law.png        IOPS x mean latency vs configured queue depth
  06_tail_ccdf.png          latency CCDF at QD1 / mid / knee / knee+70:30 mix
  07_working_set.png        4KiB random read vs LBA span
  08_steady_state.png       burst -> steady state time series (+ temperature panel)
  09_misleading.png         buffered vs direct, wrong effective QD, unwritten blocks
docs/results_tables.md      every summary table, regenerated each run
Error bars are 95% confidence intervals across repetitions (Student t).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from fiolib import PLOTS, PROC, RAW, REPO, current_run, knee, to_bytes  # noqa: E402

# categorical slots, fixed order (validated palette; see README "Plot style")
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 160, "font.size": 9, "axes.titlesize": 10,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.6,
    "lines.markersize": 5, "axes.axisbelow": True, "legend.frameon": False, "figure.facecolor": "#fcfcfb",
    "axes.facecolor": "#fcfcfb",
})
SERIES_COLOR = {"randread": C[0], "randwrite": C[1], "read": C[2], "write": C[3]}
TABLES = []


def footer(fig, text):
    fig.text(0.01, -0.02, text, fontsize=7, color=INK2, ha="left", va="top")


def save(fig, out, name):
    fig.savefig(out / name, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", (out / name).relative_to(REPO))


def table(title, df, note=""):
    TABLES.append((title, df, note))


def load(proc, exp):
    p = proc / f"{exp}_summary.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def err(s, col):
    c = f"{col}_ci95"
    if c not in s or not s[c].notna().any():
        return None          # single repetition: no error bar rather than a fake zero
    return s[c].fillna(0).values


def ceiling_gbps(run):
    si = RAW / run / "sysinfo" / "sysinfo.json"
    import os
    override = os.environ.get("INTERFACE_GBPS")
    if override:
        return float(override)
    if si.exists():
        return json.loads(si.read_text(encoding="utf-8", errors="replace")).get("pcie_raw_ceiling_GBps")
    return None


def fixed_note(s, extra=""):
    eng = s["ioengine"].iloc[0] if "ioengine" in s else "?"
    rt = s["runtime"].iloc[0] if "runtime" in s else "?"
    n = int(s["n_reps"].max()) if "n_reps" in s else 1
    plat = s["platform"].iloc[0] if "platform" in s else ""
    return f"{plat} · engine={eng}, unbuffered (direct=1), runtime={rt}s/run, reps={n}, error bars=95% CI. {extra}"


# ---------------------------------------------------------------------------
def plot_baseline(proc, out):
    s = load(proc, "baseline_qd1")
    if s.empty:
        return
    order = ["randread_4k", "randwrite_4k", "read_128k", "write_128k"]
    s = s.set_index("point").reindex([o for o in order if o in set(s.point)]).reset_index()
    stats = [("lat_mean_us", "mean"), ("p50_us", "p50"), ("p95_us", "p95"), ("p99_us", "p99"), ("p99.9_us", "p99.9")]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    x = np.arange(len(s)); w = 0.15
    for i, (col, lab) in enumerate(stats):
        e = err(s, col)
        ax.bar(x + (i - 2) * w, s[col], w * 0.88, color=C[i], label=lab,
               yerr=e, ecolor=INK2, capsize=2, error_kw={"lw": 0.8})
    ax.set_yscale("log"); ax.grid(axis="x", visible=False)
    ax.set_xticks(x, [p.replace("_", " ") for p in s.point])
    ax.set_ylabel("latency (µs, log scale)")
    ax.set_title("QD=1 latency (numjobs=1) — no queueing: pure service time")
    ax.legend(ncol=5, loc="upper left", fontsize=8)
    footer(fig, fixed_note(s))
    save(fig, out, "01_baseline_qd1.png")
    t = s[["point", "iops", "bw_MBps", "lat_mean_us", "lat_mean_us_ci95", "p50_us", "p95_us", "p99_us", "p99.9_us"]]
    table("Zero-queue baselines (QD=1)", t.round(2), "Latency in µs; throughput in MB/s.")


def plot_bs(proc, out, run):
    s = load(proc, "bs_sweep")
    if s.empty:
        return
    s["bsb"] = s["bs"].map(to_bytes)
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.8))
    for rw in ["randread", "randwrite", "read", "write"]:
        d = s[s.rw == rw].sort_values("bsb")
        if d.empty:
            continue
        kb = d.bsb / 1024
        lab = {"randread": "random read", "randwrite": "random write", "read": "seq read", "write": "seq write"}[rw]
        axs[0].errorbar(kb, d.bw_MBps, yerr=err(d, "bw_MBps"), marker="o", color=SERIES_COLOR[rw], label=lab, capsize=2)
        axs[1].errorbar(kb, d.iops / 1e3, yerr=None if err(d, "iops") is None else err(d, "iops") / 1e3,
                        marker="o", color=SERIES_COLOR[rw], label=lab, capsize=2)
        axs[2].errorbar(kb, d.lat_mean_us, yerr=err(d, "lat_mean_us"), marker="o", color=SERIES_COLOR[rw], label=f"{lab} mean", capsize=2)
        axs[2].plot(kb, d.p99_us, ls="--", marker="^", color=SERIES_COLOR[rw], alpha=0.8, label=f"{lab} p99")
    cg = ceiling_gbps(run)
    if cg:
        axs[0].axhline(cg * 1e3, color=INK2, ls=":", lw=1)
        axs[0].text(axs[0].get_xlim()[0], cg * 1e3, f" link ceiling {cg:.1f} GB/s", va="bottom", fontsize=7, color=INK2)
    for a in axs:
        a.set_xscale("log", base=2)
        a.set_xlabel("block size (KiB)")
        a.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    axs[0].set_ylabel("throughput (MB/s)"); axs[0].set_title("Throughput")
    axs[1].set_ylabel("kIOPS"); axs[1].set_title("IOPS"); axs[1].set_yscale("log")
    axs[2].set_ylabel("latency (µs, log)"); axs[2].set_yscale("log"); axs[2].set_title("Latency (solid=mean, dashed=p99)")
    axs[0].legend(fontsize=8)
    qd = s["qd"].iloc[0]
    footer(fig, fixed_note(s, f"Fixed: iodepth={qd:.0f}, numjobs=1. Varied: block size, pattern, direction."))
    save(fig, out, "02_bs_sweep.png")
    t = s.sort_values(["rw", "bsb"])[["rw", "bs", "bw_MBps", "bw_MBps_ci95", "iops", "lat_mean_us", "p99_us"]]
    table("Block-size sweep", t.round(1), f"iodepth={qd:.0f}, numjobs=1.")


def plot_mix(proc, out):
    s = load(proc, "mix_sweep")
    if s.empty:
        return
    s = s.sort_values("rwmixread")
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.6))
    axs[0].errorbar(s.rwmixread, s.iops / 1e3, yerr=None if err(s, "iops") is None else err(s, "iops") / 1e3,
                    marker="o", color=C[0], capsize=2)
    axs[0].set_ylabel("total kIOPS (read + write)"); axs[0].set_title("Throughput vs mix")
    axs[1].plot(s.rwmixread, s.lat_mean_r_us, marker="o", color=C[0], label="read mean")
    axs[1].plot(s.rwmixread, s.p99_r_us, marker="^", ls="--", color=C[0], label="read p99")
    axs[1].plot(s.rwmixread, s.lat_mean_w_us, marker="o", color=C[1], label="write mean")
    axs[1].plot(s.rwmixread, s.p99_w_us, marker="^", ls="--", color=C[1], label="write p99")
    axs[1].set_yscale("log"); axs[1].set_ylabel("latency (µs, log)"); axs[1].set_title("Per-direction latency vs mix")
    axs[1].legend(fontsize=8)
    for a in axs:
        a.set_xlabel("% reads"); a.set_xticks(sorted(s.rwmixread.unique()))
    footer(fig, fixed_note(s, f"Fixed: random {s.bs.iloc[0]}, iodepth={s.qd.iloc[0]:.0f}, numjobs=1. Varied: rwmixread."))
    save(fig, out, "03_mix_sweep.png")
    t = s[["rwmixread", "iops", "bw_MBps", "lat_mean_r_us", "p99_r_us", "lat_mean_w_us", "p99_w_us"]]
    table("Read/write mix sweep", t.round(1), f"random {s.bs.iloc[0]}, QD {s.qd.iloc[0]:.0f}.")


def plot_qd(proc, out, run):
    s = load(proc, "qd_sweep")
    if s.empty:
        return
    series = list(dict.fromkeys(s["SERIES"]))
    fig, axs = plt.subplots(1, len(series), figsize=(4.2 * len(series), 3.9), squeeze=False)
    knees = []
    for i, ser in enumerate(series):
        a = axs[0][i]
        d = s[s.SERIES == ser].sort_values("qd_cfg")
        rw, bs, nj = ser.split(":")
        big = to_bytes(bs) >= 65536
        x = d.bw_MBps if big else d.iops / 1e3
        xe = err(d, "bw_MBps") if big else (None if err(d, "iops") is None else err(d, "iops") / 1e3)
        col = SERIES_COLOR.get(rw, C[4])
        a.errorbar(x, d.lat_mean_us, xerr=xe, yerr=err(d, "lat_mean_us"), marker="o", color=col, label="mean", capsize=2)
        a.plot(x, d.p99_us, marker="^", ls="--", color=col, alpha=0.75, label="p99")
        for xx, yy, q in zip(x, d.lat_mean_us, d.qd_cfg):
            a.annotate(f"{q:.0f}", (xx, yy), textcoords="offset points", xytext=(-4, 6), fontsize=7, color=INK2)
        kp, km = knee(d.qd_cfg, d.bw_MBps, d.lat_mean_us)
        kr = d[d.qd_cfg == kp].iloc[0]
        kx = kr.bw_MBps if big else kr.iops / 1e3
        a.scatter([kx], [kr.lat_mean_us], s=120, facecolors="none", edgecolors=INK, lw=1.4, zorder=5)
        a.annotate(f"knee QD={kp}", (kx, kr.lat_mean_us), textcoords="offset points", xytext=(14, -16),
                   fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.7))
        a.set_yscale("log")
        a.set_xlabel("throughput (MB/s)" if big else "throughput (kIOPS)")
        a.set_ylabel("latency (µs, log)")
        a.set_title(f"{rw} {bs}, numjobs={nj}")
        if i == 0:
            a.legend(fontsize=8, loc="upper left")
        knees.append(dict(series=ser, knee_qd_power=kp, knee_qd_marginal=km,
                          iops_at_knee=round(kr.iops), MBps_at_knee=round(kr.bw_MBps, 1),
                          lat_mean_us_at_knee=round(kr.lat_mean_us, 1), p99_us_at_knee=round(kr.p99_us, 1),
                          max_iops=round(d.iops.max()), max_MBps=round(d.bw_MBps.max(), 1),
                          lat_qd1_us=round(d.lat_mean_us.iloc[0], 1)))
    fig.suptitle("Throughput vs latency as total queue depth grows (labels = total QD; circle = knee, max throughput/latency)", fontsize=10)
    footer(fig, fixed_note(s, "Total QD = iodepth × numjobs."))
    save(fig, out, "04_qd_curve.png")
    table("Queue-depth sweep: knees", pd.DataFrame(knees),
          "Knee (power) = argmax throughput/mean-latency (Kleinrock). Knee (marginal) = last QD before doubling QD gave <10% more throughput for ≥50% more latency.")
    full = s.sort_values(["SERIES", "qd_cfg"])[["SERIES", "qd_cfg", "iops", "bw_MBps", "lat_mean_us", "p99_us", "qd_little", "cpu_sys", "cpu_usr"]]
    table("Queue-depth sweep (all points)", full.round(2), "qd_little = IOPS × mean latency (Little's Law estimate of the in-flight I/O count).")

    # Little's law plot
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    for i, ser in enumerate(series):
        d = s[s.SERIES == ser].sort_values("qd_cfg")
        ax.plot(d.qd_cfg, d.qd_little, marker="o", color=C[i], label=ser)
    mis = load(proc, "misleading")
    if not mis.empty and "CASE" in mis:
        b = mis[mis.CASE == "B"]
        mk = {0: C[7], 1: C[6], 2: C[4]}
        for i, (_, r) in enumerate(b.sort_values("point").iterrows()):
            ax.scatter([r.qd_cfg], [r.qd_little], marker="X", s=70, color=mk.get(i, C[6]), zorder=5,
                       label=f"misleading: {r.VARIANT}")
    lim = [0.8, max(s.qd_cfg.max(), 128) * 1.3]
    ax.plot(lim, lim, color=INK2, ls=":", lw=1, label="L = QD (ideal)")
    ax.set_xscale("log", base=2); ax.set_yscale("log", base=2)
    ax.set_xlabel("configured total queue depth"); ax.set_ylabel("IOPS × mean latency  (in-flight I/Os)")
    ax.set_title("Little's Law check: L = λ·W")
    ax.legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.02, 1.0))
    footer(fig, "On the diagonal: the device really had QD I/Os outstanding. Below: the host could not keep the queue full "
                "(or the engine ignores iodepth). Above: more in flight than the reported QD.")
    save(fig, out, "05_littles_law.png")


def plot_tail(proc, out, run):
    files = sorted(proc.glob("tail_hist_*.csv"))
    s = load(proc, "tail")
    if not files and s.empty:
        return
    fig, ax = plt.subplots(figsize=(7, 4.2))
    i = 0
    for f in files:
        name = f.stem.replace("tail_hist_", "")
        if name.endswith("_write") and "randrw" not in name:
            continue
        d = pd.read_csv(f)
        d = d[d.ccdf > 0]
        ax.step(d.lat_us, d.ccdf, where="post", color=C[i % len(C)], label=name.replace("_", " "))
        i += 1
    for p, lab in ((1e-2, "p99"), (1e-3, "p99.9"), (1e-4, "p99.99")):
        ax.axhline(p, color=GRID, lw=1, zorder=0)
        ax.text(ax.get_xlim()[1] if files else 1, p, f" {lab}", fontsize=7, color=INK2, va="center")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("latency (µs, log)"); ax.set_ylabel("P(latency > x)")
    ax.set_title("Latency CCDF (4KiB random): QD1 vs mid-QD vs knee, and knee with 70:30 mix")
    ax.legend(fontsize=7)
    footer(fig, "From fio json+ histograms merged across reps; tail runs are longer than sweep runs.")
    save(fig, out, "06_tail_ccdf.png")
    if not s.empty:
        cols = ["point", "qd_cfg", "iops", "lat_mean_us", "p50_r_us", "p95_r_us", "p99_r_us", "p99.9_r_us", "p99.99_r_us", "p99_w_us"]
        t = s[[c for c in cols if c in s]].copy()
        t["p99.9/p50"] = t["p99.9_r_us"] / t["p50_r_us"]
        table("Tail latency (read direction)", t.round(2), "µs. p99_w_us only for the mixed run.")


def plot_ws(proc, out):
    s = load(proc, "working_set")
    if s.empty:
        return
    s["ws"] = pd.to_numeric(s["WS_BYTES"], errors="coerce") / 2**30
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.6))
    for i, qd in enumerate(sorted(s.qd.unique())):
        d = s[s.qd == qd].sort_values("ws")
        axs[0].errorbar(d.ws, d.iops / 1e3, yerr=None if err(d, "iops") is None else err(d, "iops") / 1e3,
                        marker="o", color=C[i], label=f"QD {qd:.0f}", capsize=2)
        axs[1].plot(d.ws, d.lat_mean_us, marker="o", color=C[i], label=f"QD {qd:.0f} mean")
        axs[1].plot(d.ws, d.p99_us, marker="^", ls="--", color=C[i], label=f"QD {qd:.0f} p99")
    ticks = s.drop_duplicates("ws").sort_values("ws")
    for a in axs:
        a.set_xscale("log", base=2); a.set_xlabel("LBA span touched (log)")
        a.set_xticks(ticks.ws, ticks.WS_LABEL.astype(str)); a.minorticks_off()
    axs[0].set_ylabel("kIOPS"); axs[0].set_yscale("log"); axs[0].set_title("4KiB random read vs working set")
    axs[1].set_ylabel("latency (µs, log)"); axs[1].set_yscale("log"); axs[1].set_title("Latency vs working set")
    axs[0].legend(fontsize=8, loc="best"); axs[1].legend(fontsize=7, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    footer(fig, fixed_note(s, "Fixed: 4KiB random read, numjobs=1. Varied: span (all LBAs pre-written)."))
    save(fig, out, "07_working_set.png")
    t = s.sort_values(["qd", "ws"])[["WS_LABEL", "qd", "iops", "lat_mean_us", "p99_us"]]
    table("Working-set sweep", t.round(1))


def plot_steady(proc, out):
    p = proc / "steady_state_timeseries.csv"
    if not p.exists():
        return
    ts = pd.read_csv(p)
    tp = proc / "steady_state_temperature.csv"
    temp = pd.read_csv(tp) if tp.exists() else pd.DataFrame()
    has_temp = not temp.empty and temp.temp_c.notna().any()
    n = 3 if has_temp else 2
    fig, axs = plt.subplots(n, 1, figsize=(9, 2.5 * n))
    a = ts[(ts.point == "seqwrite_128k_qd32") & (ts.metric == "bw")]
    b = ts[(ts.point == "randwrite_4k_qd128") & (ts.metric == "iops")]
    a, b = a[a.t_s < a.t_s.max()], b[b.t_s < b.t_s.max()]   # drop the partial final interval
    axs[0].plot(a.t_s, a.value, color=C[3], lw=1)
    axs[0].set_ylabel("MB/s"); axs[0].set_title("A) 128KiB sequential write after idle — SLC write-cache cliff")
    axs[1].plot(b.t_s, b.value / 1e3, color=C[1], lw=1)
    axs[1].set_ylabel("kIOPS"); axs[1].set_title("B) 4KiB random write, total QD 128 — burst → GC-bound steady state")
    if has_temp:
        axs[2].plot(temp.t_abs_s, temp.temp_c, color=C[7], lw=1.2)
        axs[2].set_ylabel("°C"); axs[2].set_title("Drive temperature (composite), whole experiment incl. idle periods")
        axs[2].set_xlabel("time since experiment start (s)")
    for a_ in axs[:2]:
        a_.set_xlabel("time since phase start (s)"); a_.set_ylim(bottom=0)
    footer(fig, "Per-second averages from fio logs (all jobs summed). Separate panels instead of a dual axis.")
    save(fig, out, "08_steady_state.png")
    rows = []
    for name, d, unit in (("seq write 128k", a, "MB/s"), ("rand write 4k", b, "IOPS")):
        if d.empty:
            continue
        v = d.value.values
        k = max(1, len(v) // 10)
        first, last = v[:k].mean(), v[-k:].mean()
        rows.append(dict(phase=name, unit=unit, first_10pct_mean=round(first, 1), last_10pct_mean=round(last, 1),
                         ratio_last_over_first=round(last / first, 3) if first else math.nan,
                         cov_last_10pct=round(np.std(v[-k:]) / max(np.mean(v[-k:]), 1e-9), 3)))
    s = load(proc, "steady_state")
    if not s.empty:
        for _, r in s[s.point.str.startswith("randread")].iterrows():
            rows.append(dict(phase=r.point, unit="IOPS / p99 µs", first_10pct_mean=round(r.iops),
                             last_10pct_mean=round(r.p99_us, 1)))
    if rows:
        table("Device state: burst vs steady state", pd.DataFrame(rows),
              "SNIA-style steady state: last-window variation small (CoV) and flat; ratio <1 shows burst > sustained.")


def plot_misleading(proc, out):
    s = load(proc, "misleading")
    if s.empty or "CASE" not in s:
        return
    cases = [c for c in "ABCD" if (s.CASE == c).any()]
    fig, axs = plt.subplots(1, len(cases), figsize=(4.4 * len(cases), 4.1), squeeze=False)
    ax = dict(zip(cases, axs[0]))
    for a_ in axs[0]:
        a_.grid(axis="x", visible=False)

    def ratio_label(a_, x, y, r, prefix="dev/fio bytes\n"):
        if not math.isnan(r.dev_bytes_ratio):
            a_.annotate(f"{prefix}{r.dev_bytes_ratio:.2f}", (x, y), ha="center", xytext=(0, 3),
                        textcoords="offset points", fontsize=6.5, color=INK2)

    if "A" in ax:
        a = s[s.CASE == "A"]
        order = ["buffered_cold", "buffered_warm", "direct", "buffered_write", "direct_write"]
        a = a.set_index("VARIANT").reindex([o for o in order if o in set(a.VARIANT)]).reset_index()
        cols = [C[0] if "buffered" in v else C[2] for v in a.VARIANT]
        bars = ax["A"].bar(range(len(a)), a.iops, color=cols, yerr=err(a, "iops"), capsize=2)
        ax["A"].set_xticks(range(len(a)), [v.replace("_", "\n") for v in a.VARIANT], fontsize=7)
        ax["A"].set_yscale("log"); ax["A"].set_ylabel("IOPS (log)")
        ax["A"].set_title("A) OS file cache: buffered vs unbuffered (4K, QD1)")
        for b_, (_, r) in zip(bars, a.iterrows()):
            ratio_label(ax["A"], b_.get_x() + b_.get_width() / 2, b_.get_height(), r)
    if "B" in ax:
        b = s[s.CASE == "B"].sort_values("point")
        cols = [C[7] if v.startswith(("psync", "sync")) else (C[4] if "x4jobs" in v else C[6]) for v in b.VARIANT]
        ax["B"].bar(range(len(b)), b.qd_little, color=cols)
        ax["B"].axhline(32, color=INK2, ls=":", lw=1)
        ax["B"].text(-0.45, 32, "reported QD = 32", fontsize=7, va="bottom", color=INK2)
        labels = {"x4jobs": "iodepth 32\n×4 jobs", "iodepth32": "iodepth 32"}
        ax["B"].set_xticks(range(len(b)), [v.replace("_iodepth32", "\niodepth 32").replace(
            "iodepth32_x4jobs_reported_as_32", "iodepth 32\n× 4 jobs") for v in b.VARIANT], fontsize=7)
        ax["B"].set_ylabel("IOPS × mean latency (I/Os in flight)")
        ax["B"].set_title("B) wrong effective queue depth (Little's Law)")
        for i, (_, r) in enumerate(b.iterrows()):
            ax["B"].annotate(f"{r.iops/1e3:.0f}k IOPS", (i, r.qd_little), ha="center", xytext=(0, 3),
                             textcoords="offset points", fontsize=7)
    if "C" in ax:
        c = s[s.CASE == "C"]
        ax["C"].bar(range(len(c)), c.iops / 1e3, color=[C[4] if v != "written" else C[0] for v in c.VARIANT],
                    yerr=None if err(c, "iops") is None else err(c, "iops") / 1e3, capsize=2)
        ax["C"].set_xticks(range(len(c)), c.VARIANT.str.replace("_", "\n"), fontsize=7)
        ax["C"].set_ylabel("kIOPS"); ax["C"].set_title("C) reading never-written blocks (4K, QD32)")
        for i, (_, r) in enumerate(c.iterrows()):
            ratio_label(ax["C"], i, r.iops / 1e3, r, prefix="dev/fio bytes ")
    if "D" in ax:
        d = s[s.CASE == "D"]
        ax["D"].bar(range(len(d)), d.dev_bytes_ratio, color=[C[4] if v != "written" else C[0] for v in d.VARIANT])
        if d.dev_bytes_ratio.max() > 10:
            ax["D"].set_yscale("log")
        ax["D"].axhline(1, color=INK2, ls=":", lw=1)
        ax["D"].set_xticks(range(len(d)), d.VARIANT.str.replace("_", "\n"), fontsize=7)
        ax["D"].set_ylabel("device bytes written ÷ fio bytes")
        ax["D"].set_title("D) NTFS zero-fill: random writes into an\nextended-but-unwritten file (16 MiB, QD1)")
        for i, (_, r) in enumerate(d.iterrows()):
            ax["D"].annotate(f"max lat {r.lat_max_w_us/1e3:.1f} ms", (i, r.dev_bytes_ratio), ha="center",
                             xytext=(0, 3), textcoords="offset points", fontsize=7, color=INK2)
    fig.subplots_adjust(wspace=0.38)
    footer(fig, "dev/fio bytes = bytes the OS I/O counters saw on the volume/device ÷ bytes fio reports; "
                "≈1 means the I/O really reached the SSD, ≈0 means it was served without the SSD, ≫1 means hidden I/O.")
    save(fig, out, "09_misleading.png")
    cols = ["CASE", "VARIANT", "ioengine", "direct", "qd_cfg", "iops", "lat_mean_us", "p99_us", "lat_max_w_us",
            "qd_little", "dev_bytes_ratio"]
    table("Misleading setups", s[[c for c in cols if c in s]].round(3))


def plot_peak(proc, run):
    s = load(proc, "peak")
    if s.empty:
        return
    cg = ceiling_gbps(run)
    t = s[["point", "qd_cfg", "nj", "iops", "iops_ci95", "bw_MBps", "bw_MBps_ci95", "lat_mean_us", "p99_us"]].copy()
    if cg:
        t["pct_of_link"] = 100 * t.bw_MBps / (cg * 1e3)
    table("Peak capability", t.round(1), f"Link raw ceiling: {cg} GB/s per direction (before PCIe/NVMe protocol overhead)." if cg else "")


def write_tables(run):
    path = REPO / "docs" / "results_tables.md"
    proc = PROC / run
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"# Results tables — `{run}`\n\nAuto-generated by `analysis/plot.py`; do not edit by hand.\n"
                 "Latency in µs, throughput in MB/s (10^6 B/s); `_ci95` = 95% CI half-width across reps.\n\n")
        si = RAW / run / "sysinfo" / "sysinfo.json"
        if si.exists():
            info = json.loads(si.read_text(encoding="utf-8", errors="replace"))
            fh.write("## System under test\n\n")
            fh.write(pd.DataFrame(list(info.items()), columns=["field", "value"]).to_markdown(index=False) + "\n\n")
        for title, df, note in TABLES:
            fh.write(f"## {title}\n\n")
            if note:
                fh.write(f"{note}\n\n")
            fh.write(df.to_markdown(index=False) + "\n\n")
        v = proc / "validation.md"
        if v.exists():
            fh.write("\n---\n\n" + v.read_text(encoding="utf-8", errors="replace").replace("# Validation", "## Validation"))
    (proc / "results_tables.md").write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    print("  wrote", path.relative_to(REPO))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    run = current_run(ap.parse_args().run)
    proc = PROC / run
    out = PLOTS / run
    out.mkdir(parents=True, exist_ok=True)
    plot_baseline(proc, out)
    plot_bs(proc, out, run)
    plot_mix(proc, out)
    plot_qd(proc, out, run)
    plot_peak(proc, run)
    plot_tail(proc, out, run)
    plot_ws(proc, out)
    plot_steady(proc, out)
    plot_misleading(proc, out)
    write_tables(run)


if __name__ == "__main__":
    main()
