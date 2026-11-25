#!/usr/bin/env python3
"""TRIZ lookup CLI: deterministic access to the contradiction matrix and data.

Standard library only (Python 3.9+), no network. Data is resolved relative to
this file (../data/). Output is JSON on stdout; errors are JSON on stderr with
an exit code (see docs/DESIGN.md chapter 6).

Exit codes: 0 ok, 2 invalid_argument, 3 out_of_range, 4 same_parameter,
5 data_error.
"""
import argparse
import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

N_PARAMS = 39
N_PRINCIPLES = 40
# order follows the source (MATRIZ): space, time, relation/condition, direction, system level
SEPARATION_TYPES = ("space", "time", "condition", "direction", "system")
# industry cases per principle (DESIGN 5.3, v0.3)
CASE_DOMAINS = ("mechanical", "electronics", "software", "materials", "medical", "everyday")
CASES_PER_PRINCIPLE = 4
CASE_DOMAIN_NAMES = {
    "mechanical": {"ko": "기계", "en": "mechanical"},
    "electronics": {"ko": "전기·전자", "en": "electronics"},
    "software": {"ko": "소프트웨어·IT", "en": "software/IT"},
    "materials": {"ko": "화학·소재", "en": "chemistry/materials"},
    "medical": {"ko": "의료·바이오", "en": "medical/bio"},
    "everyday": {"ko": "생활·서비스", "en": "everyday life/services"},
}
_PRINCIPLE_REF_RE = re.compile(r"#\s*\d")

EXIT_INVALID_ARGUMENT = 2
EXIT_OUT_OF_RANGE = 3
EXIT_SAME_PARAMETER = 4
EXIT_DATA_ERROR = 5

_INT_RE = re.compile(r"^-?\d+$")
_CELL_KEY_RE = re.compile(r"^(\d+)-(\d+)$")


