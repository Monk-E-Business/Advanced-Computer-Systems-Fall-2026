#!/usr/bin/env python3
"""Vectorization verification: compiler remarks + targeted disassembly, per function, per variant.

Evidence comes from two independent sources:
  1. The compiler's own report: g++ -fsave-optimization-record (gzipped JSON, one record per remark
     with its function name): vector size used, or the reason vectorization failed. The raw
     -fopt-info text is kept in build/<v>/vec_report.txt.
  2. The machine code (objdump of build/<v>/kernels.o): the widest register used by packed
     arithmetic inside the hottest loop, counts of packed vs scalar FP ops, gathers, masks.
     This is the ground truth: it is what actually executes.

Writes to <outdir>:
  vectorization_summary.csv   one row per (variant, function)
  vectorization_summary.md    compact table: compiler verdict vs disassembly verdict
  hot_loops.md                short inner-loop excerpts for a few key functions (not full dumps)
usage: python scripts/verify_vectorization.py <outdir>
"""
import collections
import csv
import gzip
import json
import os
import re
import subprocess
import sys

from simdlib import BUILD, ROOT, uopen

FP_OP = re.compile(r"^v?(add|sub|mul|div|fmadd\d+|fmsub\d+|fnmadd\d+|fnmsub\d+|max|min|sqrt)(p|s)(s|d)$")
INT_VEC_OP = re.compile(r"^v?p(add|sub|mull|mulhu|mulu)[bwdq]{0,2}$|^v?pmuludq$")
VEC_MEM = re.compile(r"^v?(movup[sd]|movap[sd]|movdq[au]|movdqu(8|16|32|64)|movdqa(32|64)|movntp[sd]|maskmov\w*|vmaskmovp[sd])$")
SHUF_OP = re.compile(r"^v?(shufps|unpck|perm|vperm|blend|insert|extract|pshuf|vpermt2|vpermi2|movhlps|movlhps|vpcompress|vexpand)")
REG = re.compile(r"%(x|y|z)mm\d+")


def objdump(path):
    out = subprocess.run(["objdump", "-d", "--no-show-raw-insn", path], capture_output=True, text=True, check=True,
                         encoding="utf-8", errors="replace").stdout
    funcs, cur = {}, None
    for line in out.splitlines():
        m = re.match(r"^[0-9a-f]+ <([^>]+)>:", line)
        if m:
            cur = m.group(1)
            funcs[cur] = []
            continue
        m = re.match(r"^\s+([0-9a-f]+):\s+(\S+)\s*(.*)$", line)
        if m and cur:
            funcs[cur].append((int(m.group(1), 16), m.group(2), m.group(3).split("#")[0].strip()))
    return funcs


def width_of(ops):
    regs = REG.findall(ops)
    if "z" in regs:
        return 512
    if "y" in regs:
        return 256
    if "x" in regs:
        return 128
    return 0


def analyse(ins):
    """Find the innermost loop (backward branch) doing vector work; report its widest packed width."""
    loops = []
    for idx, (addr, mn, ops) in enumerate(ins):
        if mn.startswith("j") and mn != "jmpq" or mn == "jmp":
            m = re.match(r"^([0-9a-f]+)", ops)
            if m:
                tgt = int(m.group(1), 16)
                if tgt <= addr:
                    body = [x for x in ins if tgt <= x[0] <= addr]
                    loops.append(body)
    def stats(body):
        packed = scalar = ivec = gath = masked = shuf = vmem = 0
        width = 0
        for _, mn, ops in body:
            m = FP_OP.match(mn)
            if m and m.group(2) == "p":
                packed += 1
                width = max(width, width_of(ops))
            elif m:
                scalar += 1
            if INT_VEC_OP.match(mn) and REG.search(ops):
                ivec += 1
                width = max(width, width_of(ops))
            if "gather" in mn:
                gath += 1
                width = max(width, width_of(ops))
            if VEC_MEM.match(mn) and REG.search(ops) and "(" in ops:
                vmem += 1
                width = max(width, width_of(ops))
            if "{%k" in ops:
                masked += 1
            if SHUF_OP.match(mn):
                shuf += 1
        return dict(packed_fp=packed, scalar_fp=scalar, int_vec=ivec, gathers=gath, masked=masked,
                    shuffles=shuf, vec_mem=vmem, width=width, loop_len=len(body))
    if not loops:
        return stats(ins), []
    def vec_work(b):
        st = stats(b)
        return st["packed_fp"] + st["int_vec"] + st["gathers"] + st["vec_mem"]
    # main vector loop = widest vector width, then innermost (shortest); this skips the
    # narrower vectorized epilogue loop that the compiler may emit after a wide main loop
    with_vec = [b for b in loops if vec_work(b) > 0]
    best = min(with_vec or loops, key=lambda b: (-stats(b)["width"], len(b)))
    return stats(best), best


