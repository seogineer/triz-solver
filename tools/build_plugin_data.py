#!/usr/bin/env python3
"""Build plugin/skills/triz-analysis/data/ from the canonical data/ (DESIGN.md 12.3).

Usage:
    python tools/build_plugin_data.py          # write the split data
    python tools/build_plugin_data.py --check  # exit 1 if plugin data differs

Python 3.9+ standard library only. No network access.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data"
OUT = ROOT / "plugin" / "skills" / "triz-analysis" / "data"
COPIED = ("parameters.json", "separation-principles.json")


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


_INT_LIST = re.compile(r"\[\n\s+(-?\d+(?:,\n\s+-?\d+)*)\n\s*\]")


def dumps_compact(obj):
    """Like dumps, but lists of integers go on one line (fewer tokens to read)."""
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
    text = _INT_LIST.sub(lambda m: "[" + ", ".join(re.findall(r"-?\d+", m.group(1))) + "]", text)
    return text + "\n"


def load(name):
    with open(SRC / name, encoding="utf-8") as f:
        return json.load(f)


def build_files():
    """Return {relative posix path: text} for every generated file."""
    files = {}
    for name in COPIED:
        files[name] = dumps(load(name))

    params = load("parameters.json")["parameters"]
    names = {p["id"]: p["name"] for p in params}
    matrix = load("contradiction-matrix.json")
    size = matrix.get("size", 39)

    rows = {i: {} for i in range(1, size + 1)}
    for key, value in matrix["cells"].items():
        improve, worsen = (int(x) for x in key.split("-"))
        rows[improve][str(worsen)] = list(value)

    unverified = {i: [] for i in range(1, size + 1)}
    for key in matrix.get("unverified_cells", []):
        improve, worsen = (int(x) for x in key.split("-"))
        unverified[improve].append(worsen)
        rows[improve].pop(str(worsen), None)   # a disputed cell ships no values

    for i in range(1, size + 1):
        row = {"improve": i, "name": names[i], "cells": rows[i]}
        if unverified[i]:
            row["unverified"] = sorted(unverified[i])
        files[f"matrix/row-{i:02d}.json"] = dumps_compact(row)

    for p in load("inventive-principles.json")["principles"]:
        files[f"principles/p-{p['id']:02d}.json"] = dumps_compact(p)
    return files


def check(files):
    """Return a list of differences between generated files and OUT."""
    diffs = []
    for rel, text in sorted(files.items()):
        path = OUT / rel
        if not path.is_file():
            diffs.append(f"missing: {rel}")
        elif path.read_bytes() != text.encode("utf-8"):
            diffs.append(f"differs: {rel}")
    if OUT.is_dir():
        for path in sorted(OUT.rglob("*")):
            if path.is_file() and path.relative_to(OUT).as_posix() not in files:
                diffs.append(f"unexpected: {path.relative_to(OUT).as_posix()}")
    return diffs


def write(files):
    for rel, text in files.items():
        path = OUT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    # remove stale files so the output always matches the input
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.relative_to(OUT).as_posix() not in files:
            path.unlink()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if plugin data differs from the build")
    args = ap.parse_args(argv)
    files = build_files()
    if args.check:
        diffs = check(files)
        for d in diffs:
            print(d, file=sys.stderr)
        return 1 if diffs else 0
    write(files)
    print(f"wrote {len(files)} files to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
