"""Small helpers shared by the scripts (works on Windows/MSYS2 and Linux)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
IS_WINDOWS = os.name == "nt" or sys.platform in ("msys", "cygwin")

# Windows consoles default to a legacy code page; make our own output UTF-8 regardless.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def bench_path(variant):
    """Path of a variant's benchmark binary (bench.exe on Windows, bench elsewhere)."""
    for name in ("bench.exe", "bench"):
        p = os.path.join(BUILD, variant, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"build/{variant}/bench not found: run  bash scripts/build.sh")


def variants():
    with open(os.path.join(BUILD, "variants.txt"), encoding="utf-8") as f:
        return [l.split("|", 1) for l in f.read().splitlines() if l.strip()]


def uopen(path, mode="r"):
    """open() with UTF-8 (Windows' default encoding cannot write '×', '≈', '→')."""
    return open(path, mode, encoding="utf-8", newline="" if ("w" in mode or "a" in mode) else None)
