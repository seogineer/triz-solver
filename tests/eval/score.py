#!/usr/bin/env python3
"""Score an eval run (DESIGN 10.1). Stdlib only.

Usage: python tests/eval/score.py results.json [--cases physical-cases.json]

results.json maps case id -> {"improve": [ids ranked best-first],
"worsen": [ids ranked best-first], "principles_cited": [ids]}.

- A side "hits" if any expected id is among that side's top-3 candidates.
- A case hits if both sides hit.
- "unverified": among runs where a data file the agent read marks a pair of
  its answer as unverified (observed in the Read calls), how many told the user.
- A cited principle is a hallucination if no data file the agent read in that
  run contains it (matrix row cells, principle records, separation-principles;
  observed in the Read calls, the files re-read from the plugin copy). Older
  result files without that field fall back to recomputing from the reported
  candidate pairs with the oracle.
- ranking_match: the answer's ranking table (rank, id, count) equals the first
  N rows of the oracle ranking for the answer's top-3 improve x top-3 worsen
  candidates (N = rows the answer wrote). It checks the hand-counted ranking.
  The oracle (tools/lookup.py) runs here only, never in the subject's session.

Physical-contradiction cases (they carry "expected_separation") are scored on
the separation types the answer's table marks as chosen (stated_separations).
A case hits if any of them is expected. The subject reads separation-principles.json
as a whole, so the types it read are not a choice. A cited principle is a
hallucination unless a matrix row, principle or separation file the run read
contains it.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOOKUP = HERE.parent.parent / "tools" / "lookup.py"
TOP_N = 3


def real_matrix(improve, worsen):
    """Return the set of principle ids lookup.py ranks, or None if it errors."""
    p = subprocess.run(
        [sys.executable, str(LOOKUP), "matrix",
         "--improve", ",".join(map(str, improve)), "--worsen", ",".join(map(str, worsen))],
        capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return None
    return {r["id"] for r in json.loads(p.stdout)["ranking"]}


def real_ranking(improve, worsen):
    """Oracle ranking [(id, count), ...] from lookup.py, or None if it errors."""
    p = subprocess.run(
        [sys.executable, str(LOOKUP), "matrix",
         "--improve", ",".join(map(str, improve)), "--worsen", ",".join(map(str, worsen))],
        capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return None
    return [(r["id"], r["count"]) for r in json.loads(p.stdout)["ranking"]]


def ranking_match(answer_ranking, oracle):
    """True/False if the answer's table equals the oracle's first N rows; None if not checkable."""
    if not answer_ranking or oracle is None:
        return None
    got = [(r["id"], r["count"]) for r in answer_ranking]
    return got == list(oracle[:len(got)])


def score(cases, results, matrix=real_matrix, ranking=real_ranking):
    rows, hits, imp_hits, wor_hits, halluc, missing = [], 0, 0, 0, 0, []
    rank_checks, rank_unchecked = [], []
    for c in cases:
        r = results.get(c["id"])
        if r is None:
            missing.append(c["id"])
            continue
        imp, wor = r["improve"][:TOP_N], r["worsen"][:TOP_N]
        ih = bool(set(imp) & set(c["expected_improve"]))
        wh = bool(set(wor) & set(c["expected_worsen"]))
        # Prefer the principles in the files the agent actually read (observed); fall back
        # to recomputing from the reported candidates for older result files.
        observed = r.get("returned_principles")
        allowed = set(observed) if observed is not None else matrix(imp, wor)
        cited = list(r.get("principles_cited", []))
        bad = cited if allowed is None else [p for p in cited if p not in allowed]
        hits += ih and wh
        imp_hits += ih
        wor_hits += wh
        halluc += len(bad)
        rm = ranking_match(r.get("ranking"), ranking(imp, wor)) if r.get("ranking") else None
        if rm is not None:
            rank_checks.append(rm)
        else:
            rank_unchecked.append(c["id"])
        rows.append({"id": c["id"], "improve_hit": ih, "worsen_hit": wh,
                     "hit": ih and wh, "hallucinated_principles": bad, "ranking_match": rm})
    n = len(rows)
    warned = [c["id"] for c in cases if c["id"] in results and results[c["id"]].get("saw_unverified")]
    undisclosed = [i for i in warned if not results[i].get("disclosed")]
    return {"ranking_checked": len(rank_checks),
            "ranking_unchecked": rank_unchecked,
            "ranking_match_rate": sum(rank_checks) / len(rank_checks) if rank_checks else 0.0,
            "unverified": {"cases_with_warning": len(warned),
                           "disclosed": len(warned) - len(undisclosed),
                           "not_disclosed": undisclosed},
            **_summary(rows, n, hits, imp_hits, wor_hits, halluc, missing)}


def _summary(rows, n, hits, imp_hits, wor_hits, halluc, missing):
    return {"cases_scored": n, "cases_missing": missing,
            "top3_hit_rate": hits / n if n else 0.0,
            "improve_hit_rate": imp_hits / n if n else 0.0,
            "worsen_hit_rate": wor_hits / n if n else 0.0,
            "hallucinated_principles": halluc, "rows": rows}


def score_physical(cases, results):
    rows, missing = [], []
    for c in cases:
        r = results.get(c["id"])
        if r is None:
            missing.append(c["id"])
            continue
        stated = list(r.get("stated_separations", []))
        read = list(r.get("separation_types_read", []))
        expected = set(c["expected_separation"])
        recommended = set(r.get("recommended_principles", []))
        bad = [p for p in r.get("principles_cited", []) if p not in recommended]
        rows.append({"id": c["id"], "stated_separations": stated,
                     "hit": bool(set(stated) & expected),
                     "first_hit": bool(stated) and stated[0] in expected,
                     "used_separation": bool(read),
                     "hallucinated_principles": bad})
    n = len(rows)

    def rate(key):
        return sum(r[key] for r in rows) / n if n else 0.0
    return {"cases_scored": n, "cases_missing": missing,
            "separation_hit_rate": rate("hit"), "first_choice_hit_rate": rate("first_hit"),
            "used_separation_rate": rate("used_separation"),
            "hallucinated_principles": sum(len(r["hallucinated_principles"]) for r in rows),
            "rows": rows}


def main(argv):
    args = argv[1:]
    cases_path = HERE / "cases.yaml"
    if "--cases" in args:
        i = args.index("--cases")
        if i + 1 >= len(args):
            print(__doc__)
            return 2
        cases_path = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1:
        print(__doc__)
        return 2
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))["cases"]
    results = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    physical = [c for c in cases if "expected_separation" in c]
    out = score_physical(physical, results) if physical else score(cases, results)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
