"""Tests for skills/triz-analysis/scripts/lookup.py (DESIGN.md 6장).

Logic tests run against a synthetic fixture: the script is copied next to a
tiny data dir, which also proves data paths resolve relative to the script.
Smoke tests run against the real data files and compare with the JSON itself.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "triz-analysis"
REAL_SCRIPT = SKILL / "scripts" / "lookup.py"
REAL_DATA = SKILL / "data"


def run(script, *args):
    p = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = json.loads(p.stdout) if p.stdout.strip() else None
    err = json.loads(p.stderr) if p.stderr.strip() else None
    return p.returncode, out, err


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def default_cells():
    """Named cells used by the tests, plus one filler cell per row (except the
    declared-missing row 16) so that every other row counts as populated."""
    filler = {f"{r}-39" if r != 39 else "39-38": [40] for r in range(1, 40) if r != 16}
    named = {"1-2": [5, 3, 7], "1-3": [3, 9], "4-2": [9, 5],
             "9-2": [2, 28], "17-1": [1]}
    return {**filler, **named}


def make_sandbox(tmp_path, cells=None, missing_rows=None, unverified=None):
    """Copy the script into tmp_path/scripts and create tmp_path/data."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "data").mkdir()
    script = tmp_path / "scripts" / "lookup.py"
    shutil.copy(REAL_SCRIPT, script)
    write(tmp_path / "data" / "parameters.json", {
        "version": "t", "source": "t",
        "parameters": [
            {"id": i, "name": {"en": f"Param{i}", "ko": f"파라미터{i}"},
             "definition": {"en": f"def{i}", "ko": f"정의{i}"},
             "keywords": ["속도", "speed"] if i == 9 else [f"kw{i}"]}
            for i in range(1, 40)
        ],
    })
    write(tmp_path / "data" / "contradiction-matrix.json", {
        "version": "t", "source": "t", "size": 39,
        "missing_rows": [16] if missing_rows is None else missing_rows,
        "unverified_cells": [] if unverified is None else unverified,
        "cells": cells if cells is not None else default_cells(),
    })
    write(tmp_path / "data" / "inventive-principles.json", {
        "version": "t", "source": "t",
        "principles": [
            {"id": i, "name": {"en": f"Prin{i}", "ko": f"원리{i}"},
             "sub_principles": {"ko": [f"하위{i}a", f"하위{i}b"], "en": [f"sub{i}a"]},
             "examples": {"ko": [f"예{i}"], "en": [f"ex{i}"]},
             "cases": [{"domain": d, "sub_principle": 1 + k % 2, "ko": f"사례{i}{d}", "en": f"case{i}{d}"}
                       for k, d in enumerate(("mechanical", "electronics", "software", "everyday"))]}
            for i in range(1, 41)
        ],
    })
    write(tmp_path / "data" / "separation-principles.json", {
        "version": "t", "source": "t",
        "separations": [
            {"id": k, "name": {"en": f"Sep {k}", "ko": f"{k} 분리"},
             "question": {"en": f"q {k}?", "ko": f"{k} 질문?"},
             "when_to_use": {"en": f"use {k}", "ko": f"{k} 사용"},
             "related_principles": rel,
             "examples": [{"en": f"ex {k}", "ko": f"예 {k}"}]}
            for k, rel in (("space", [1, 2]), ("time", [10, 15]), ("condition", [3, 40]),
                           ("direction", [4, 14]), ("system", [1, 5]))
        ],
    })
    return script


@pytest.fixture
def sandbox(tmp_path):
    return make_sandbox(tmp_path)


# ---------------------------------------------------------------- matrix ---

def test_matrix_pairs_in_input_order(sandbox):
    code, out, err = run(sandbox, "matrix", "--improve", "1,4", "--worsen", "2,3")
    assert code == 0 and err is None
    assert out["pairs"] == [
        {"improve": 1, "worsen": 2, "principles": [5, 3, 7]},
        {"improve": 1, "worsen": 3, "principles": [3, 9]},
        {"improve": 4, "worsen": 2, "principles": [9, 5]},
    ]


def test_matrix_empty_pairs_not_an_error(sandbox):
    code, out, _ = run(sandbox, "matrix", "--improve", "4", "--worsen", "3")
    assert code == 0
    assert out["pairs"] == []
    assert out["empty_pairs"] == [{"improve": 4, "worsen": 3}]
    assert out["ranking"] == []


