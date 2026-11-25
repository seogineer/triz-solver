#!/usr/bin/env python3
"""Run the eval cases blind against the plugin with `claude -p` (DESIGN 10.1).

Blindness: the plugin is copied to a temp dir WITHOUT tests/, docs/ and .git,
and each case runs in a fresh process from a directory outside the repo, so the
session cannot read the expected parameters. Only the problem text is sent,
plus one fixed suffix (the same for every case) that skips the confirmation
question. Raw answers are saved; parsing and scoring are done by scripts.

Modes: "command" sends `/triz-solver:triz <problem>` (measures mapping
accuracy; the skill is forced); "natural" sends the problem alone (measures
whether the skill activates by itself, FR-05). Tool calls are read from
stream-json, so "which data files did it read" is observed, not inferred from
prose. The subject only has Read and Skill; its values come from plugin/ data files.

Usage: python tests/eval/run_blind.py --mode command|natural [--jobs 3] [--out DIR]
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
SUFFIX = {
    "ko": "\n\n(모순 문장은 확인 완료했으니 확인 질문 없이 끝까지 진행해줘.)",
    "en": "\n\n(The contradiction statement is confirmed; do not ask for confirmation, run through to the end.)",
    # for inputs whose contradiction nobody has confirmed (patent abstracts)
    "en_neutral": "\n\n(Do not ask me any questions; make your own choices and run through to the end.)",
    # interview smoke runs: the plain input, so the skill may ask its first question
    "none": "",
}
TIMEOUT = 280
# Only the tools the skill needs, no MCP servers: a host session's messaging or
# agent tools must not leak into a blind run. No Bash: the plugin has no script to
# run, and the subject must not run tools/lookup.py (the scoring oracle). --add-dir
# lets a sandboxed host read the plugin copy that lives outside the working directory.
ISOLATION = ["--tools", "Read,Skill", "--strict-mcp-config"]

# side label may carry a translation or rank after it ("개선 (Improving)", "개선 1순위");
# the id may be bold (**#35 ...**)
_MAP_ROW = re.compile(
    r"^\|\s*\**(개선|악화|Improv\w*|Worsen\w*)[^|\n]*\|\s*\**\s*#\s*(\d+)", re.M)
_DISCLOSE = re.compile(
    r"unverified|not (?:yet )?verified|no verified|cannot (?:be )?look|미확정|검증(?:된|되지|을 못|이 안)|"
    r"확정(?:하지|되지|된 값이 없)|조회할 수 없|조회가 불가|데이터가 없", re.I)
# ranking-table row: | rank | #id name | count |
_RANK_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*\**\s*#?\s*(\d+)[^|\n]*\|\s*\**(\d+)\**\s*\|", re.M)
_PRINCIPLE_HEAD = re.compile(r"^#{2,4}\s*(?:원리|Principle)\s*#\s*(\d+)", re.M)


_SEP_NAMES = (("space", r"공간|space"), ("time", r"시간|time"),
              ("condition", r"관계|조건|relation|condition"), ("direction", r"방향|direction"),
              ("system", r"시스템|system"))
_CHOSEN = re.compile(r"선택|채택|select|chosen|adopt", re.I)
_REJECTED = re.compile(
    r"제외|기각|reject|not select|not chosen|not adopt|not picked|unselect|deselect"
    r"|excluded|미선택|미채택"
    r"|(?:선택|채택)\s*(?:하지|않|못|안\s*(?:함|됨|한|했|돼))|(?:선택|채택)\s*되지", re.I)


def stated_separations(text):
    """Separation types the answer's table marks as chosen (first cell names the type,
    last cell carries the verdict), in table order."""
    chosen = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not _CHOSEN.search(cells[-1]) or _REJECTED.search(cells[-1]):
            continue
        for sep_id, pattern in _SEP_NAMES:
            if re.search(pattern, cells[0], re.I) and sep_id not in chosen:
                chosen.append(sep_id)
                break
    return chosen


def discloses_unverified(text):
    """True if the answer tells the user a pair has no verified data."""
    return bool(_DISCLOSE.search(text))


def parse_answer(text):
    """Extract ranked candidates and cited principles from a markdown answer."""
    improve, worsen = [], []
    for side, num in _MAP_ROW.findall(text):
        target = improve if side.startswith(("개선", "Improv")) else worsen
        if int(num) not in target:
            target.append(int(num))
    cited = []
    for num in _PRINCIPLE_HEAD.findall(text):
        if int(num) not in cited:
            cited.append(int(num))
    ranking = [{"id": int(pid), "count": int(n)} for _, pid, n in
               sorted(_RANK_ROW.findall(text), key=lambda r: int(r[0]))]
    return {"improve": improve, "worsen": worsen, "principles_cited": cited, "ranking": ranking,
            "stated_separations": stated_separations(text)}


def make_plugin_copy(dest):
    for name in (".claude-plugin", "skills", "commands"):
        shutil.copytree(ROOT / "plugin" / name, dest / name,
                        ignore=shutil.ignore_patterns("__pycache__"))


DATA_DIR = ROOT / "plugin" / "skills" / "triz-analysis" / "data"
_DATA_PATH = re.compile(
    r"(?:^|[/\\])data[/\\](?:matrix[/\\]row-(\d{2})\.json|principles[/\\]p-(\d{2})\.json"
    r"|(separation-principles|parameters)\.json)$")


def data_file_kind(file_path):
    """Classify a Read path: ("row", n), ("principle", n), ("separation", 0), ("parameters", 0) or None."""
    m = _DATA_PATH.search(str(file_path))
    if not m:
        return None
    if m.group(1):
        return "row", int(m.group(1))
    if m.group(2):
        return "principle", int(m.group(2))
    return ("separation" if m.group(3) == "separation-principles" else "parameters"), 0


def read_data_file(kind, num, data_dir):
    """Parse a data file the agent read. The copy on disk is re-read instead of the
    tool result, which may carry `cat -n` line numbers. Returns None if unreadable."""
    rel = {"row": f"matrix/row-{num:02d}.json", "principle": f"principles/p-{num:02d}.json",
           "separation": "separation-principles.json", "parameters": "parameters.json"}[kind]
    try:
        return json.loads((Path(data_dir) / rel).read_text(encoding="utf-8")), rel
    except (OSError, ValueError):
        return None, rel


def _int_list(values):
    return [x for x in values or [] if isinstance(x, int)]


def file_principles(kind, data):
    """Principle ids a data file contains: (recommended, record). Rows and
    separation types recommend principles; a principle file is a record."""
    if not isinstance(data, dict):
        return set(), set()
    if kind == "row":
        cells = data.get("cells", {})
        return {p for cell in (cells.values() if isinstance(cells, dict) else []) for p in _int_list(cell)}, set()
    if kind == "separation":
        ids = set()
        for sep in data.get("separations", []) or []:
            if isinstance(sep, dict):
                ids.update(_int_list(sep.get("related_principles")))
        return ids, set()
    if kind == "principle" and isinstance(data.get("id"), int):
        return set(), {data["id"]}
    return set(), set()


def _tool_result_error(block):
    return bool(block.get("is_error"))


def parse_stream(lines, data_dir=DATA_DIR):
    """Read claude stream-json lines: final text, skills used, data files read.

    A file counts as read only if the transcript has a Read tool_use for it and
    a non-error tool_result. Values come from that file, not from memory.
    """
    info = {"text": "", "model": "", "plugin_loaded": False, "skills": [], "file_reads": 0,
            "files_read": [], "unverified_rows": {}, "separation_types_read": []}
    calls, results = {}, {}   # tool_use id -> file_path / is_error
    anonymous = []            # Read calls without an id (cannot be matched to a result)
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        kind = ev.get("type")
        if kind == "system" and ev.get("subtype") == "init":
            info["model"] = ev.get("model", "")
            plugins = json.dumps(ev.get("plugins", []) + ev.get("slash_commands", []))
            # "triz-decider" is the slug before 2026-09-24; keeps old recorded runs scorable
            info["plugin_loaded"] = "triz-solver" in plugins or "triz-decider" in plugins
        elif kind == "assistant":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") != "tool_use":
                    continue
                inp = block.get("input", {})
                if block.get("name") == "Skill":
                    info["skills"].append(str(inp.get("skill", "")))
                if block.get("name") == "Read" and inp.get("file_path"):
                    if block.get("id"):
                        calls[block["id"]] = str(inp["file_path"])
                    else:
                        anonymous.append(str(inp["file_path"]))
        elif kind == "user":
            content = ev.get("message", {}).get("content", [])
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result" and block.get("tool_use_id"):
                    results[block["tool_use_id"]] = _tool_result_error(block)
        elif kind == "result":
            info["text"] = ev.get("result", "") or ""
    paths = [p for i, p in calls.items() if i in results and not results[i]] + anonymous
    recommended, returned, seen = set(), set(), set()
    for path in paths:
        parsed = data_file_kind(path)
        if parsed is None:
            continue
        data, rel = read_data_file(*parsed, data_dir)
        if data is None or rel in seen:
            continue
        seen.add(rel)
        info["files_read"].append(rel)
        rec, record = file_principles(parsed[0], data)
        recommended |= rec
        returned |= rec | record
        if parsed[0] == "row" and isinstance(data, dict) and data.get("unverified"):
            info["unverified_rows"][str(parsed[1])] = _int_list(data["unverified"])
        if parsed[0] == "separation":
            info["separation_types_read"] = [s["id"] for s in data.get("separations", [])
                                             if isinstance(s, dict) and isinstance(s.get("id"), str)]
    info["file_reads"] = len(info["files_read"])
    info["returned_principles"] = sorted(returned)
    info["recommended_principles"] = sorted(recommended)
    info["skill_used"] = any("triz-analysis" in x for x in info["skills"])
    return info


def saw_unverified(unverified_rows, improve, worsen):
    """True if a row the agent read marks a (improve, worsen) pair of its answer as unverified."""
    return any(w in unverified_rows.get(str(i), []) for i in improve for w in worsen)


def safe_name(case_id):
    """File-system safe name for a case id (patent ids can contain slashes)."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(case_id))


