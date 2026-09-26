"""The worker: forge work runs claude -p in the item's checkout with the whole brief."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from test_task import story

ROOT = Path(__file__).resolve().parents[1]


def install_claude(repo) -> Path:
    """Put the stub claude on PATH; its calls land in claude-calls.jsonl beside it."""
    stub = repo.bin / "claude"
    shutil.copy(ROOT / "tests" / "stubs" / "claude", stub)
    stub.chmod(0o755)
    if os.name == "nt":
        (repo.bin / "claude.cmd").write_text(f'@"{sys.executable}" "%~dp0claude" %*\n',
                                             encoding="utf-8")
    return repo.bin / "claude-calls.jsonl"


def calls(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []


def test_17_worker(repo, gh, monkeypatch):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nmodel = "sonnet"\ntest = "pytest -q"\n')
    # Tests already in the repo: one names a file in PAGE's Scope, the other doesn't, and one sits
    # next to its code.
    repo.write("tests/test_old_board.py", "from web import board\n")
    repo.write("tests/test_help_text.py", "from web import help\n")
    repo.write("web/test_board.py", "from web import board\n")
    repo.git("add", "forge.toml", "tests", "web")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    story(repo)

    refused = repo.forge("work", "BOARD/PAGE")
    assert refused.stderr == "BOARD/PAGE has no checkout here, so it hasn't been started.\nNext: forge next\n"
    assert repo.forge("task", "start", "BOARD/PAGE").returncode == 0
    folder = repo.path.parent / "repo-BOARD-PAGE"

    # First build: the story's sections, the task row, moving parts, risks, notes, standards.
    built = repo.forge("work", "BOARD/PAGE")
    assert built.returncode == 0, built.stderr
    assert "stub claude: built it" in built.stdout
    call = calls(log)[-1]
    assert call["args"][:5] == ["-p", "--model", "sonnet", "--permission-mode", "acceptEdits"]
    assert "Bash(git commit:*)" in call["args"] and "Bash(pytest -q:*)" in call["args"]
    assert Path(call["cwd"]).resolve() == folder.resolve()
    brief = call["brief"]
    for text in ("Board shows each story in plain English", "Anyone can open one page",
                 "People keep asking", "1. The board shows every story.",
                 "2. Each story has a state sentence.",
                 "| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |",
                 "| PAGE | The page | The board page | 1 | `web/board.py`, `web/templates/` |",
                 "New moving parts: none", "Risks: none", "Reuse the old board's look.",
                 "Functional check"):
        assert text in brief, text
    assert "Fix round" not in brief and "$" not in brief.split("## Standards")[0]
    standards = ROOT / "src" / "forge" / "standards.md"
    if standards.is_file():
        assert standards.read_text(encoding="utf-8").strip() in brief
    # The existing tests that name the Scope, and the shipped conventions the worker may read.
    assert ("Existing tests that name a file or folder in your Scope, which must still pass: "
            "`tests/test_old_board.py`, `web/test_board.py`.") in brief
    conventions = ROOT / "src" / "forge" / "templates" / "conventions"
    assert f"`{conventions}`" in brief and (conventions / "stack.md").is_file()
    assert call["args"][call["args"].index("--add-dir") + 1] == str(conventions)

    # The log sits in .git/forge/, where git never commits it.
    logs = list((repo.path / ".git" / "forge").glob("*.log"))
    assert [p.name for p in logs] == ["work-BOARD-PAGE.log"]
    assert "stub claude: built it" in logs[0].read_text(encoding="utf-8")
    assert repo.git("status", "--porcelain", "--ignored", cwd=folder) == ""

    # A fix round adds the open serious findings and the failing checks with their log tails.
    state_file = folder / ".factory" / "stories" / "BOARD" / "tasks" / "PAGE.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["review"] = {"commit": "0" * 40, "tree": "1" * 40, "status": "blocked",
                       "dismissals": [{"finding": 3, "because": "web/board.py:3 not real"}],
                       "findings": [
        {"priority": "P1", "title": "Archived stories are missing", "body": "Show them too.",
         "file": "web/board.py", "line": 12},
        {"priority": "P2", "title": "Simpler: drop the cache", "body": "Unneeded.",
         "file": "web/board.py", "line": 20},
        {"priority": "P0", "title": "Dismissed finding", "body": "Not real.", "file": "web/board.py",
         "line": 3}]}
    state_file.write_text(json.dumps(state), encoding="utf-8")
    gh.respond("pr", "checks", exit=1, stdout=json.dumps([
        {"name": "tests", "bucket": "fail", "link": "https://github.com/o/r/actions/runs/1/job/22"},
        {"name": "forge-pr-check", "bucket": "pass", "link": ""}]))
    gh.respond("run", "view", stdout="collected 3 items\nFAILED tests/test_board.py::test_page\n")
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    brief = calls(log)[-1]["brief"]
    assert "- P1 Archived stories are missing (web/board.py:12): Show them too." in brief
    assert "### tests" in brief and "FAILED tests/test_board.py::test_page" in brief
    for text in ("Simpler: drop the cache", "Dismissed finding", "forge-pr-check"):
        assert text not in brief, text
    assert ["run", "view", "--job", "22", "--log-failed"] in gh.calls()

    # A fix's brief holds its why and done-when lines.
    started = repo.forge("fix", "start", "Fix the login typo", "--done", "The login page says Log in")
    assert started.returncode == 0, started.stderr
    assert repo.forge("work", "fix-the-login-typo").returncode == 0
    brief = calls(log)[-1]["brief"]
    assert "Why: Fix the login typo" in brief and "Done when: The login page says Log in" in brief
    assert "Your task" not in brief

    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    failed = repo.forge("work", "fix-the-login-typo")
    assert failed.returncode == 1
    assert failed.stderr.startswith("The worker stopped with exit code 3; its log is ")
    assert failed.stderr.endswith("work-fix-the-login-typo.log.\nNext: forge work fix-the-login-typo\n")

    # Codex workers arrive with the warm-threads story.
    count = len(calls(log))
    repo.write("forge.toml", f'version = "{version}"\nworkers = "codex"\n')
    refused = repo.forge("work", "BOARD/PAGE")
    assert refused.returncode == 1
    assert refused.stderr == (
        "Codex workers come with the warm-threads story; v1 runs its workers on Claude Code.\n"
        'Next: set workers = "claude" in forge.toml, then forge work BOARD/PAGE\n')
    assert len(calls(log)) == count