def test_matrix_ranking_count_desc(sandbox):
    _, out, _ = run(sandbox, "matrix", "--improve", "1,4", "--worsen", "2,3")
    # cells [5,3,7], [3,9], [9,5]: 5, 3, 9 twice each, 7 once
    assert [(r["id"], r["count"]) for r in out["ranking"]] == [
        (5, 2), (3, 2), (9, 2), (7, 1),
    ]


def test_matrix_ranking_ties_go_by_position_within_cell(sandbox):
    _, out, _ = run(sandbox, "matrix", "--improve", "1", "--worsen", "2,3")
    # cells [5,3,7], [3,9]: 3 twice; among ties 5 (1st in a cell) and 9 (2nd)
    # come before 7 (3rd), even though 7 appears earlier in the output
    assert [(r["id"], r["count"]) for r in out["ranking"]] == [(3, 2), (5, 1), (9, 1), (7, 1)]


def test_matrix_ranking_name_follows_lang(sandbox):
    _, ko, _ = run(sandbox, "matrix", "--improve", "9", "--worsen", "2")
    _, en, _ = run(sandbox, "matrix", "--improve", "9", "--worsen", "2", "--lang", "en")
    assert ko["ranking"][0]["name"] == "원리2"
    assert en["ranking"][0]["name"] == "Prin2"


def test_matrix_duplicate_ids_are_deduplicated(sandbox):
    _, out, _ = run(sandbox, "matrix", "--improve", "9,9", "--worsen", "2,2")
    assert len(out["pairs"]) == 1
    assert out["ranking"][0]["count"] == 1


def test_matrix_missing_row_reported_not_silent(sandbox):
    code, out, _ = run(sandbox, "matrix", "--improve", "16", "--worsen", "1")
    assert code == 0
    assert out["empty_pairs"] == [{"improve": 16, "worsen": 1}]
    assert out["warnings"] == [{"code": "missing_row", "improve": 16}]


def test_matrix_no_warnings_for_normal_pairs(sandbox):
    _, out, _ = run(sandbox, "matrix", "--improve", "1", "--worsen", "2")
    assert out["warnings"] == []


def test_matrix_direction_matters(sandbox):
    _, out, _ = run(sandbox, "matrix", "--improve", "17", "--worsen", "1")
    assert out["pairs"] == [{"improve": 17, "worsen": 1, "principles": [1]}]
    _, out, _ = run(sandbox, "matrix", "--improve", "1", "--worsen", "17")
    assert out["pairs"] == []


# ---------------------------------------------------------- error codes ---

@pytest.mark.parametrize("args", [
    ["matrix"],
    ["matrix", "--improve", "1"],
    ["matrix", "--improve", "a", "--worsen", "2"],
    ["matrix", "--improve", "1,,2", "--worsen", "3"],
    ["matrix", "--improve", "", "--worsen", "3"],
    ["matrix", "--improve", "1.5", "--worsen", "3"],
    ["principle"],
    ["principle", "--id", "x"],
    ["param"],
    ["param", "--id", "1", "--search", "a"],
    ["param", "--search", ""],
    ["matrix", "--improve", "1", "--worsen", "2", "--lang", "fr"],
    ["nonexistent"],
    [],
])
def test_invalid_argument_exit_2(sandbox, args):
    code, out, err = run(sandbox, *args)
    assert code == 2
    assert out is None
    assert err["error"]["code"] == "invalid_argument"
    assert err["error"]["message"]


@pytest.mark.parametrize("args", [
    ["matrix", "--improve", "0", "--worsen", "2"],
    ["matrix", "--improve", "1", "--worsen", "40"],
    ["matrix", "--improve", "-1", "--worsen", "2"],
    ["principle", "--id", "41"],
    ["principle", "--id", "0"],
    ["param", "--id", "40"],
])
def test_out_of_range_exit_3(sandbox, args):
    code, out, err = run(sandbox, *args)
    assert code == 3
    assert out is None
    assert err["error"]["code"] == "out_of_range"


def test_same_parameter_exit_4(sandbox):
    code, out, err = run(sandbox, "matrix", "--improve", "9", "--worsen", "9")
    assert code == 4
    assert out is None
    assert err["error"]["code"] == "same_parameter"


def test_same_parameter_anywhere_in_lists_exit_4(sandbox):
    code, _, err = run(sandbox, "matrix", "--improve", "1,9", "--worsen", "2,9")
    assert code == 4
    assert err["error"]["code"] == "same_parameter"


