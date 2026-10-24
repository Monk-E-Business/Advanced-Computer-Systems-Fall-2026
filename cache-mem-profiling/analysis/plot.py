#!/usr/bin/env python3
"""Processed tables (data/processed) -> figures/*.png.

Every figure: units on axes, 95% CI error bars over repetitions, cache-capacity
boundaries where the x-axis is a working set. Run analysis/process.py first.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator, NullFormatter  # noqa: E402

from common import FIG, PAGE_LABEL, caches, counter_hint, fmt_bytes, huge_mode, load, load_proc, sysenv  # noqa: E402

# Validated categorical palette (fixed order) + per-series markers as secondary encoding.
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MARK = ["o", "s", "^", "D", "v", "P", "X", "*"]
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#8a8984", "#e4e3de", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.size": 9.5, "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
    "axes.edgecolor": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "lines.linewidth": 1.8, "lines.markersize": 5, "legend.frameon": False, "legend.fontsize": 8.5,
    "errorbar.capsize": 2,
})

C = caches()
ENV = sysenv()
MADE: list[str] = []


def save(fig, name: str, note: str | None = None) -> None:
    sub = f"{ENV.get('cpu_model', '')}  |  CPU {ENV.get('cpu', '?')}  |  error bars: 95% CI over repetitions"
    if ENV.get("quick") == "1":
        sub += "  |  QUICK smoke run"
    if note:
        sub += "  |  " + note
    fig.text(0.01, 0.005, sub, fontsize=7, color=MUTED, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    p = FIG / f"{name}.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    MADE.append(p.name)


def bytes_axis(ax, axis: str = "x") -> None:
    f = FuncFormatter(lambda v, _: fmt_bytes(v).replace(" ", "") if v > 0 else "")
    if axis == "x":
        ax.set_xscale("log", base=2)
        ax.xaxis.set_major_formatter(f)
        ax.xaxis.set_minor_formatter(NullFormatter())
    else:
        ax.set_yscale("log", base=2)
        ax.yaxis.set_major_formatter(f)


def plain_log_y(ax) -> None:
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(FuncFormatter(lambda v, _: f"{v:g}" if str(f"{v:g}")[0] in "25" else ""))


def cache_regions(ax, scale: float = 1.0, llc_div: float = 1.0) -> None:
    """Dashed boundaries at cache capacities + region labels at the top."""
    if not C:
        return
    lo, hi = ax.get_xlim()
    edges = [lo]
    names = []
    for k, label in (("L1", "L1"), ("L2", "L2"), ("L3", "LLC")):
        if k in C:
            x = C[k] * scale / (llc_div if k == "L3" else 1)
            if lo < x < hi:
                ax.axvline(x, color=MUTED, lw=0.8, ls=(0, (4, 3)), zorder=1)
                edges.append(x)
                names.append(label)
            elif x <= lo:
                names = []
                edges = [lo]
    names.append("DRAM")
    edges.append(hi)
    for a, b, n in zip(edges[:-1], edges[1:], names):
        ax.text(np.sqrt(a * b), 1.0, n, transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                fontsize=8, color=INK2)
    ax.set_xlim(lo, hi)


def clip_err(y, ci):
    """Asymmetric error bars whose lower whisker never crosses zero (keeps log
    axes valid and avoids impossible negative bandwidth/latency)."""
    if ci is None:
        return None
    y = np.asarray(y, float)
    ci = np.nan_to_num(np.asarray(ci, float))
    return np.vstack([np.minimum(ci, y * 0.98), ci])


def series(ax, x, y, ci=None, i=0, label=None, ls="-", **kw):
    ax.errorbar(x, y, yerr=clip_err(y, ci), color=PAL[i % 8], marker=MARK[i % 8], ls=ls, label=label,
                elinewidth=0.9, ms=kw.pop("ms", 4.5), **kw)


def empty(ax, msg: str) -> None:
    import textwrap
    msg = "\n".join(textwrap.fill(line, 42) for line in msg.split("\n"))
    ax.text(0.5, 0.5, msg, transform=ax.transAxes, ha="center", va="center", color=MUTED, wrap=True)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)


def bars(ax, cats, groups: dict, errs: dict | None = None, ylabel="") -> None:
    """Grouped bars: groups = {series_name: values aligned with cats}."""
    n = len(groups)
    w = 0.8 / max(n, 1)
    x = np.arange(len(cats))
    for i, (name, vals) in enumerate(groups.items()):
        e = None if errs is None else errs.get(name)
        ax.bar(x + (i - (n - 1) / 2) * w, vals, w * 0.92, yerr=None if e is None else clip_err(vals, e), color=PAL[i % 8], label=name,
               error_kw={"elinewidth": 0.9, "ecolor": INK2})
    ax.set_xticks(x, cats, rotation=30, ha="right")
    ax.set_ylabel(ylabel)
    ax.grid(axis="x", visible=False)
    if n > 1:
        ax.legend()


# ------------------------------------------------------------------ figures --
def fig_latency_wss():
    s = load_proc("latency_wss_summary")
    if s is None:
        return
    r = s[s.pattern == "rand"]
    mdl = load_proc("amat_model")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, col, unit in ((axes[0], "lat_ns", "ns"), (axes[1], "lat_cycles", "core cycles")):
        for i, (pages, g) in enumerate(r.groupby("pages")):
            g = g.sort_values("size_bytes")
            series(ax, g.size_bytes, g[f"{col}_mean"], g[f"{col}_ci95"], i, f"random, {PAGE_LABEL.get(pages, pages)}")
            if col == "lat_ns" and mdl is not None:
                m = mdl[mdl.pages == pages].sort_values("size_bytes")
                ax.plot(m.size_bytes, m.amat_model_ns, color=PAL[i], lw=1, ls=":", label=f"AMAT model ({pages})")
        bytes_axis(ax)
        plain_log_y(ax)
        ax.set_xlabel("working set")
        ax.set_ylabel(f"load-to-use latency ({unit})")
        cache_regions(ax)
        ax.legend(loc="upper left")
    axes[0].set_title("a  Latency vs working set (ns)", pad=14)
    axes[1].set_title("b  Same data in cycles (robust to clock changes)", pad=14)
    t = load_proc("latency_table")
    if t is not None:
        pages = huge_mode(t.pages) or t.pages.iloc[0]
        for _, row in t[t.pages == pages].iterrows():
            axes[0].annotate(f"{row.level} {row.lat_ns:.1f}", (row.size_bytes, row.lat_ns), xytext=(0, 7),
                             textcoords="offset points", ha="center", fontsize=7.5, color=INK)
    save(fig, "fig1_latency_wss")


def fig_pattern_latency():
    s = load_proc("latency_wss_summary")
    if s is None:
        return
    fig, ax = plt.subplots(figsize=(7.5, 4.3))
    i = 0
    g = s[(s.pattern == "rand") & (s.pages == "4k")].sort_values("size_bytes")
    series(ax, g.size_bytes, g.lat_ns_mean, g.lat_ns_ci95, i, "random (64 B lines)")
    for st, g in s[s.pattern == "seq"].groupby("stride"):
        i += 1
        g = g.sort_values("size_bytes")
        series(ax, g.size_bytes, g.lat_ns_mean, g.lat_ns_ci95, i, f"sequential, stride {int(st)} B")
    bytes_axis(ax)
    plain_log_y(ax)
    ax.set_xlabel("working set")
    ax.set_ylabel("latency per dependent load (ns)")
    cache_regions(ax)
    ax.set_title("Access pattern: prefetchers hide latency for regular strides", pad=14)
    ax.legend(loc="upper left")
    save(fig, "fig2_pattern_latency", "4 KB pages")


def fig_pattern_bw():
    s = load_proc("bw_pattern_summary")
    if s is None:
        return
    ts = sorted(s.threads.unique())
    fig, axes = plt.subplots(1, len(ts), figsize=(5.6 * len(ts), 4.3), squeeze=False)
    for ax, t in zip(axes[0], ts):
        g = s[s.threads == t]
        cats = [("seq" if p == "seq" else f"stride {st}B" if p == "stride" else f"rand {gr}B")
                for p, st, gr in zip(g.pattern, g.stride, g.gran)]
        bars(ax, cats, {"useful bytes": g.gbps_mean.to_numpy(), "64 B lines moved": g.line_gbps_mean.to_numpy()},
             {"useful bytes": g.gbps_ci95.to_numpy(), "64 B lines moved": g.line_gbps_ci95.to_numpy()}, "GB/s")
        ax.set_title(f"{'a' if t == ts[0] else 'b'}  {t} thread{'s' if t > 1 else ''}: bandwidth by pattern")
    save(fig, "fig3_pattern_bw", f"buffer {fmt_bytes(s.size_bytes.iloc[0])}/thread; 'stride' touches 8 B per stride")


def fig_rwmix():
    s = load_proc("bw_rwmix_summary")
    if s is None:
        return
    names = {100: "100% read", 70: "70/30", 50: "50/50", 0: "100% write"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axes[0]
    for i, mix in enumerate([100, 70, 50, 0]):
        g = s[(s.label == "rwmix") & (s.read_pct == mix)].sort_values("threads")
        if len(g):
            series(ax, g.threads, g.gbps_mean, g.gbps_ci95, i, names[mix])
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("threads (one per physical core)")
    ax.set_ylabel("demanded bandwidth (GB/s)")
    ax.set_ylim(bottom=0)
    ax.set_title("a  Sequential bandwidth vs threads per R/W mix")
    ax.legend()
    ax = axes[1]
    tmax = s.threads.max()
    mixes = [m for m in (100, 70, 50, 0) if m in set(s.read_pct)]
    groups, errs = {}, {}
    for lab, nm in (("rwmix", "seq, normal stores"), ("rwmix_nt", "seq, non-temporal stores"),
                    ("rwmix_rand", "random 64 B")):
        vals, e = [], []
        for m in mixes:
            r = s[(s.label == lab) & (s.read_pct == m) & (s.threads == tmax)]
            vals.append(r.gbps_mean.iloc[0] if len(r) else (s[(s.label == "rwmix") & (s.read_pct == m) & (s.threads == tmax)].gbps_mean.iloc[0] if lab == "rwmix_nt" and m == 100 else np.nan))
            e.append(r.gbps_ci95.iloc[0] if len(r) else 0)
        groups[nm], errs[nm] = vals, e
    bars(ax, [names[m] for m in mixes], groups, errs, "demanded bandwidth (GB/s)")
    ax.legend(loc="upper left")
    ax.set_title(f"b  {tmax} threads: store type and pattern")
    save(fig, "fig4_rwmix", "normal stores also read each line (RFO): DRAM traffic > demanded bytes")


def fig_mlp():
    s = load_proc("mlp_summary")
    if s is None:
        return
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
    lat1 = s.lat_ns_mean.iloc[0]
    series(axes[0], s.chains, s.lat_ns_mean, s.lat_ns_ci95, 0, "measured")
    axes[0].axhline(lat1, color=MUTED, ls=":", lw=1, label=f"idle latency {lat1:.0f} ns")
    axes[0].set_xlabel("independent pointer chains (outstanding misses)")
    axes[0].set_ylabel("latency per hop (ns)")
    axes[0].set_ylim(bottom=0)
    axes[0].set_title("a  Latency vs memory-level parallelism (1 core)")
    axes[0].legend()
    series(axes[1], s.chains, s.gbps_mean, s.gbps_ci95, 0, "measured")
    axes[1].plot(s.chains, s.ideal_gbps, color=PAL[1], ls="--", lw=1.2, label="Little's Law, no queueing: K·64 B / idle lat.")
    pk = s.gbps_mean.max()
    axes[1].axhline(pk, color=MUTED, ls=":", lw=1)
    axes[1].annotate(f"peak {pk:.1f} GB/s  =>  {pk / 64 * lat1:.1f} lines in flight", (s.chains.max(), pk),
                     xytext=(0, 5), textcoords="offset points", ha="right", fontsize=8)
    axes[1].set_ylim(0, pk * 1.35)
    axes[1].set_xlabel("independent pointer chains (outstanding misses)")
    axes[1].set_ylabel("throughput (GB/s)")
    axes[1].set_title("b  Throughput saturates at the core's miss limit")
    axes[1].legend(loc="upper left")
    save(fig, "fig5_mlp", f"random chase over {fmt_bytes(s.size_bytes.iloc[0])}, {s.pages.iloc[0]} pages")


def fig_loaded():
    s = load_proc("loaded_summary")
    if s is None:
        return
    fig, ax = plt.subplots(figsize=(8, 4.8))
    idle = s[s.gens == 0]
    if len(idle):
        ax.axhline(idle.lat_ns_mean.iloc[0], color=MUTED, ls=":", lw=1, label=f"idle {idle.lat_ns_mean.iloc[0]:.0f} ns")
    names = {100: "100% read", 70: "70/30", 50: "50/50", 0: "100% write"}
    for i, mix in enumerate([100, 70, 50, 0]):
        g = s[(s.gens > 0) & (s.read_pct == mix)].sort_values("total_gbps_mean")
        if not len(g):
            continue
        ax.errorbar(g.total_gbps_mean, g.lat_ns_mean, yerr=clip_err(g.lat_ns_mean, g.lat_ns_ci95),
                    xerr=clip_err(g.total_gbps_mean, g.total_gbps_ci95),
                    color=PAL[i], marker=MARK[i], label=names[mix], elinewidth=0.8, ms=4.5)
        k = g[g.is_knee]
        if len(k):
            k = k.iloc[0]
            ax.plot(k.total_gbps_mean, k.lat_ns_mean, marker="o", ms=12, mfc="none", mec=PAL[i], mew=1.5)
            if mix == 100:
                ax.annotate(f"knee: {k.total_gbps_mean:.1f} GB/s, {k.lat_ns_mean:.0f} ns\n"
                            f"Little: {k.outstanding_lines:.0f} lines in flight",
                            (k.total_gbps_mean, k.lat_ns_mean), xytext=(-12, 22), textcoords="offset points",
                            ha="right", fontsize=8, arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
    m = load_proc("mlc_loaded")
    if m is not None:
        ax.plot(m.gbps, m.lat_ns, color=MUTED, marker="x", ls="--", lw=1, label="Intel MLC (all reads)")
    ax.set_xlabel("total bandwidth: generators + chaser (GB/s)")
    ax.set_ylabel("loaded latency of a random load (ns)")
    # Keep the curve readable: cap at 4x idle (or above the 90th percentile), report what is cut off.
    ref = idle.lat_ns_mean.iloc[0] if len(idle) else s.lat_ns_mean.min()
    ymax = max(4 * ref, 1.2 * s.lat_ns_mean.quantile(0.9))
    above = int((s.lat_ns_mean > ymax).sum())
    ax.set_ylim(0, ymax)
    if above:
        ax.text(0.99, 0.98, f"{above} point(s) above axis (max {s.lat_ns_mean.max():.0f} ns)", transform=ax.transAxes,
                ha="right", va="top", fontsize=8, color=INK2)
    ax.set_xlim(left=0)
    ax.set_title("Throughput vs latency as offered load grows (circles = knee)")
    ax.legend(loc="upper left")
    save(fig, "fig6_loaded_latency", "delay injected between generator accesses, swept large -> 0")


def fig_bw_wss():
    s = load_proc("bw_wss_summary")
    if s is None:
        return
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = {"wss_read_1t": "1 thread, read", "wss_write_1t": "1 thread, write", "wss_read_all": "all cores, read (aggregate)"}
    for i, (lab, nm) in enumerate(labels.items()):
        g = s[s.label == lab].sort_values("size_bytes")
        if len(g):
            series(ax, g.size_bytes, g.gbps_mean, g.gbps_ci95, i, nm + (f", {int(g.threads.iloc[0])} thr" if lab.endswith("all") else ""))
    bytes_axis(ax)
    plain_log_y(ax)
    ax.set_xlabel("working set per thread")
    ax.set_ylabel("bandwidth (GB/s)")
    cache_regions(ax)
    ax.set_title("Sequential bandwidth vs working set: one plateau per level", pad=14)
    ax.legend(loc="lower left")
    nt = s[s.label == "wss_read_all"].threads.max()
    save(fig, "fig7_bw_wss", f"all-core curve: LLC is shared, so its per-thread boundary is LLC/{int(nt) if nt == nt else 'N'}")


def fig_kernels():
    s = load_proc("kernels_summary")
    if s is None:
        return
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
    ax = axes[0]
    for i, (k, g) in enumerate(s[s.label == "footprint"].groupby("kernel")):
        g = g.sort_values("footprint_bytes")
        series(ax, g.footprint_bytes, g.ns_per_elem_mean, g.ns_per_elem_ci95, i, "z = x·y" if k == "mul" else "y = a·x + y")
    bytes_axis(ax)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("total footprint (all arrays)")
    ax.set_ylabel("time per element (ns)")
    cache_regions(ax)
    ax.legend(loc="upper left")
    ax.set_title("a  Unit stride: runtime vs footprint", pad=14)

    ax = axes[1]
    loc = s[s.label == "locality"].copy()
    order_keys = [("stride", st) for st in sorted(loc[loc.order == "stride"].stride.unique())] + [("rand", 1)]
    cats = [f"{st}" if o == "stride" else "random" for o, st in order_keys]
    for i, (k, g) in enumerate(loc.groupby("kernel")):
        vals = [g[(g.order == o) & ((g.stride == st) | (o == "rand"))].ns_per_elem_mean.mean() for o, st in order_keys]
        errs = [g[(g.order == o) & ((g.stride == st) | (o == "rand"))].ns_per_elem_ci95.mean() for o, st in order_keys]
        series(ax, np.arange(len(cats)), vals, errs, i, "z = x·y" if k == "mul" else "y = a·x + y")
    ax.set_xticks(np.arange(len(cats)), cats)
    plain_log_y(ax)
    ax.set_xlabel("element stride (8 = one 64 B line, 512 = one 4 KB page)")
    ax.set_ylabel("time per element (ns)")
    ax.legend(loc="upper left")
    ax.set_title(f"b  Same work, worse locality ({fmt_bytes(loc.footprint_bytes.iloc[0]) if len(loc) else ''})")

    ax = axes[2]
    raw = load("kernels")
    if raw is not None and pd.to_numeric(raw.llc_miss, errors="coerce").notna().any():
        raw["elems"] = raw.passes * raw.n
        reg = load_proc("kernel_regression")
        for i, (k, g) in enumerate(raw.groupby("kernel")):
            x = g.llc_miss / g.elems
            ax.scatter(x, g.ns_per_elem, s=22, color=PAL[i], marker=MARK[i], label="z = x·y" if k == "mul" else "y = a·x + y",
                       edgecolor=SURF, linewidth=0.6)
            if reg is not None and len(reg[reg.kernel == k]):
                rr = reg[reg.kernel == k].iloc[0]
                ax.text(0.02, 0.95 - 0.07 * i, f"{k}: R² = {rr.R2:.2f} (multi-counter fit)", transform=ax.transAxes,
                        fontsize=8, color=INK)
        ax.set_xlabel("LLC misses per element")
        ax.set_ylabel("time per element (ns)")
        ax.legend(loc="lower right")
    else:
        empty(ax, "Hardware counters unavailable here.\n" + counter_hint(ENV))
    ax.set_title("c  Runtime vs LLC misses (all kernel runs)")
    save(fig, "fig8_kernels_cache", "counters: AMD uProf, (full run) - (setup-only run)" if ENV.get("counters") == "uprof"
         else "counters cover only the timed loop (perf_event_open in-process)")


def fig_tlb():
    s = load_proc("tlb_summary")
    if s is None:
        return
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
    ax = axes[0]
    for i, (pages, g) in enumerate(s.groupby("pages")):
        g = g.sort_values("pages_touched")
        series(ax, g.pages_touched, g.lat_ns_mean, g.lat_ns_ci95, i, PAGE_LABEL.get(pages, pages))
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v)}" if v >= 1 else ""))
    ax.set_xlabel("distinct 4 KB pages touched (1 line each)")
    ax.set_ylabel("latency per access (ns)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left")
    ax.set_title("a  Page-stride chase: TLB reach")
    ax = axes[1]
    if "dtlb_miss_pa_mean" in s and s.dtlb_miss_pa_mean.notna().any():
        for i, (pages, g) in enumerate(s.groupby("pages")):
            g = g.sort_values("pages_touched")
            series(ax, g.pages_touched, g.dtlb_miss_pa_mean, g.dtlb_miss_pa_ci95, i, PAGE_LABEL.get(pages, pages))
        ax.set_xscale("log", base=2)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v)}"))
        ax.set_xlabel("distinct 4 KB pages touched")
        ax.set_ylabel("dTLB load misses per access")
        ax.legend(loc="upper left")
    else:
        empty(ax, "dTLB counters unavailable here.\n" + counter_hint(ENV))
    ax.set_title("b  dTLB misses per access")
    ax = axes[2]
    k = load_proc("kernels_tlb_summary")
    if k is not None:
        k = k.copy()
        k["cfg"] = k.kernel + " " + np.where(k.order == "rand", "random", "stride " + k.stride.astype(str))
        cats = list(dict.fromkeys(k.cfg))
        groups = {PAGE_LABEL.get(p, p): [k[(k.cfg == c) & (k.pages == p)].ns_per_elem_mean.mean() for c in cats] for p in k.pages.unique()}
        errs = {PAGE_LABEL.get(p, p): [k[(k.cfg == c) & (k.pages == p)].ns_per_elem_ci95.mean() for c in cats] for p in k.pages.unique()}
        bars(ax, cats, groups, errs, "time per element (ns)")
        ax.set_title("c  Kernels: 4 KB vs 2 MB pages (unit stride, page stride, random)")
    else:
        empty(ax, "no kernel TLB data")
    save(fig, "fig9_tlb")


def fig_pitfalls():
    bw, lat, ld = load("pitfall_bw"), load("pitfall_lat"), load("pitfall_loaded")
    if bw is None and lat is None:
        return
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))

    def barpair(ax, df, labels, names, col, ylabel, title):
        vals = [df[df.label == l][col].mean() for l in labels]
        errs = [df[df.label == l][col].std() for l in labels]
        ax.bar(range(len(labels)), vals, 0.55, yerr=clip_err(vals, errs), color=[PAL[1], PAL[0]][: len(labels)] if len(labels) == 2 else PAL[: len(labels)],
               error_kw={"elinewidth": 0.9, "ecolor": INK2})
        for j, v in enumerate(vals):
            ax.text(j, v, f"{v:.1f}", ha="center", va="bottom", fontsize=8.5)
        ax.set_xticks(range(len(labels)), names)
        ax.set_ylabel(ylabel)
        ax.grid(axis="x", visible=False)
        ax.set_title(title)

    if bw is not None:
        barpair(axes[0, 0], bw, ["P1_llc_resident", "P1_dram_sized"], ["buffer fits LLC\n(naive)", "DRAM-sized\n(correct)"],
                "gbps", "reported 'DRAM' bandwidth (GB/s)", "P1  Cache reuse inflates 'DRAM' bandwidth")
        ax = axes[0, 1]
        for i, (l, n) in enumerate([("P2_read_uninitialized", "never written (faults, then zero page)"),
                                    ("P2_read_initialized", "initialised")]):
            g = bw[bw.label == l]
            ax.plot(g.rep, g.gbps, color=PAL[1 - i], marker=MARK[i], label=n)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_xlabel("repetition")
        ax.set_ylabel("read bandwidth (GB/s)")
        ax.set_ylim(bottom=0)
        ax.legend()
        ax.set_title("P2  Reading untouched memory")
        ax = axes[0, 2]
        for i, (l, n) in enumerate([("P2_write_first_touch", "no pre-fault"), ("P2_write_prefaulted", "pre-faulted")]):
            g = bw[bw.label == l]
            ax.plot(g.rep, g.gbps, color=PAL[1 - i], marker=MARK[i], label=n)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_xlabel("repetition")
        ax.set_ylabel("write bandwidth (GB/s)")
        ax.set_ylim(bottom=0)
        ax.legend()
        ax.set_title("P2  First repetition pays page faults")
    if lat is not None:
        barpair(axes[1, 0], lat, ["P3_sequential_chase", "P3_random_chase"], ["sequential chase\n(naive)", "random chase\n(correct)"],
                "lat_ns", "reported DRAM latency (ns)", "P3  Prefetchers hide latency")
    ax = axes[1, 1]
    groups = []
    if bw is not None:
        groups += [(bw, "P4_pinned", "bw pinned", "gbps"), (bw, "P4_unpinned", "bw unpinned", "gbps")]
    if groups:
        for j, (df, l, n, col) in enumerate(groups):
            v = df[df.label == l][col].to_numpy()
            ax.scatter(np.full(len(v), j) + np.linspace(-0.12, 0.12, len(v)), v, color=PAL[j % 2],
                       marker=MARK[j], s=24, edgecolor=SURF, linewidth=0.6)
            if len(v):
                ax.text(j, v.max(), f"CV {100 * v.std() / v.mean():.1f}%", ha="center", va="bottom", fontsize=8)
        ax.set_xticks(range(len(groups)), [g[2] for g in groups])
        ax.set_ylabel("bandwidth (GB/s), each dot = 1 repetition")
        ax.grid(axis="x", visible=False)
    if ld is not None and len(ld):
        txt = "\n".join(f"{l.replace('P4_', '')}: {g.lat_ns.mean():.0f} ns (CV {100 * g.lat_ns.std() / g.lat_ns.mean():.0f}%)"
                        for l, g in ld.groupby("label", sort=False))
        ax.text(0.02, 0.02, "loaded latency:\n" + txt, transform=ax.transAxes, fontsize=7.5, color=INK2, va="bottom")
    ax.set_title("P4  Pinning and SMT placement")
    ax = axes[1, 2]
    if lat is not None:
        for i, (l, n) in enumerate([("P5_cold_nominal_ghz", "cold, 2 ms runs"), ("P5_warm_calibrated", "warmed, calibrated")]):
            g = lat[lat.label == l]
            if len(g):
                ax.plot(g.rep, g.lat_ns, color=PAL[1 - i], marker=MARK[i],
                        label=f"{n}: {g.lat_cycles.mean():.2f} cycles @ {g.ghz.iloc[0]:.2f} GHz")
        ax.set_xlabel("repetition")
        ax.set_ylabel("L1 latency (ns)")
        ax.set_ylim(bottom=0)
        ax.legend(loc="lower right")
    ax.set_title("P5  Frequency: ns and cycle conversions drift")
    save(fig, "fig10_pitfalls", "naive vs correct measurement, same code otherwise")


def main():
    for f in (fig_latency_wss, fig_pattern_latency, fig_pattern_bw, fig_rwmix, fig_mlp, fig_loaded,
              fig_bw_wss, fig_kernels, fig_tlb, fig_pitfalls):
        try:
            f()
        except Exception as e:  # keep going: one broken figure should not hide the rest
            print(f"  figure {f.__name__} failed: {e!r}")
    print(f"wrote {len(MADE)} figures to {FIG}: {', '.join(MADE)}")


if __name__ == "__main__":
    main()
