"""The story doc, its one cold read, and promotion from a fix (spec criteria 1, 11, 12 and 22).

The helpers here set up stories; test_approval.py and test_next.py use them too.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

DOC = """# Shoppers can save a basket

## What changes for you

Shoppers can save a basket and come back to it later.

## Why

People lose their basket when they leave.

## Done when

1. A saved basket is still there after signing out and back in.
2. The basket page says when it was saved.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SAVE | Save baskets | Baskets are stored | 1 | `src/basket.py` | `tests/test_basket.py` | none | no |
| SHOW | Show the saved time | The page shows the time | 2 | `src/page.py` | `tests/test_page.py` | SAVE | yes |

New moving parts: none

## Risks

Risks: none

## Notes
"""

# A stub reader: it records each call, prints claude-says.md (or "No findings."), and writes the
# file named in claude-touch, to stand for a reader that changes a file.
READER = """#!{python}
import io, json, os, pathlib, sys
here = pathlib.Path(__file__).resolve().parent
prompt = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8").read()  # UTF-8 whatever the code page
with open(here / "claude-calls.jsonl", "a", encoding="utf-8") as calls:
    calls.write(json.dumps({{"args": sys.argv[1:], "cwd": os.getcwd(), "prompt": prompt}}) + "\\n")
touch = here / "claude-touch"
if touch.exists():
    pathlib.Path(touch.read_text("utf-8")).write_text("changed by the reader\\n", encoding="utf-8")