def test_out_of_range_takes_precedence_over_same_parameter(sandbox):
    code, _, err = run(sandbox, "matrix", "--improve", "50", "--worsen", "50")
    assert code == 3


@pytest.mark.parametrize("victim", [
    "parameters.json", "contradiction-matrix.json", "inventive-principles.json",
])
def test_missing_data_file_exit_5(tmp_path, victim):
    script = make_sandbox(tmp_path)
    (tmp_path / "data" / victim).unlink()
    args = {
        "parameters.json": ["param", "--id", "1"],
        "contradiction-matrix.json": ["matrix", "--improve", "1", "--worsen", "2"],
        "inventive-principles.json": ["principle", "--id", "1"],
    }[victim]
    code, out, err = run(script, *args)
    assert code == 5
    assert out is None
    assert err["error"]["code"] == "data_error"


def test_corrupt_data_file_exit_5(tmp_path):
    script = make_sandbox(tmp_path)
    (tmp_path / "data" / "contradiction-matrix.json").write_text("{not json", encoding="utf-8")
    code, _, err = run(script, "matrix", "--improve", "1", "--worsen", "2")
    assert code == 5
    assert err["error"]["code"] == "data_error"


def test_matrix_with_unrelated_data_missing_still_works(tmp_path):
    """matrix needs the matrix + principle names; parameters.json is not required."""
    script = make_sandbox(tmp_path)
    (tmp_path / "data" / "parameters.json").unlink()
    code, _, _ = run(script, "matrix", "--improve", "1", "--worsen", "2")
    assert code == 0


# ------------------------------------------------------------- principle ---

def test_principle_lookup_ko(sandbox):
    code, out, _ = run(sandbox, "principle", "--id", "1,15,35")
    assert code == 0
    assert [p["id"] for p in out["principles"]] == [1, 15, 35]
    p = out["principles"][0]
    assert p["name"] == "원리1"
    assert p["sub_principles"] == ["하위1a", "하위1b"]
    assert p["examples"] == ["예1"]


def test_principle_lookup_en(sandbox):
    _, out, _ = run(sandbox, "principle", "--id", "2", "--lang", "en")
    p = out["principles"][0]
    assert p["name"] == "Prin2"
    assert p["sub_principles"] == ["sub2a"]
    assert p["examples"] == ["ex2"]


def test_principle_omits_cases_by_default(sandbox):
    _, out, _ = run(sandbox, "principle", "--id", "1")
    assert "cases" not in out["principles"][0]


def test_principle_cases_on_request(sandbox):
    _, ko, _ = run(sandbox, "principle", "--id", "1", "--cases")
    _, en, _ = run(sandbox, "principle", "--id", "1", "--cases", "--lang", "en")
    assert ko["principles"][0]["cases"][0] == {"domain": "mechanical", "domain_name": "기계",
                                               "sub_principle": 1, "text": "사례1mechanical"}
    assert en["principles"][0]["cases"][2]["domain_name"] == "software/IT"
    assert [c["text"] for c in en["principles"][0]["cases"]] == [
        "case1mechanical", "case1electronics", "case1software", "case1everyday"]


def test_principle_cases_empty_list_when_not_written(tmp_path):
    script = make_sandbox(tmp_path)
    p = tmp_path / "data" / "inventive-principles.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    del d["principles"][4]["cases"]
    write(p, d)
    _, out, _ = run(script, "principle", "--id", "5", "--cases")
    assert out["principles"][0]["cases"] == []
    code, out, _ = run(script, "validate")
    assert code == 0 and {"code": "missing_cases", "count": 1} in out["warnings"]


def _bad_case(case):
    def mutate(cases):
        cases[0].update(case)
    return mutate


@pytest.mark.parametrize("mutate, message", [
    (lambda cs: cs.pop(), "exactly 4"),
    (_bad_case({"domain": "space"}), "domain must be one of"),
    (_bad_case({"domain": "electronics"}), "domains must differ"),
    (_bad_case({"sub_principle": 3}), "sub_principle must be 1..2"),
    (_bad_case({"sub_principle": 0}), "sub_principle must be 1..2"),
    (_bad_case({"en": ""}), "missing en text"),
    (_bad_case({"ko": "TODO"}), "missing ko text"),
    (_bad_case({"ko": "원리 #15처럼 바꾼다"}), "must not cite a principle number"),
])
def test_validate_rejects_bad_cases(tmp_path, mutate, message):
    script = make_sandbox(tmp_path)
    p = tmp_path / "data" / "inventive-principles.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    mutate(d["principles"][0]["cases"])
    write(p, d)
    code, _, err = run(script, "validate")
    assert code == 5
    assert message in json.dumps(err, ensure_ascii=False)