class LookupError_(Exception):
    """An error that maps to a JSON error payload and an exit code."""

    def __init__(self, code, message, exit_code, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details


def data_error(message, details=None):
    return LookupError_("data_error", message, EXIT_DATA_ERROR, details)


# ------------------------------------------------------------------ I/O ---

def emit(obj, stream=None):
    stream = stream or sys.stdout
    stream.write(json.dumps(obj, ensure_ascii=False, indent=2))
    stream.write("\n")


def fail(err):
    payload = {"code": err.code, "message": err.message}
    if err.details:
        payload["details"] = err.details
    emit({"error": payload}, sys.stderr)
    sys.exit(err.exit_code)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        fail(LookupError_("invalid_argument", message, EXIT_INVALID_ARGUMENT))


def load(name):
    path = DATA_DIR / name
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise data_error(f"data file not found: {name}")
    except (OSError, ValueError) as exc:  # ValueError covers JSON/Unicode errors
        raise data_error(f"cannot read data file {name}: {exc}")


def pick(text_map, lang):
    """Choose text for lang from {"ko": ..., "en": ...}, falling back to the other."""
    if not isinstance(text_map, dict):
        return text_map
    if text_map.get(lang):
        return text_map[lang]
    for other in ("ko", "en"):
        if text_map.get(other):
            return text_map[other]
    return None


# ------------------------------------------------------- argument parsing ---

def parse_ids(raw, label, upper):
    """Parse '1,9,14' into a de-duplicated list of ints within 1..upper."""
    parts = [p.strip() for p in raw.split(",")]
    if not raw.strip() or any(not _INT_RE.match(p) for p in parts):
        raise LookupError_(
            "invalid_argument",
            f"{label} must be comma-separated integers (e.g. 1,9), got {raw!r}",
            EXIT_INVALID_ARGUMENT,
        )
    ids = []
    for p in parts:
        n = int(p)
        if not 1 <= n <= upper:
            raise LookupError_(
                "out_of_range", f"{label} {n} is out of range 1-{upper}", EXIT_OUT_OF_RANGE
            )
        if n not in ids:
            ids.append(n)
    return ids


# --------------------------------------------------------------- commands ---

def rank_principles(lists):
    """Principle ids ranked by count (desc); ties go round-robin over the lists.

    A tie is broken by the principle's earliest position within any list, then
    by that list's order: every list's 1st principle, then every list's 2nd, and
    so on. Lists are matrix cells in pair order, or separation types in --type
    order, so on a tie the first list never fills the top of the ranking alone.
    """
    counts, first = {}, {}
    for l_idx, ids in enumerate(lists):
        for pos, pid in enumerate(ids):
            counts[pid] = counts.get(pid, 0) + 1
            first[pid] = min(first.get(pid, (pos, l_idx)), (pos, l_idx))
    return [(pid, counts[pid]) for pid in sorted(counts, key=lambda pid: (-counts[pid], first[pid]))]


def cmd_matrix(args):
    improve = parse_ids(args.improve, "--improve", N_PARAMS)
    worsen = parse_ids(args.worsen, "--worsen", N_PARAMS)
    same = sorted(set(improve) & set(worsen))
    if same:
        raise LookupError_(
            "same_parameter",
            f"improving and worsening parameter must differ; shared: {same}",
            EXIT_SAME_PARAMETER,
        )

    matrix = load("contradiction-matrix.json")
    principles = load("inventive-principles.json")
    try:
        cells = matrix["cells"]
        missing_rows = set(matrix.get("missing_rows", []))
        unverified = set(matrix.get("unverified_cells", []))
        names = {p["id"]: pick(p["name"], args.lang) for p in principles["principles"]}
    except (KeyError, TypeError) as exc:
        raise data_error(f"malformed data file: {exc!r}")

    pairs, empty_pairs, unverified_pairs = [], [], []
    for i in improve:
        for w in worsen:
            if f"{i}-{w}" in unverified:  # never answer from a disputed cell
                empty_pairs.append({"improve": i, "worsen": w})
                unverified_pairs.append({"code": "unverified_cell", "improve": i, "worsen": w})
                continue
            cell = cells.get(f"{i}-{w}")
            if not cell:
                empty_pairs.append({"improve": i, "worsen": w})
                continue
            pairs.append({"improve": i, "worsen": w, "principles": list(cell)})

    try:
        ranking = [{"id": pid, "count": n, "name": names[pid]}
                   for pid, n in rank_principles([p["principles"] for p in pairs])]
    except KeyError as exc:
        raise data_error(f"matrix references unknown principle id {exc}")

    warnings = [{"code": "missing_row", "improve": i} for i in improve if i in missing_rows]
    warnings += unverified_pairs
    return {"pairs": pairs, "empty_pairs": empty_pairs, "ranking": ranking, "warnings": warnings}


def cmd_principle(args):
    ids = parse_ids(args.id, "--id", N_PRINCIPLES)
    data = load("inventive-principles.json")
    try:
        by_id = {p["id"]: p for p in data["principles"]}
        out = []
        for pid in ids:
            p = by_id[pid]
            out.append({
                "id": pid,
                "name": pick(p["name"], args.lang),
                "sub_principles": pick(p["sub_principles"], args.lang),
                "examples": pick(p["examples"], args.lang),
            })
            if args.cases:
                out[-1]["cases"] = [{"domain": c["domain"],
                                     "domain_name": CASE_DOMAIN_NAMES[c["domain"]][args.lang],
                                     "sub_principle": c["sub_principle"], "text": c[args.lang]}
                                    for c in p.get("cases", [])]
    except (KeyError, TypeError) as exc:
        raise data_error(f"principle data missing or malformed: {exc!r}")
    return {"principles": out}


def parse_types(raw):
    """Parse 'time,space' into separation type ids; None means all types."""
    if raw is None:
        return list(SEPARATION_TYPES)
    types = []
    for t in (x.strip() for x in raw.split(",")):
        if t not in SEPARATION_TYPES:
            raise LookupError_(
                "invalid_argument",
                f"--type must be one or more of {', '.join(SEPARATION_TYPES)}, got {t!r}",
                EXIT_INVALID_ARGUMENT,
            )
        if t not in types:
            types.append(t)
    return types


def cmd_separation(args):
    types = parse_types(args.type)
    data = load("separation-principles.json")
    principles = load("inventive-principles.json")
    try:
        names = {p["id"]: pick(p["name"], args.lang) for p in principles["principles"]}
        by_id = {s["id"]: s for s in data["separations"]}
        out = []
        for t in types:
            s = by_id[t]
            out.append({
                "id": t,
                "name": pick(s["name"], args.lang),
                "question": pick(s["question"], args.lang),
                "when_to_use": pick(s["when_to_use"], args.lang),
                "related_principles": [{"id": pid, "name": names[pid]}
                                       for pid in s["related_principles"]],
                "examples": [pick(e, args.lang) for e in s.get("examples", [])],
            })
    except (KeyError, TypeError) as exc:
        raise data_error(f"separation data missing or malformed: {exc!r}")
    ranking = [{"id": pid, "count": n, "name": names[pid]}
               for pid, n in rank_principles([[rp["id"] for rp in sep["related_principles"]] for sep in out])]
    return {"separations": out, "ranking": ranking}


def _param_view(p, lang, full):
    view = {"id": p["id"], "name": pick(p["name"], lang), "keywords": p.get("keywords", [])}
    if full:
        view["definition"] = pick(p["definition"], lang)
    return view


def cmd_param(args):
    data = load("parameters.json")
    try:
        params = data["parameters"]
        if args.id is not None:
            ids = parse_ids(args.id, "--id", N_PARAMS)
            by_id = {p["id"]: p for p in params}
            return {"parameters": [_param_view(by_id[i], args.lang, True) for i in ids]}

        query = args.search.strip()
        if not query:
            raise LookupError_("invalid_argument", "--search must not be empty", EXIT_INVALID_ARGUMENT)
        q = query.lower()
        matches = []
        for p in params:
            haystack = [p["name"].get("en", ""), p["name"].get("ko", "")] + list(p.get("keywords", []))
            if any(q in str(h).lower() for h in haystack):
                matches.append(_param_view(p, args.lang, False))
        return {"query": query, "matches": matches}
    except (KeyError, TypeError, AttributeError) as exc:
        raise data_error(f"parameter data missing or malformed: {exc!r}")


def _check_meta(name, data, errors):
    for field in ("version", "source"):
        if not data.get(field):
            errors.append(f"{name}: missing metadata field '{field}'")


def _check_names(label, item, errors):
    name = item.get("name") or {}
    for lang in ("en", "ko"):
        if not name.get(lang):
            errors.append(f"{label}: missing {lang} name")


def _check_cases(p, errors):
    """Industry cases of one principle (DESIGN 5.3)."""
    where = f"principle {p.get('id')} cases"
    cases = p["cases"]
    if not isinstance(cases, list) or len(cases) != CASES_PER_PRINCIPLE:
        errors.append(f"{where}: need exactly {CASES_PER_PRINCIPLE}")
        return
    n_sub = len((p.get("sub_principles") or {}).get("ko") or [])
    domains = []
    for i, c in enumerate(cases, 1):
        if not isinstance(c, dict):
            errors.append(f"{where} #{i}: must be an object")
            continue
        domains.append(c.get("domain"))
        if c.get("domain") not in CASE_DOMAINS:
            errors.append(f"{where} #{i}: domain must be one of {', '.join(CASE_DOMAINS)}")
        sub = c.get("sub_principle")
        if not isinstance(sub, int) or isinstance(sub, bool) or not 1 <= sub <= n_sub:
            errors.append(f"{where} #{i}: sub_principle must be 1..{n_sub}")
        for lang in ("ko", "en"):
            text = c.get(lang)
            if not isinstance(text, str) or not text.strip() or text.strip() == "TODO":
                errors.append(f"{where} #{i}: missing {lang} text")
            elif _PRINCIPLE_REF_RE.search(text):
                errors.append(f"{where} #{i}: {lang} text must not cite a principle number")
    if len(set(domains)) != len(domains):
        errors.append(f"{where}: domains must differ")


def cmd_validate(_args):
    files = {n: load(n) for n in (
        "parameters.json", "contradiction-matrix.json",
        "inventive-principles.json", "separation-principles.json")}
    errors, warnings = [], []
    for name, data in files.items():
        if not isinstance(data, dict):
            errors.append(f"{name}: top level must be an object")
            continue
        _check_meta(name, data, errors)

    params = files["parameters.json"].get("parameters", [])
    if [p.get("id") for p in params] != list(range(1, N_PARAMS + 1)):
        errors.append(f"parameters.json: parameter ids must be exactly 1..{N_PARAMS}")
    todo_defs = empty_kw = 0
    for p in params:
        _check_names(f"parameter {p.get('id')}", p, errors)
        definition = p.get("definition") or {}
        if not definition.get("en") or not definition.get("ko"):
            errors.append(f"parameter {p.get('id')}: missing definition text")
        elif "TODO" in (definition["en"], definition["ko"]):
            todo_defs += 1
        if not p.get("keywords"):
            empty_kw += 1
    if todo_defs:
        warnings.append({"code": "todo_definition", "count": todo_defs})
    if empty_kw:
        warnings.append({"code": "empty_keywords", "count": empty_kw})

    principles = files["inventive-principles.json"].get("principles", [])
    if [p.get("id") for p in principles] != list(range(1, N_PRINCIPLES + 1)):
        errors.append(f"inventive-principles.json: principle ids must be exactly 1..{N_PRINCIPLES}")
    for p in principles:
        _check_names(f"principle {p.get('id')}", p, errors)
        if not (p.get("sub_principles") or {}).get("ko"):
            errors.append(f"principle {p.get('id')}: missing ko sub_principles")
        if not (p.get("examples") or {}).get("ko"):
            errors.append(f"principle {p.get('id')}: missing ko examples")
        if "cases" in p:
            _check_cases(p, errors)
    no_cases = sum(1 for p in principles if not p.get("cases"))
    if no_cases:
        warnings.append({"code": "missing_cases", "count": no_cases})

    matrix = files["contradiction-matrix.json"]
    if matrix.get("size") != N_PARAMS:
        errors.append(f"contradiction-matrix.json: size must be {N_PARAMS}")
    cells = matrix.get("cells")
    if not isinstance(cells, dict):
        errors.append("contradiction-matrix.json: 'cells' must be an object")
        cells = {}
    populated = set()
    for key, ids in cells.items():
        m = _CELL_KEY_RE.match(key)
        if not m:
            errors.append(f"cell '{key}': malformed key (expected 'improve-worsen')")
            continue
        i, w = int(m.group(1)), int(m.group(2))
        if not (1 <= i <= N_PARAMS and 1 <= w <= N_PARAMS):
            errors.append(f"cell '{key}': parameter id out of range 1-{N_PARAMS}")
            continue
        if i == w:
            errors.append(f"cell '{key}': diagonal key must be omitted")
        populated.add(i)
        if not isinstance(ids, list) or not ids:
            errors.append(f"cell '{key}': empty cells must be omitted")
            continue
        if any(not isinstance(x, int) or not 1 <= x <= N_PRINCIPLES for x in ids):
            errors.append(f"cell '{key}': principle id out of range 1-{N_PRINCIPLES}")
        if len(set(ids)) != len(ids):
            errors.append(f"cell '{key}': duplicate principle id")
    missing_rows = matrix.get("missing_rows", [])
    for row in range(1, N_PARAMS + 1):
        if row not in populated and row not in missing_rows:
            errors.append(f"row {row} has no cells but is not declared in missing_rows")
    for row in missing_rows:
        if row in populated:
            errors.append(f"row {row} is declared in missing_rows but has cells")
        else:
            warnings.append({"code": "missing_row", "improve": row})

    for key in matrix.get("unverified_cells", []):
        m = _CELL_KEY_RE.match(key) if isinstance(key, str) else None
        i, w = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        if not m or not (1 <= i <= N_PARAMS and 1 <= w <= N_PARAMS) or i == w:
            errors.append(f"unverified_cells: malformed or out-of-range key {key!r}")
        elif key in cells:
            errors.append(f"unverified_cells: {key} is listed but also has a value in cells")
        else:
            warnings.append({"code": "unverified_cell", "improve": i, "worsen": w})

    seps = files["separation-principles.json"].get("separations", [])
    if [s.get("id") for s in seps] != list(SEPARATION_TYPES):
        errors.append("separation-principles.json: ids must be " + ", ".join(SEPARATION_TYPES))
    for s in seps:
        label = f"separation {s.get('id')}"
        _check_names(label, s, errors)
        for field in ("question", "when_to_use"):
            text = s.get(field) or {}
            if not text.get("ko") or not text.get("en") or "TODO" in (text.get("ko"), text.get("en")):
                errors.append(f"{label}: missing {field} text")
        related = s.get("related_principles")
        if not isinstance(related, list) or not related:
            errors.append(f"{label}: related_principles must be a non-empty list")
        elif any(not isinstance(x, int) or not 1 <= x <= N_PRINCIPLES for x in related):
            errors.append(f"{label}: related principle id out of range")
        elif len(set(related)) != len(related):
            errors.append(f"{label}: duplicate related principle id")
        if not s.get("examples") or any(not e.get("ko") or not e.get("en") for e in s["examples"]):
            errors.append(f"{label}: examples need ko and en text")

    if errors:
        raise data_error(f"{len(errors)} data integrity violation(s)", details=errors)
    return {"ok": True, "errors": [], "warnings": warnings}


# ------------------------------------------------------------------- main ---

def build_parser():
    parser = JsonArgumentParser(prog="lookup.py", description=__doc__.splitlines()[0],
                                allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)

    def add_lang(p):
        p.add_argument("--lang", choices=["ko", "en"], default="ko")

    p = sub.add_parser("matrix", help="look up contradiction-matrix cells", allow_abbrev=False)
    p.add_argument("--improve", required=True, help="improving parameter ids, e.g. 1,9")
    p.add_argument("--worsen", required=True, help="worsening parameter ids, e.g. 2,14")
    add_lang(p)
    p.set_defaults(func=cmd_matrix)

    p = sub.add_parser("principle", help="look up inventive principles", allow_abbrev=False)
    p.add_argument("--id", required=True, help="principle ids, e.g. 1,15,35")
    p.add_argument("--cases", action="store_true",
                   help="also return industry cases (domain, sub_principle, text)")
    add_lang(p)
    p.set_defaults(func=cmd_principle)

    p = sub.add_parser("param", help="look up or search parameters", allow_abbrev=False)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", help="parameter ids, e.g. 9")
    g.add_argument("--search", help="keyword search over names and keywords")
    add_lang(p)
    p.set_defaults(func=cmd_param)

    p = sub.add_parser("separation", help="look up separation principles (physical contradictions)",
                       allow_abbrev=False)
    p.add_argument("--type", help="separation types, e.g. time,space (default: all): "
                   + ", ".join(SEPARATION_TYPES))
    add_lang(p)
    p.set_defaults(func=cmd_separation)

    p = sub.add_parser("validate", help="check data integrity", allow_abbrev=False)
    add_lang(p)
    p.set_defaults(func=cmd_validate)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        result = args.func(args)
    except LookupError_ as err:
        fail(err)
    emit(result)


if __name__ == "__main__":
    main()
