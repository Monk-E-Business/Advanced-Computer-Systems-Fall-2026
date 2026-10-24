#!/usr/bin/env python3
"""Run all experiments, pinned to one core, writing raw per-sample CSVs.

usage:
  python scripts/run_experiments.py --out results/<tag> [--cpu N] [--quick]
         [--only peak,license,sizes,bandwidth,align,tail,stride,dtype,perf] [--max-ws 1G]

Pinning: every benchmark process pins itself (bench --cpu N; Windows: SetThreadAffinityMask + HIGH
priority class, Linux: sched_setaffinity). The default CPU is the one sysinfo.py chose (on hybrid
Intel CPUs, a performance core).
Raw output: <out>/raw/<experiment>.csv, one row per timing sample. Columns:
  variant,kernel,type,n,offset,stride,pattern,ws_bytes,bytes,flops,reps,sample,sec_per_call,ghz,yshift,round
Each experiment is repeated in --rounds independent rounds (default 3), each with its own shuffled
job order, so a burst of interference on a shared/virtualised host can only contaminate one round of
a configuration; the analysis reports the median of per-round medians.
Every command is logged to <out>/raw/commands.log so any point can be re-run by hand.
Job order inside each experiment is shuffled (fixed seed), so slow thermal or background
drift does not consistently favour whichever variant would otherwise run first.
"""
import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time

from simdlib import IS_WINDOWS, bench_path, uopen, variants

HEADER = "variant,kernel,type,n,offset,stride,pattern,ws_bytes,bytes,flops,reps,sample,sec_per_call,ghz,yshift,round\n"
ALL_EXPS = ["peak", "license", "sizes", "bandwidth", "align", "tail", "stride", "dtype", "perf"]


def parse_size(s):
    s = s.strip().upper()
    mult = {"K": 1024, "M": 1024**2, "G": 1024**3}
    return int(float(s[:-1]) * mult[s[-1]]) if s[-1] in mult else int(s)