def test_principle_duplicates_deduplicated(sandbox):
    _, out, _ = run(sandbox, "principle", "--id", "3,3")
    assert [p["id"] for p in out["principles"]] == [3]


# ----------------------------------------------------------------- param ---

def test_param_by_id(sandbox):
    code, out, _ = run(sandbox, "param", "--id", "9")
    assert code == 0
    p = out["parameters"][0]
    assert p["id"] == 9
    assert p["name"] == "파라미터9"
    assert p["definition"] == "정의9"
    assert p["keywords"] == ["속도", "speed"]


def test_param_by_id_en(sandbox):
    _, out, _ = run(sandbox, "param", "--id", "9", "--lang", "en")
    assert out["parameters"][0]["name"] == "Param9"
    assert out["parameters"][0]["definition"] == "def9"


def test_param_search_keyword(sandbox):
    code, out, _ = run(sandbox, "param", "--search", "속도")
    assert code == 0
    assert out["query"] == "속도"
    assert [m["id"] for m in out["matches"]] == [9]


def test_param_search_is_case_insensitive_and_matches_names(sandbox):
    _, out, _ = run(sandbox, "param", "--search", "SPEED")
    assert [m["id"] for m in out["matches"]] == [9]
    _, out, _ = run(sandbox, "param", "--search", "param12")
    assert [m["id"] for m in out["matches"]] == [12]


def test_param_search_no_match_is_not_an_error(sandbox):
    code, out, _ = run(sandbox, "param", "--search", "zzzz")
    assert code == 0
    assert out["matches"] == []


# -------------------------------------------------------------- validate ---

def test_validate_ok_with_warning_for_missing_rows(sandbox):
    code, out, err = run(sandbox, "validate")
    assert code == 0 and err is None
    assert out["ok"] is True
    assert out["errors"] == []
    assert any(w["code"] == "missing_row" for w in out["warnings"])


def test_validate_no_warning_when_rows_complete(tmp_path):
    cells = {f"{r}-{1 if r != 1 else 2}": [1] for r in range(1, 40)}
    script = make_sandbox(tmp_path, cells=cells, missing_rows=[])
    code, out, _ = run(script, "validate")
    assert code == 0
    assert out["warnings"] == []


@pytest.mark.parametrize("cells, needle", [
    ({"1-2": [41]}, "principle"),
    ({"1-2": [0]}, "principle"),
    ({"0-2": [1]}, "parameter"),
    ({"1-40": [1]}, "parameter"),
    ({"5-5": [1]}, "diagonal"),
    ({"1-2": []}, "empty"),
    ({"1-2": [3, 3]}, "duplicate"),
    ({"bad": [1]}, "key"),
])
def test_validate_detects_violations(tmp_path, cells, needle):
    script = make_sandbox(tmp_path, cells=cells)
    code, out, err = run(script, "validate")
    assert code == 5
    assert err["error"]["code"] == "data_error"
    assert needle in json.dumps(err, ensure_ascii=False).lower()


def test_validate_detects_silent_missing_row(tmp_path):
    """A row with no cells that is not declared in missing_rows is an error."""
    script = make_sandbox(tmp_path, cells={"1-2": [1]}, missing_rows=[])
    code, _, err = run(script, "validate")
    assert code == 5
    assert "missing_rows" in json.dumps(err, ensure_ascii=False)


def test_validate_detects_missing_name(tmp_path):
    script = make_sandbox(tmp_path)
    p = tmp_path / "data" / "parameters.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["parameters"][3]["name"]["ko"] = ""
    write(p, d)
    code, _, err = run(script, "validate")
    assert code == 5


def test_validate_detects_wrong_principle_count(tmp_path):
    script = make_sandbox(tmp_path)
    p = tmp_path / "data" / "inventive-principles.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["principles"].pop()
    write(p, d)
    code, _, _ = run(script, "validate")
    assert code == 5


