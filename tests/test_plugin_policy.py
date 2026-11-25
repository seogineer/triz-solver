"""Directory policy tests for plugin/ (DESIGN.md 12.1, 12.5 d and e).

The checks are plain functions that take a plugin root, so negative tests can
run them on a fake tree and prove that they fail when they should.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugin"

ALLOWED_EXT = {".md", ".txt", ".json", ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
BINARY_EXT = IMAGE_EXT
FORBIDDEN_DIRS = {"scripts", "node_modules", ".claude"}
FORBIDDEN_NAMES = {"claude.md", "agents.md"}


def files_of(root):
    return sorted(p for p in Path(root).rglob("*") if p.is_file())


def check_extensions(root):
    errs = []
    for p in files_of(root):
        if p.suffix.lower() in ALLOWED_EXT:
            continue
        if p.name == "LICENSE" and p.suffix == "":
            continue
        errs.append(f"disallowed file type: {p.relative_to(root)}")
    return errs


def check_content(root):
    errs = []
    for p in files_of(root):
        rel = p.relative_to(root)
        data = p.read_bytes()
        if data.startswith(b"#!"):
            errs.append(f"shebang: {rel}")
        if p.suffix.lower() not in BINARY_EXT:  # images legitimately contain NUL bytes
            if b"\x00" in data:
                errs.append(f"NUL byte: {rel}")
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                errs.append(f"not UTF-8: {rel}")
        if p.name.lower() in FORBIDDEN_NAMES:
            errs.append(f"forbidden name: {rel}")
    return errs


def check_names(root):
    root = Path(root)
    errs = []
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if p.is_dir() and p.name in FORBIDDEN_DIRS:
            errs.append(f"forbidden directory: {rel}")
        if p.is_file() and "lookup" in p.name.lower():
            errs.append(f"lookup in file name: {rel}")
    return errs


def check_no_lookup_text(root):
    root = Path(root)
    errs = []
    targets = list(root.glob("skills/*/SKILL.md")) + list(root.glob("commands/**/*.md")) \
        + list(root.glob("skills/*/references/**/*.md"))
    for p in targets:
        if "lookup.py" in p.read_text(encoding="utf-8"):
            errs.append(f"lookup.py mentioned: {p.relative_to(root)}")
    return errs


def check_all(root):
    return check_extensions(root) + check_content(root) + check_names(root) + check_no_lookup_text(root)


# ------------------------------------------------------------ real tree ---

def test_plugin_has_files():
    assert (PLUGIN / "skills" / "triz-analysis" / "SKILL.md").is_file()
    assert (PLUGIN / "commands" / "triz.md").is_file()


def test_extensions_allowed():
    assert check_extensions(PLUGIN) == []


def test_no_shebang_nul_or_bad_encoding_or_claude_md():
    assert check_content(PLUGIN) == []


def test_no_forbidden_dirs_or_lookup_names():
    assert check_names(PLUGIN) == []


def test_no_lookup_py_in_prose():
    assert check_no_lookup_text(PLUGIN) == []


def test_plugin_dot_dir_has_only_manifest_and_images():
    d = PLUGIN / ".claude-plugin"
    names = {p.name for p in d.iterdir()}
    assert "plugin.json" in names
    for p in d.iterdir():
        assert p.is_file()
        assert p.name == "plugin.json" or p.suffix.lower() in IMAGE_EXT, p.name


def test_root_claude_plugin_has_only_marketplace():
    d = ROOT / ".claude-plugin"
    assert [p.name for p in d.iterdir()] == ["marketplace.json"]


def test_marketplace_points_to_plugin_dir_and_names_match():
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert market["plugins"][0]["source"] == "./plugin"
    assert market["plugins"][0]["name"] == manifest["name"]


def test_plugin_json_name():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "triz-solver"


def test_skill_md_size_and_frontmatter():
    text = (PLUGIN / "skills" / "triz-analysis" / "SKILL.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 500
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    name = re.search(r"^name:\s*(\S+)\s*$", m.group(1), re.M)
    assert name and name.group(1) == "triz-analysis"


# ------------------------------------------------------ negative tests ---

def make_clean_tree(root):
    (root / "skills" / "triz-analysis").mkdir(parents=True)
    (root / "commands").mkdir()
    (root / "skills" / "triz-analysis" / "SKILL.md").write_text("---\nname: x\n---\nbody\n", encoding="utf-8")
    (root / "commands" / "triz.md").write_text("cmd\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")


def test_checks_pass_on_clean_fake_tree(tmp_path):
    make_clean_tree(tmp_path)
    assert check_all(tmp_path) == []


def test_checks_catch_script_directory_and_lookup(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "skills" / "triz-analysis" / "scripts").mkdir()
    (tmp_path / "skills" / "triz-analysis" / "scripts" / "lookup.py").write_text("print(1)\n", encoding="utf-8")
    assert check_extensions(tmp_path)
    assert check_names(tmp_path)


def test_checks_catch_shebang_and_claude_md_and_prose(tmp_path):
    make_clean_tree(tmp_path)
    (tmp_path / "hook.json").write_text("#!/bin/sh\n", encoding="utf-8")
    (tmp_path / "Claude.MD").write_text("x\n", encoding="utf-8")
    (tmp_path / "skills" / "triz-analysis" / "SKILL.md").write_text("run lookup.py\n", encoding="utf-8")
    (tmp_path / "bin.json").write_bytes(b"a\x00b")
    (tmp_path / "bad.txt").write_bytes(b"\xff\xfe")
    errs = check_all(tmp_path)
    for needle in ("shebang: hook.json", "forbidden name: Claude.MD", "lookup.py mentioned",
                   "NUL byte: bin.json", "not UTF-8: bad.txt"):
        assert any(needle in e for e in errs), needle
