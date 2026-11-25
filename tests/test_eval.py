"""Tests for the eval cases and the scoring tool (DESIGN 10.1)."""
import importlib.util
import json
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent / "eval"
spec = importlib.util.spec_from_file_location("eval_score", EVAL / "score.py")
score_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(score_mod)

CASES = json.loads((EVAL / "cases.yaml").read_text(encoding="utf-8"))["cases"]


def test_cases_have_unique_ids():
    assert len(CASES) >= 20
    assert len({c["id"] for c in CASES}) == len(CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case_is_well_formed(case):
    assert case["problem"].strip()
    assert case["lang"] in ("ko", "en")
    for key in ("expected_improve", "expected_worsen"):
        assert case[key] and all(1 <= x <= 39 for x in case[key])
    assert not set(case["expected_improve"]) & set(case["expected_worsen"])


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_expected_pair_matches_case_kind(case):
    """Normal cases must be answerable from verified data; expect_unverified
    cases must land exactly on withheld cells, expect_empty cases on cells the
    classic matrix leaves empty (both exercise the remapping path)."""
    import subprocess, sys
    p = subprocess.run(
        [sys.executable, str(score_mod.LOOKUP), "matrix",
         "--improve", ",".join(map(str, case["expected_improve"])),
         "--worsen", ",".join(map(str, case["expected_worsen"]))],
        capture_output=True, text=True, encoding="utf-8")
    out = json.loads(p.stdout)
    if case.get("expect_unverified"):
        assert out["pairs"] == [], f"{case['id']}: expected only withheld cells"
        assert any(w["code"] == "unverified_cell" for w in out["warnings"])
    elif case.get("expect_empty"):
        # the correct mapping lands on cells the classic matrix leaves empty
        assert out["pairs"] == [], f"{case['id']}: expected only empty cells"
        assert out["warnings"] == []
    else:
        assert out["ranking"], f"{case['id']}: expected pair gives no principles"


def fake_matrix(imp, wor):
    return {1, 2, 3}


CASES_2 = [
    {"id": "A", "expected_improve": [14], "expected_worsen": [1]},
    {"id": "B", "expected_improve": [9], "expected_worsen": [27]},
]


def test_score_hit_needs_both_sides_in_top3():
    results = {
        "A": {"improve": [5, 6, 14, 7], "worsen": [1], "principles_cited": [1]},   # 14 is 3rd: hit
        "B": {"improve": [9], "worsen": [4, 5, 6, 27], "principles_cited": []},    # 27 is 4th: miss
    }
    out = score_mod.score(CASES_2, results, matrix=fake_matrix)
    assert out["top3_hit_rate"] == 0.5
    assert out["improve_hit_rate"] == 1.0
    assert out["worsen_hit_rate"] == 0.5
    assert [r["hit"] for r in out["rows"]] == [True, False]


def test_score_counts_hallucinated_principles():
    results = {
        "A": {"improve": [14], "worsen": [1], "principles_cited": [1, 2, 39, 40]},
        "B": {"improve": [9], "worsen": [27], "principles_cited": [3]},
    }
    out = score_mod.score(CASES_2, results, matrix=fake_matrix)
    assert out["hallucinated_principles"] == 2
    assert out["rows"][0]["hallucinated_principles"] == [39, 40]


def test_score_oracle_error_counts_all_cited_as_hallucinated():
    results = {"A": {"improve": [14], "worsen": [14], "principles_cited": [1, 2]}}
    out = score_mod.score(CASES_2[:1], results, matrix=lambda i, w: None)
    assert out["hallucinated_principles"] == 2


def test_score_reports_missing_cases():
    out = score_mod.score(CASES_2, {"A": {"improve": [14], "worsen": [1]}}, matrix=fake_matrix)
    assert out["cases_missing"] == ["B"]
    assert out["cases_scored"] == 1


# ------------------------------------------------------- blind-run parser ---

spec2 = importlib.util.spec_from_file_location("run_blind", EVAL / "run_blind.py")
run_blind = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(run_blind)

ANSWER_KO = """## 파라미터 매핑
| 구분 | 파라미터 | 근거 |
| --- | --- | --- |
| 개선 | #9 속도 | 빠르기 |
| 개선 | #39 생산성 | 산출량 |
| 악화 | #29 제조 정밀도 | 자국 |
| 악화 | #9 속도 | 중복은 무시 |

## 추천 원리 (행렬 조회 결과)
| 1 | #10 사전 조치 | 2 |

## 적용 아이디어
### 원리 #10 사전 조치
- 아이디어
### 원리 #35 매개변수 변화
- 아이디어
### 원리 #10 사전 조치
"""

ANSWER_EN = """| Improve | #9 Speed | x |
| Worsen | #23 Loss of substance | y |
### Principle #35 Parameter changes
"""


def test_parse_answer_korean():
    r = run_blind.parse_answer(ANSWER_KO)
    assert r["improve"] == [9, 39]
    assert r["worsen"] == [29, 9]
    assert r["principles_cited"] == [10, 35]  # ranking-table rows are not "cited"
    assert r["ranking"] == [{"id": 10, "count": 2}]


def test_parse_answer_english():
    r = run_blind.parse_answer(ANSWER_EN)
    assert r == {"improve": [9], "worsen": [23], "principles_cited": [35], "ranking": [],
                 "stated_separations": []}


def test_parse_stream_extracts_tool_calls_and_result():
    lines = [
        json.dumps({"type": "system", "subtype": "init", "plugins": [{"name": "triz-solver"}], "slash_commands": []}),
        json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "triz-solver:triz-analysis"}},
            read_call("r1", "/x/skills/triz-analysis/data/matrix/row-01.json"),
            read_call("r2", "/x/skills/triz-analysis/SKILL.md")]}}),
        read_result("r1"), read_result("r2"),
        "not json",
        json.dumps({"type": "result", "result": "final text"}),
    ]
    info = run_blind.parse_stream(lines)
    assert info["plugin_loaded"] and info["skill_used"]
    assert info["file_reads"] == 1 and info["files_read"] == ["matrix/row-01.json"]  # SKILL.md is no data file
    assert info["text"] == "final text"


