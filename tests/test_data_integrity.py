"""Data integrity tests (DESIGN.md 5.5) plus schema-shape checks."""
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parent.parent / "data"


def load(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def matrix():
    return load("contradiction-matrix.json")


@pytest.fixture(scope="module")
def params():
    return load("parameters.json")


@pytest.fixture(scope="module")
def principles():
    return load("inventive-principles.json")


@pytest.fixture(scope="module")
def separations():
    return load("separation-principles.json")


@pytest.mark.parametrize(
    "name",
    ["parameters.json", "contradiction-matrix.json",
     "inventive-principles.json", "separation-principles.json"],
)
def test_metadata_present(name):
    d = load(name)
    assert d.get("version")
    assert d.get("source")


def test_matrix_size(matrix):
    assert matrix["size"] == 39


def test_matrix_keys_in_range_and_no_diagonal(matrix):
    for key in matrix["cells"]:
        i, w = (int(x) for x in key.split("-"))
        assert 1 <= i <= 39 and 1 <= w <= 39, key
        assert i != w, f"diagonal key {key}"


def test_matrix_principles_in_range_and_nonempty(matrix):
    for key, ids in matrix["cells"].items():
        assert ids, f"{key} is empty; empty cells must be omitted"
        assert all(isinstance(x, int) and 1 <= x <= 40 for x in ids), key
        assert len(set(ids)) == len(ids), f"duplicate principle in {key}"


def test_matrix_missing_rows_declared(matrix):
    """A row with no cells must be declared in missing_rows, never silent."""
    populated = {int(k.split("-")[0]) for k in matrix["cells"]}
    silent = [r for r in range(1, 40) if r not in populated and r not in matrix["missing_rows"]]
    assert silent == []
    for r in matrix["missing_rows"]:
        assert r not in populated, f"row {r} declared missing but has cells"


def test_parameters_complete(params):
    ps = params["parameters"]
    assert [p["id"] for p in ps] == list(range(1, 40))
    for p in ps:
        assert p["name"]["en"] and p["name"]["ko"]
        assert set(p["definition"]) >= {"en", "ko"}
        assert isinstance(p["keywords"], list)


def test_principles_complete(principles):
    ps = principles["principles"]
    assert [p["id"] for p in ps] == list(range(1, 41))
    for p in ps:
        assert p["name"]["en"] and p["name"]["ko"]
        assert p["sub_principles"]["ko"]
        assert p["examples"]["ko"]


def test_every_principle_has_four_cases_from_distinct_domains(principles):
    domains = {"mechanical", "electronics", "software", "materials", "medical", "everyday"}
    for p in principles["principles"]:
        cases = p.get("cases", [])
        assert len(cases) == 4, p["id"]
        assert len({c["domain"] for c in cases}) == 4 and {c["domain"] for c in cases} <= domains, p["id"]
        for c in cases:
            assert 1 <= c["sub_principle"] <= len(p["sub_principles"]["ko"]), p["id"]
            assert c["ko"].strip() and c["en"].strip() and "#" not in c["ko"] + c["en"], p["id"]


def test_separations_reference_valid_principles(separations):
    ids = [s["id"] for s in separations["separations"]]
    assert ids == ["space", "time", "condition", "direction", "system"]
    for s in separations["separations"]:
        assert s["name"]["en"] and s["name"]["ko"]
        assert s["question"]["en"] and s["question"]["ko"]
        assert s["related_principles"] and all(1 <= x <= 40 for x in s["related_principles"])
        assert len(set(s["related_principles"])) == len(s["related_principles"])
        assert all(e["ko"] and e["en"] for e in s["examples"])
    assert "TODO" not in json.dumps(separations, ensure_ascii=False)


def test_parameters_reference_md_in_sync(params):
    """references/parameters-39.md must list every parameter from parameters.json."""
    md = (DATA.parent / "plugin" / "skills" / "triz-analysis" / "references" / "parameters-39.md").read_text(encoding="utf-8")
    for p in params["parameters"]:
        row = next((l for l in md.splitlines() if l.startswith(f"| {p['id']} |")), None)
        assert row is not None, f"parameter {p['id']} missing from parameters-39.md"
        for text in (p["name"]["ko"], p["name"]["en"], p["definition"]["ko"]):
            assert text in row, f"parameter {p['id']}: '{text}' out of sync with parameters.json"


def test_matrix_unverified_cells_are_valid_and_have_no_value(matrix):
    for key in matrix["unverified_cells"]:
        i, w = (int(x) for x in key.split("-"))
        assert 1 <= i <= 39 and 1 <= w <= 39 and i != w, key
        assert key not in matrix["cells"], f"{key} is unverified but has a value"


def test_matrix_has_the_classic_cell_count(matrix):
    """All independent sources agree the classic matrix has 1248 non-empty cells."""
    assert len(matrix["cells"]) == 1248