def build_prompt(case, mode):
    suffix = SUFFIX[case.get("suffix", case["lang"])]
    if mode == "command":
        return "/triz-solver:triz " + case["problem"] + suffix
    return case["problem"] + suffix


def run_case(case, mode, plugin_dir, workdir, raw_dir, attempts=3):
    """Retry only infrastructure failures (plugin not loaded / no output)."""
    info, code = {}, -1
    for attempt in range(1, attempts + 1):
        try:
            p = subprocess.run(
                ["claude", "-p", build_prompt(case, mode), "--plugin-dir", str(plugin_dir),
                 *ISOLATION, "--add-dir", str(plugin_dir),
                 "--allowedTools", "Read",
                 "--output-format", "stream-json", "--verbose"],
                cwd=workdir, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT)
            code, lines = p.returncode, p.stdout.splitlines()
        except subprocess.TimeoutExpired:
            code, lines = -1, []
        info = parse_stream(lines, Path(plugin_dir) / "skills" / "triz-analysis" / "data")
        (raw_dir / f"{safe_name(case['id'])}.jsonl").write_text("\n".join(lines), encoding="utf-8")
        (raw_dir / f"{safe_name(case['id'])}.md").write_text(info["text"], encoding="utf-8")
        if code == 0 and info["plugin_loaded"] and info["text"]:
            break
    res = parse_answer(info["text"])
    res.update({"skill_used": info["skill_used"], "file_reads": info["file_reads"],
                "files_read": info["files_read"], "plugin_loaded": info["plugin_loaded"], "model": info["model"], "attempts": attempt, "exit_code": code,
                "saw_unverified": saw_unverified(info["unverified_rows"], res["improve"], res["worsen"]),
                "returned_principles": info["returned_principles"],
                "recommended_principles": info["recommended_principles"],
                "separation_types_read": info["separation_types_read"],
                "disclosed": discloses_unverified(info["text"])})
    return case["id"], res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["command", "natural"], required=True)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--out", default=None)
    ap.add_argument("--only", help="comma-separated case ids (default: all)")
    ap.add_argument("--cases", default=str(HERE / "cases.yaml"), help="case file (JSON/YAML 1.2)")
    args = ap.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    out = Path(args.out or HERE / f"blind-run-{args.mode}")
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        plugin, work = Path(tmp) / "plugin", Path(tmp) / "work"
        work.mkdir()
        make_plugin_copy(plugin)
        assert not any((plugin / n).exists() for n in ("tests", "docs", "data", "tools"))
        assert not any(plugin.rglob("lookup.py"))
        with ThreadPoolExecutor(args.jobs) as ex:
            done = list(ex.map(lambda c: run_case(c, args.mode, plugin, work, raw), cases))
    results = dict(done)
    c_by_id = {c["id"]: c for c in cases}
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [cid for cid, r in done if not r["plugin_loaded"]
           or not (r["stated_separations"] if "expected_separation" in c_by_id[cid]
                   else r["improve"] and r["worsen"])]
    print(json.dumps({"mode": args.mode, "ran": len(done), "skill_used": sum(r["skill_used"] for _, r in done),
                      "infra_or_unparsed": bad}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