def test_parse_stream_command_alone_is_not_skill_use():
    """Invoking the /triz command without loading triz-analysis must not count."""
    lines = [json.dumps({"type": "system", "subtype": "init", "plugins": [{"name": "triz-solver"}], "slash_commands": []}),
             json.dumps({"type": "assistant", "message": {"content": [
                 {"type": "tool_use", "name": "Skill", "input": {"skill": "triz-solver:triz"}}]}}),
             json.dumps({"type": "result", "result": "x"})]
    assert run_blind.parse_stream(lines)["skill_used"] is False


def test_parse_stream_detects_missing_plugin_and_skill():
    lines = [json.dumps({"type": "system", "subtype": "init", "plugins": [], "slash_commands": ["help"]}),
             json.dumps({"type": "result", "result": "answer from memory"})]
    info = run_blind.parse_stream(lines)
    assert not info["plugin_loaded"] and not info["skill_used"] and info["file_reads"] == 0


def test_build_prompt_modes():
    case = {"problem": "P", "lang": "en"}
    assert run_blind.build_prompt(case, "command").startswith("/triz-solver:triz P")
    assert run_blind.build_prompt(case, "natural").startswith("P")


def test_build_prompt_neutral_suffix_does_not_claim_confirmation():
    case = {"problem": "P", "lang": "en", "suffix": "en_neutral"}
    prompt = run_blind.build_prompt(case, "command")
    assert "confirmed" not in prompt and prompt.endswith(run_blind.SUFFIX["en_neutral"])


def test_build_prompt_none_suffix_sends_plain_problem():
    case = {"problem": "P", "lang": "ko", "suffix": "none"}
    assert run_blind.build_prompt(case, "command") == "/triz-solver:triz P"


def test_parse_answer_labels_with_translation_and_bold_ids():
    text = ("| 개선 (Improving) | #12 Shape | a |\n"
            "| Improving | **#35 Adaptability or versatility** | b |\n"
            "| **Worsening** | **#36 Device complexity** | c |\n"
            "| 악화 (Worsen) | #32 제조 용이성 | d |\n"
            "| 개선 2순위 | #33 작동 용이성 | e |\n")
    got = run_blind.parse_answer(text)
    assert got["improve"] == [12, 35, 33] and got["worsen"] == [36, 32]


