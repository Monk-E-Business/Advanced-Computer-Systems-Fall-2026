"""Report figures (fig01-fig10) for docs/report. Usage, from the repo root:
    python3 analysis/report_figs.py            # writes plots/<run>/report/
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mt
import numpy as np
import pandas as pd

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]   # repo root
RUN = sys.argv[3] if len(sys.argv) > 3 else "run_20261023_215950"
P = ROOT / "data/processed" / RUN
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "plots" / RUN / "report"; OUT.mkdir(parents=True, exist_ok=True)

C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "figure.dpi": 100, "savefig.dpi": 200, "font.size": 9.5, "axes.titlesize": 10.5,
    "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.8,
    "lines.markersize": 5, "legend.frameon": False, "legend.fontsize": 8.5,
    "figure.facecolor": "white", "axes.facecolor": "white",
})
LINK = 3.938  # GB/s raw, PCIe Gen3 x4
runs = pd.read_csv(P / "all_runs.csv")
runs["t"] = pd.to_datetime(runs.timestamp, utc=True)
T0 = runs.t.min()
NAME = {"randread": "4K random read", "randwrite": "4K random write", "read": "seq read", "write": "seq write"}
SER = {"randread": C[0], "randwrite": C[1], "read": C[2], "write": C[3]}
kb = lambda b: {"k": 1, "m": 1024}[b[-1]] * int(b[:-1])


def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


def rng(df, keys, col):
    g = df.groupby(keys)[col]
    return g.mean(), g.min(), g.max()


# ---- Fig 1: QD=1 percentiles ------------------------------------------------
b = runs[runs.experiment == "baseline_qd1"]
cases = [("randread", "4k", "4 KiB random read"), ("randwrite", "4k", "4 KiB random write"),
         ("read", "128k", "128 KiB seq read"), ("write", "128k", "128 KiB seq write")]
pcts = [("p50_us", "p50"), ("p95_us", "p95"), ("p99_us", "p99"), ("p99.9_us", "p99.9")]
fig, ax = plt.subplots(figsize=(9, 3.9))
w = 0.19
for j, (col, lab) in enumerate(pcts):
    xs, ys, lo, hi = [], [], [], []
    for i, (rw, bs, _) in enumerate(cases):
        s = b[(b.rw == rw) & (b.bs == bs)][col]
        xs.append(i + (j - 1.5) * w); ys.append(s.mean()); lo.append(s.mean() - s.min()); hi.append(s.max() - s.mean())
    ax.bar(xs, ys, w * 0.9, color=C[j], label=lab, yerr=[lo, hi], ecolor=INK2, capsize=2, error_kw={"lw": 0.8})
for i, (rw, bs, _) in enumerate(cases):
    m = b[(b.rw == rw) & (b.bs == bs)].lat_mean_us.mean()
    ax.plot([i - 2 * w, i + 2 * w], [m, m], color=INK, lw=1.2, ls="--")
    ax.annotate(f"mean {m:.0f} µs", (i + 2 * w, m), xytext=(2, 2), textcoords="offset points", fontsize=7.5, color=INK)
ax.set_yscale("log"); ax.grid(axis="x", visible=False)
ax.set_xticks(range(4), [c[2] for c in cases])
ax.set_ylabel("latency (µs, log scale)")
ax.set_title("QD=1 latency percentiles (numjobs=1; bars = mean of 3 reps, whiskers = rep range)")
ax.legend(ncol=4, loc="upper left")
save(fig, "fig01_qd1.png")

# ---- Fig 2: block-size sweep -----------------------------------------------
s = runs[runs.experiment == "bs_sweep"].copy(); s["kib"] = s.bs.map(kb)
fig, axs = plt.subplots(1, 2, figsize=(10, 3.9))
for rw in ["read", "randread", "write", "randwrite"]:
    d = s[s.rw == rw]
    m, lo, hi = rng(d, "kib", "bw_MBps")
    axs[0].errorbar(m.index, m / 1e3, yerr=[(m - lo) / 1e3, (hi - m) / 1e3], marker="o", color=SER[rw], capsize=2,
                    label=NAME[rw].replace("4K ", ""))
    ml, lol, hil = rng(d, "kib", "lat_mean_us")
    axs[1].errorbar(ml.index, ml / 1e3, yerr=[(ml - lol) / 1e3, (hil - ml) / 1e3], marker="o", color=SER[rw], capsize=2)
axs[0].axhline(LINK, color=INK2, ls=":", lw=1.1)
axs[0].text(1024, LINK, "PCIe Gen3 ×4 raw ceiling 3.94 GB/s ", va="bottom", ha="right", fontsize=7.5, color=INK2)
axs[0].set_ylim(0, 4.4); axs[0].set_ylabel("throughput (GB/s)")
axs[0].set_title("A. Throughput vs block size")
axs[1].set_yscale("log"); axs[1].set_ylabel("mean latency (ms, log)")
axs[1].set_title("B. Mean latency vs block size (same runs)")
for a in axs:
    a.set_xscale("log", base=2); a.set_xlabel("block size (KiB)")
    a.xaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v:g}"))
axs[0].legend(loc="upper left", bbox_to_anchor=(0, 0.88))
fig.suptitle("Block-size sweep, iodepth 32, numjobs 1 (mean of 3 reps; whiskers = rep range)", x=0.01, ha="left",
             fontsize=9, color=INK2, y=1.0)
save(fig, "fig02_bs.png")

# ---- Fig 3: mix sweep -------------------------------------------------------
mx = runs[runs.experiment == "mix_sweep"]
g = mx.groupby("rwmixread")
iops = g.iops.mean() / 1e3; lo = g.iops.min() / 1e3; hi = g.iops.max() / 1e3
R, Wr = iops.loc[100], iops.loc[0]
r = np.linspace(0, 1, 51)
fig, axs = plt.subplots(1, 2, figsize=(10, 3.7))
axs[0].errorbar(iops.index, iops, yerr=[iops - lo, hi - iops], marker="o", color=C[0], capsize=3, label="measured", zorder=3)
axs[0].plot(r * 100, r * R + (1 - r) * Wr, color=INK2, ls=":", lw=1.2, label="linear interpolation")
axs[0].plot(r * 100, 1 / (r / R + (1 - r) / Wr), color=C[6], ls="--", lw=1.2, label="harmonic (time-shared) model")
axs[0].set_ylabel("total kIOPS (reads + writes)"); axs[0].set_title("A. Throughput vs read share")
axs[0].legend(loc="upper left")
for dirn, col, lab in [("r", C[0], "read"), ("w", C[1], "write")]:
    m = g[f"p99_{dirn}_us"].mean() / 1e3
    axs[1].plot(m.index, m, marker="o", color=col, label=f"{lab} p99")
    m2 = g[f"lat_mean_{dirn}_us"].mean() / 1e3
    axs[1].plot(m2.index, m2, marker="s", ls="--", color=col, alpha=0.7, label=f"{lab} mean")
axs[1].set_yscale("log"); axs[1].set_ylabel("latency (ms, log)"); axs[1].set_title("B. Per-direction latency")
axs[1].legend(loc="upper right", ncol=2)
for a in axs:
    a.set_xlabel("% reads"); a.set_xticks([0, 50, 70, 100])
fig.suptitle("Random 4 KiB, iodepth 32, numjobs 1", x=0.01, ha="left", fontsize=9, color=INK2, y=1.0)
save(fig, "fig03_mix.png")

# ---- Fig 4: QD curves -------------------------------------------------------
q = runs[runs.experiment == "qd_sweep"]
fig, axs = plt.subplots(1, 3, figsize=(12, 4.1))


def curve(ax, d, x_scale, color, label, knee=None, unit="kIOPS"):
    m = d.groupby("qd_cfg").agg(x=("iops" if unit == "kIOPS" else "bw_MBps", "mean"), lat=("lat_mean_us", "mean"),
                                xlo=("iops" if unit == "kIOPS" else "bw_MBps", "min"),
                                xhi=("iops" if unit == "kIOPS" else "bw_MBps", "max"))
    x = m.x / x_scale
    ax.errorbar(x, m.lat, xerr=[(m.x - m.xlo) / x_scale, (m.xhi - m.x) / x_scale], marker="o", color=color,
                capsize=2, label=label)
    for qd, xx, yy in zip(m.index, x, m.lat):
        ax.annotate(f"{qd:.0f}", (xx, yy), xytext=(-9, 5), textcoords="offset points", fontsize=7, color=INK2)
    if knee:
        ax.scatter([x.loc[knee]], [m.lat.loc[knee]], s=150, facecolors="none", edgecolors=INK, lw=1.4, zorder=5)
        ax.annotate(f"knee QD {knee}", (x.loc[knee], m.lat.loc[knee]), xytext=(10, -14), textcoords="offset points",
                    fontsize=8, color=INK)


curve(axs[0], q[q.SERIES == "randread:4k:1"], 1e3, C[0], "1 job", knee=8)
curve(axs[0], q[q.SERIES == "randread:4k:4"], 1e3, C[6], "4 jobs", knee=32)
axs[0].set_title("A. 4 KiB random read"); axs[0].legend(loc="upper left")
curve(axs[1], q[q.SERIES == "randwrite:4k:4"], 1e3, C[1], "4 jobs", knee=4)
axs[1].set_title("B. 4 KiB random write (4 jobs)")
curve(axs[2], q[q.SERIES == "read:128k:1"], 1e3, C[2], "1 job", unit="MBps")
axs[2].set_title("C. 128 KiB sequential read (1 job)")
for a, xl in zip(axs, ["throughput (kIOPS)", "throughput (kIOPS)", "throughput (GB/s)"]):
    a.set_yscale("log"); a.set_xlabel(xl); a.set_ylabel("mean latency (µs, log)")
fig.suptitle("Throughput vs mean latency as total queue depth grows (labels = total QD; circle = knee by "
             "max throughput/latency; whiskers = rep range)", x=0.01, ha="left", fontsize=9, color=INK2, y=1.01)
save(fig, "fig04_qd.png")

# ---- Fig 5: Little's law ----------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.6))
labels = {"randread:4k:1": "4K rand read, 1 job", "randread:4k:4": "4K rand read, 4 jobs",
          "randwrite:4k:4": "4K rand write, 4 jobs", "read:128k:1": "128K seq read, 1 job"}
for i, ser in enumerate(labels):
    d = q[q.SERIES == ser].groupby("qd_cfg").qd_little.mean()
    ax.plot(d.index, d, marker="o", color=[C[0], C[6], C[1], C[2]][i], label=labels[ser])
lim = np.array([0.8, 330])
ax.plot(lim, lim, color=INK2, ls=":", lw=1, label="L = configured QD")
mis = runs[(runs.experiment == "misleading") & (runs.CASE == "B")].groupby("VARIANT").qd_little.mean()
mk = {"sync_iodepth32": (C[7], "sync engine, iodepth 32"),
      "windowsaio_iodepth32": (C[3], "windowsaio, iodepth 32"),
      "iodepth32_x4jobs_reported_as_32": (C[4], "iodepth 32 × 4 jobs, reported as 32")}
for k, (col, lab) in mk.items():
    ax.scatter([32], [mis[k]], marker="X", s=90, color=col, zorder=5, label=f"demo B: {lab}")
ax.set_xscale("log", base=2); ax.set_yscale("log", base=2)
for a in (ax.xaxis, ax.yaxis):
    a.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v:g}"))
ax.set_xlabel("configured total queue depth"); ax.set_ylabel("IOPS × mean latency = I/Os in flight (L)")
ax.set_title("Little's Law check: L = λ·W")
ax.legend(loc="upper left", fontsize=7.8)
ax.annotate("below the line: the host could not\nkeep the configured queue full", (128, 68), xytext=(40, 6),
            fontsize=8, color=INK2, arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8))
save(fig, "fig05_little.png")

# ---- Fig 6: tail CCDF -------------------------------------------------------
fig, ax = plt.subplots(figsize=(8, 4.4))
curves = [("tail_hist_randread_4k_base_qd1_read.csv", "random read, QD 1", C[0]),
          ("tail_hist_randread_4k_mid_qd8_read.csv", "random read, QD 8 (mid)", C[2]),
          ("tail_hist_randread_4k_knee_qd32_read.csv", "random read, QD 32 (knee)", C[6]),
          ("tail_hist_randrw70_4k_qd32_read.csv", "reads in 70:30 mix, QD 32", C[1])]
for f, lab, col in curves:
    d = pd.read_csv(P / f); d = d[d.ccdf > 0]
    ax.step(d.lat_us / 1e3, d.ccdf, where="post", color=col, label=lab)
for p, lab in ((1e-2, "p99"), (1e-3, "p99.9"), (1e-4, "p99.99")):
    ax.axhline(p, color=INK2, lw=0.7, ls=":", zorder=0)
    ax.text(0.03, p, f"{lab} ", fontsize=7.5, color=INK2, va="bottom")
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(0.02, 200); ax.set_ylim(1e-6, 1.5)
ax.xaxis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v:g}"))
ax.set_xlabel("read latency (ms, log)"); ax.set_ylabel("P(latency > x)")
ax.set_title("Read-latency CCDF, 4 KiB random (90 s runs, 3 reps merged)")
ax.legend(loc="lower left")
save(fig, "fig06_tail.png")

# ---- Fig 7: working set -----------------------------------------------------
ws = runs[runs.experiment == "working_set"].copy()
ws["gib"] = pd.to_numeric(ws.WS_BYTES) / 2**30
fig, axs = plt.subplots(1, 2, figsize=(10, 3.5))
for a, qd in zip(axs, [1, 32]):
    d = ws[ws.qd == qd].groupby("gib")
    for col, lab, cc, ls in [("lat_mean_us", "mean", C[0], "-"), ("p99_us", "p99", C[1], "--")]:
        m = d[col].mean(); lo = d[col].min(); hi = d[col].max()
        a.errorbar(m.index, m, yerr=[m - lo, hi - m], marker="o", color=cc, ls=ls, capsize=2, label=lab)
    a.set_xscale("log", base=2); a.set_xticks([1, 4, 16, 32, 64], ["1", "4", "16", "32", "64 (full)"])
    a.minorticks_off(); a.set_xlabel("LBA span touched (GiB)"); a.set_ylabel("latency (µs)")
    a.set_ylim(0, None); a.set_title(f"{'A' if qd == 1 else 'B'}. 4 KiB random read, QD {qd}")
    a.legend(loc="lower left")
save(fig, "fig07_ws.png")

# ---- Fig 8: device state ----------------------------------------------------
ts = pd.read_csv(P / "steady_state_timeseries.csv")
tp = pd.read_csv(P / "steady_state_temperature.csv")
sw = ts[(ts.point == "seqwrite_128k_qd32") & (ts.metric == "bw")].sort_values("t_s")
rwr = ts[(ts.point == "randwrite_4k_qd128") & (ts.metric == "iops")].sort_values("t_s")
fig, axs = plt.subplots(3, 1, figsize=(10, 8.2), gridspec_kw={"hspace": 0.55})
axs[0].plot(sw.t_s, sw.value / 1e3, color=C[3], lw=0.9)
axs[0].axvspan(0, 11, color=C[3], alpha=0.12)
axs[0].annotate("SLC cache: 25.6 GB at 2.1–3.3 GB/s", (11, 3.0), xytext=(40, 2.6), fontsize=8, color=INK,
                arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8))
axs[0].axhline(np.median(sw.value) / 1e3, color=INK2, ls=":", lw=1)
axs[0].text(600, np.median(sw.value) / 1e3, " median 67 MB/s", fontsize=7.5, color=INK2, va="bottom", ha="right")
axs[0].set_ylabel("GB/s"); axs[0].set_xlabel("seconds since phase start")
axs[0].set_title("A. 128 KiB sequential write after 5 min idle (QD 32): SLC cache cliff")
axs[1].plot(rwr.t_s, rwr.value / 1e3, color=C[1], lw=0.5, alpha=0.55, label="per second")
roll = rwr.set_index("t_s").value.rolling(60, center=True).median() / 1e3
axs[1].plot(roll.index, roll, color=INK, lw=1.4, label="60 s rolling median")
axs[1].set_ylabel("kIOPS"); axs[1].set_xlabel("seconds since phase start")
axs[1].set_title("B. 4 KiB random write, total QD 128, 30 min: GC-bound start, recovery, then a decline toward ~39k IOPS")
axs[1].legend(loc="upper right", ncol=2)
axs[2].plot(tp.t_abs_s / 60, tp.temp_c, color=C[7], lw=1.1)
axs[2].set_ylabel("°C"); axs[2].set_xlabel("minutes since steady-state experiment start (incl. idle)")
axs[2].set_ylim(35, 50)
axs[2].set_title("C. Drive temperature (warning threshold 81 °C, not shown)")
save(fig, "fig08_state.png")

# ---- Fig 9: write history vs sequential read --------------------------------
rd = runs[(runs.rw == "read") & (runs.bs_bytes >= 131072) & (runs.qd * runs.nj >= 4)
          & runs.experiment.isin(["bs_sweep", "qd_sweep", "peak"])].copy()
rd["h"] = (rd.t - T0).dt.total_seconds() / 3600
wr = runs[(runs.bs == "4k") & runs.rw.isin(["randwrite", "randrw"]) &
          ~runs.experiment.isin(["misleading", "steady_state", "precondition", "validation"])].copy()
wr = wr[(wr.rwmixread.fillna(0) < 100) | (wr.rw == "randwrite")]
wr["h0"] = (wr.t - T0).dt.total_seconds() / 3600; wr["h1"] = wr.h0 + 35 / 3600
pre = runs[runs.experiment == "precondition"].copy()
pre["h0"] = (pre.t - T0).dt.total_seconds() / 3600
pre["dur"] = [64 * 2**30 * (2 if p_ == "seqfill" else 1) / (bw * 1e6) / 3600 for p_, bw in zip(pre.point, pre.bw_MBps)]
sq = runs[(runs.rw == "write") & runs.experiment.isin(["validation", "baseline_qd1", "bs_sweep"])].copy()
sq["h0"] = (sq.t - T0).dt.total_seconds() / 3600
fig, ax = plt.subplots(figsize=(10, 4.4))
for _, r_ in wr.iterrows():
    ax.axvspan(r_.h0, r_.h1, color=C[1], alpha=0.28, lw=0)
for _, r_ in sq.iterrows():
    ax.axvspan(r_.h0, r_.h0 + 35 / 3600, color=C[3], alpha=0.35, lw=0)
for _, r_ in pre.iterrows():
    ax.axvspan(r_.h0, r_.h0 + r_.dur, color=C[1] if r_.point == "randfill" else C[3], alpha=0.28 if r_.point == "randfill" else 0.35, lw=0)
ax.text(0.01, 0.35, "pre-\ncondition", fontsize=7, color=INK2)
for exp, col, lab in [("bs_sweep", C[2], "block-size sweep (QD 32, 128 KiB–1 MiB)"),
                      ("qd_sweep", C[0], "queue-depth sweep (128 KiB, QD 4–256)"),
                      ("peak", C[6], "peak test (1 MiB, 2 jobs)")]:
    d = rd[rd.experiment == exp]
    ax.scatter(d.h, d.bw_MBps / 1e3, color=col, s=22, label=lab, zorder=3)
ax.axhline(1.03, color=C[0], ls="--", lw=1)
ax.text(2.97, 1.03, "4 KiB random-read plateau\n(255k IOPS = 1.03 GB/s)", fontsize=7.5, color=C[0], va="bottom", ha="right")
ax.axhline(LINK, color=INK2, ls=":", lw=1)
ax.text(0.05, LINK, " PCIe Gen3 ×4 raw ceiling", fontsize=7.5, color=INK2, va="bottom")
ax.fill_between([], [], color=C[1], alpha=0.28, label="4 KiB random-write runs (scatter data)")
ax.fill_between([], [], color=C[3], alpha=0.35, label="sequential-write runs (rewrite data contiguously)")
ax.set_ylim(0, 4.3); ax.set_xlim(0, 3.0)
ax.set_xlabel(f"hours since run start ({T0.tz_convert('America/New_York'):%H:%M} local)")
ax.set_ylabel("sequential read (GB/s)")
ax.set_title("Sequential-read throughput across the run vs preceding 4 KiB random writes")
ax.legend(loc="upper right", fontsize=7.8)
save(fig, "fig09_history.png")

# ---- Fig 10: misleading setups ----------------------------------------------
m = runs[runs.experiment == "misleading"]
fig, axs = plt.subplots(2, 2, figsize=(10, 7.4), gridspec_kw={"hspace": 0.62, "wspace": 0.3})
a = m[m.CASE == "A"].groupby("VARIANT").agg(iops=("iops", "mean"), ratio=("dev_bytes_ratio", "mean"))
order = [("buffered_warm", "buffered\nread,\nwarm"), ("buffered_cold", "buffered\nread,\npurged"),
         ("direct", "unbuf-\nfered\nread"), ("buffered_write", "buffered\nwrite"), ("direct_write", "unbuf-\nfered\nwrite")]
ax = axs[0, 0]
vals = [a.loc[k, "iops"] / 1e3 for k, _ in order]
bars = ax.bar(range(5), vals, color=[C[4], C[4], C[0], C[4], C[0]])
for bb, (k, _) in zip(bars, order):
    ax.annotate(f"{a.loc[k, 'ratio']:.2f}", (bb.get_x() + bb.get_width() / 2, bb.get_height()), ha="center",
                xytext=(0, 2), textcoords="offset points", fontsize=7.5, color=INK2)
ax.set_xticks(range(5), [o[1] for o in order], fontsize=7.5); ax.grid(axis="x", visible=False)
ax.set_ylabel("kIOPS"); ax.set_title("A. OS file cache (4 KiB, QD 1, 1 GiB)\nlabels = device bytes ÷ fio bytes", fontsize=9.5)
bq = m[m.CASE == "B"].groupby("VARIANT").agg(L=("qd_little", "mean"), iops=("iops", "mean"))
order = [("sync_iodepth32", "sync engine\niodepth 32"), ("windowsaio_iodepth32", "windowsaio\niodepth 32"),
         ("iodepth32_x4jobs_reported_as_32", "iodepth 32 × 4 jobs\n(\"QD 32\")")]
ax = axs[0, 1]
ax.bar(range(3), [bq.loc[k, "L"] for k, _ in order], color=[C[7], C[0], C[4]])
ax.axhline(32, color=INK2, ls=":", lw=1); ax.text(2.45, 32, "reported QD 32", fontsize=7.5, color=INK2, va="bottom", ha="right")
for i, (k, _) in enumerate(order):
    ax.annotate(f"L = {bq.loc[k, 'L']:.1f}", (i, bq.loc[k, "L"]), ha="center", xytext=(0, 2), textcoords="offset points", fontsize=7.5)
ax.set_xticks(range(3), [o[1] for o in order], fontsize=7.5); ax.grid(axis="x", visible=False)
ax.set_ylabel("I/Os really in flight (IOPS × mean latency)"); ax.set_title("B. Wrong effective queue depth", fontsize=9.5)
c = m[m.CASE == "C"].groupby("VARIANT").agg(iops=("iops", "mean"), ratio=("dev_bytes_ratio", "mean"))
ax = axs[1, 0]
ax.bar([0, 1], [c.loc["unwritten", "iops"] / 1e3, c.loc["written", "iops"] / 1e3], color=[C[4], C[0]])
for i, k in enumerate(["unwritten", "written"]):
    ax.annotate(f"device/fio bytes {c.loc[k, 'ratio']:.2f}", (i, c.loc[k, "iops"] / 1e3), ha="center", xytext=(0, 2),
                textcoords="offset points", fontsize=7.5, color=INK2)
ax.set_xticks([0, 1], ["never-written\nfile region", "written region"], fontsize=7.5); ax.grid(axis="x", visible=False)
ax.set_ylabel("kIOPS"); ax.set_title("C. Reading never-written blocks (4 KiB, QD 32)", fontsize=9.5)
dd = m[m.CASE == "D"].groupby("VARIANT").agg(ratio=("dev_bytes_ratio", "mean"), mx=("lat_max_w_us", "max"))
ax = axs[1, 1]
ax.bar([0, 1], [dd.loc["unwritten", "ratio"], dd.loc["written", "ratio"]], color=[C[4], C[0]])
ax.set_yscale("log"); ax.axhline(1, color=INK2, ls=":", lw=1)
for i, k in enumerate(["unwritten", "written"]):
    ax.annotate(f"{dd.loc[k, 'ratio']:.1f}×, worst write {dd.loc[k, 'mx'] / 1e3:.0f} ms", (i, dd.loc[k, "ratio"]),
                ha="center", xytext=(0, 3), textcoords="offset points", fontsize=7.5)
ax.set_xticks([0, 1], ["extended, never-written\nfile", "fully written file"], fontsize=7.5); ax.grid(axis="x", visible=False)
ax.set_ylim(0.5, 300); ax.set_ylabel("device bytes written ÷ fio bytes (log)")
ax.set_title("D. NTFS zero-fill (16 MiB of 4 KiB random writes, QD 1)", fontsize=9.5)
save(fig, "fig10_misleading.png")
