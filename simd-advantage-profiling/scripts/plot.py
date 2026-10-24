#!/usr/bin/env python3
"""Processed tables -> figures (PNG). usage: python scripts/plot.py results/<tag>

Conventions used in every figure:
  * each build variant keeps one colour + marker everywhere (colour never carries identity alone)
  * shaded bands / error bars = inter-quartile range over timing samples
  * dotted vertical lines = L1d / L2 / LLC capacity of the measured core
  * working-set (WS) axis is log2 bytes
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from simdlib import uopen  # noqa: E402

INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
STYLE = {  # fixed entity -> (colour, marker, linestyle, label)
    "scalar": ("#52514e", "o", "--", "scalar (x86-64, no vec)"),
    "scalar_native": ("#e87ba4", "v", ":", "scalar_native (-march=native, no vec)"),
    "sse2": ("#1baf7a", "s", "-", "sse2 (-O3 default, 128-bit)"),
    "avx2": ("#eb6834", "^", "-", "avx2 (x86-64-v3, 256-bit)"),
    "native": ("#eda100", "D", "-.", "native (-march=native)"),
    "avx512": ("#2a78d6", "P", "-", "avx512 (native + 512-bit)"),
    "neon": ("#1baf7a", "s", "-", "neon (-O3)"),
    "mask_avx2": ("#008300", "x", "-", "hand-written AVX2, masked tail"),
    "mask_avx512": ("#6250d6", "*", "-", "hand-written AVX-512, masked tail"),
}
DTYPE = {"f32": "#2a78d6", "f64": "#eb6834", "i32": "#1baf7a"}
ORDER = ["scalar", "scalar_native", "sse2", "neon", "avx2", "native", "avx512"]

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9.5,
    "axes.titlesize": 10.5, "axes.titleweight": "bold", "legend.frameon": False, "lines.linewidth": 1.6,
    "lines.markersize": 4.5,
})


def st(v):
    return STYLE.get(v, ("#6250d6", "o", "-", v))


def fmt_bytes(x, _=None):
    for unit, d in (("G", 2**30), ("M", 2**20), ("K", 2**10)):
        if x >= d:
            v = x / d
            return f"{v:.0f}{unit}" if abs(v - round(v)) < 1e-6 else f"{v:.1f}{unit}"
    return f"{x:.0f}"


def ws_axis(ax, caches, label=True):
    ax.set_xscale("log", base=2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(fmt_bytes))
    ax.xaxis.set_major_locator(matplotlib.ticker.LogLocator(base=4))
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    llc_name = "LLC (measured knee)" if caches.get("L3_sysfs", caches["L3"]) > 1.1 * caches["L3"] else "LLC"
    for name, b in (("L1d", caches["L1"]), ("L2", caches["L2"]), (llc_name, caches["L3"])):
        ax.axvline(b, color=INK2, lw=0.9, ls=":", zorder=0)
        ax.text(b, 1.0, f" {name}", transform=ax.get_xaxis_transform(), fontsize=7.5, color=INK2, va="top", ha="left")
    if label:
        ax.set_xlabel("working set (bytes, log scale)")


def line(ax, d, x, y, v, lo=None, hi=None, label=True, **kw):
    c, m, ls, lab = st(v)
    d = d.sort_values(x)
    ax.plot(d[x], d[y], color=c, marker=m, ls=ls, label=lab if label else None, markeredgewidth=0.6, **kw)
    if lo is not None and len(d):
        ax.fill_between(d[x], d[lo], d[hi], color=c, alpha=0.18, lw=0)


def variants_in(df):
    return [v for v in ORDER if v in set(df["variant"])]


def save(fig, out, name):
    fig.savefig(os.path.join(out, name), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("  ", name)


# ------------------------------------------------------------------ figures
def fig_sizes(s, caches, out):
    kernels = [k for k in ["saxpy", "dot", "dotsimd", "mul", "stencil"] if k in set(s["kernel"])]
    titles = {"saxpy": "SAXPY  y = a·x + y", "dot": "dot (plain loop)", "dotsimd": "dot (omp simd reduction)",
              "mul": "elementwise  z = x·y", "stencil": "3-point stencil"}
    vs = variants_in(s)
    # speedup
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.2), sharex=True)
    for ax, k in zip(axes.flat, kernels):
        d = s[(s["kernel"] == k) & (s["type"] == "f32")]
        for v in vs:
            if v == "scalar":
                continue
            line(ax, d[d["variant"] == v], "ws_bytes", "speedup", v, "speedup_lo", "speedup_hi")
        ax.axhline(1, color=INK, lw=1)
        ax.set_yscale("log", base=2)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}×"))
        ax.set_title(titles[k], loc="left")
        ax.set_ylabel("speedup vs scalar build")
        ws_axis(ax, caches, label=ax in axes[1])
    leg = axes.flat[len(kernels)]
    leg.axis("off")
    h, lab = axes.flat[0].get_legend_handles_labels()
    leg.legend(h, lab, loc="center left", title="build variant (g++)", alignment="left")
    fig.suptitle("Fig. 1a — SIMD speedup over the scalar build vs working-set size (float32, 1 core)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig1a_speedup_vs_size.png")
    # throughput
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.2), sharex=True)
    for ax, k in zip(axes.flat, kernels):
        d = s[(s["kernel"] == k) & (s["type"] == "f32")]
        for v in vs:
            line(ax, d[d["variant"] == v], "ws_bytes", "gflops", v, "gflops_lo", "gflops_hi")
        ax.set_yscale("log", base=2)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}"))
        ax.set_title(titles[k], loc="left")
        ax.set_ylabel("GFLOP/s (median)")
        ws_axis(ax, caches, label=ax in axes[1])
    leg = axes.flat[len(kernels)]
    leg.axis("off")
    h, lab = axes.flat[0].get_legend_handles_labels()
    leg.legend(h, lab, loc="center left", title="build variant (g++)", alignment="left")
    fig.suptitle("Fig. 1b — Achieved throughput vs working-set size (float32, 1 core)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig1b_throughput_vs_size.png")
    # cycles per element
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.2), sharex=True)
    for ax, k in zip(axes.flat, kernels):
        d = s[(s["kernel"] == k) & (s["type"] == "f32")]
        for v in vs:
            line(ax, d[d["variant"] == v], "ws_bytes", "cycles_per_elem", v)
        ax.set_yscale("log", base=2)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}"))
        ax.set_title(titles[k], loc="left")
        ax.set_ylabel("cycles / element")
        ws_axis(ax, caches, label=ax in axes[1])
    leg = axes.flat[len(kernels)]
    leg.axis("off")
    h, lab = axes.flat[0].get_legend_handles_labels()
    leg.legend(h, lab, loc="center left", title="build variant (g++)", alignment="left")
    fig.suptitle("Fig. 1c — Cycles per element (measured clock × time / n)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig1c_cycles_per_element.png")


def fig_locality(s, bw, roofs, caches, out):
    d = s[(s["kernel"] == "saxpy") & (s["type"] == "f32")]
    vs = [v for v in variants_in(d) if v in ("scalar", "sse2", "avx2", "avx512", "native")]
    best = "avx512" if "avx512" in vs else "native"
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9.5, 7.5), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    for v in vs:
        line(a1, d[d["variant"] == v], "ws_bytes", "gibs", v, "gibs_lo", "gibs_hi")
    a1.set_yscale("log", base=2)
    a1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}"))
    a1.set_ylabel("GiB/s of compulsory traffic\n(12 B per element)")
    a1.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8.5)
    a1.set_title("SAXPY bandwidth falls level by level; the vector advantage falls faster", loc="left")
    ws_axis(a1, caches, label=False)
    for v in [x for x in vs if x != "scalar"]:
        line(a2, d[d["variant"] == v], "ws_bytes", "speedup", v, "speedup_lo", "speedup_hi", label=False)
    a2.axhline(1, color=INK, lw=1)
    a2.set_yscale("log", base=2)
    a2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}×"))
    a2.set_ylabel(f"speedup vs scalar")
    # annotate best variant at representative points
    b = d[d["variant"] == best].sort_values("ws_bytes")
    for reg, ws in (("L1", caches["L1"] / 2), ("L2", caches["L2"] / 2), ("LLC", np.sqrt(4 * caches["L2"] * caches["L3"] / 2)), ("DRAM", b["ws_bytes"].max())):
        if b.empty:
            break
        r = b.iloc[(np.log(b["ws_bytes"]) - np.log(ws)).abs().argsort()[:1]]
        a2.annotate(f"{reg}: {r['speedup'].iloc[0]:.1f}×", (r["ws_bytes"].iloc[0], r["speedup"].iloc[0]),
                    xytext=(0, 12), textcoords="offset points", ha="center", fontsize=8.5, color=INK,
                    arrowprops=dict(arrowstyle="-", color=INK2, lw=0.7))
    ws_axis(a2, caches)
    fig.suptitle("Fig. 2 — Locality sweep: SAXPY float32 across L1 → L2 → LLC → DRAM", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig2_locality_saxpy.png")


def fig_align(ar, out):
    kernels = [k for k in ("saxpy", "dotsimd") if k in set(ar["kernel"])]
    regs = [r for r in ("L1", "L2", "LLC", "DRAM") if r in set(ar["regime"])]
    fig, axes = plt.subplots(len(kernels), len(regs), figsize=(4 * len(regs), 3.4 * len(kernels)), sharey="row", squeeze=False)
    offs = sorted(ar["offset"].unique())
    for i, k in enumerate(kernels):
        for j, reg in enumerate(regs):
            ax = axes[i][j]
            d = ar[(ar["kernel"] == k) & (ar["regime"] == reg)]
            for v in [x for x in ORDER if x in set(d["variant"])]:
                dv = d[d["variant"] == v].sort_values("offset")
                c, m, ls, lab = st(v)
                ax.plot([offs.index(o) for o in dv["offset"]], dv["ratio"], color=c, marker=m, ls=ls, label=lab)
            ax.axhline(1, color=INK, lw=1)
            ax.set_xticks(range(len(offs)), [str(o) for o in offs])
            ax.set_title(f"{k} — {reg}-resident", loc="left")
            if i == len(kernels) - 1:
                ax.set_xlabel("base-address offset from 64 B boundary (bytes)")
            if j == 0:
                ax.set_ylabel("time / time at offset 0")
    axes[0][0].legend(fontsize=7.5, loc="upper left")
    fig.suptitle("Fig. 3a — Misalignment penalty (float32; min time ratio vs offset 0; 64 = aligned again, control)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig3a_alignment.png")


def fig_tail(t, out):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.6))
    t = t.assign(series=np.where(t["kernel"].str.startswith("mask"), t["kernel"], t["variant"]))
    for v in [x for x in ORDER + ["mask_avx2", "mask_avx512"] if x in set(t["series"])]:
        d = t[t["series"] == v].sort_values("n")
        c, m, ls, lab = st(v)
        a1.plot(d["n"], d["min_s"] * 1e9, color=c, ls=ls, lw=1.3, label=lab)
        if v not in ("scalar", "scalar_native", "sse2"):
            a2.plot(d["n"], d["min_s"] * 1e9, color=c, ls=ls, lw=1.3, label=lab, marker=m, markersize=2.5)
    for ax in (a1, a2):
        ax.set_xlabel("n (elements)")
        ax.set_ylabel("ns per call (minimum over samples)")
        for x in range(1024, 1153, 64):
            ax.axvline(x, color=INK2, lw=0.8, ls=":", zorder=0)
    a1.set_title("all builds: scalar cost is linear in n", loc="left")
    a2.set_title("vector builds vs hand-written masked tails (remainder cost = sawtooth height)", loc="left")
    a1.legend(fontsize=7.5, loc="upper left")
    a2.legend(fontsize=7.5, loc="upper left")
    fig.suptitle("Fig. 3b — Tail handling: SAXPY float32, n = 1024…1152, L1-resident (dotted = multiples of 64)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig3b_tail.png")


def fig_stride(stt, out):
    stt = stt.assign(pat=np.where(stt["kernel"] == "gather", "gather\n" + stt["pattern"], "stride " + stt["stride"].astype(str)))
    order = ["stride 1", "stride 2", "stride 4", "stride 8", "stride 16", "gather\nseq", "gather\nrandom"]
    regs = [r for r in ("L1", "L2", "LLC", "DRAM") if r in set(stt["level"])]
    fig, axes = plt.subplots(2, len(regs), figsize=(4.1 * len(regs), 7.2), squeeze=False, sharey="row")
    for j, reg in enumerate(regs):
        d = stt[stt["level"] == reg]
        for v in variants_in(d):
            dv = d[d["variant"] == v].set_index("pat").reindex(order)
            c, m, ls, lab = st(v)
            axes[0][j].plot(range(len(order)), dv["gibs"], color=c, marker=m, ls=ls, label=lab)
            if v != "scalar":
                axes[1][j].plot(range(len(order)), dv["speedup"], color=c, marker=m, ls=ls, label=lab)
        ws = d["ws_bytes"].median()
        axes[0][j].set_title(f"{reg} target (span ≈ {fmt_bytes(ws)}B)", loc="left")
        axes[0][j].set_yscale("log", base=2)
        axes[0][j].yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}"))
        axes[1][j].axhline(1, color=INK, lw=1)
        axes[1][j].set_yscale("log", base=2)
        axes[1][j].yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}×"))
        for i in (0, 1):
            axes[i][j].set_xticks(range(len(order)), order, fontsize=7.5)
    axes[0][0].set_ylabel("useful GiB/s (12 B per element)")
    axes[1][0].set_ylabel("speedup vs scalar build")
    axes[0][0].legend(fontsize=7.5, loc="lower left")
    fig.suptitle("Fig. 4 — Stride and gather: SAXPY float32 touching x[i·s], y[i·s] or x[idx[i]]", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig4_stride_gather.png")


def fig_dtype(d, out):
    best = "avx512" if "avx512" in set(d["variant"]) else "native"
    kernels = ["saxpy", "dot", "dotsimd", "mul", "stencil"]
    regs = [r for r in ("L1", "L2", "DRAM") if r in set(d["level"])]
    fig, axes = plt.subplots(2, len(regs), figsize=(4.4 * len(regs), 7), squeeze=False)
    w = 0.26
    for j, reg in enumerate(regs):
        dr = d[(d["level"] == reg) & (d["variant"] == best)]
        for i, (col, ylab) in enumerate((("speedup", f"{best} speedup vs scalar"), ("gelems", f"{best} Gelem/s"))):
            ax = axes[i][j]
            for t_i, ty in enumerate(("f32", "f64", "i32")):
                vals = []
                for k in kernels:
                    r = dr[(dr["kernel"] == k) & (dr["type"] == ty)]
                    vals.append(np.nan if r.empty else (r["speedup"].iloc[0] if col == "speedup" else 1 / r["ns_per_elem"].iloc[0]))
                xs = np.arange(len(kernels)) + (t_i - 1) * (w + 0.02)
                ax.bar(xs, vals, width=w, color=DTYPE[ty], label=ty, edgecolor=SURF, linewidth=1)
                for x, v in zip(xs, vals):
                    if np.isfinite(v):
                        ax.text(x, v, f"{v:.1f}" if v < 10 else f"{v:.0f}", ha="center", va="bottom", fontsize=6.5, color=INK2)
            ax.set_xticks(range(len(kernels)), kernels)
            ax.set_ylabel(ylab)
            ax.grid(axis="x", visible=False)
            if col == "speedup":
                ax.axhline(1, color=INK, lw=1)
                ax.set_title(f"{reg}-resident", loc="left")
    axes[0][0].legend(title="data type", fontsize=8)
    fig.suptitle("Fig. 5 — Data type: float32 vs float64 vs int32 (lane count, op cost, bytes/element)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig5_dtype.png")


def fig_roofline(s, roofs, out):
    peaks = pd.DataFrame(roofs["peaks"])
    bw = roofs["bandwidth_gibs"].get("roof", {})
    bwk = roofs["bandwidth_gibs"].get("roof_kernel", {})
    if peaks.empty or not bw:
        return
    best = roofs["bandwidth_gibs"]["variant"]
    fig, ax = plt.subplots(figsize=(9.5, 6.4))
    ai = np.logspace(-5, 3.2, 300, base=2)
    p32 = peaks[peaks["dtype"] == "f32"]
    top = p32["gflops"].max()
    roof_lab = {"scalar_sse": "scalar mul+add", "sse2": "SSE2 4-wide", "scalar_fma": "scalar FMA",
                "avx2_fma": "AVX2 FMA 8-wide", "avx512_fma": "AVX-512 FMA 16-wide"}
    for _, r in p32.iterrows():
        if r["isa"] == "scalar_fma":
            continue
        ax.axhline(r["gflops"], color=INK2, lw=0.9, ls="--")
        ax.text(2**3.1, r["gflops"] * 1.04, f"{roof_lab.get(r['isa'], r['isa'])}: {r['gflops']:.0f} GFLOP/s", ha="right", fontsize=7.5, color=INK2)
    lvl_c = {"L1": "#2a78d6", "L2": "#1baf7a", "LLC": "#eb6834", "DRAM": "#52514e"}
    for lvl in ("L1", "L2", "LLC", "DRAM"):
        b = bw.get(lvl)
        if b is None or not np.isfinite(b):
            continue
        gb = b * 2**30 / 1e9
        y = np.minimum(gb * ai, top)
        ax.plot(ai, y, color=lvl_c[lvl], lw=1.4)
        x0 = 2**-4.15
        ax.text(x0, gb * x0 * 1.18, f"{lvl}: {b:.0f} GiB/s (set by {bwk.get(lvl)})", color=lvl_c[lvl], fontsize=7.5,
                rotation=24, rotation_mode="anchor", ha="left", va="bottom")
    ai_k = {"saxpy": 2 / 12, "dot": 2 / 8, "dotsimd": 2 / 8, "mul": 1 / 12, "stencil": 5 / 8}
    mk = {"saxpy": "o", "dot": "X", "dotsimd": "s", "mul": "^", "stencil": "D"}
    d = s[s["type"] == "f32"]
    regs = {"L1": d["ws_bytes"].min() * 0 + 0, }
    for k, a in ai_k.items():
        dk = d[d["kernel"] == k]
        for v, fill in (("scalar", False), (best, True)):
            dv = dk[dk["variant"] == v]
            for reg, col in (("L1", lvl_c["L1"]), ("DRAM", lvl_c["DRAM"])):
                r = dv[dv["regime"] == reg]
                if r.empty:
                    continue
                g = r["gflops"].max() if reg == "L1" else r.sort_values("ws_bytes")["gflops"].iloc[-1]
                ax.scatter([a], [g], marker=mk[k], s=55, facecolors=col if fill else SURF, edgecolors=col, linewidths=1.4, zorder=5)
                if fill:
                    ax.annotate(k, (a, g), xytext=(6, -3), textcoords="offset points", fontsize=7.5, color=INK)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log", base=2)
    ax.set_xlim(2**-4.2, 2**3.2)
    ax.set_ylim(0.25, top * 2)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:g}"))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}"))
    ax.set_xlabel("arithmetic intensity (flop per compulsory byte, float32)")
    ax.set_ylabel("GFLOP/s")
    from matplotlib.lines import Line2D
    h = [Line2D([], [], marker=mk[k], ls="", color=INK2, label=k) for k in mk]
    h += [Line2D([], [], marker="o", ls="", markerfacecolor=lvl_c["L1"], markeredgecolor=lvl_c["L1"], label=f"{best} build, L1-resident"),
          Line2D([], [], marker="o", ls="", markerfacecolor=SURF, markeredgecolor=lvl_c["L1"], label="scalar build, L1-resident"),
          Line2D([], [], marker="o", ls="", markerfacecolor=lvl_c["DRAM"], markeredgecolor=lvl_c["DRAM"], label=f"{best} build, DRAM-resident"),
          Line2D([], [], marker="o", ls="", markerfacecolor=SURF, markeredgecolor=lvl_c["DRAM"], label="scalar build, DRAM-resident")]
    ax.legend(handles=h, loc="lower right", fontsize=7.5, ncol=2)
    ax.set_title("Fig. 6 — Roofline: best measured single-core bandwidth per level × measured peak FLOP/s", loc="left")
    fig.tight_layout()
    save(fig, out, "fig6_roofline.png")


def fig_negative(s, stt, out, caches):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
    d = s[(s["type"] == "f32")]
    best = "avx512" if "avx512" in set(d["variant"]) else "native"
    combos = [("dot", "scalar", "dot — scalar build"), ("dot", "sse2", "dot — sse2 build"),
              ("dot", best, f"dot — {best} build (\"vectorized\" in-order reduction)"), ("dotsimd", best, f"dotsimd — {best} build")]
    for k, v, lab in combos:
        dv = d[(d["kernel"] == k) & (d["variant"] == v)].sort_values("ws_bytes")
        c, m, ls, _ = st(v)
        if k == "dotsimd":
            ls = "-"
        elif v == best:
            ls = "--"
        a1.plot(dv["ws_bytes"], dv["gflops"], color=c, marker="x" if (k == "dot" and v == best) else m, ls=ls, label=lab)
        a1.fill_between(dv["ws_bytes"], dv["gflops_lo"], dv["gflops_hi"], color=c, alpha=0.18, lw=0)
    a1.set_yscale("log", base=2)
    a1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}"))
    a1.set_ylabel("GFLOP/s")
    a1.legend(fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
    a1.set_title("(a) FP reduction: reported as vectorized, still a serial add chain", loc="left")
    ws_axis(a1, caches)
    if stt is not None:
        stt = stt[stt["kernel"].str.startswith("saxpy_s")]
        for v in [x for x in variants_in(stt) if x != "scalar"]:
            for reg, ls in (("L1", "-"), ("DRAM", ":")):
                dv = stt[(stt["variant"] == v) & (stt["level"] == reg)].sort_values("stride")
                if dv.empty:
                    continue
                c, m, _, lab = st(v)
                a2.plot(dv["stride"], dv["speedup"], color=c, marker=m, ls=ls, label=f"{v} — {reg}")
        a2.axhline(1, color=INK, lw=1)
        a2.set_xscale("log", base=2)
        a2.set_yscale("log", base=2)
        a2.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:g}"))
        a2.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, _: f"{y:g}×"))
        a2.set_xlabel("stride (elements)")
        a2.set_ylabel("speedup vs scalar build")
        a2.legend(fontsize=7, ncol=2, loc="upper right")
        a2.set_title("(b) strided SAXPY: vectorized with shuffles; wins at stride 2,\n     loses at larger strides (solid = L1, dotted = DRAM)", loc="left")
    fig.suptitle("Fig. 7 — Negative results", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    save(fig, out, "fig7_negative.png")


def main():
    run = sys.argv[1]
    proc, out = os.path.join(run, "processed"), os.path.join(run, "figures")
    os.makedirs(out, exist_ok=True)
    with uopen(os.path.join(proc, "roofs.json")) as f:
        roofs = json.load(f)
    caches = roofs["caches"]
    rd = lambda n: pd.read_csv(os.path.join(proc, n)) if os.path.exists(os.path.join(proc, n)) else None  # noqa: E731
    s, bw, al, ar, t, stt, d = (rd(x) for x in ("sizes_summary.csv", "bandwidth_summary.csv", "align_summary.csv",
                                                 "align_ratios.csv", "tail_summary.csv", "stride_summary.csv", "dtype_summary.csv"))
    print("[plot] ->", out)
    if s is not None:
        fig_sizes(s, caches, out)
        fig_locality(s, bw, roofs["bandwidth_gibs"], caches, out)
        fig_roofline(s, roofs, out)
        fig_negative(s, stt, out, caches)
    if ar is not None:
        fig_align(ar, out)
    if t is not None:
        fig_tail(t, out)
    if stt is not None:
        fig_stride(stt, out)
    if d is not None:
        d = d.assign(gelems=1 / d["ns_per_elem"])
        fig_dtype(d, out)


if __name__ == "__main__":
    main()