def test_run_command_is_isolated_from_host_tools():
    assert run_blind.ISOLATION[:2] == ["--tools", "Read,Skill"]   # no Bash: no oracle for the subject
    assert "--strict-mcp-config" in run_blind.ISOLATION


def test_parse_answer_empty():
    assert run_blind.parse_answer("") == {"improve": [], "worsen": [], "principles_cited": [],
                                          "ranking": [], "stated_separations": []}


def test_plugin_copy_excludes_expected_values(tmp_path):
    run_blind.make_plugin_copy(tmp_path)
    assert (tmp_path / "skills" / "triz-analysis" / "SKILL.md").exists()
    assert not (tmp_path / "tests").exists()
    assert not any(tmp_path.rglob("cases.yaml")) and not any(tmp_path.rglob("physical-cases.json"))
    # the copy holds plugin/ only: the data the subject reads, no root data/, tools/ or oracle
    assert (tmp_path / "skills" / "triz-analysis" / "data" / "matrix" / "row-01.json").exists()
    assert not any(tmp_path.rglob("lookup.py")) and not any(tmp_path.rglob("contradiction-matrix.json"))
    assert not (tmp_path / "data").exists() and not (tmp_path / "tools").exists()


# ------------------------------------------- unverified-cell disclosure ---

def test_parse_stream_collects_unverified_rows_from_read_row(tmp_path):
    data = tmp_path / "data"
    (data / "matrix").mkdir(parents=True)
    (data / "matrix" / "row-01.json").write_text(
        json.dumps({"cells": {"3": [1, 2]}, "unverified": [28], "improve": 1}), encoding="utf-8")
    lines = [json.dumps({"type": "assistant", "message": {"content": [
                 read_call("r1", "/p/skills/triz-analysis/data/matrix/row-01.json")]}}),
             read_result("r1")]
    info = run_blind.parse_stream(lines, data)
    assert info["unverified_rows"] == {"1": [28]}
    assert run_blind.saw_unverified(info["unverified_rows"], [1], [28, 3]) is True
    assert run_blind.saw_unverified(info["unverified_rows"], [1], [3]) is False
    assert run_blind.saw_unverified(info["unverified_rows"], [2], [28]) is False


def test_parse_stream_ignores_the_word_in_file_text():
    """Reading SKILL.md shows 'unverified' in prose; that is not a data warning."""
    lines = [json.dumps({"type": "assistant", "message": {"content": [
                 read_call("r1", "/p/skills/triz-analysis/SKILL.md")]}}),
             read_result("r1", text="162\t**`unverified` 키** ...")]
    assert run_blind.parse_stream(lines)["unverified_rows"] == {}


@pytest.mark.parametrize("text, expected", [
    ("이 조합은 검증된 데이터가 없어 조회할 수 없습니다.", True),
    ("Cell is unverified in the dataset, so I cannot look it up.", True),
    ("해당 셀은 미확정이라 원리를 추천하지 않습니다.", True),
    ("추천 원리는 #10, #35 입니다.", False),
])
def test_discloses_unverified(text, expected):
    assert run_blind.discloses_unverified(text) is expected


def test_score_unverified_disclosure_summary():
    cases = [{"id": "U1", "expected_improve": [1], "expected_worsen": [28], "expect_unverified": True},
             {"id": "U2", "expected_improve": [34], "expected_worsen": [1], "expect_unverified": True},
             {"id": "N1", "expected_improve": [9], "expected_worsen": [27]}]
    results = {
        "U1": {"improve": [1], "worsen": [28], "principles_cited": [], "saw_unverified": True, "disclosed": True},
        "U2": {"improve": [34], "worsen": [1], "principles_cited": [], "saw_unverified": True, "disclosed": False},
        "N1": {"improve": [9], "worsen": [27], "principles_cited": [], "saw_unverified": False, "disclosed": False},
    }
    out = score_mod.score(cases, results, matrix=fake_matrix)
    u = out["unverified"]
    assert u == {"cases_with_warning": 2, "disclosed": 1, "not_disclosed": ["U2"]}


