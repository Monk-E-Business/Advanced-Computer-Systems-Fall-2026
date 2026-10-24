#!/usr/bin/env python3
"""Raw samples -> processed tables.

usage: python scripts/analyze.py results/<tag>

Per configuration (variant, kernel, type, n, offset, stride, pattern):
  median / p25 / p75 / min / mean / std of seconds-per-call over the samples,
  GFLOP/s (or Gop/s for int32), GiB/s of compulsory traffic, ns/element, cycles/element
  (using the clock measured by the same process), and speedup vs the scalar build with a
  conservative interval  [scalar_p25 / variant_p75 , scalar_p75 / variant_p25].
Writes <tag>/processed/*.csv and <tag>/summary.md (key numbers for the report).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

from simdlib import uopen

KEYS = ["variant", "kernel", "type", "n", "offset", "stride", "pattern"]


def regime(ws, c):
    if ws <= c["L1"]:
        return "L1"
    if ws <= c["L2"]:
        return "L2"
    if ws <= c["L3"]:
        return "LLC"
    return "DRAM"


def summarise(df, caches):
    """Robust two-level summary: per (config, round) median, then median across rounds.
    p25/p75 are quantiles of the per-round medians when there are >= 3 rounds (between-round
    spread), otherwise quantiles of the pooled samples. min_s is the minimum over all samples."""
    if "yshift" not in df:
        df = df.assign(yshift=0)
    if "round" not in df:
        df = df.assign(round=0)
    keys = KEYS + ["yshift"]
    per = df.groupby(keys + ["round"], sort=False).agg(
        ws_bytes=("ws_bytes", "first"), bytes=("bytes", "first"), flops=("flops", "first"),
        reps=("reps", "first"), n_samples=("sec_per_call", "size"), rmed=("sec_per_call", "median"),
        rmin=("sec_per_call", "min"), ghz=("ghz", "median")).reset_index()
    pooled = df.groupby(keys, sort=False)["sec_per_call"]
    out = per.groupby(keys, sort=False).agg(
        ws_bytes=("ws_bytes", "first"), bytes=("bytes", "first"), flops=("flops", "first"),
        reps=("reps", "first"), rounds=("round", "nunique"), samples=("n_samples", "sum"),
        median_s=("rmed", "median"), min_s=("rmin", "min"), ghz=("ghz", "median"),
        round_spread=("rmed", lambda s: s.max() / s.min())).reset_index()
    q = per.groupby(keys, sort=False)["rmed"]
    multi = out["rounds"] >= 3
    p25r, p75r = q.quantile(0.25).values, q.quantile(0.75).values
    p25p, p75p = pooled.quantile(0.25).values, pooled.quantile(0.75).values
    out["p25_s"] = np.where(multi, p25r, p25p)
    out["p75_s"] = np.where(multi, p75r, p75p)
    out["mean_s"] = pooled.mean().values
    out["std_s"] = pooled.std().values
    out["cv"] = out["std_s"] / out["mean_s"]
    out["gflops"] = out["flops"] / out["median_s"] / 1e9
    out["gflops_lo"] = out["flops"] / out["p75_s"] / 1e9
    out["gflops_hi"] = out["flops"] / out["p25_s"] / 1e9
    out["gibs"] = out["bytes"] / out["median_s"] / 2**30
    out["gibs_lo"] = out["bytes"] / out["p75_s"] / 2**30
    out["gibs_hi"] = out["bytes"] / out["p25_s"] / 2**30
    out["ns_per_elem"] = out["median_s"] / out["n"].clip(lower=1) * 1e9
    out["cycles_per_elem"] = out["ns_per_elem"] * out["ghz"]
    out["ns_per_call"] = out["median_s"] * 1e9
    out["regime"] = [regime(w, caches) for w in out["ws_bytes"]]
    return out


def add_speedup(s, base="scalar"):
    keys = ["kernel", "type", "n", "offset", "stride", "pattern", "yshift"]
    b = s[s["variant"] == base][keys + ["median_s", "p25_s", "p75_s"]].rename(
        columns={"median_s": "b_med", "p25_s": "b_p25", "p75_s": "b_p75"})
    m = s.merge(b, on=keys, how="left")
    m["speedup"] = m["b_med"] / m["median_s"]
    m["speedup_lo"] = m["b_p25"] / m["p75_s"]
    m["speedup_hi"] = m["b_p75"] / m["p25_s"]
    return m.drop(columns=["b_med", "b_p25", "b_p75"])


def nearest(df, ws):
    return df.iloc[(np.log(df["ws_bytes"]) - np.log(ws)).abs().argsort()[:1]]


def plateau(bw, lo, hi):
    sel = bw[(bw["ws_bytes"] >= lo) & (bw["ws_bytes"] <= hi)]
    return float(sel["gibs"].median()) if len(sel) else float("nan")


def main():
    run = sys.argv[1]
    raw, proc = os.path.join(run, "raw"), os.path.join(run, "processed")
    os.makedirs(proc, exist_ok=True)
    with uopen(os.path.join(run, "sysinfo.json")) as f:
        info = json.load(f)
    ca = info["caches"]
    c = {"L1": ca.get("L1d", {}).get("bytes") or 32 * 1024, "L2": ca.get("L2", {}).get("bytes") or 1024 * 1024}
    c["L3"] = ca.get("L3", {}).get("bytes") or 8 * 1024 * 1024
    # measured LLC knee (needs only the bandwidth CSV) before regimes are assigned
    bpath = os.path.join(raw, "bandwidth.csv")
    if os.path.exists(bpath):
        b0 = summarise(pd.read_csv(bpath), c)
        vs0 = list(b0["variant"].unique())
        best0 = "avx512" if "avx512" in vs0 else [v for v in vs0 if v != "scalar"][0]
        rd0 = b0[(b0["variant"] == best0) & (b0["kernel"] == "read")].sort_values("ws_bytes")
        early0 = rd0[(rd0["ws_bytes"] >= 2 * c["L2"]) & (rd0["ws_bytes"] <= 4 * c["L2"])]["gibs"].median()
        drop0 = rd0[(rd0["ws_bytes"] > 4 * c["L2"]) & (rd0["gibs"] < 0.75 * early0)]
        # knee = midpoint (geometric) between the last size still on the LLC plateau and the first below it
        if len(drop0):
            prev = rd0[rd0["ws_bytes"] < drop0["ws_bytes"].iloc[0]]["ws_bytes"].max()
            drop0 = drop0.assign(ws_bytes=np.sqrt(prev * drop0["ws_bytes"]))
            c["L3_sysfs"] = c["L3"]
            c["L3"] = min(c["L3"], float(drop0["ws_bytes"].iloc[0]))
    tables = {}
    for exp in ("sizes", "bandwidth", "align", "tail", "stride", "dtype"):
        p = os.path.join(raw, f"{exp}.csv")
        if not os.path.exists(p):
            continue
        df = pd.read_csv(p)
        s = summarise(df, c)
        if exp != "bandwidth":
            s = add_speedup(s)
        # 'level' = the hierarchy level a size was *chosen* to target (ranked n within each kernel/type)
        labels = {"stride": ["L1", "L2", "LLC", "DRAM"], "dtype": ["L1", "L2", "DRAM"], "align": ["L1", "L2", "DRAM"]}.get(exp)
        if labels:
            lv = {}
            for (k, ty), g in s.groupby(["kernel", "type"]):
                for i, n in enumerate(sorted(g["n"].unique())):
                    lv[(k, ty, n)] = labels[min(i, len(labels) - 1)]
            s["level"] = [lv[(k, ty, n)] for k, ty, n in zip(s["kernel"], s["type"], s["n"])]
        else:
            s["level"] = s["regime"]
        s.to_csv(os.path.join(proc, f"{exp}_summary.csv"), index=False, float_format="%.6g")
        tables[exp] = s

    # ---------------- derived: bandwidth roofs, peaks ----------------
    roofs = {}
    if "bandwidth" in tables:
        bw = tables["bandwidth"]
        variants = list(bw["variant"].unique())
        best = "avx512" if "avx512" in variants else [v for v in variants if v != "scalar"][0]
        eff = c["L3"]  # effective (measured) LLC size, see the knee detection above
        bands = {"L1": (0, 0.75 * c["L1"]), "L2": (2 * c["L1"], 0.75 * c["L2"]),
                 "LLC": (2 * c["L2"], 0.5 * eff), "DRAM": (2 * eff, 1e18)}
        for k in ("read", "write"):
            sel = bw[(bw["variant"] == best) & (bw["kernel"] == k)]
            roofs[k] = {lvl: plateau(sel, lo, hi) for lvl, (lo, hi) in bands.items()}
        # Roofline roof = best sustained bandwidth demonstrated by ANY streaming kernel at that level.
        # (The read-only probe alone under-reports L1: its 4 accumulators are add-latency bound.)
        pool = [bw[bw["variant"] == best]]
        if "sizes" in tables:
            sz = tables["sizes"]
            # every vector build counts: the widest one can run at a lower clock (AVX-512 licence)
            pool.append(sz[(~sz["variant"].isin(["scalar", "scalar_native"])) & (sz["kernel"].isin(["saxpy", "dotsimd", "mul"]))])
        pool = pd.concat(pool)
        roofs["roof"], roofs["roof_kernel"] = {}, {}
        for lvl, (lo, hi) in bands.items():
            best_k, best_v = None, float("nan")
            for (k, vv), g in pool.groupby(["kernel", "variant"]):
                v = plateau(g, lo, hi)
                if np.isfinite(v) and not (best_v >= v):
                    best_k, best_v = f"{k}/{vv}", v
            roofs["roof"][lvl], roofs["roof_kernel"][lvl] = best_v, best_k
        roofs["variant"] = best
    peaks = pd.read_csv(os.path.join(raw, "peak.csv")) if os.path.exists(os.path.join(raw, "peak.csv")) else None
    json.dump({"caches": c, "bandwidth_gibs": roofs,
               "peaks": peaks.to_dict(orient="records") if peaks is not None else []},
              uopen(os.path.join(proc, "roofs.json"), "w"), indent=2)

    # ---------------- summary.md ----------------
    L = []
    L.append(f"# Results summary — {os.path.basename(os.path.abspath(run))}\n")
    L.append(f"CPU: **{info['cpu_model']}** · {info.get('os', '?')} · {info.get('platform', '')} "
             f"{'(MSYS2 ' + info['msystem'] + ')' if info.get('msystem', 'none') != 'none' else ''} · "
             f"hypervisor: {info.get('hypervisor', '?')}  ")
    L.append(f"Caches (from sysfs): L1d {c['L1'] >> 10} KiB · L2 {c['L2'] >> 10} KiB · LLC {int(c.get('L3_sysfs', c['L3'])) >> 20} MiB  ")
    if "L3_sysfs" in c and c["L3"] < 0.9 * c["L3_sysfs"]:
        L.append(f"**Measured LLC knee: ~{c['L3'] / 2**20:.0f} MiB.** The read stream falls to DRAM speed far below the "
                 f"{int(c['L3_sysfs']) >> 20} MiB that sysfs reports (shared / partitioned L3). Regimes below use the measured size.  ")
    L.append(f"Measured clock (dependent-add chain): {info['measured_ghz_dependent_add_chain']} GHz · "
             f"frequency policy: {str(info.get('frequency_policy', '?'))[:110]}  ")
    L.append(f"Cores: {info.get('physical_cores', '?')} physical / {info.get('logical_cpus', '?')} logical · SMT active: "
             f"{info.get('smt_active', '?')} · hybrid (P/E cores): {info.get('hybrid_cpu', '?')} · pinned CPU: "
             f"{info['pinned_cpu']} · timer: {info.get('timer', '?')}  ")
    L.append(f"Compiler: {info['compiler'].splitlines()[1] if len(info['compiler'].splitlines()) > 1 else info['compiler']}\n")
    if info.get("windows_host"):
        L.append("Windows details (CIM / powercfg):\n```\n" + json.dumps(info["windows_host"], indent=1) + "\n```\n")
    L.append("All numbers are medians over samples; speedup = scalar median / variant median. "
             "Brackets are the conservative IQR-based interval.\n")

    if "sizes" in tables:
        s = tables["sizes"]
        L.append("## 1. Speedup vs scalar build, by regime (float32)\n")
        targets = {"L1": c["L1"] / 2, "L2": c["L2"] / 2, "LLC": np.sqrt(4 * c["L2"] * c["L3"] / 2),
                   "DRAM": s["ws_bytes"].max()}
        vs = [v for v in s["variant"].unique() if v != "scalar"]
        L.append("| kernel | regime (WS) | scalar GFLOP/s | " + " | ".join(vs) + " |")
        L.append("|---|---|---|" + "---|" * len(vs))
        for k in ["saxpy", "dot", "dotsimd", "mul", "stencil"]:
            sk = s[s["kernel"] == k]
            if sk.empty:
                continue
            for reg, ws in targets.items():
                row = nearest(sk[sk["variant"] == "scalar"], ws)
                if row.empty:
                    continue
                n = int(row["n"].iloc[0])
                cells = []
                for v in vs:
                    r = sk[(sk["variant"] == v) & (sk["n"] == n)]
                    cells.append(f"{r['speedup'].iloc[0]:.2f}× [{r['speedup_lo'].iloc[0]:.2f}–{r['speedup_hi'].iloc[0]:.2f}]" if len(r) else "-")
                L.append(f"| {k} | {reg} ({int(row['ws_bytes'].iloc[0]) >> 10} KiB) | {row['gflops'].iloc[0]:.2f} | " + " | ".join(cells) + " |")
        L.append("")

    if roofs:
        L.append(f"## 2. Measured single-core bandwidth plateaus (GiB/s, `{roofs['variant']}` build)\n")
        L.append("| stream | L1 | L2 | LLC | DRAM |\n|---|---|---|---|---|")
        for k in ("read", "write", "roof"):
            lab = "**roof used in roofline** (best of read/write/saxpy/dotsimd/mul, any vector build)" if k == "roof" else k
            L.append(f"| {lab} | " + " | ".join(f"{roofs[k][r]:.1f}" for r in ("L1", "L2", "LLC", "DRAM")) + " |")
        L.append("| (kernel that set the roof) | " + " | ".join(str(roofs["roof_kernel"][r]) for r in ("L1", "L2", "LLC", "DRAM")) + " |")
        L.append("")
    if peaks is not None and len(peaks):
        L.append("## 3. Measured peak FLOP/s (independent FMA / mul+add chains)\n")
        L.append("| ISA | dtype | lanes | GFLOP/s | flop/cycle |\n|---|---|---|---|---|")
        for _, r in peaks.iterrows():
            L.append(f"| {r['isa']} | {r['dtype']} | {r['lanes']} | {r['gflops']:.1f} | {r['flops_per_cycle']:.1f} |")
        L.append("")

    lic_path = os.path.join(raw, "license.csv")
    if os.path.exists(lic_path):
        lic = pd.read_csv(lic_path)
        g = lic.groupby("after", sort=False)["ghz_median"].median()
        base = g.get("scalar_mul_add", g.iloc[0])
        L.append("## 3b. Frequency licence: core clock right after ~30 ms of each kind of work\n")
        L.append("| preceding work | clock (GHz, median of trials) | relative to scalar |\n|---|---|---|")
        for k, v in g.items():
            L.append(f"| {k} | {v:.2f} | {v / base:.2f} |")
        L.append("")
        lic_summary = g.to_dict()
    else:
        lic_summary = {}

    if "align" in tables:
        a = tables["align"]
        L.append("## 4. Alignment: slowdown vs offset 0 (time ratio, >1 = slower)\n")
        L.append("Ratios use the **minimum** time over all samples and rounds: alignment costs are deterministic, and the "
                 "minimum filters interference bursts that can hit every round of one configuration. Median-based "
                 "ratios are kept in `processed/align_ratios.csv` (`ratio_median`).\n")
        rows = []
        for (v, k, n), g in a.groupby(["variant", "kernel", "n"]):
            base = g[g["offset"] == 0]
            if base.empty:
                continue
            for _, r in g.iterrows():
                rows.append(dict(variant=v, kernel=k, regime=r["level"], n=n, offset=r["offset"],
                                 ratio=r["min_s"] / base["min_s"].iloc[0],
                                 ratio_median=r["median_s"] / base["median_s"].iloc[0]))
        ar = pd.DataFrame(rows)
        ar.to_csv(os.path.join(proc, "align_ratios.csv"), index=False, float_format="%.4f")
        piv = ar.pivot_table(index=["kernel", "regime", "variant"], columns="offset", values="ratio")
        try:
            L.append(piv.to_markdown(floatfmt=".2f"))
        except ImportError:  # 'tabulate' not installed
            L.append("```\n" + piv.round(2).to_string() + "\n```")
        L.append("")

    if "tail" in tables:
        t = tables["tail"]
        L.append("## 5. Tail handling (n = 1024…1152, L1-resident): ns per call (minimum over samples)\n")
        L.append("| variant/kernel | n=1024 | max over 1025–1087 | n=1088 | worst extra ns vs n=1024 |\n|---|---|---|---|---|")
        for (v, k), g in t.groupby(["variant", "kernel"]):
            g = (g.set_index("n")["min_s"] * 1e9)
            a0 = g.get(1024, np.nan)
            mid = g[(g.index > 1024) & (g.index < 1088)]
            L.append(f"| {v}/{k} | {a0:.1f} | {mid.max():.1f} | {g.get(1088, np.nan):.1f} | {mid.max() - a0:.1f} |")
        L.append("")

    if "stride" in tables:
        st = tables["stride"]
        L.append("## 6. Stride / gather: useful GiB/s (speedup vs scalar)\n")
        st = st.assign(pat=np.where(st["kernel"] == "gather", "gather-" + st["pattern"], "s" + st["stride"].astype(str)))
        order = ["s1", "s2", "s4", "s8", "s16", "gather-seq", "gather-random"]
        for reg in ("L1", "L2", "LLC", "DRAM"):
            sr = st[st["level"] == reg]
            if sr.empty:
                continue
            L.append(f"**{reg}**\n")
            vs = list(sr["variant"].unique())
            L.append("| pattern | " + " | ".join(vs) + " |\n|---|" + "---|" * len(vs))
            for p in order:
                cells = []
                for v in vs:
                    r = sr[(sr["pat"] == p) & (sr["variant"] == v)]
                    cells.append(f"{r['gibs'].iloc[0]:.1f} ({r['speedup'].iloc[0]:.2f}×)" if len(r) else "-")
                L.append(f"| {p} | " + " | ".join(cells) + " |")
            L.append("")

    if "dtype" in tables:
        d = tables["dtype"]
        L.append("## 7. Data type: speedup vs scalar and element throughput (Gelem/s)\n")
        best = "avx512" if "avx512" in d["variant"].unique() else "native"
        L.append(f"Best-vector build = `{best}`.\n")
        L.append("| kernel | type | regime | scalar Gelem/s | " + best + " Gelem/s | speedup |\n|---|---|---|---|---|---|")
        for (k, ty, reg), g in d.groupby(["kernel", "type", "level"], sort=False):
            sc = g[g["variant"] == "scalar"]
            bv = g[g["variant"] == best]
            if sc.empty or bv.empty:
                continue
            L.append(f"| {k} | {ty} | {reg} | {1 / sc['ns_per_elem'].iloc[0]:.2f} | {1 / bv['ns_per_elem'].iloc[0]:.2f} | {bv['speedup'].iloc[0]:.2f}× |")
        L.append("")

    # variability overview
    allv = pd.concat([t.assign(exp=e) for e, t in tables.items()])
    L.append("## 8. Measurement variability\n")
    if "round_spread" in allv and allv["rounds"].max() > 1:
        L.append(f"Each configuration was measured in {int(allv['rounds'].max())} independent rounds. "
                 f"{(allv['round_spread'] > 1.5).mean() * 100:.1f}% of configurations had one round >1.5× slower than another "
                 f"(interference bursts on the host)" + ("; with >= 3 rounds the median of round medians discards such a single bad round.  " if allv["rounds"].max() >= 3 else ".  "))
    L.append(f"Median coefficient of variation across all {len(allv)} configurations: {allv['cv'].median() * 100:.2f}% "
             f"(90th percentile {allv['cv'].quantile(0.9) * 100:.2f}%, worst {allv['cv'].max() * 100:.1f}%).  ")
    L.append(f"Measured clock across all runs: median {allv['ghz'].median():.3f} GHz, range {allv['ghz'].min():.3f}–{allv['ghz'].max():.3f} GHz.\n")
    with uopen(os.path.join(run, "summary.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"[analyze] processed {', '.join(tables)} -> {proc}, summary.md")


if __name__ == "__main__":
    main()
