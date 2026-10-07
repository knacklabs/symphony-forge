"""The shipped coordinator guide explains the pane, strip and event turns.

This docs-only contract is checked at init and at sync after an earlier adoption,
for both hosts. Missing guidance is the regression; runtime behavior is owned by
the mod tests, not reimplemented here. No production test seam is needed.
"""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version

# Documentation delivery owns separate rules from the mod's runtime behavior.
STORY = "FORGE-MOD-1-GUIDE"


@pytest.fixture(params=["new", "previous adoption"])
def guide(repo, gh, tmp_path, request):
    if request.param == "new":
        client, result = _fresh_client(repo, gh, tmp_path)
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("checkout", "-q", "-b", "fix/mod-guide")
        config = (repo.path / "forge.toml").read_text(encoding="utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        client, result = repo.path, repo.forge("sync")
    assert result.returncode == 0, result.stdout + result.stderr
    skills = [(client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
              for host in (".claude", ".codex")]
    assert skills[0] == skills[1]
    return skills[0]


def section(guide, heading):
    return " ".join(guide.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0].split())


def test_1_guide_explains_core_and_pane_on_every_surface(guide):
    core = section(guide, "Claude Code plugin core")
    for instruction in ("forge board --json", "forge next --json", "forge lanes --json",
                        "every 10 seconds", "skipped", "20 seconds", "last good rows",
                        "Couldn't refresh:", "next tick", "never edits repo files",
                        "Upgrade Forge in this repo to use the board."):
        assert instruction in core, instruction
    pane = section(guide, "The pane and strip")
    for instruction in ("`/forge`", "144", "110", "80", "focus", "Desktop",
                        "timeline", "hover", "native buttons", "VS Code", "Remote Control",
                        "claude -p", "two lines per item", "Nothing in progress.",
                        "model", "findings", "unknown"):
        assert instruction in pane, instruction


def test_2_guide_explains_strip_and_safe_next_step(guide):
    pane = section(guide, "The pane and strip")
    for instruction in ("at most three lines", "Agents N/M", "Tests:", "two active items",
                        "+N more", "Build → Tests → Review → CI → Merge", "✓", "●", "✗",
                        "Tests –", "round", "total", "under 80 columns", "without lane data",
                        "empty prompt", "Claude is idle", "re-reads `forge next --json`",
                        "changed", "runs nothing", "as the user", "null",
                        "Couldn't check the next step:", "Couldn't run the next step:"):
        assert instruction in pane, instruction


def test_3_guide_explains_event_turns_and_coordinator_action(guide):
    events = section(guide, "Events")
    for instruction in ("review findings", "failed checks", "ready to merge", "worker questions",
                        "finished runs", "Progress only updates the pane", "act on it",
                        "own next command", "`forge next`", "occurrence ids", "completion time",
                        "head commit", "repo root and session id", "start or reload",
                        "one turn", "current turn ends", "failed submission", "next refresh",
                        "terminal or Desktop", "FORGE_WORKER=1", "never act on events",
                        "own repo", "Codex"):
        assert instruction in events, instruction
