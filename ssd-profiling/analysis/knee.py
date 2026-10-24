#!/usr/bin/env python3
"""Print "<mid_qd> <knee_qd> <numjobs>" for the 4KiB random-read QD sweep of a
run (used by scripts/exp_tail.sh). Prefers the multi-job series because a single
submitting thread can saturate a CPU before the device saturates."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fiolib import knee, load_runs, summarize  # noqa: E402

raw_dir = Path(sys.argv[1])
df = load_runs(raw_dir.name, "qd_sweep")
df = df[(df["rw"] == "randread") & (df["bs"] == "4k")]
if df.empty:
    sys.exit(1)
s = summarize(df)
nj = int(s["nj"].max())
s = s[s["nj"] == nj]
k_power, k_marg = knee(s["qd_cfg"], s["iops"], s["lat_mean_us"])
k = k_power
mid = max(2, k // 4) if k >= 8 else max(1, k // 2)
print(mid, k, nj)
