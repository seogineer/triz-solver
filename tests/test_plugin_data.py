"""Tests for the split plugin data (DESIGN.md 12.3, 12.5 a and b)."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "plugin" / "skills" / "triz-analysis" / "data"
BUILD = ROOT / "tools" / "build_plugin_data.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_plugin_data", BUILD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_check_command_reports_no_difference():
    p = subprocess.run([sys.executable, str(BUILD), "--check"],
                       capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr


def test_build_result_equals_plugin_data_bytes():
    b = load_builder()
    files = b.build_files()
    assert b.check(files) == []
    for rel, text in files.items():
        assert (OUT / rel).read_bytes() == text.encode("utf-8")


def test_exact_file_set():
    found = {p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file()}
    expected = {"parameters.json", "separation-principles.json"}
    expected |= {f"matrix/row-{i:02d}.json" for i in range(1, 40)}
    expected |= {f"principles/p-{i:02d}.json" for i in range(1, 41)}
    assert found == expected
    assert len([f for f in found if f.startswith("matrix/")]) == 39
    assert len([f for f in found if f.startswith("principles/")]) == 40


def test_row_files_match_source_cells_exactly():
    src = read(DATA / "contradiction-matrix.json")["cells"]
    rebuilt = {}
    for i in range(1, 40):
        row = read(OUT / "matrix" / f"row-{i:02d}.json")
        assert row["improve"] == i
        assert str(i) not in row["cells"], f"diagonal {i}-{i} present"
        for w, ids in row["cells"].items():
            key = f"{i}-{w}"
            assert key in src, f"{key} is not in the source"
            rebuilt[key] = ids
    assert len(rebuilt) == 1248
    assert rebuilt == src


def test_row_files_have_names_and_no_unverified_now():
    params = {p["id"]: p["name"] for p in read(DATA / "parameters.json")["parameters"]}
    for i in range(1, 40):
        row = read(OUT / "matrix" / f"row-{i:02d}.json")
        assert row["name"] == params[i]
        assert "unverified" not in row


def test_principle_files_match_source():
    src = read(DATA / "inventive-principles.json")["principles"]
    assert [p["id"] for p in src] == list(range(1, 41))
    for p in src:
        assert read(OUT / "principles" / f"p-{p['id']:02d}.json") == p


@pytest.mark.parametrize("name", ["parameters.json", "separation-principles.json"])
def test_copied_files_equal_source(name):
    assert read(OUT / name) == read(DATA / name)


def fake_source(tmp_path, unverified, missing):
    src = tmp_path / "src"
    src.mkdir()
    params = [{"id": i, "name": {"en": f"P{i}", "ko": f"파{i}"}} for i in range(1, 40)]
    (src / "parameters.json").write_text(json.dumps({"parameters": params}), encoding="utf-8")
    (src / "separation-principles.json").write_text(json.dumps({"separations": []}), encoding="utf-8")
    (src / "inventive-principles.json").write_text(
        json.dumps({"principles": [{"id": 1, "name": {"en": "a", "ko": "가"}}]}), encoding="utf-8")
    cells = {"3-5": [1, 2], "3-7": [3], "3-9": [4], "4-1": [5]}
    (src / "contradiction-matrix.json").write_text(json.dumps({
        "size": 39, "cells": cells, "unverified_cells": unverified, "missing_rows": missing,
    }), encoding="utf-8")
    return src


def test_unverified_and_missing_rows_mapping(tmp_path):
    b = load_builder()
    src = fake_source(tmp_path, ["3-5", "3-7"], [12])
    out = tmp_path / "out"
    old_src, old_out = b.SRC, b.OUT
    b.SRC, b.OUT = src, out
    try:
        files = b.build_files()
        b.write(files)
        assert b.check(files) == []
    finally:
        b.SRC, b.OUT = old_src, old_out
    row3 = read(out / "matrix" / "row-03.json")
    assert row3["unverified"] == [5, 7]
    for i in range(1, 40):
        row = read(out / "matrix" / f"row-{i:02d}.json")
        if i != 3:
            assert "unverified" not in row
    row12 = read(out / "matrix" / "row-12.json")
    assert row12["cells"] == {}
    assert row12["improve"] == 12
    assert len(list((out / "matrix").glob("row-*.json"))) == 39