# ------------------------------------------ principles in the files read ---

DATA = Path(__file__).resolve().parent.parent / "plugin" / "skills" / "triz-analysis" / "data"


def read_call(tool_id, path):
    return {"type": "tool_use", "id": tool_id, "name": "Read", "input": {"file_path": path}}


def read_result(tool_id, text="1\t{", is_error=False):
    """A Read tool result; the text may carry `cat -n` line numbers (it is not parsed)."""
    block = {"type": "tool_result", "tool_use_id": tool_id, "content": text}
    if is_error:
        block["is_error"] = True
    return json.dumps({"type": "user", "message": {"content": [block]}})


def read_stream(*reads, errors=()):
    """Fake stream: the agent reads each path (under a plugin copy path), one result each."""
    base = "/tmp/x/plugin/skills/triz-analysis/data/"
    calls = [read_call(f"t{i}", base + p) for i, p in enumerate(reads)]
    out = [json.dumps({"type": "assistant", "message": {"content": calls}})]
    out += [read_result(f"t{i}", is_error=p in errors) for i, p in enumerate(reads)]
    return out


def _row_principles(n):
    cells = json.loads((DATA / "matrix" / f"row-{n:02d}.json").read_text(encoding="utf-8"))["cells"]
    return {p for cell in cells.values() for p in cell}


def test_parse_stream_collects_principles_from_read_files():
    info = run_blind.parse_stream(read_stream("matrix/row-34.json", "principles/p-35.json"))
    assert info["file_reads"] == 2
    assert info["recommended_principles"] == sorted(_row_principles(34))
    assert info["returned_principles"] == sorted(_row_principles(34) | {35})


def test_read_principle_record_is_returned_not_recommended():
    info = run_blind.parse_stream(read_stream("principles/p-07.json"))
    assert info["returned_principles"] == [7] and info["recommended_principles"] == []


def test_unread_file_is_no_evidence():
    no_reads = run_blind.parse_stream([json.dumps({"type": "result", "result": "answer from memory"})])
    assert no_reads["returned_principles"] == [] and no_reads["file_reads"] == 0
    only_row = run_blind.parse_stream(read_stream("matrix/row-34.json"))
    assert only_row["files_read"] == ["matrix/row-34.json"]


def test_failed_read_and_non_data_paths_do_not_count():
    lines = read_stream("matrix/row-34.json", "principles/p-01.json", errors={"matrix/row-34.json"})
    lines += [json.dumps({"type": "assistant", "message": {"content": [
        read_call("z1", "/tmp/x/plugin/skills/triz-analysis/data/../../../../../etc/passwd"),
        read_call("z2", "/tmp/x/tools/contradiction-matrix.json"),
        read_call("z3", "/tmp/x/data/contradiction-matrix.json")]}}),
        read_result("z1"), read_result("z2"), read_result("z3")]
    info = run_blind.parse_stream(lines)
    assert info["files_read"] == ["principles/p-01.json"]


def test_read_without_result_does_not_count():
    lines = read_stream("principles/p-03.json")[:1]
    assert run_blind.parse_stream(lines)["file_reads"] == 0


def test_same_file_read_twice_counts_once():
    info = run_blind.parse_stream(read_stream("principles/p-03.json", "principles/p-03.json"))
    assert info["file_reads"] == 1


def test_data_file_kind():
    k = run_blind.data_file_kind
    assert k("/a/plugin/skills/triz-analysis/data/matrix/row-09.json") == ("row", 9)
    assert k("data/principles/p-40.json") == ("principle", 40)
    assert k("/a/data/separation-principles.json") == ("separation", 0)
    assert k("/a/data/parameters.json") == ("parameters", 0)
    assert k("/a/mydata/matrix/row-09.json") is None
    assert k("/a/data/matrix/row-9.json") is None
    assert k("/a/SKILL.md") is None


