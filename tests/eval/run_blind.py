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
stream-json, so "did it run lookup.py" is observed, not inferred from prose.

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
# agent tools must not leak into a blind run. --add-dir lets a sandboxed host
# read and run the plugin copy that lives outside the working directory.
ISOLATION = ["--tools", "Bash,Read,Skill", "--strict-mcp-config"]

# side label may carry a translation or rank after it ("개선 (Improving)", "개선 1순위");
# the id may be bold (**#35 ...**)
_MAP_ROW = re.compile(
    r"^\|\s*\**(개선|악화|Improv\w*|Worsen\w*)[^|\n]*\|\s*\**\s*#\s*(\d+)", re.M)
_DISCLOSE = re.compile(
    r"unverified|not (?:yet )?verified|no verified|cannot (?:be )?look|미확정|검증(?:된|되지|을 못|이 안)|"
    r"확정(?:하지|되지|된 값이 없)|조회할 수 없|조회가 불가|데이터가 없", re.I)
_PRINCIPLE_HEAD = re.compile(r"^#{2,4}\s*(?:원리|Principle)\s*#\s*(\d+)", re.M)


_SEP_NAMES = (("space", r"공간|space"), ("time", r"시간|time"),
              ("condition", r"관계|조건|relation|condition"), ("direction", r"방향|direction"),
              ("system", r"시스템|system"))
_CHOSEN = re.compile(r"선택|채택|select|chosen|adopt", re.I)
_REJECTED = re.compile(r"제외|기각|reject|not select|excluded", re.I)


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
    return {"improve": improve, "worsen": worsen, "principles_cited": cited,
            "stated_separations": stated_separations(text)}


def make_plugin_copy(dest):
    for name in (".claude-plugin", "skills", "commands"):
        shutil.copytree(ROOT / "plugin" / name, dest / name,
                        ignore=shutil.ignore_patterns("__pycache__"))


def _recommended_principles(payload):
    """Principle ids a matrix or separation result recommends (not principle records)."""
    ids = set()
    if isinstance(payload, dict):
        for pair in payload.get("pairs", []) or []:
            ids.update(x for x in pair.get("principles", []) if isinstance(x, int))
        for sep in payload.get("separations", []) or []:
            for rec in (sep.get("related_principles", []) if isinstance(sep, dict) else []):
                if isinstance(rec, dict) and isinstance(rec.get("id"), int):
                    ids.add(rec["id"])
        for rec in payload.get("ranking", []) or []:
            if isinstance(rec, dict) and isinstance(rec.get("id"), int):
                ids.add(rec["id"])
    return ids


def _returned_principles(payload):
    """Principle ids a lookup.py result carries (recommendations or principle records)."""
    ids = _recommended_principles(payload)
    if isinstance(payload, dict):
        for rec in payload.get("principles", []) or []:
            if isinstance(rec, dict) and isinstance(rec.get("id"), int):
                ids.add(rec["id"])
    return ids


_SEP_TYPE_ARG = re.compile(r"lookup\.py\s+separation\b[^|;&\n]*?--type[ =]+([A-Za-z,]+)")


def separation_types(command):
    """Separation types a `lookup.py separation --type ...` command asks for."""
    m = _SEP_TYPE_ARG.search(command)
    return [t for t in m.group(1).split(",") if t] if m else []


def _tool_result_payloads(block):
    content = block.get("content", "")
    texts = [content] if isinstance(content, str) else [
        c.get("text", "") for c in content if isinstance(c, dict)]
    for text in texts:
        yield from _json_objects(text)


def _json_objects(text):
    """JSON objects in a tool result, also when other output surrounds them.

    Runs often chain commands (`cat guide.md && lookup.py separation`), so the
    result is not pure JSON. lookup.py prints each object starting at a line.
    """
    try:
        yield json.loads(text)
        return
    except ValueError:
        pass
    dec = json.JSONDecoder()
    pos = 0
    while True:
        start = text.find("\n{", pos) if pos or not text.startswith("{") else 0
        if start < 0:
            return
        start += text[start] == "\n"
        try:
            obj, end = dec.raw_decode(text, start)
        except ValueError:
            pos = start + 1
            continue
        if isinstance(obj, dict):
            yield obj
        pos = end


def parse_stream(lines):
    """Read claude stream-json lines: final text, skills used, lookup.py calls."""
    info = {"text": "", "model": "", "plugin_loaded": False, "skills": [], "lookup_calls": 0,
            "saw_unverified": False, "separation_types": []}
    returned, recommended = set(), set()
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
                if block.get("name") == "Bash" and "lookup.py" in str(inp.get("command", "")):
                    info["lookup_calls"] += 1
                    for t in separation_types(str(inp.get("command", ""))):
                        if t not in info["separation_types"]:
                            info["separation_types"].append(t)
        elif kind == "user":
            content = ev.get("message", {}).get("content", [])
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result":
                    for payload in _tool_result_payloads(block):
                        # only a lookup.py JSON warning counts; reading SKILL.md also shows the word
                        if isinstance(payload, dict) and any(
                                isinstance(w, dict) and w.get("code") == "unverified_cell"
                                for w in payload.get("warnings", []) or []):
                            info["saw_unverified"] = True
                        returned |= _returned_principles(payload)
                        recommended |= _recommended_principles(payload)
        elif kind == "result":
            info["text"] = ev.get("result", "") or ""
    info["returned_principles"] = sorted(returned)
    info["recommended_principles"] = sorted(recommended)
    info["skill_used"] = any("triz-analysis" in x for x in info["skills"])
    return info


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
                 "--allowedTools", "Bash(python3:*)", "Read",
                 "--output-format", "stream-json", "--verbose"],
                cwd=workdir, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT)
            code, lines = p.returncode, p.stdout.splitlines()
        except subprocess.TimeoutExpired:
            code, lines = -1, []
        info = parse_stream(lines)
        (raw_dir / f"{safe_name(case['id'])}.jsonl").write_text("\n".join(lines), encoding="utf-8")
        (raw_dir / f"{safe_name(case['id'])}.md").write_text(info["text"], encoding="utf-8")
        if code == 0 and info["plugin_loaded"] and info["text"]:
            break
    res = parse_answer(info["text"])
    res.update({"skill_used": info["skill_used"], "lookup_calls": info["lookup_calls"],
                "plugin_loaded": info["plugin_loaded"], "model": info["model"], "attempts": attempt, "exit_code": code,
                "saw_unverified": info["saw_unverified"],
                "returned_principles": info["returned_principles"],
                "recommended_principles": info["recommended_principles"],
                "separation_types": info["separation_types"],
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
        assert not (plugin / "tests").exists() and not (plugin / "docs").exists()
        with ThreadPoolExecutor(args.jobs) as ex:
            done = list(ex.map(lambda c: run_case(c, args.mode, plugin, work, raw), cases))
    results = dict(done)
    c_by_id = {c["id"]: c for c in cases}
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [cid for cid, r in done if not r["plugin_loaded"]
           or not ((r["separation_types"] or r["stated_separations"]) if "expected_separation" in c_by_id[cid]
                   else r["improve"] and r["worsen"])]
    print(json.dumps({"mode": args.mode, "ran": len(done), "skill_used": sum(r["skill_used"] for _, r in done),
                      "infra_or_unparsed": bad}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
