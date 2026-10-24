#!/usr/bin/env python3
"""Diagnostic: is a slow measurement caused by the *address layout* or by *time* (interference)?

Runs the scalar SAXPY (L1-resident) as many separate processes, alternating base offsets and
y-shifts in a shuffled order each round, and records the array addresses of every process.
If one layout is consistently slow -> address effect (alignment, 4K aliasing, ...).
If slow runs land on random layouts while addresses are identical -> temporal interference.

usage: python scripts/probe_interference.py [--cpu N] [--rounds 14] [--out file.txt]
"""
import argparse
import collections
import os
import random
import re
import statistics
import json
import subprocess

from simdlib import bench_path, uopen


def default_cpu():
    try:
        return json.loads(subprocess.run([bench_path("scalar"), "--sysinfo"], capture_output=True, text=True).stdout)["suggested_cpu"]
    except Exception:  # noqa: BLE001
        return max(0, (os.cpu_count() or 1) - 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cpu", type=int, default=None)
    ap.add_argument("--rounds", type=int, default=14)
    ap.add_argument("--n", type=int, default=2816)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.cpu is None:
        a.cpu = default_cpu()
    bench = bench_path("scalar")
    env = dict(os.environ, SIMD_DEBUG_ADDR="1")
    configs = [(0, 0), (64, 0), (48, 0), (0, 4), (0, 64), (0, 2048)]
    res, addrs, seq = collections.defaultdict(list), collections.defaultdict(set), []
    rng = random.Random(1)
    for rnd in range(a.rounds):
        order = configs[:]
        rng.shuffle(order)
        for off, ys in order:
            r = subprocess.run([bench, "--cpu", str(a.cpu), "--kernel", "saxpy", "--n", str(a.n),
                                "--offset", str(off), "--yshift", str(ys), "--samples", "5"],
                               capture_output=True, text=True, env=env)
            t = statistics.median(float(l.split(",")[12]) * 1e9 for l in r.stdout.splitlines())
            m = re.search(r"x=(0x[0-9a-f]+) y=(0x[0-9a-f]+)", r.stderr)
            x, y = int(m.group(1), 16), int(m.group(2), 16)
            res[(off, ys)].append(t)
            addrs[(off, ys)].add((x & 0xFFF, y - x))
            seq.append((rnd, off, ys, t))
    base = statistics.median(t for v in res.values() for t in v)
    lines = [f"scalar saxpy, n={a.n}, {a.rounds} rounds x {len(configs)} layouts, pinned CPU {a.cpu}",
             f"overall median {base:.0f} ns; 'slow' = > 1.4x overall median", ""]
    for k in configs:
        v = res[k]
        slow = sum(t > 1.4 * base for t in v)
        lines.append(f"offset={k[0]:3d} yshift={k[1]:5d}  median={statistics.median(v):6.0f} ns  slow runs {slow:2d}/{len(v)}"
                     f"   x mod 4096, y-x = {sorted(addrs[k])}")
    lines += ["", "time order (round, offset, yshift, ns):"] + [f"{r:2d} {o:3d} {y:5d} {t:7.0f}" for r, o, y, t in seq]
    txt = "\n".join(lines) + "\n"
    print("\n".join(lines[: 3 + len(configs)]))
    if a.out:
        with uopen(a.out, "w") as f:
            f.write(txt)


if __name__ == "__main__":
    main()
