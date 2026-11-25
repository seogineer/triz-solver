"""The hand ranking procedure of SKILL.md ("순위 집계", DESIGN.md 12.4) against lookup.py.

The procedure is written here from the document text only and reads the
plugin's split data files, not the root data/ and not rank_principles.
"""
import importlib.util
import itertools
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDATA = ROOT / "plugin" / "skills" / "triz-analysis" / "data"
TYPES = ("space", "time", "condition", "direction", "system")


def _load_lookup():
    spec = importlib.util.spec_from_file_location("lookup_tool", ROOT / "tools" / "lookup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LOOKUP = _load_lookup()


def run_lookup(*argv):
    args = LOOKUP.build_parser().parse_args(list(argv))
    return args.func(args)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


ROWS = {i: read_json(PDATA / "matrix" / f"row-{i:02d}.json") for i in range(1, 40)}
SEPS = {s["id"]: s for s in read_json(PDATA / "separation-principles.json")["separations"]}


def hand_rank(cells):
    """Steps 2-4 of the document. `cells` is the list of cells in cell order (step 1 done)."""
    count = {}
    earliest = {}
    for cell_order, cell in enumerate(cells):
        for in_cell, pid in enumerate(cell):
            count[pid] = count.get(pid, 0) + 1          # step 2
            pos = (in_cell, cell_order)                  # step 4: position
            if pid not in earliest or pos < earliest[pid]:
                earliest[pid] = pos
    # step 3: larger count first; step 4: ties by earliest position
    order = sorted(count, key=lambda pid: (-count[pid], earliest[pid]))
    return [(pid, count[pid]) for pid in order]


def hand_cells(improve, worsen):
    """Step 1: cells in pair order (improve candidates, then worsen candidates); skip empty."""
    cells = []
    for i in improve:
        for w in worsen:
            cell = ROWS[i]["cells"].get(str(w))
            if cell:
                cells.append(cell)
    return cells


def sample_pairs(n=300, seed=0):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        ni, nw = rng.randint(1, 3), rng.randint(1, 3)
        picked = rng.sample(range(1, 40), ni + nw)
        out.append((picked[:ni], picked[ni:]))
    return out


def test_document_example():
    assert hand_rank([[8, 15, 35, 38], [14, 20, 19, 35]]) == [
        (35, 2), (8, 1), (14, 1), (15, 1), (20, 1), (19, 1), (38, 1)]


def test_matrix_ranking_matches_procedure_on_300_random_combinations():
    nonempty_ranking = 0
    for improve, worsen in sample_pairs():
        out = run_lookup("matrix", "--improve", ",".join(map(str, improve)),
                         "--worsen", ",".join(map(str, worsen)))
        got = [(r["id"], r["count"]) for r in out["ranking"]]
        want = hand_rank(hand_cells(improve, worsen))
        assert got == want, (improve, worsen)
        # cells themselves must also agree with the split files
        assert [p["principles"] for p in out["pairs"]] == hand_cells(improve, worsen)
        nonempty_ranking += bool(want)
    assert nonempty_ranking > 250


def test_samples_include_combinations_with_empty_cells():
    with_empty = 0
    for improve, worsen in sample_pairs():
        out = run_lookup("matrix", "--improve", ",".join(map(str, improve)),
                         "--worsen", ",".join(map(str, worsen)))
        if out["empty_pairs"]:
            with_empty += 1
            n_total = len(improve) * len(worsen)
            assert len(out["pairs"]) + len(out["empty_pairs"]) == n_total
            for e in out["empty_pairs"]:
                assert str(e["worsen"]) not in ROWS[e["improve"]]["cells"]
    assert with_empty >= 1


def test_separation_ranking_matches_procedure_on_all_ordered_type_subsets():
    checked = 0
    for k in range(1, 6):
        for combo in itertools.permutations(TYPES, k):
            out = run_lookup("separation", "--type", ",".join(combo))
            got = [(r["id"], r["count"]) for r in out["ranking"]]
            want = hand_rank([SEPS[t]["related_principles"] for t in combo])
            assert got == want, combo
            checked += 1
    assert checked == 325 and checked >= 100