class Runner:
    def __init__(self, args):
        self.args = args
        self.out = args.out
        self.raw = os.path.join(self.out, "raw")
        os.makedirs(self.raw, exist_ok=True)
        self.variants = [v for v, _ in variants()]
        self.log = uopen(os.path.join(self.raw, "commands.log"), "a")
        with uopen(os.path.join(self.out, "sysinfo.json")) as f:
            info = json.load(f)
        self.cpu = args.cpu if args.cpu is not None else int(info.get("pinned_cpu", 0))
        self.pin = ["--cpu", str(self.cpu)]
        c = info["caches"]
        self.L1 = c.get("L1d", {}).get("bytes") or 32 * 1024     # fall back to typical sizes if
        self.L2 = c.get("L2", {}).get("bytes") or 1024 * 1024    # the OS reported nothing
        self.L3 = c.get("L3", {}).get("bytes") or 8 * 1024 * 1024
        self.max_ws = parse_size(args.max_ws)
        # DRAM-resident working set: well beyond the LLC (4x), capped by --max-ws
        self.dram_ws = min(self.max_ws, max(64 * 1024**2, 4 * self.L3))
        if self.dram_ws < 2 * self.L3:
            print(f"[warn] --max-ws {self.max_ws >> 20} MiB is < 2x LLC ({self.L3 >> 20} MiB): "
                  "the 'DRAM' points may still be partly cache resident", file=sys.stderr)
        self.samples = 5 if args.quick else args.samples
        self.dram_samples = 3 if args.quick else args.dram_samples
        self.rounds = 1 if args.quick else args.rounds
        self.best = "avx512" if "avx512" in self.variants else "native"
        self.rng = random.Random(42)
        self.round = 0

    def have(self, v):
        return v in self.variants

    def run(self, exp, variant, kernel, ns, typ="f32", offset=0, pattern="seq", samples=None, min_time=None):
        """Run one binary over a list of n; split cache-resident and DRAM-resident sizes."""
        csv = os.path.join(self.raw, f"{exp}.csv")
        new = not os.path.exists(csv)
        es = 8 if typ == "f64" else 4
        groups = {}
        for n in ns:
            big = n * es * 2 > self.L3  # rough: >LLC -> long calls -> fewer samples
            groups.setdefault(big, []).append(n)
        with uopen(csv, "a") as f:
            if new:
                f.write(HEADER)
            for big, group in sorted(groups.items()):
                s = samples or (self.dram_samples if big else self.samples)
                cmd = [bench_path(variant)] + self.pin + ["--kernel", kernel, "--type", typ,
                                  "--n", ",".join(str(n) for n in group), "--offset", str(offset),
                                  "--pattern", pattern, "--samples", str(s),
                                  "--min-time", str(min_time or self.args.min_time)]
                self.log.write(" ".join(cmd) + "\n")
                self.log.flush()
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode != 0:
                    print(f"[error] {' '.join(cmd)}\n{r.stderr}", file=sys.stderr)
                    continue
                f.write("".join(f"{line},{self.round}\n" for line in r.stdout.splitlines() if line))

    # ---------------------------------------------------------------- grids
    def ws_grid(self, per_octave):
        lo, hi = 4 * 1024, self.max_ws
        k = int(math.floor(math.log2(hi / lo) * per_octave))
        return [lo * 2 ** (i / per_octave) for i in range(k + 1)]

    @staticmethod
    def n_for(ws, bytes_per_elem, multiple=64):
        return max(multiple, int(round(ws / bytes_per_elem / multiple)) * multiple)

    def shuffled(self, jobs):
        self.rng.shuffle(jobs)
        return jobs

    # ---------------------------------------------------------------- experiments
    def exp_peak(self):
        out = subprocess.run([bench_path("native")] + self.pin + ["--peak"], capture_output=True, text=True).stdout
        with uopen(os.path.join(self.raw, "peak.csv"), "w") as f:
            f.write(out)

    def exp_license(self):
        """Core clock immediately after sustained scalar / AVX2 / AVX-512 work (frequency licences)."""
        rows = []
        for rep in range(1 if self.args.quick else 3):
            out = subprocess.run([bench_path("native")] + self.pin + ["--license"], capture_output=True, text=True).stdout
            lines = out.strip().splitlines()
            if rep == 0:
                rows.append(lines[0] + ",rep")
            rows += [f"{l},{rep}" for l in lines[1:]]
        with uopen(os.path.join(self.raw, "license.csv"), "w") as f:
            f.write("\n".join(rows) + "\n")

    def exp_sizes(self):
        """Scalar vs auto-vectorized builds for every kernel across the working-set sweep."""
        grid = self.ws_grid(1 if self.args.quick else 2)
        ws_per_elem = {"saxpy": 8, "dot": 8, "dotsimd": 8, "mul": 12, "stencil": 8}
        jobs = [(v, k) for v in self.variants for k in ws_per_elem]
        for v, k in self.shuffled(jobs):
            ns = sorted({self.n_for(ws, ws_per_elem[k]) for ws in grid})
            self.run("sizes", v, k, ns)

    def exp_bandwidth(self):
        """Read-only and write-only streams: the memory roofs for each level."""
        grid = self.ws_grid(1 if self.args.quick else 2)
        jobs = [(v, k) for v in ("scalar", self.best) for k in ("read", "write")]
        for v, k in self.shuffled(jobs):
            self.run("bandwidth", v, k, sorted({self.n_for(ws, 4) for ws in grid}))

    def exp_align(self):
        """Base address shifted off the vector / cache-line boundary."""
        offsets = [0, 4, 8, 16, 32, 48, 64]
        vs = [v for v in ("scalar", "sse2", "avx2", "native", "avx512") if self.have(v)]
        n_l1, n_l2 = self.n_for(self.L1 / 2, 8), self.n_for(self.L2 / 2, 8)
        jobs = [(v, k, o) for v in vs for k in ("saxpy", "dotsimd") for o in offsets]
        for v, k, o in self.shuffled(jobs):
            self.run("align", v, k, [n_l1, n_l2], offset=o)
        n_dram = self.n_for(self.dram_ws, 8)
        jobs = [(v, k, o) for v in ("scalar", self.best) for k in ("saxpy", "dotsimd") for o in (0, 4, 32)]
        for v, k, o in self.shuffled(jobs):
            self.run("align", v, k, [n_dram], offset=o)

    def exp_tail(self):
        """N = 1024..1152 step 1 (L1 resident): remainder/epilogue cost vs masked tails."""
        ns = list(range(1024, 1153, 1 if not self.args.quick else 3))
        vs = [v for v in ("scalar", "sse2", "avx2", "native", "avx512") if self.have(v)]
        jobs = [(v, "saxpy") for v in vs]
        if self.have("avx2"):
            jobs.append(("native", "mask_avx2"))
        if self.have("avx512"):
            jobs.append(("native", "mask_avx512"))
        for v, k in self.shuffled(jobs):
            self.run("tail", v, k, ns, samples=5, min_time=0.002)

    def exp_stride(self):
        """Unit vs non-unit stride and gathers, at several hierarchy levels."""
        levels = [self.L1 / 2, self.L2 / 2, self.L3 / 2, self.dram_ws]
        vs = [v for v in ("scalar", "sse2", "avx2", "native", "avx512") if self.have(v)]
        jobs = []
        for v in vs:
            for s in (1, 2, 4, 8, 16):
                jobs.append((v, f"saxpy_s{s}", "seq", [self.n_for(ws, 8 * s) for ws in levels]))
            for pat in ("seq", "random"):
                jobs.append((v, "gather", pat, [self.n_for(ws, 12) for ws in levels]))
        for v, k, pat, ns in self.shuffled(jobs):
            self.run("stride", v, k, ns, pattern=pat)

    def exp_dtype(self):
        """float32 vs float64 vs int32 for each kernel, in L1, L2 and DRAM."""
        vs = [v for v in ("scalar", "sse2", "avx2", "native", "avx512") if self.have(v)]
        jobs = [(v, k, t) for v in vs for k in ("saxpy", "dot", "dotsimd", "mul", "stencil") for t in ("f32", "f64", "i32")]
        for v, k, t in self.shuffled(jobs):
            es = 8 if t == "f64" else 4
            per = (3 if k == "mul" else 2) * es
            ns = [self.n_for(self.L1 / 2, per), self.n_for(self.L2 / 2, per), self.n_for(self.dram_ws, per)]
            self.run("dtype", v, k, ns, typ=t)

    def exp_perf(self):
        """Optional hardware counters (Linux perf). Skipped with a note on Windows and wherever perf is unusable."""
        note = os.path.join(self.raw, "perf_counters.txt")
        if IS_WINDOWS:
            with uopen(note, "w") as f:
                f.write("SKIPPED: perf is Linux-only. On Windows, Intel VTune or AMD uProf can collect the same "
                        "counters (vector FP instructions, L1/LLC misses) for bench.exe by hand.\n")
            print("[perf] skipped: not available on Windows")
            return
        perf = shutil.which("perf")
        probe = subprocess.run([perf, "stat", "-e", "cycles,instructions", "true"], capture_output=True, text=True) if perf else None
        if not perf or probe.returncode != 0 or "not supported" in (probe.stderr or "") or "<not" in (probe.stderr or ""):
            msg = "perf not installed" if not perf else ("perf cannot read hardware counters here:\n" + (probe.stderr or "")[:800])
            with uopen(note, "w") as f:
                f.write("SKIPPED: " + msg + "\n")
            print("[perf] skipped: " + msg.splitlines()[0])
            return
        events = ["cycles", "instructions", "L1-dcache-load-misses", "LLC-load-misses",
                  "fp_arith_inst_retired.scalar_single", "fp_arith_inst_retired.128b_packed_single",
                  "fp_arith_inst_retired.256b_packed_single", "fp_arith_inst_retired.512b_packed_single"]
        avail = subprocess.run([perf, "list"], capture_output=True, text=True).stdout
        events = [e for e in events if e in avail or "." not in e]
        rows = ["variant,kernel,ws_bytes,event,count"]
        for v in ("scalar", self.best):
            for k in ("saxpy", "dot", "dotsimd"):
                for ws in (self.L1 / 2, self.dram_ws):
                    n = self.n_for(ws, 8)
                    cmd = [perf, "stat", "-x", ",", "-e", ",".join(events), bench_path(v)] + self.pin + [
                        "--kernel", k, "--n", str(n), "--samples", "5"]
                    r = subprocess.run(cmd, capture_output=True, text=True)
                    for line in r.stderr.splitlines():
                        p = line.split(",")
                        if len(p) >= 3 and p[2]:
                            rows.append(f"{v},{k},{int(ws)},{p[2]},{p[0]}")
        with uopen(os.path.join(self.raw, "perf_counters.csv"), "w") as f:
            f.write("\n".join(rows) + "\n")
        with uopen(note, "w") as f:
            f.write("perf counters collected; note: counts include harness setup/initialisation.\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--cpu", type=int, default=None, help="logical CPU to pin to (default: sysinfo's choice)")
    ap.add_argument("--quick", action="store_true", help="coarse grid, few samples (~5 min)")
    ap.add_argument("--only", default=",".join(ALL_EXPS))
    ap.add_argument("--max-ws", default="1G", help="largest working set (default 1G)")
    ap.add_argument("--samples", type=int, default=7, help="timing samples per configuration per round")
    ap.add_argument("--dram-samples", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=3, help="independent repetitions of each experiment")
    ap.add_argument("--min-time", type=float, default=0.01, help="seconds per timing sample")
    args = ap.parse_args()
    r = Runner(args)
    meta = dict(vars(args), started=time.strftime("%Y-%m-%dT%H:%M:%S%z"), variants=r.variants,
                dram_ws=r.dram_ws, L1=r.L1, L2=r.L2, L3=r.L3)
    for exp in [e for e in ALL_EXPS if e in args.only.split(",")]:
        t0 = time.time()
        print(f"[run] {exp} ...", flush=True)
        for rnd in range(1 if exp in ("peak", "license", "perf") else r.rounds):
            r.round = rnd
            getattr(r, f"exp_{exp}")()
        meta[f"seconds_{exp}"] = round(time.time() - t0, 1)
        print(f"[run] {exp} done in {time.time() - t0:.0f} s", flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    meta["pinned_cpu"] = r.cpu
    with uopen(os.path.join(args.out, "run_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)


if __name__ == "__main__":
    main()
