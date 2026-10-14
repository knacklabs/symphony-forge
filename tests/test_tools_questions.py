"""Code questions use the session's explorer instead of a separate Forge command."""
import shutil

import pytest

from conftest import ROOT, patient
from test_read_only_model_selection import MODELS
from test_subagent_roles import _settings, _synced

STORY = "FORGE-TOOLS-1"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_2_questions_use_the_session_explorer_in_new_and_earlier_adopted_repos(repo, adopted):
    # The old command and model override are deliberately removed; both hosts receive the
    # native explorer instruction and their own explore model when their files are synced.
    asked = repo.forge("ask", "x")
    assert asked.returncode == 1 and "invalid choice: 'ask'" in asked.stderr
    help_text = repo.forge("--help").stdout
    commands = help_text.split("commands:\n", 1)[1]
    assert "    handback " in commands and "    ask " not in commands

    if adopted:
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                                         repo.path, dirs_exist_ok=True))
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge files")
    synced = _synced(repo, MODELS)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".codex", ".claude"):
        skill = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
        row = next(line for line in skill.splitlines() if '"Ask about this code"' in line)
        assert "explorer" in row and "forge ask" not in skill
    assert _settings(repo.path, "explorer") == (
        ("gpt-6-luna", "high"), ("claude-haiku-5-5", "high"))