said = here / "claude-says.md"
sys.stdout.write(said.read_text("utf-8") if said.exists() else "No findings.\\n")
"""


def setup(repo, kind="forge-source", keys=("SHOP",)):
    """forge.toml pinned to this Forge, a roadmap with these keys, and a stub claude reader."""
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "{kind}"\n')
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": key} for key in keys]}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up Forge")
    repo.git("push", "-q", "origin", "main")
    path = repo.bin / "claude"
    path.write_text(READER.format(python=sys.executable), encoding="utf-8")
    path.chmod(0o755)
    if os.name == "nt":
        (repo.bin / "claude.cmd").write_text(f'@"{sys.executable}" "%~dp0claude" %*\n', encoding="utf-8")


def worktree(repo, branch):
    """The folder a branch is checked out in, from git."""
    listing = repo.git("worktree", "list", "--porcelain")
    return Path(re.search(rf"^worktree (.+)\n[^\n]*\nbranch refs/heads/{re.escape(branch)}$",
                          listing, re.M)[1])


def new_story(repo, key, title="Shoppers can save a basket"):
    made = repo.forge("story", "new", key, title)
    assert made.returncode == 0, made.stderr
    return worktree(repo, f"story/{key}")


def ready(repo, key, doc=DOC):
    """A story with its doc written and read, with nothing to answer: ready for approval."""
    path = new_story(repo, key)
    (path / "plans" / f"{key}.md").write_text(doc, encoding="utf-8")
    read = repo.forge("read", key)
    assert read.returncode == 0, read.stderr
    return path


def hook(repo, payload):
    return repo.forge("hook", "approval", input=json.dumps(payload))


def claude_plan(claude_payload, text, cwd=None):
    """A successful ExitPlanMode showing this text as the plan."""
    return claude_payload("PostToolUse", "ExitPlanMode", {"plan": text},
                          {"plan": text, "isAgent": False, "filePath": "/plans/plan.md"}, cwd=cwd)


def codex_question(codex_payload, digest, answer="Approve plan", cwd=None):
    """A completed Codex approval question, as the approval contract asks it."""
    qid = f"approve_plan_{digest}"
    options = [{"label": label} for label in ("Approve plan", "Request changes", "Stop")]
    return codex_payload("PostToolUse", "request_user_input",
                         {"questions": [{"id": qid, "header": "Approve plan",
                                         "question": "Approve this plan?", "options": options}]},
                         {"answers": {qid: {"answers": [answer]}}}, cwd=cwd)


def test_1_what_changes_first(repo):
    setup(repo)
    shop = new_story(repo, "SHOP")
    template = (shop / "plans" / "SHOP.md").read_text(encoding="utf-8")
    assert template.startswith("# Shoppers can save a basket\n")
    assert re.findall(r"^## (.+)$", template, re.M)[0] == "What changes for you"

    # forge-pr-check fails a pull request carrying a story doc that breaks the rule.
    if "not built yet" in repo.forge("hook", "pr-check").stderr:
        pytest.skip("forge hook pr-check comes with CLOSE; its story-doc half runs once it lands")
    (shop / "plans" / "SHOP.md").write_text(DOC, encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    repo.git("add", "-A", cwd=shop)
    repo.git("commit", "-q", "-m", "Plan the story", cwd=shop)
    base = repo.git("rev-parse", "main")
    # ponytail: a task state stand-in so CLOSE's pr-check sees a branch Forge started.
    repo.git("checkout", "-q", "-B", "task-base", "story/SHOP")
    repo.write(".factory/stories/SHOP/tasks/SAVE.json",
               '{"branch": "task/SHOP-SAVE", "status": "working", "steps": []}\n')
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Start task SAVE")
    repo.git("checkout", "-q", "main")
    cases = {
        "SHOP.md": (DOC.replace("## What changes for you", "## Summary"),
                    'must start with "What changes for you"'),
        "SHOP.read.md": ("---\nreader: claude (opus)\nread_hash: 0\n---\n1. Too big\n",
                         "Finding 1 in plans/SHOP.read.md has no disposition"),
        "SHOP.md ": (DOC.replace("2. The basket page", "2. The shop page"),
                     "doesn't match its \"What changes for you\" and \"Done when\""),
    }
    for name, (text, problem) in cases.items():
        repo.git("checkout", "-q", "-B", "task/SHOP-SAVE", "task-base")
        repo.write(f"plans/{name.strip()}", text)
        repo.git("commit", "-q", "-am", "A pull request")
        checked = repo.forge("hook", "pr-check", "--base", base, "--head", "HEAD",
                             "--branch", "task/SHOP-SAVE")
        assert checked.returncode != 0 and problem in checked.stdout + checked.stderr
        repo.git("checkout", "-q", "main")


def test_11_story_doc_shape(repo):
    setup(repo)
    refused = repo.forge("story", "new", "NOPE", "Not planned")
    assert refused.returncode == 1
    assert refused.stderr == ("NOPE is not on the roadmap (plans/roadmap.json).\n"
                              "Next: forge roadmap add <spec>\n")

    shop = new_story(repo, "SHOP")
    malformed = {
        "the ID is used twice": ("| SHOW | Show the saved time", "| SAVE | Show the saved time",
                                 "Tasks row SAVE: the ID is used twice"),
        "an unknown After": ("| SAVE | yes |", "| MISSING | yes |",
                             "Tasks row SHOW: After MISSING is not a task in this table"),
        "a cycle": ("`tests/test_basket.py` | none |", "`tests/test_basket.py` | SHOW |",
                    "Tasks row SAVE: its After list makes a cycle (SAVE -> SHOW -> SAVE)"),
        "a Covers number": ("| 2 | `src/page.py`", "| 7 | `src/page.py`",
                            "Tasks row SHOW: Covers 7 is not a Done-when item"),
        "an empty Scope": ("`src/page.py`", "", "Tasks row SHOW: Scope is empty"),
        "no Risks": ("## Risks\n\nRisks: none\n", "", 'it has no "Risks" section'),
    }
    for old, new, problem in malformed.values():
        assert old in DOC
        (shop / "plans" / "SHOP.md").write_text(DOC.replace(old, new), encoding="utf-8")
        read = repo.forge("read", "SHOP")
        assert read.returncode == 1
        assert read.stderr == (f"plans/SHOP.md is malformed: {problem}.\n"
                               "Next: edit plans/SHOP.md, then run forge next\n")
    assert not (repo.bin / "claude-calls.jsonl").exists(), "a malformed doc was read"


def test_12_cold_read(repo, claude_payload, monkeypatch):
    monkeypatch.setenv("FORGE_NOW", "2026-09-25T10:00:00+00:00")
    setup(repo)
    shop = new_story(repo, "SHOP")
    doc, notes = shop / "plans" / "SHOP.md", shop / "plans" / "SHOP.read.md"
    doc.write_text(DOC, encoding="utf-8")

    def approve(text):
        return hook(repo, claude_plan(claude_payload, text))

    refused = approve(DOC)
    assert refused.returncode == 1
    assert refused.stderr == "plans/SHOP.md has no cold read.\nNext: forge read SHOP\n"

    # A read during which any file changed is discarded.
    (repo.bin / "claude-touch").write_text("scratch.txt", encoding="utf-8")
    discarded = repo.forge("read", "SHOP")
    assert discarded.returncode == 1
    assert discarded.stderr == ("A file changed during the cold read of plans/SHOP.md, so the read "
                                "was discarded.\nNext: git status, then forge read SHOP\n")
    assert not notes.exists()
    (repo.bin / "claude-touch").unlink()
    (shop / "scratch.txt").unlink()

    # The read runs read-only in the story's worktree and records who, when and the doc's hash.
    (repo.bin / "claude-says.md").write_text("1. Saving needs sign-in first.\n   Cut or defer: the "
                                             "saved time.\n", encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    call = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])
    assert call["args"][0] == "-p"
    assert call["args"][call["args"].index("--permission-mode") + 1] == "plan"
    assert Path(call["cwd"]).resolve() == shop.resolve()
    assert "Shoppers can save a basket and come back" in call["prompt"]
    read_hash = repo.git("hash-object", "plans/SHOP.md", cwd=shop)
    written = notes.read_text("utf-8")
    for fact in ("reader: claude (opus)", "read_at: 2026-09-25T10:00:00+00:00",
                 f"read_hash: {read_hash}", "1. Saving needs sign-in first."):
        assert fact in written
    again = repo.forge("read", "SHOP")
    assert again.returncode == 1
    assert again.stderr == ("plans/SHOP.md already has its one cold read.\n"
                            "Next: forge read SHOP --amended\n")

    # A finding with no disposition blocks approval.
    refused = approve(DOC)
    assert refused.stderr == ("Finding 1 in plans/SHOP.read.md has no disposition: cut, defer, or "
                              "keep with a reason.\nNext: edit plans/SHOP.read.md, then forge next\n")
    notes.write_text(written + "   Disposition: keep because shoppers asked for it\n", encoding="utf-8")

    # A doc changed after its read blocks approval until the amendment is recorded.
    amended = DOC.replace("People lose", "Shoppers lose")
    doc.write_text(amended, encoding="utf-8")
    refused = approve(amended)
    assert refused.stderr == ("plans/SHOP.md changed after its cold read.\n"
                              "Next: forge read SHOP --amended\n")
    assert repo.forge("read", "SHOP", "--amended").returncode == 0
    assert f"amended_hash: {repo.git('hash-object', 'plans/SHOP.md', cwd=shop)}" in notes.read_text("utf-8")
    doc.write_text(amended + "More notes.\n", encoding="utf-8")
    refused = approve(amended)
    assert refused.stderr == ("plans/SHOP.md changed after its recorded amendment.\n"
                              "Next: forge read SHOP --amended\n")
    doc.write_text(amended, encoding="utf-8")
    recorded = approve(amended)
    assert recorded.returncode == 0, recorded.stderr

    # A spec gets the same read, never on the default branch.
    repo.write("docs/specs/saved-baskets.md", "# Saved baskets\n\n## Why\n\nBaskets get lost.\n")
    refused = repo.forge("read", "saved-baskets")
    assert refused.returncode == 1 and refused.stderr.startswith("Forge changes nothing on main")
    (shop / "docs" / "specs").mkdir(parents=True)
    (shop / "docs" / "specs" / "saved-baskets.md").write_text("# Saved baskets\n", encoding="utf-8")
    assert repo.forge("read", "saved-baskets", cwd=shop).returncode == 0
    assert "read_hash: " in (shop / "docs" / "specs" / "saved-baskets.read.md").read_text("utf-8")


def test_22_promote(repo):
    setup(repo)
    fix = repo.path.parent / "repo-fix-keep-baskets"
    # ponytail: WORK's `forge fix start` isn't in this branch; this builds the same fix by hand.
    repo.git("worktree", "add", "-q", "-b", "fix/keep-baskets", str(fix), "main")
    state = fix / ".factory" / "fixes" / "keep-baskets.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"why": "Shoppers lose their basket when they leave",
                                 "done_when": "A basket survives signing out"}), encoding="utf-8")
    (fix / "basket.py").write_text("SAVED = True\n", encoding="utf-8")
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-q", "-m", "Keep baskets", cwd=fix)
    fixed = repo.git("rev-parse", "HEAD", cwd=fix)

    missing = repo.forge("story", "new", "BASKET", "--from-fix", "no-such-fix")
    assert missing.returncode == 1
    assert missing.stderr == "There is no fix named no-such-fix in a worktree here.\nNext: forge next\n"

    promoted = repo.forge("story", "new", "BASKET", "--from-fix", "keep-baskets")
    assert promoted.returncode == 0, promoted.stderr
    assert subprocess.run(["git", "merge-base", "--is-ancestor", fixed, "task/BASKET-KEEP-BASKETS"],
                          cwd=repo.path).returncode == 0
    assert repo.git("branch", "--list", "fix/keep-baskets") == ""
    doc = repo.git("show", "story/BASKET:plans/BASKET.md")
    assert "## Why\n\nShoppers lose their basket when they leave\n" in doc
    row = next(line for line in doc.splitlines() if line.startswith("| KEEP-BASKETS |"))
    assert "`basket.py`" in row and ".factory" not in row  # its Scope is what the fix changed
    roadmap = json.loads(repo.git("show", "story/BASKET:plans/roadmap.json"))
    assert [item["key"] for item in roadmap["items"]] == ["SHOP", "BASKET"]
    read = repo.forge("read", "BASKET")  # the promoted story's doc is well formed
    assert read.returncode == 0, read.stderr