def test_validate_missing_file_exit_5(tmp_path):
    script = make_sandbox(tmp_path)
    (tmp_path / "data" / "parameters.json").unlink()
    code, _, err = run(script, "validate")
    assert code == 5
    assert err["error"]["code"] == "data_error"


# ------------------------------------------------------ unverified cells ---

def test_matrix_unverified_cell_reported_as_empty_with_warning(tmp_path):
    script = make_sandbox(tmp_path, unverified=["1-17"])
    code, out, _ = run(script, "matrix", "--improve", "1", "--worsen", "17")
    assert code == 0
    assert out["pairs"] == []
    assert out["empty_pairs"] == [{"improve": 1, "worsen": 17}]
    assert out["warnings"] == [{"code": "unverified_cell", "improve": 1, "worsen": 17}]


def test_matrix_unverified_cell_does_not_affect_other_pairs(tmp_path):
    script = make_sandbox(tmp_path, unverified=["1-17"])
    _, out, _ = run(script, "matrix", "--improve", "1", "--worsen", "2,17")
    assert [p["worsen"] for p in out["pairs"]] == [2]
    assert out["warnings"] == [{"code": "unverified_cell", "improve": 1, "worsen": 17}]


def test_validate_warns_about_unverified_cells(tmp_path):
    script = make_sandbox(tmp_path, unverified=["1-17"])
    code, out, _ = run(script, "validate")
    assert code == 0
    assert {"code": "unverified_cell", "improve": 1, "worsen": 17} in out["warnings"]


def test_validate_rejects_unverified_cell_that_also_has_a_value(tmp_path):
    script = make_sandbox(tmp_path, unverified=["1-2"])  # 1-2 exists in default cells
    code, _, err = run(script, "validate")
    assert code == 5
    assert "unverified_cells" in json.dumps(err, ensure_ascii=False)


@pytest.mark.parametrize("bad", ["x", "5-5", "0-3", "1-40"])
def test_validate_rejects_malformed_unverified_key(tmp_path, bad):
    script = make_sandbox(tmp_path, unverified=[bad])
    code, _, err = run(script, "validate")
    assert code == 5
    assert "unverified_cells" in json.dumps(err, ensure_ascii=False)


# ------------------------------------------------ real data (smoke tests) ---

def _real_cells():
    return json.loads((REAL_DATA / "contradiction-matrix.json").read_text(encoding="utf-8"))["cells"]


def test_real_validate_passes():
    code, out, err = run(REAL_SCRIPT, "validate")
    assert code == 0, err
    assert out["ok"] is True


def test_real_matrix_matches_data_file_exactly():
    cells = _real_cells()
    improve = [1, 9]
    worsen = [2, 3, 14, 25]
    code, out, _ = run(REAL_SCRIPT, "matrix",
                       "--improve", ",".join(map(str, improve)),
                       "--worsen", ",".join(map(str, worsen)))
    assert code == 0
    for pair in out["pairs"]:
        assert pair["principles"] == cells[f"{pair['improve']}-{pair['worsen']}"]
    # every requested pair is accounted for exactly once, in exactly one bucket
    assert len(out["pairs"]) + len(out["empty_pairs"]) == len(improve) * len(worsen)
    for i in improve:
        for w in worsen:
            in_pairs = any(p["improve"] == i and p["worsen"] == w for p in out["pairs"])
            assert in_pairs == (f"{i}-{w}" in cells)


def test_real_matrix_flags_declared_gaps():
    data = json.loads((REAL_DATA / "contradiction-matrix.json").read_text(encoding="utf-8"))
    for row in data["missing_rows"]:
        code, out, _ = run(REAL_SCRIPT, "matrix", "--improve", str(row), "--worsen", "1")
        assert code == 0
        assert {"code": "missing_row", "improve": row} in out["warnings"]
    for key in data["unverified_cells"]:
        i, w = key.split("-")
        code, out, _ = run(REAL_SCRIPT, "matrix", "--improve", i, "--worsen", w)
        assert code == 0
        assert out["pairs"] == [] and out["empty_pairs"] == [{"improve": int(i), "worsen": int(w)}]
        assert {"code": "unverified_cell", "improve": int(i), "worsen": int(w)} in out["warnings"]


def test_real_principle_all_40_resolve():
    code, out, _ = run(REAL_SCRIPT, "principle", "--id", ",".join(str(i) for i in range(1, 41)))
    assert code == 0
    assert len(out["principles"]) == 40


