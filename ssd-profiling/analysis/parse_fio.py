#!/usr/bin/env python3
"""Raw fio JSON -> processed CSVs.

data/processed/<run>/
  all_runs.csv              one row per fio run (every rep, every experiment)
  <experiment>_runs.csv     same, split per experiment
  <experiment>_summary.csv  mean / std / 95% CI across reps per point
  steady_state_timeseries.csv   per-second bw/iops/lat for long runs + temperature
  tail_hist_<point>.csv     merged latency histograms (json+) for the CCDF
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from fiolib import (PROC, RAW, _lat_block, current_run, hist_from_bins,  # noqa: E402
                    load_fio_json, load_runs, read_fio_log, summarize)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    run = current_run(ap.parse_args().run)
    out = PROC / run
    out.mkdir(parents=True, exist_ok=True)
    df = load_runs(run)
    if df.empty:
        raise SystemExit(f"no fio results in {RAW / run}")
    df.to_csv(out / "all_runs.csv", index=False)
    for exp, d in df.groupby("experiment"):
        d.to_csv(out / f"{exp}_runs.csv", index=False)
        summarize(d).to_csv(out / f"{exp}_summary.csv", index=False)
    bad = df[df["fio_error"] != 0]
    if len(bad):
        print(f"WARNING: {len(bad)} runs reported fio errors:\n{bad[['file','fio_error']]}")

    # --- device-state time series --------------------------------------------
    ss = RAW / run / "steady_state"
    if ss.exists():
        t0 = float((ss / "t0_epoch").read_text(encoding="utf-8", errors="replace")) if (ss / "t0_epoch").exists() else None
        frames = []
        for meta in sorted(ss.glob("*_rep1.meta.json")):
            prefix = str(meta).replace(".meta.json", "")
            import json
            m = json.loads(meta.read_text(encoding="utf-8", errors="replace"))
            start = pd.Timestamp(m["timestamp"]).timestamp()
            for kind in ("bw", "iops", "lat"):
                d = read_fio_log(prefix, kind)
                if d.empty:
                    continue
                d["metric"] = kind
                d["phase"] = m.get("PHASE", m["point"])
                d["point"] = m["point"]
                d["t_abs_s"] = d["t_s"] + start - (t0 or start)
                frames.append(d)
        if frames:
            ts = pd.concat(frames)
            # unit normalisation: bw log is KiB/s -> MB/s ; lat log is ns -> us
            ts.loc[ts.metric == "bw", "value"] *= 1024 / 1e6
            ts.loc[ts.metric == "lat", "value"] /= 1e3
            ts.to_csv(out / "steady_state_timeseries.csv", index=False)
        temp = ss / "temperature.csv"
        if temp.exists():
            t = pd.read_csv(temp)
            t["temp_c"] = pd.to_numeric(t["temp_c"], errors="coerce")
            t["t_abs_s"] = t["epoch_s"] - (t0 or t["epoch_s"].iloc[0])
            t.to_csv(out / "steady_state_temperature.csv", index=False)

    # --- tail histograms (json+) ---------------------------------------------
    tail = RAW / run / "tail"
    if tail.exists():
        groups = {}
        for j in sorted(tail.glob("*_rep*.json")):
            if j.name.endswith(".meta.json"):
                continue
            point = j.name.rsplit("_rep", 1)[0]
            job = load_fio_json(j)["jobs"][0]
            for ddir in ("read", "write"):
                lat, cnt = hist_from_bins(_lat_block(job.get(ddir, {})))
                if lat is None:
                    continue
                key = (point, ddir)
                h = groups.setdefault(key, {})
                for l_, c in zip(lat, cnt):
                    h[l_] = h.get(l_, 0) + c
        for (point, ddir), h in groups.items():
            lat = np.array(sorted(h))
            cnt = np.array([h[x] for x in lat])
            ccdf = 1 - np.cumsum(cnt) / cnt.sum()
            pd.DataFrame({"lat_us": lat, "count": cnt, "ccdf": ccdf}).to_csv(
                out / f"tail_hist_{point}_{ddir}.csv", index=False)
    print(f"processed {len(df)} runs -> {out.relative_to(PROC.parent.parent)}")


if __name__ == "__main__":
    main()
