#!/usr/bin/env python3
"""Raw CSVs (data/raw) -> processed tables (data/processed) + summary.md.

Every processed table is per-configuration statistics over repetitions
(mean, std, median, min, max, n, 95% CI). Derived analyses:
  * per-level latency table, raw and AMAT-corrected, in ns and cycles
  * AMAT model of the working-set curve from the level latencies
  * Little's Law: single-core miss concurrency (MLP) and system-wide
    outstanding lines along the loaded-latency curve, plus its knee
  * regression of kernel runtime on cache/TLB misses per element
  * TLB penalty estimate (4 KB vs huge pages)
  * automatic sanity checks that flag results which should not be trusted
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from common import (LINE, PERF, PROC, RAW, add_per_access, agg, caches, counter_hint, fmt_bytes, has_perf,
                    huge_mode, knee, load, md_table, sysenv)

SUMMARY: list[str] = []
CHECKS: list[tuple[str, str, str]] = []   # (status, check, detail)


def say(s: str = "") -> None:
    SUMMARY.append(s)


def check(ok: bool | None, name: str, detail: str) -> None:
    CHECKS.append(("PASS" if ok else ("WARN" if ok is None else "FAIL"), name, detail))


def save(df: pd.DataFrame, name: str) -> None:
    df.to_csv(PROC / f"{name}.csv", index=False)


PA = [c + "_pa" for c in PERF]
PE = [c + "_pe" for c in PERF]


# ---------------------------------------------------------------- latency ----
def hit_fractions(size: float, caps: list[int]) -> list[float]:
    """Fraction of uniformly random accesses over `size` bytes served by each
    level, assuming inclusive, fully-associative LRU-like caches of capacity
    caps (ascending). Last element = memory."""
    cov = [min(1.0, c / size) for c in caps]
    fr, prev = [], 0.0
    for c in cov:
        fr.append(max(c - prev, 0.0))
        prev = c
    fr.append(1.0 - prev)
    return fr


def latency_section(c: dict) -> None:
    df = load("latency_wss")
    if df is None:
        return
    df = add_per_access(df, "accesses")
    s = agg(df, ["label", "pattern", "pages", "size_bytes", "stride"],
            ["lat_ns", "lat_cycles", "ghz", "gbps", "huge_kb"] + PA)
    save(s, "latency_wss_summary")

    check(bool((df["chain_ok"] == 1).all()), "pointer chains valid", "every chain is one cycle over all nodes")
    cv = df["ghz"].std() / df["ghz"].mean()
    check(cv < 0.03 if cv == cv else None, "core clock stable across latency runs",
          f"calibrated GHz mean {df['ghz'].mean():.3f}, CV {100 * cv:.1f}% (>3% suggests frequency scaling)")
    hm = huge_mode(df["pages"])
    if hm:
        hp = df[df["pages"] == hm]
        cover = (hp["huge_kb"] * 1024 / hp["size_bytes"]).clip(upper=1)
        big = cover[hp["size_bytes"] >= 8 << 20]
        check(bool((big > 0.9).all()) if len(big) else None, f"huge pages ({hm}) actually granted",
              f"median huge-page coverage of >=8 MiB {hm} buffers: {100 * big.median():.0f}%" if len(big) else "no large runs")

    caps_names = [k for k in ("L1", "L2", "L3") if k in c]
    caps = [c[k] for k in caps_names]
    rows, model_rows = [], []
    rnd = s[s["pattern"] == "rand"]
    for pages, g in rnd.groupby("pages"):
        g = g.sort_values("size_bytes")
        sizes = g["size_bytes"].to_numpy()
        lat = g["lat_ns_mean"].to_numpy()

        def pick(limit: float, floor: float = 0.0):
            ok = sizes[(sizes <= limit) & (sizes > floor)]
            return int(ok.max()) if len(ok) else None

        picks, prev_cap = [], 0
        for name, cap in zip(caps_names, caps):
            picks.append((name, pick(cap / 2, prev_cap), cap))
            prev_cap = cap
        picks.append(("DRAM", int(sizes.max()), None))

        corrected = []
        for i, (name, sz, cap) in enumerate(picks):
            if sz is None:
                corrected.append(np.nan)
                continue
            m = g[g["size_bytes"] == sz].iloc[0]
            fr = hit_fractions(sz, caps)
            known = sum(fr[j] * corrected[j] for j in range(i) if not np.isnan(corrected[j]))
            t = (m["lat_ns_mean"] - known) / fr[i] if fr[i] > 0.05 else np.nan
            corrected.append(t)
            perf_cyc = m.get("cycles_pa_mean", np.nan)
            rows.append({
                "pages": pages, "level": name, "working_set": fmt_bytes(sz), "size_bytes": sz,
                "lat_ns": m["lat_ns_mean"], "ci95_ns": m["lat_ns_ci95"],
                # per-repetition cycles (each run calibrates its own clock), robust to frequency drift
                "lat_cycles": m["lat_cycles_mean"], "perf_cycles": perf_cyc,
                "frac_served_at_level": fr[i], "amat_corrected_ns": t,
                "amat_corrected_cycles": t * m["ghz_mean"] if t == t else np.nan,
            })
        tl = [t for t in corrected]
        if all(t == t for t in tl):
            for sz, meas in zip(sizes, lat):
                fr = hit_fractions(sz, caps)
                model_rows.append({"pages": pages, "size_bytes": sz, "measured_ns": meas,
                                   "amat_model_ns": float(np.dot(fr, tl))})
    if not rows:
        return
    table = pd.DataFrame(rows)
    save(table, "latency_table")
    say("## 1. Zero-queue latency per level (random pointer chase, idle system)")
    say("")
    say("Working set chosen at <= half of each level's capacity. `amat_corrected` removes the share of accesses "
        "that still hit a smaller level (uniform-random model, inclusive caches); `perf_cycles` comes from the "
        "PMU and checks the GHz conversion.")
    say("")
    say(md_table(table[["pages", "level", "working_set", "lat_ns", "ci95_ns", "lat_cycles", "perf_cycles",
                        "frac_served_at_level", "amat_corrected_ns", "amat_corrected_cycles"]]))
    say("")
    for pages, t in table.groupby("pages"):
        v = t["lat_ns"].to_numpy()
        check(bool(np.all(np.diff(v) > 0)), f"latency increases L1<L2<...<DRAM ({pages})",
              " < ".join(f"{x:.1f}" for x in v) + " ns")
        l1 = t[t["level"] == "L1"]
        if len(l1):
            cyc = float(l1["lat_cycles"].iloc[0])
            check(3 <= cyc <= 7, f"L1 load-to-use in 3-7 cycles ({pages})",
                  f"{cyc:.2f} cycles (vendor docs: 4-5; outside range => clock calibration or timing is off)")
        if "L3" in c:
            dram_sz = int(t[t["level"] == "DRAM"]["size_bytes"].iloc[0])
            check(dram_sz >= 4 * c["L3"], f"DRAM point well beyond LLC ({pages})",
                  f"largest working set {fmt_bytes(dram_sz)} vs LLC {fmt_bytes(c['L3'])} "
                  f"({100 * min(1, c['L3'] / dram_sz):.0f}% of random accesses can still hit LLC)")
    if model_rows:
        mdl = pd.DataFrame(model_rows)
        save(mdl, "amat_model")
        say("**AMAT model vs measurement** (mean absolute % error over the whole sweep): " + ", ".join(
            f"{p}: {100 * np.mean(np.abs(g.amat_model_ns - g.measured_ns) / g.measured_ns):.1f}%"
            for p, g in mdl.groupby("pages")))
        say("")
    hm = huge_mode(table["pages"])
    if hm and "4k" in set(table["pages"]):
        d4 = table[(table.pages == "4k") & (table.level == "DRAM")]["lat_ns"].iloc[0]
        dh = table[(table.pages == hm) & (table.level == "DRAM")]["lat_ns"].iloc[0]
        say(f"DRAM latency with 4 KB pages exceeds huge pages by **{d4 - dh:.1f} ns** "
            f"({100 * (d4 / dh - 1):.0f}%): page-walk cost folded into 'memory latency'.")
        say("")

    seq = s[s["pattern"] == "seq"]
    if len(seq) and len(rnd):
        say("**Prefetching (sequential chase) at the largest working set:** " + ", ".join(
            f"stride {int(st)} B: {g.sort_values('size_bytes').iloc[-1]['lat_ns_mean']:.1f} ns"
            for st, g in seq.groupby("stride")) + f"; random: {rnd[rnd.pages == '4k'].sort_values('size_bytes').iloc[-1]['lat_ns_mean']:.1f} ns.")
        say("")


# -------------------------------------------------------------- bandwidth ----
BWKEYS = ["label", "pattern", "pages", "size_bytes", "gran", "stride", "read_pct", "nt", "delay",
          "threads", "pinned", "init"]


def traffic_factor(read_pct, nt):
    """DRAM transfers per demanded byte: a normal store to a missing line
    reads it first (RFO) and later writes it back -> 2 transfers; NT store -> 1."""
    r = read_pct / 100.0
    return r + (1 - r) * np.where(nt == 1, 1.0, 2.0)


def bandwidth_section(c: dict) -> None:
    out = {}
    for name in ("bw_pattern", "bw_rwmix", "bw_wss"):
        df = load(name)
        if df is None:
            continue
        s = agg(df, BWKEYS, ["gbps", "line_gbps", "gbps_min_thread", "gbps_max_thread", "huge_kb"])
        s["dram_traffic_gbps"] = s["line_gbps_mean"] * traffic_factor(s["read_pct"], s["nt"])
        save(s, f"{name}_summary")
        out[name] = s

    if "bw_wss" in out:
        w = out["bw_wss"]
        hm = huge_mode(w["pages"])
        if hm:
            hp = w[(w["pages"] == hm) & (w["size_bytes"] >= 8 << 20)]
            cover = (hp["huge_kb_mean"] * 1024 / (hp["size_bytes"] * hp["threads"])).clip(upper=1)
            check(bool((cover > 0.9).all()) if len(cover) else None, f"bandwidth buffers really on {hm} pages",
                  (f"median coverage {100 * cover.median():.0f}% of >=8 MiB buffers"
                   + ("" if (cover > 0.9).all() else f"; {int((cover <= 0.9).sum())} configuration(s) fell back "
                      "to 4 KB pages (large pages ran out) - compare them as 4 KB")) if len(cover) else "no large runs")

    if "bw_pattern" in out:
        s = out["bw_pattern"]
        say("## 2. Bandwidth vs access pattern and granularity (DRAM-sized buffers)")
        say("")
        t = s[["threads", "pattern", "gran", "stride", "gbps_mean", "gbps_ci95", "line_gbps_mean"]].copy()
        t.columns = ["threads", "pattern", "gran_B", "stride_B", "useful_GBps", "ci95", "lines_GBps"]
        say(md_table(t))
        say("")
        say("`useful` = bytes the program asked for; `lines` = whole 64 B lines moved. "
            "Their ratio is the wasted-bandwidth factor of sparse access.")
        say("")

    if "bw_rwmix" in out:
        s = out["bw_rwmix"]
        say("## 3. Read/write mix")
        say("")
        nt_max = s["threads"].max()
        t = s[s["threads"] == nt_max][["label", "pattern", "read_pct", "nt", "gbps_mean", "gbps_ci95",
                                       "dram_traffic_gbps"]].copy()
        t.columns = ["config", "pattern", "read_%", "nt_stores", "demanded_GBps", "ci95", "est_DRAM_traffic_GBps"]
        say(f"At {nt_max} threads. `est_DRAM_traffic` adds read-for-ownership traffic for normal stores "
            "(each written line is read, then written back).")
        say("")
        say(md_table(t))
        say("")
        ceil = parse_generic_ceiling()
        one = s[(s.threads == 1) & (s.label == "rwmix")]
        for _, r in one.iterrows():
            cap = ceil.get(int(r.read_pct))
            if cap:
                check(r.gbps_mean < 0.8 * cap, f"1-thread mix {int(r.read_pct)}% read is memory-bound",
                      f"{r.gbps_mean:.1f} GB/s vs generic-loop ceiling {cap:.1f} GB/s (L2-resident)")

    env = sysenv()
    peak = env.get("peak_gbps")
    allbw = pd.concat([v for v in out.values()], ignore_index=True) if out else None
    if allbw is not None and peak:
        dram = allbw[allbw["size_bytes"] * allbw["threads"] >= 4 * c.get("L3", 0)]
        mx = dram["dram_traffic_gbps"].max()
        check(mx <= float(peak), "DRAM traffic below theoretical peak",
              f"max {mx:.1f} GB/s vs theoretical {float(peak):.1f} GB/s")


def parse_generic_ceiling() -> dict:
    p = RAW / "validation.txt"
    out = {}
    if p.exists():
        for m in re.finditer(r"read_pct=(\d+): ([\d.]+) GB/s", p.read_text(encoding="utf-8", errors="replace")):
            out[int(m.group(1))] = float(m.group(2))
    return out


# ---------------------------------------------------------------- intensity --
def intensity_section() -> None:
    df = load("mlp")
    say("## 4. Access intensity, the knee, and Little's Law")
    say("")
    if df is not None:
        s = agg(df, ["chains", "pages", "size_bytes"], ["lat_ns", "gbps", "ghz"])
        s = s.sort_values("chains")
        lat1 = float(s.iloc[0]["lat_ns_mean"])
        s["ideal_gbps"] = s["chains"] * LINE / lat1          # perfect overlap
        s["latency_inflation"] = s["lat_ns_mean"] / lat1
        save(s, "mlp_summary")
        peak = float(s["gbps_mean"].max())
        conc = peak / LINE * lat1
        over = s[s["latency_inflation"] > 1.25]
        kknee = int(over.iloc[0]["chains"]) if len(over) else None
        say(f"**Single core (independent random chains, {fmt_bytes(s.iloc[0]['size_bytes'])}):** "
            f"idle latency {lat1:.1f} ns, peak {peak:.2f} GB/s. Little's Law, L = λ·W: "
            f"in-flight lines = {peak:.2f} GB/s / 64 B x {lat1:.1f} ns = **{conc:.1f}**, "
            "an estimate of the core's outstanding-miss limit (L1 fill buffers / superqueue). "
            + (f"Latency per hop exceeds 1.25x idle at **{kknee} chains**." if kknee else
               "Latency never exceeded 1.25x idle in the tested range."))
        say("")
        say(md_table(s[["chains", "lat_ns_mean", "lat_ns_ci95", "gbps_mean", "ideal_gbps", "latency_inflation"]]))
        say("")

    ld = load("loaded")
    if ld is None:
        return
    ld["total_gbps"] = ld["gen_gbps"] + LINE / ld["lat_ns"]       # generators + chaser's own traffic
    s = agg(ld, ["label", "read_pct", "nt", "delay", "gens"], ["lat_ns", "gen_gbps", "total_gbps"])
    s["outstanding_lines"] = s["total_gbps_mean"] / LINE * s["lat_ns_mean"]
    s["dram_traffic_gbps"] = s["total_gbps_mean"] * traffic_factor(s["read_pct"], s["nt"])
    idle = s[s["gens"] == 0]
    idle_lat = float(idle["lat_ns_mean"].min()) if len(idle) else float(s["lat_ns_mean"].min())
    s["latency_inflation"] = s["lat_ns_mean"] / idle_lat
    s["is_knee"] = False
    knees = []
    for (lab, mix), g in s[s["gens"] > 0].groupby(["label", "read_pct"]):
        g = g.sort_values("total_gbps_mean")
        k = knee(g["total_gbps_mean"].to_numpy(), g["lat_ns_mean"].to_numpy())
        r = g.iloc[k]
        s.loc[r.name, "is_knee"] = True
        mx = g.iloc[-1]
        knees.append({"mix_read_%": int(mix), "knee_GBps": r.total_gbps_mean, "knee_lat_ns": r.lat_ns_mean,
                      "knee_outstanding_lines": r.outstanding_lines, "max_GBps": g.total_gbps_mean.max(),
                      "lat_at_max_ns": mx.lat_ns_mean, "outstanding_at_max": mx.outstanding_lines,
                      "est_DRAM_traffic_at_max": mx.dram_traffic_gbps})
    save(s, "loaded_summary")
    if knees:
        kt = pd.DataFrame(knees).sort_values("mix_read_%", ascending=False)
        save(kt, "loaded_knees")
        say(f"**Loaded latency (all other cores streaming, delay swept).** Idle latency {idle_lat:.1f} ns. "
            "`outstanding_lines` = throughput / 64 B x latency (Little's Law) - the number of memory requests "
            "the whole system keeps in flight. Past the knee, extra offered load only adds queueing delay.")
        say("")
        say(md_table(kt))
        say("")
    mlc_section(s)


def mlc_section(loaded: pd.DataFrame) -> None:
    d = RAW / "mlc"
    if not d.exists():
        return
    say("**Intel MLC cross-check**")
    say("")
    idle = d / "idle_latency.txt"
    if idle.exists():
        m = re.search(r"\(\s*([\d.]+)\s*ns\)", idle.read_text(encoding="utf-8", errors="replace"))
        if m:
            say(f"MLC idle latency: {float(m.group(1)):.1f} ns")
    ll = d / "loaded_latency.txt"
    if ll.exists():
        rows = [(int(a), float(b), float(c2) / 1000) for a, b, c2 in
                re.findall(r"^\s*(\d{5})\s+([\d.]+)\s+([\d.]+)", ll.read_text(encoding="utf-8", errors="replace"), re.M)]
        if rows:
            m = pd.DataFrame(rows, columns=["inject_delay", "lat_ns", "gbps"])
            save(m, "mlc_loaded")
            say(f"MLC loaded latency: {len(m)} points, max {m.gbps.max():.1f} GB/s, "
                f"latency {m.lat_ns.min():.0f}-{m.lat_ns.max():.0f} ns (overlaid on Fig. 6).")
    say("")


# ----------------------------------------------------------------- kernels ---
def kernels_section() -> None:
    frames = []
    for name in ("kernels", "kernels_tlb"):
        df = load(name)
        if df is not None:
            df["elems"] = df["passes"] * df["n"]
            df = add_per_access(df, "elems", "_pe")
            frames.append(df)
            s = agg(df, ["label", "kernel", "order", "stride", "pages", "footprint_bytes"],
                    ["ns_per_elem", "gbps"] + PE)
            save(s, f"{name}_summary")
            check(bool((df["check_ok"] == 1).all()), f"{name}: results match reference loop",
                  "element-wise comparison against a plain sequential loop")
    if not frames:
        return
    df = pd.concat(frames, ignore_index=True)
    say("## 5. Cache-miss impact on z=x*y and y=a*x+y")
    say("")
    s = load_summary("kernels_summary")
    if s is not None:
        loc = s[s.label == "locality"].copy()
        if len(loc):
            loc["order"] = np.where(loc.order == "stride", "stride " + loc.stride.astype(str), loc.order)
            cols = ["kernel", "order", "ns_per_elem_mean", "ns_per_elem_ci95", "gbps_mean"]
            for cnum in ("l1d_miss_pe_mean", "llc_miss_pe_mean", "dtlb_miss_pe_mean"):
                if cnum in loc and loc[cnum].notna().any():
                    cols.append(cnum)
            say(f"Fixed footprint {fmt_bytes(loc.footprint_bytes.iloc[0])}, identical work, varying locality:")
            say("")
            say(md_table(loc[cols], ".3f"))
            say("")
    env = sysenv()
    if env.get("counters") == "uprof":
        say("_Counters from AMD uProf CPU profiling (AMDuProfCLI, event-based sampling), differential method: (full run) - (setup-only run), split "
            "over repetitions. On AMD, `llc_ref` = L2 misses (requests that reach the L3, AMD's LLC), `llc_miss` = "
            "demand fills from DRAM, `dtlb_miss` = L2 DTLB misses (page walks). Event mapping: "
            "analysis/uprof_events.csv._")
        say("")
    if has_perf(df, "l1d_miss"):
        rows = []
        for kern, g in df.groupby("kernel"):
            g = g.dropna(subset=["ns_per_elem"])
            # use every counter present in >= 60% of runs, and drop the runs missing one
            # (sampling-based counters occasionally give an unusable difference -> NaN)
            feats = [f for f in ("l1d_miss_pe", "llc_miss_pe", "dtlb_miss_pe") if g[f].notna().mean() >= 0.6]
            g = g.dropna(subset=feats)
            if len(g) < len(feats) + 3 or not feats:
                continue
            X = np.column_stack([np.ones(len(g))] + [g[f].to_numpy() for f in feats])
            y = g["ns_per_elem"].to_numpy()
            coef, *_ = np.linalg.lstsq(X, y, rcond=None)
            r2 = 1 - np.sum((y - X @ coef) ** 2) / np.sum((y - y.mean()) ** 2)
            row = {"kernel": kern, "n_runs": len(g), "intercept_ns": coef[0], "R2": r2}
            for f, b in zip(feats, coef[1:]):
                row[f"ns_per_{f.replace('_pe', '')}"] = b
                row[f"corr_{f.replace('_pe', '')}"] = np.corrcoef(g[f], y)[0, 1]
            rows.append(row)
        if rows:
            rt = pd.DataFrame(rows)
            save(rt, "kernel_regression")
            say("**Runtime vs counters (least squares, per element, all kernel runs):** ns/elem = a + "
                "b1·L1-miss/elem + b2·LLC-miss/elem + b3·dTLB-miss/elem. The coefficients are AMAT-style "
                "effective miss penalties (overlapped by prefetching/MLP, so far below the idle latencies).")
            say("")
            say(md_table(rt, ".3f"))
            say("")
    else:
        say("_Hardware counters unavailable on this machine: counter correlation not computed. "
            f"To fix: {counter_hint(sysenv())}._")
        say("")


def load_summary(name):
    p = PROC / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else None


# --------------------------------------------------------------------- TLB ---
def tlb_section() -> None:
    df = load("tlb")
    if df is None:
        return
    df = add_per_access(df, "accesses")
    df["pages_touched"] = df["size_bytes"] // 4096
    s = agg(df, ["pages", "pages_touched", "size_bytes"], ["lat_ns", "huge_kb"] + PA)
    save(s, "tlb_summary")
    say("## 6. TLB-miss impact (one line per 4 KB page, random page order)")
    say("")
    piv = s.pivot_table(index="pages_touched", columns="pages", values="lat_ns_mean")
    piv.columns = [f"lat_ns_{c}" for c in piv.columns]
    if "dtlb_miss_pa_mean" in s and s["dtlb_miss_pa_mean"].notna().any():
        p2 = s.pivot_table(index="pages_touched", columns="pages", values="dtlb_miss_pa_mean")
        p2.columns = [f"dtlb_miss_per_access_{c}" for c in p2.columns]
        piv = piv.join(p2)
    piv = piv.reset_index()
    piv.insert(1, "page_span", [fmt_bytes(p * 4096) for p in piv.pages_touched])
    piv.insert(2, "lines_footprint", [fmt_bytes(p * 64) for p in piv.pages_touched])
    say(md_table(piv))
    say("")
    hm = huge_mode(s["pages"])
    if "lat_ns_4k" in piv and hm and f"lat_ns_{hm}" in piv:
        last = piv.iloc[-1]
        d = last.lat_ns_4k - last[f"lat_ns_{hm}"]
        msg = f"At {int(last.pages_touched)} pages, 4 KB pages cost **{d:.1f} ns more per access** than huge pages."
        if "dtlb_miss_per_access_4k" in piv and last.dtlb_miss_per_access_4k > 0.05:
            msg += f" With {last.dtlb_miss_per_access_4k:.2f} dTLB misses/access that is ~{d / last.dtlb_miss_per_access_4k:.0f} ns per miss (page walk)."
        first = piv.iloc[0]
        msg += (f" At {int(first.pages_touched)} pages (inside TLB reach) the difference is "
                f"{first.lat_ns_4k - first[f'lat_ns_{hm}']:+.1f} ns: huge pages do not help when the TLB already covers the footprint.")
        say(msg)
        say("")
    kt = load_summary("kernels_tlb_summary")
    if kt is not None:
        p = kt.pivot_table(index=["kernel", "order", "stride"], columns="pages", values="ns_per_elem_mean").reset_index()
        hk = huge_mode(p.columns)
        if "4k" in p and hk:
            p["huge_page_speedup"] = p["4k"] / p[hk]
        say("Kernels, 4 KB vs huge pages (ns per element):")
        say("")
        say(md_table(p, ".3f"))
        say("")


# ---------------------------------------------------------------- pitfalls --
def pitfalls_section() -> None:
    say("## 7. Pitfalls / failure cases")
    say("")
    rows = []
    bw = load("pitfall_bw")
    if bw is not None:
        for lab, g in bw.groupby("label", sort=False):
            v = g["gbps"]
            rows.append({"case": lab, "metric": "GB/s", "mean": v.mean(), "min": v.min(), "max": v.max(),
                         "cv_%": 100 * v.std() / v.mean(), "first_rep": v.iloc[0],
                         "later_reps_mean": v.iloc[1:].mean() if len(v) > 1 else np.nan})
    lat = load("pitfall_lat")
    if lat is not None:
        for lab, g in lat.groupby("label", sort=False):
            v = g["lat_ns"]
            rows.append({"case": lab, "metric": "ns", "mean": v.mean(), "min": v.min(), "max": v.max(),
                         "cv_%": 100 * v.std() / v.mean(), "first_rep": v.iloc[0],
                         "later_reps_mean": v.iloc[1:].mean() if len(v) > 1 else np.nan})
            c = g["lat_cycles"]
            rows.append({"case": lab + " (cycles via GHz)", "metric": "cycles", "mean": c.mean(), "min": c.min(),
                         "max": c.max(), "cv_%": 100 * c.std() / c.mean(), "first_rep": c.iloc[0],
                         "later_reps_mean": c.iloc[1:].mean() if len(c) > 1 else np.nan})
    ld = load("pitfall_loaded")
    if ld is not None:
        for lab, g in ld.groupby("label", sort=False):
            v = g["lat_ns"]
            rows.append({"case": lab, "metric": "ns", "mean": v.mean(), "min": v.min(), "max": v.max(),
                         "cv_%": 100 * v.std() / v.mean(), "first_rep": v.iloc[0],
                         "later_reps_mean": v.iloc[1:].mean() if len(v) > 1 else np.nan})
    if rows:
        t = pd.DataFrame(rows)
        save(t, "pitfalls_summary")
        say(md_table(t))
        say("")


# ------------------------------------------------------------------- main ----
def main() -> None:
    c = caches()
    env = sysenv()
    say("# Results summary (auto-generated by analysis/process.py)")
    say("")
    say(f"CPU: {env.get('cpu_model', '?')} | measurement CPU {env.get('cpu', '?')} | threads for bandwidth: "
        f"{env.get('nt', '?')} | power policy {env.get('governor', '?')} | SMT {env.get('smt', '?')} | pages: "
        f"{env.get('thp', '?')} | OS {env.get('kernel', '?')} | {env.get('compiler', '?')} | counters "
        f"{env.get('counters', '?')} | "
        f"reps {env.get('reps', '?')} x {env.get('ms', '?')} ms" + (" | **QUICK smoke run**" if env.get("quick") == "1" else ""))
    say("")
    say("Caches: " + ", ".join(f"{k} {fmt_bytes(v)}" for k, v in c.items()) + ". Error terms are 95% confidence "
        "intervals over repetitions (t-distribution).")
    say("")
    body_start = len(SUMMARY)
    for f in (latency_section, bandwidth_section):
        f(c)
    intensity_section()
    kernels_section()
    tlb_section()
    pitfalls_section()
    fails = RAW / "failures.txt"
    if fails.exists():
        lines = [l for l in fails.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        check(not lines, "every configuration ran",
              f"{len(lines)} configuration(s) failed and were skipped - see data/raw/failures.txt"
              if lines else "data/raw/failures.txt is empty")
    if not any(has_perf(load(n)) for n in ("latency_wss", "kernels", "tlb", "kernels_tlb")):
        check(None, "hardware counters available", f"counter columns are NaN: {counter_hint(env)}")
    chk = ["## 0. Sanity checks", "", "| status | check | detail |", "|---|---|---|"]
    chk += [f"| {s} | {n} | {d} |" for s, n, d in CHECKS]
    chk.append("")
    SUMMARY[body_start:body_start] = chk
    (PROC / "summary.md").write_text("\n".join(SUMMARY) + "\n", encoding="utf-8")
    print(f"wrote {PROC}/summary.md and {len(list(PROC.glob('*.csv')))} processed tables")
    for s, n, d in CHECKS:
        if s != "PASS":
            print(f"  {s}: {n} - {d}")


if __name__ == "__main__":
    main()