def opt_records(path):
    """Parse g++ -fsave-optimization-record output (gzipped JSON).

    Every remark carries its function name, so this works even though kernels.cpp generates
    its functions from macros (where file:line in -fopt-info text is ambiguous).
    Returns {function: "vectorized 64B (+32B epilogue)" | "NOT vectorized: <reason>"}."""
    res = {}
    if not os.path.exists(path):
        return res
    with gzip.open(path, "rt", encoding="utf-8") as f:
        data = json.load(f)
    passes = {}

    def walk_pass(p):
        passes[p["id"]] = p["name"]
        for ch in p.get("children", []):
            walk_pass(ch)

    for p in data[1]:
        walk_pass(p)
    recs = []

    def walk(r):
        recs.append(r)
        for ch in r.get("children", []):
            walk(ch)

    for r in data[2]:
        walk(r)

    def text(r):
        return "".join(m if isinstance(m, str) else str(m.get("expr", m.get("stmt", m.get("symtab_node", ""))))
                       for m in r.get("message", [])).strip()

    ok, fail = collections.defaultdict(list), collections.defaultdict(list)
    for r in recs:
        fn = r.get("function")
        if not fn or passes.get(r.get("pass")) != "vect":
            continue
        msg = text(r)
        m = re.search(r"loop vectorized using (\d+) byte vectors", msg)
        if r["kind"] == "success" and m:
            ok[fn].append(int(m.group(1)))
        elif r["kind"] == "failure" and msg and "misalignment" not in msg.lower():
            fail[fn].append(msg.splitlines()[0])
    for fn in set(ok) | set(fail):
        if ok[fn]:
            sizes = sorted(set(ok[fn]), reverse=True)
            res[fn] = f"vectorized {sizes[0]}B" + (f" (+{'/'.join(str(x) + 'B' for x in sizes[1:])} epilogue)" if len(sizes) > 1 else "")
        else:
            reasons = [m for m in fail[fn] if any(k in m for k in ("reduc", "not supported", "cost", "not profitable",
                                                                    "unsupported", "not vectorized:", "complicated"))]
            res[fn] = "NOT vectorized: " + (reasons[0] if reasons else (fail[fn][0] if fail[fn] else "?"))[:90]
    return res


def verdict(st):
    if st["gathers"]:
        return f"vector-{st['width']} (gather)"
    if st["packed_fp"] or st["int_vec"] or st["vec_mem"]:
        extra = " (+shuffles)" if st["shuffles"] >= 4 else ""
        return f"vector-{st['width']}{extra}"
    return "scalar"


KEY = ["saxpy_f32", "dot_f32", "dotsimd_f32", "dot_i32", "saxpy_s4_f32", "saxpy_gather_f32"]


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "results", "verification")
    os.makedirs(outdir, exist_ok=True)
    with uopen(os.path.join(BUILD, "variants.txt")) as f:
        variants = [l.split("|", 1) for l in f.read().splitlines() if l.strip()]
    rows, excerpts = [], {}
    for name, flags in variants:
        funcs = objdump(os.path.join(BUILD, name, "kernels.o"))
        recs = opt_records(os.path.join(BUILD, name, "opt_record.json.gz"))
        for fn, ins in sorted(funcs.items()):
            st, loop = analyse(ins)
            rep = recs.get(fn, "n/a (see build/%s/vec_report.txt)" % name)
            if ("no-vectorize" in flags or "no-tree-vectorize" in flags) and not rep.startswith("vectorized"):
                rep = "vectorizer disabled by flags"
            rows.append(dict(variant=name, function=fn, compiler_report=rep,
                             disasm_verdict=verdict(st), **st, total_instr=len(ins)))
            if fn in KEY:
                excerpts[(fn, name)] = loop
    keys = list(rows[0].keys())
    with uopen(os.path.join(outdir, "vectorization_summary.csv"), "w") as f:
        w = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    names = [v[0] for v in variants]
    fns = sorted({r["function"] for r in rows})
    lut = {(r["function"], r["variant"]): r for r in rows}
    with uopen(os.path.join(outdir, "vectorization_summary.md"), "w") as f:
        f.write("# Vectorization verification\n\n")
        f.write("Each cell: **disassembly verdict** (widest packed register in the hottest loop) / compiler report.\n\n")
        f.write("| function | " + " | ".join(names) + " |\n|---|" + "---|" * len(names) + "\n")
        for fn in fns:
            cells = []
            for v in names:
                r = lut.get((fn, v))
                if not r:
                    cells.append("-")
                    continue
                rep = r["compiler_report"].replace("vectorized ", "").replace("NOT vectorized: ", "✗ ")
                cells.append(f"**{r['disasm_verdict']}**<br><sub>{rep}</sub>")
            f.write(f"| `{fn}` | " + " | ".join(cells) + " |\n")
        f.write("\nFlags per variant:\n\n")
        for n, fl in variants:
            f.write(f"- `{n}`: `{fl}`\n")
    with uopen(os.path.join(outdir, "hot_loops.md"), "w") as f:
        f.write("# Hot-loop excerpts (targeted disassembly)\n\n")
        f.write("Inner loop only (backward-branch body with the most packed work), truncated to 24 lines.\n\n")
        for fn in KEY:
            for v in names:
                loop = excerpts.get((fn, v))
                if loop is None:
                    continue
                f.write(f"## `{fn}` — `{v}`\n\n```asm\n")
                for addr, mn, ops in loop[:24]:
                    f.write(f"{addr:6x}: {mn:<14} {ops}\n")
                if len(loop) > 24:
                    f.write(f"   ... ({len(loop) - 24} more instructions)\n")
                f.write("```\n\n")
    print(f"[verify] {len(rows)} function/variant rows -> {outdir}")


if __name__ == "__main__":
    main()