def test_hallucination_judged_by_files_read():
    """A principle from a file the agent read passes; one from an unread file is caught."""
    row = sorted(_row_principles(34))
    outside = next(p for p in range(1, 41) if p not in row)
    info = run_blind.parse_stream(read_stream("matrix/row-34.json"))
    cases = [{"id": "A", "expected_improve": [34], "expected_worsen": [1]}]
    results = {"A": {"improve": [34], "worsen": [1], "principles_cited": [row[0], outside],
                     "returned_principles": info["returned_principles"]}}
    out = score_mod.score(cases, results, matrix=lambda i, w: set())
    assert out["rows"][0]["hallucinated_principles"] == [outside]
    # reading the record of the missing principle makes the citation legitimate
    info2 = run_blind.parse_stream(read_stream("matrix/row-34.json", f"principles/p-{outside:02d}.json"))
    results["A"]["returned_principles"] = info2["returned_principles"]
    assert score_mod.score(cases, results, matrix=lambda i, w: set())["hallucinated_principles"] == 0


def test_score_prefers_principles_of_read_files_over_recomputation():
    cases = [{"id": "A", "expected_improve": [34], "expected_worsen": [1]}]
    results = {"A": {"improve": [34], "worsen": [1], "principles_cited": [2, 25, 99],
                     "returned_principles": [2, 25, 28]}}
    # recomputation from the reported candidates would allow nothing; observed output allows 2 and 25
    out = score_mod.score(cases, results, matrix=lambda i, w: set())
    assert out["rows"][0]["hallucinated_principles"] == [99]


def test_safe_name_handles_patent_ids_with_slashes():
    assert run_blind.safe_name("WO01/13760") == "WO01_13760"
    assert run_blind.safe_name("US4966257") == "US4966257"
    assert "/" not in run_blind.safe_name("../../etc/passwd")


# ------------------------------------------------------- physical cases ---

PHYSICAL = json.loads((EVAL / "physical-cases.json").read_text(encoding="utf-8"))["cases"]
SEPARATION_IDS = {"space", "time", "condition", "direction", "system"}


def test_physical_cases_are_well_formed():
    ids = [c["id"] for c in PHYSICAL]
    assert len(PHYSICAL) >= 10 and len(set(ids)) == len(ids)
    assert not set(ids) & {c["id"] for c in CASES}
    for c in PHYSICAL:
        assert c["lang"] in ("ko", "en") and c["problem"].strip()
        assert c["expected_separation"] and set(c["expected_separation"]) <= SEPARATION_IDS


def test_parse_stream_reads_separation_file():
    info = run_blind.parse_stream(read_stream("separation-principles.json", "principles/p-35.json"))
    sep = json.loads((DATA / "separation-principles.json").read_text(encoding="utf-8"))["separations"]
    assert info["separation_types_read"] == [x["id"] for x in sep]
    want = {p for x in sep for p in x["related_principles"]}
    assert info["recommended_principles"] == sorted(want)
    assert info["returned_principles"] == sorted(want | {35})
    assert run_blind.parse_stream(read_stream("principles/p-35.json"))["separation_types_read"] == []


def test_score_physical():
    cases = [{"id": "P1", "expected_separation": ["time"]},
             {"id": "P2", "expected_separation": ["space", "system"]},
             {"id": "P3", "expected_separation": ["direction"]},
             {"id": "P4", "expected_separation": ["time"]}]
    results = {
        "P1": {"stated_separations": ["time"], "separation_types_read": ["time", "space"],
               "principles_cited": [10], "recommended_principles": [9, 10]},
        "P2": {"stated_separations": ["condition", "system"], "separation_types_read": ["time"],
               "principles_cited": [1, 99], "recommended_principles": [1, 5]},
        "P3": {"stated_separations": [], "separation_types_read": [],
               "principles_cited": [4], "recommended_principles": []},
    }
    out = score_mod.score_physical(cases, results)
    assert out["cases_scored"] == 3 and out["cases_missing"] == ["P4"]
    assert [r["hit"] for r in out["rows"]] == [True, True, False]
    assert [r["first_hit"] for r in out["rows"]] == [True, False, False]
    assert out["hallucinated_principles"] == 2   # 99 in P2, 4 in P3 (nothing read)
    assert out["used_separation_rate"] == 2 / 3


