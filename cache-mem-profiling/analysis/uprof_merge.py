#!/usr/bin/env python3
"""Fill the counter columns of benchmark rows from AMD uProf CPU-profile
reports (Windows + AMD Ryzen), using the differential method:

    events(timed reps) = events(full run) - events(setup-only run, --reps 0)

Both runs execute the same allocation, initialisation, chain validation and
warm-up, so the difference is what the R timed repetitions caused. It is split
evenly over the R rows (one row per repetition).

Usage (called by run_counted in scripts/lib.sh):
    uprof_merge.py --rows ROWS.csv --full A.full[,B.full] --base A.base[,B.base] \
                   --exe kernels --events uprof_events.csv
--full/--base are output prefixes; every *.csv below PREFIX.d/ is read.

uProf's report layout differs between versions, so parsing is tolerant:
  1. In every CSV, find header rows followed by data rows. If a data row's
     first cell names our executable (process or module summary), take that
     row's values: they exclude other processes.
  2. Otherwise fall back to column totals of the first table found.
EBP values may be event counts or sample counts depending on the uProf
version/options; the merge cross-checks cycles against the benchmark's own
timing and prints the ratio so you can tell which (see uprof_probe.sh).
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from pathlib import Path

COUNTERS = ["cycles", "instructions", "l1d_miss", "llc_ref", "llc_miss", "dtlb_ref", "dtlb_miss"]
# derived metrics cannot be differenced or summed
BAD = re.compile(r"ratio|rate|%|pti|per[ _]|/|utiliz|^ipc$|^cpi$|\bipc\b|\bcpi\b|freq|time|timestamp|"
                 r"^pid$|^tid$|core ?id|^cpu$|percent|average|avg", re.I)


def num(s: str):
    s = s.strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def tables(rows: list[list[str]]):
    """Yield (header, data_rows) for every header followed by >=1 row whose
    cells after the first are mostly numeric."""
    i = 0
    while i < len(rows):
        h = [c.strip() for c in rows[i]]
        if len(h) >= 2 and sum(num(c) is None and c != "" for c in h[1:]) >= 1:
            body = []
            j = i + 1
            while j < len(rows):
                r = rows[j]
                vals = [num(c) for c in r[1:]]
                filled = [c for c in r[1:] if c.strip()]
                if not filled or sum(v is not None for v in vals) < max(1, len(filled) // 2):
                    break
                body.append(r)
                j += 1
            if body:
                yield h, body
                i = j
                continue
        i += 1


PTI_RE = re.compile(r"^\(?\s*(\w+)\s*\*\s*([\d.]+)\s*\)?\s*/\s*(\w+)\s*$")   # ( A * k ) / B
DIV_RE = re.compile(r"^\(?\s*(\w+)\s*\)?\s*/\s*\(?\s*(\w+)\s*\)?\s*$")         # A / B


def parse_uprof_report(path: Path, exe: str) -> dict[str, float] | None:
    """AMD uProf 5.x CPU-profile report.csv -> {EVENT_NAME: event count} for the
    benchmark PROCESS row.

    The report lists only some events as raw columns, in SAMPLES (one sample per
    `Interval` events, see MONITORED EVENTS); the others appear only as derived
    metrics (per-1000-instructions, %, rates) whose formulas are given in
    DERIVED METRICS. Event counts are recovered as samples x interval for the raw
    columns, then by solving each formula for its unknown event. When several
    metrics give the same event, the one printed with the most significant digits
    (largest magnitude) is used, since the report rounds to 4 decimals."""
    rows = [[c.strip() for c in r] for r in csv.reader(path.read_text(encoding="utf-8", errors="replace").splitlines())]
    interval: dict[str, float] = {}
    codekey: dict[str, str] = {}   # event name -> "PMCx043:0x08"
    exprs: dict[str, str] = {}
    sec = ""
    for r in rows:
        if not any(r):
            continue
        if len(r) == 1 or (r[0] and len(r) > 1 and not any(r[1:])):
            sec = r[0].upper()
        if r[0].startswith("PMC Events"):
            sec = "MONITORED"
            continue
        if sec == "MONITORED" and len(r) > 2 and r[0] == "" and r[1]:
            m = re.search(r"PMCx([0-9A-Fa-f]+)", r[1])
            name = re.sub(r"\s*\(PMCx[0-9A-Fa-f]+\)\s*$", "", r[1])
            iv = num(r[2])
            if iv:
                interval[name] = iv
                if m:
                    um = r[3] if len(r) > 3 and r[3] else "0x00"
                    try:
                        um = f"0x{int(um, 16):02X}"
                    except ValueError:
                        um = "0x00"
                    codekey[name] = f"PMCx{int(m.group(1), 16):03X}:{um}"
        if "DERIVED METRICS" in sec and len(r) > 1 and r[0] and r[0] != "Metric Name":
            exprs[r[0]] = r[1]
    if not interval:
        return None
    # the PROCESS table row of the benchmark (not FUNCTION rows like kernels.exe!0x...)
    exe_re = re.compile(r"[\\/]" + re.escape(exe) + r"(\.exe)?\b|^" + re.escape(exe) + r"(\.exe)?\b", re.I)
    for i, h in enumerate(rows):
        if h and h[0].upper() == "PROCESS":
            for r in rows[i + 1:]:
                if not r or not r[0]:
                    break
                if exe_re.search(r[0]) and "!" not in r[0]:
                    vals = {h[j]: num(r[j]) for j in range(1, min(len(h), len(r))) if h[j]}
                    break
            else:
                continue
            break
    else:
        return None
    ev = {k: v * interval[k] for k, v in vals.items() if k in interval and v is not None}
    best: dict[str, float] = {}  # magnitude of the metric each event was derived from
    for _ in range(6):
        cands: dict[str, tuple[float, float]] = {}
        for m, e in exprs.items():
            v = vals.get(m)
            if v is None:
                continue
            m1, m2 = PTI_RE.match(e), DIV_RE.match(e)
            if m1:
                a_, k, b_ = m1.group(1), float(m1.group(2)), m1.group(3)
            elif m2:
                a_, k, b_ = m2.group(1), 1.0, m2.group(2)
            else:
                continue
            if b_ in ev and (a_ not in interval or a_ not in ev or abs(v) > best.get(a_, -1)):
                if a_ in vals and a_ in interval:
                    continue  # raw column already exact
                cand = v * ev[b_] / k
                if a_ not in cands or abs(v) > cands[a_][1]:
                    cands[a_] = (cand, abs(v))
        changed = False
        for a_, (cand, mag) in cands.items():
            if a_ not in ev or mag > best.get(a_, -1):
                ev[a_], best[a_] = cand, mag
                changed = True
        if not changed:
            break
    for name, key in codekey.items():   # also index by exact PMC code + unit mask
        if name in ev:
            ev.setdefault(key, ev[name])
    return ev


def parse_dir(prefix: Path, exe: str) -> tuple[dict[str, float], str]:
    """Event totals for one uProf run (prefix.d/**.csv). Returns (events, how)."""
    d = Path(str(prefix) + ".d")
    # PREFIX.d/ plus sibling session folders (older uProf treats -o as a base name)
    dirs = [d] + sorted(x for x in d.parent.glob(d.name + "?*") if x.is_dir())
    files = sorted({f for x in dirs if x.exists() for f in x.rglob("*.csv")})
    for f in files:  # uProf 5.x report: exact event counts for the process
        r = parse_uprof_report(f, exe)
        if r:
            return r, f"uProf report, process row, samples x interval + derived metrics ({len(r)} events)"
    exe_re = re.compile(re.escape(exe) + r"(\.exe)?\b", re.I)
    own: dict[str, float] = {}
    total: dict[str, float] = {}
    for f in files:
        rows = [r for r in csv.reader(f.read_text(encoding="utf-8", errors="replace").splitlines()) if any(c.strip() for c in r)]
        for h, body in tables(rows):
            for r in body:
                target = own if exe_re.search(r[0]) else (total if not own else None)
                if target is None:
                    continue
                for j, name in enumerate(h):
                    if j == 0 or j >= len(r) or not name or BAD.search(name):
                        continue
                    v = num(r[j])
                    if v is not None and name not in target:
                        target[name] = v
                    elif v is not None and target is total:
                        target[name] += v
        if own:
            break
    if own:
        return own, f"row for {exe}"
    return total, ("column totals (no row naming the executable)" if total else f"nothing parsed under {d}")


def read_meta(path: Path) -> float | None:
    """Expected busy cycles of a run from its --meta file (total_ns * ghz)."""
    try:
        lines = [l for l in path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        ns, ghz = (float(x) for x in lines[1].split(",")[:2])
        return ns * ghz if ns > 0 and ghz > 0 else None
    except (OSError, ValueError, IndexError):
        return None


def load_patterns(path: Path) -> dict[str, list]:
    """Per counter, in priority order: a list of exact event names to SUM (entry
    written as "A + B") or a compiled regex (first matching event name wins)."""
    pats: dict[str, list[tuple[int, object]]] = {c: [] for c in COUNTERS}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip() or line.startswith("#") or line.startswith("counter,"):
            continue
        parts = line.split(",", 3)
        if len(parts) >= 3 and parts[0] in pats:
            pat = parts[2].strip()
            if pat.startswith("="):  # "=A + B": exact names, summed
                obj: object = [x.strip() for x in pat[1:].split("+") if x.strip()]
            else:
                obj = re.compile(pat, re.I)
            pats[parts[0]].append((int(parts[1]), obj))
    return {c: [p for _, p in sorted(v, key=lambda t: t[0])] for c, v in pats.items()}


def pick(names: list[str], patterns: list) -> list[str] | None:
    """Event names feeding one counter (summed), or None."""
    usable = [n for n in names if not BAD.search(n)]
    for p in patterns:
        if isinstance(p, list):
            low = {n.lower(): n for n in names}
            if all(x.lower() in low for x in p):
                return [low[x.lower()] for x in p]
            continue
        for n in usable:
            if p.search(n):
                return [n]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True, type=Path)
    ap.add_argument("--full", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--exe", required=True)
    ap.add_argument("--events", required=True, type=Path)
    a = ap.parse_args()

    rows = [l.rstrip("\r\n") for l in a.rows.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    full: dict[str, float] = {}
    base: dict[str, float] = {}
    hows = []
    covs = []
    for fp, bp in zip(a.full.split(","), a.base.split(",")):
        f, how = parse_dir(Path(fp), a.exe)
        b, _ = parse_dir(Path(bp), a.exe)
        # Coverage correction: uProf multiplexes / drops samples, so it sees only a fraction
        # of each event. The program wrote its own runtime and clock (--meta); a pinned,
        # single-threaded, always-busy process used total_ns x GHz cycles. Scale every event
        # of that run by expected / measured cycles (uniform-capture assumption).
        for ev, pre in ((f, fp), (b, bp)):
            exp_cyc = read_meta(Path(pre + ".meta"))
            cyc = next((ev[k] for k in ("PMCx076:0x00", "CYCLES_NOT_IN_HALT") if k in ev), None)
            if exp_cyc and cyc:
                cov = cyc / exp_cyc
                covs.append(cov)
                if 0.02 < cov < 1.5:
                    for k in list(ev):
                        ev[k] /= cov
        hows.append(how)
        for k, v in f.items():
            full.setdefault(k, v)
        for k, v in b.items():
            base.setdefault(k, v)
    pats = load_patterns(a.events)
    avail = a.rows.parent / "available_events.txt"
    if full and not avail.exists():
        avail.write_text("\n".join(sorted(full), encoding="utf-8") + "\n")

    reps = max(len(rows), 1)
    vals, notes = [], []
    for c in COUNTERS:
        names = pick(list(full), pats[c])
        if names is None:
            vals.append(math.nan)
            notes.append(f"{c}=<not found>")
            continue
        d = sum(full[n] - base.get(n, 0.0) for n in names)
        vals.append(d / reps if d >= 0 else math.nan)
        notes.append(f"{c}<-{'+'.join(names)}")

    # cycles cross-check: uProf cycles vs the benchmark's own time x calibrated GHz
    check = ""
    try:
        # column positions of ns_total / ghz in the kernels and latency CSV formats
        if not math.isnan(vals[0]):
            tot_ns = 0.0
            ghz = None
            for r in rows:
                f = r.split(",")
                bench = f[1] if len(f) > 1 else ""
                if bench == "kernel":
                    tot_ns += float(f[11]); ghz = float(f[14])
                elif bench == "latency":
                    tot_ns += float(f[10]); ghz = float(f[13])
            if ghz and tot_ns:
                ratio = vals[0] * reps / (tot_ns * ghz)
                check = f"; cycles check: uProf/expected = {ratio:.3g}" + (
                    " (event counts)" if 0.7 < ratio < 1.3 else
                    " (looks like SAMPLE counts: multiply by the sampling interval, see WINDOWS_SETUP.md)" if ratio < 0.05
                    else " (too LOW: events were multiplexed or samples dropped - keep <= 6 events per set)"
                    if ratio < 0.7 else " (unexpected - check the setup)")
    except (ValueError, IndexError):
        pass
    cov_txt = ("; uProf captured " + "/".join(f"{100 * c:.0f}%" for c in covs) +
               " of the cycles (full/base runs), counts scaled up accordingly") if covs else \
              "; no --meta runtime: counts NOT corrected for multiplexing"
    print(f"  uprof counters [{'; '.join(hows)}]: {'; '.join(notes)}{check}{cov_txt}", file=sys.stderr)

    tail = ",".join("nan" if math.isnan(v) else f"{v:.0f}" for v in vals)
    for r in rows:
        f = r.split(",")
        print(",".join(f[: len(f) - len(COUNTERS)]) + "," + tail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