def test_real_param_all_39_resolve():
    for i in (1, 20, 39):
        code, out, _ = run(REAL_SCRIPT, "param", "--id", str(i))
        assert code == 0
        assert out["parameters"][0]["id"] == i


def test_output_is_utf8_json_not_escaped():
    proc = subprocess.run([sys.executable, str(REAL_SCRIPT), "principle", "--id", "1"],
                          capture_output=True)
    assert "분할".encode("utf-8") in proc.stdout


# ------------------------------------------------------------ separation ---

def test_separation_all_types_in_data_order(sandbox):
    code, out, err = run(sandbox, "separation")
    assert code == 0 and err is None
    assert [s["id"] for s in out["separations"]] == ["space", "time", "condition", "direction", "system"]


def test_separation_selected_types_with_names_and_lang(sandbox):
    code, out, _ = run(sandbox, "separation", "--type", "time,space", "--lang", "en")
    assert code == 0
    time, space = out["separations"]
    assert time["id"] == "time" and space["id"] == "space"
    assert time["name"] == "Sep time" and time["question"] == "q time?"
    assert time["related_principles"] == [{"id": 10, "name": "Prin10"}, {"id": 15, "name": "Prin15"}]
    assert time["examples"] == ["ex time"]
    _, ko, _ = run(sandbox, "separation", "--type", "time")
    assert ko["separations"][0]["question"] == "time 질문?"
    assert ko["separations"][0]["related_principles"][0]["name"] == "원리10"


def test_separation_ranking_counts_shared_principles(sandbox):
    _, out, _ = run(sandbox, "separation", "--type", "space,system,condition")
    # space [1,2], system [1,5], condition [3,40]: 1 appears twice; ties go
    # round-robin by position, then by --type order
    assert [(r["id"], r["count"]) for r in out["ranking"]] == [(1, 2), (3, 1), (2, 1), (5, 1), (40, 1)]


def test_separation_ties_interleave_types_in_given_order(sandbox):
    _, out, _ = run(sandbox, "separation", "--type", "time,direction")
    # time [10,15], direction [4,14]: all count 1
    assert [r["id"] for r in out["ranking"]] == [10, 4, 15, 14]
    _, out, _ = run(sandbox, "separation", "--type", "direction,time")
    assert [r["id"] for r in out["ranking"]] == [4, 10, 14, 15]


def test_separation_duplicate_type_is_collapsed(sandbox):
    _, out, _ = run(sandbox, "separation", "--type", "time,time")
    assert len(out["separations"]) == 1


@pytest.mark.parametrize("raw", ["foo", "time,", "Time", ""])
def test_separation_rejects_unknown_type(sandbox, raw):
    code, out, err = run(sandbox, "separation", "--type", raw)
    assert code == 2 and out is None
    assert err["error"]["code"] == "invalid_argument"


def test_separation_missing_data_file(tmp_path):
    script = make_sandbox(tmp_path)
    (tmp_path / "data" / "separation-principles.json").unlink()
    code, _, err = run(script, "separation")
    assert code == 5 and err["error"]["code"] == "data_error"


def test_separation_real_data_matches_json():
    data = json.loads((REAL_DATA / "separation-principles.json").read_text(encoding="utf-8"))
    code, out, _ = run(REAL_SCRIPT, "separation", "--lang", "en")
    assert code == 0
    for got, want in zip(out["separations"], data["separations"]):
        assert got["id"] == want["id"]
        assert [r["id"] for r in got["related_principles"]] == want["related_principles"]
        assert got["question"] == want["question"]["en"]


@pytest.mark.parametrize("mutate, message", [
    (lambda seps: seps.pop(), "ids must be"),
    (lambda seps: seps[0]["question"].update(ko="TODO"), "missing question text"),
    (lambda seps: seps[1].update(related_principles=[]), "non-empty list"),
    (lambda seps: seps[1].update(related_principles=[9, 9]), "duplicate related principle"),
    (lambda seps: seps[2].update(related_principles=[41]), "out of range"),
    (lambda seps: seps[3].update(examples=[{"ko": "예"}]), "examples need ko and en"),
])
def test_validate_rejects_bad_separation_data(tmp_path, mutate, message):
    script = make_sandbox(tmp_path)
    path = tmp_path / "data" / "separation-principles.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data["separations"])
    write(path, data)
    code, _, err = run(script, "validate")
    assert code == 5
    assert any(message in d for d in err["error"]["details"])