def test_stated_separations_reads_chosen_rows():
    text = """## 분리 유형
| 유형 | P | 반대 P | 판단 |
| --- | --- | --- | --- |
| 공간 | 머리 위 | (같은 표면) | 겹침 → 제외 |
| 시간 | 비가 올 때 | 보관할 때 | 겹치지 않음 → **선택** |
| 관계·조건 | a | b | 제외 |
| 시스템 수준 | 전체 | 조각 | 겹치지 않음 → 선택 |
| Separation in direction | a | b | selected |
"""
    assert run_blind.stated_separations(text) == ["time", "system", "direction"]


def test_stated_separations_ignores_negated_choices():
    text = """| 유형 | P | 반대 P | 판단 |
| --- | --- | --- | --- |
| 공간 | a | b | 이번에는 선택하지 않음 |
| 시간 | a | b | 미선택 |
| 관계 | a | b | 선택 안 함 |
| 방향 | a | b | not selected |
| Separation in space | a | b | not adopted |
| Separation in time | a | b | unselected |
| Separation in relation | a | b | deselected |
| 시스템 수준 | a | b | 선택 |
"""
    assert run_blind.stated_separations(text) == ["system"]
    assert run_blind.stated_separations("| 시간 | a | b | 선택 안정적 |\n| 공간 | a | b | 선택 안 B |") == ["time", "space"]


def test_score_physical_hit_needs_a_stated_choice():
    """Reading the separation file is not a choice: only the answer's chosen types count."""
    cases = [{"id": "P1", "expected_separation": ["time"]}]
    results = {"P1": {"stated_separations": [], "separation_types_read": ["time", "space"],
                      "principles_cited": [], "recommended_principles": [9]}}
    out = score_mod.score_physical(cases, results)
    assert out["separation_hit_rate"] == 0 and out["used_separation_rate"] == 1


# ----------------------------------------------------------- ranking_match ---

def test_ranking_match_compares_first_n_of_oracle():
    oracle = [(35, 2), (8, 1), (14, 1), (15, 1)]
    rm = score_mod.ranking_match
    assert rm([{"id": 35, "count": 2}, {"id": 8, "count": 1}], oracle) is True
    assert rm([{"id": 35, "count": 2}, {"id": 14, "count": 1}], oracle) is False   # wrong order
    assert rm([{"id": 35, "count": 1}], oracle) is False                           # wrong count
    assert rm([], oracle) is None and rm([{"id": 35, "count": 2}], None) is None


def test_score_reports_ranking_match_rate():
    cases = [{"id": "A", "expected_improve": [9], "expected_worsen": [1]},
             {"id": "B", "expected_improve": [9], "expected_worsen": [27]},
             {"id": "C", "expected_improve": [9], "expected_worsen": [2]}]
    good = [{"id": 35, "count": 2}, {"id": 8, "count": 1}]
    bad = [{"id": 8, "count": 1}, {"id": 35, "count": 2}]
    base = {"principles_cited": [], "returned_principles": []}
    results = {"A": {"improve": [9], "worsen": [1], **base, "ranking": good},
               "B": {"improve": [9], "worsen": [27], **base, "ranking": bad},
               "C": {"improve": [9], "worsen": [2], **base}}
    out = score_mod.score(cases, results, matrix=fake_matrix, ranking=lambda i, w: [(35, 2), (8, 1)])
    assert [r["ranking_match"] for r in out["rows"]] == [True, False, None]
    assert out["ranking_checked"] == 2 and out["ranking_match_rate"] == 0.5
    assert out["ranking_unchecked"] == ["C"]


def test_parse_answer_ranking_feeds_ranking_match():
    text = "| 순위 | 원리 | 등장 횟수 |\n| --- | --- | --- |\n| 2 | #8 x | 1 |\n| 1 | #35 y | 2 |\n"
    assert run_blind.parse_answer(text)["ranking"] == [{"id": 35, "count": 2}, {"id": 8, "count": 1}]
