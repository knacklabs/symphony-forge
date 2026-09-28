"""The real Forge commands deliver the worker, reviewer, and close guidance."""

import pytest

from test_close import CLEAN, GREEN, env
from test_worker import calls, install_claude

STORY = "FIX-WORKERS-STOP-REVIEWS-CHASE-AND-HANDOFFS"


@pytest.fixture
def worker_brief(repo):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n'
               'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Clarify worker guidance", "--done", "Workers get clear rules")
    assert started.returncode == 0, started.stderr
    worked = repo.forge("work", "clarify-worker-guidance")
    assert worked.returncode == 0, worked.stderr
    return calls(log)[-1]["brief"]


def test_1_worker_can_update_tests_for_intended_behaviour_change(worker_brief):
    assert "update tests when Done-when deliberately changes behaviour" in worker_brief
    assert "old and new contract" in worker_brief
    assert "never weaken a test to hide a defect" in worker_brief


def test_2_worker_requires_default_branch_match_for_unrelated_failure(worker_brief):
    assert "unrelated only with a matching failure on the default branch" in worker_brief
    assert "otherwise treat it as unresolved" in worker_brief


def test_3_reviewer_requires_named_doc_tests(env):
    # The old reviewer exemption is replaced by the named-test requirement.
    item, _ = env.start_fix({"README.md": "# Hello\n"})
    env.reviews(CLEAN)
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    prompt = env.prompt()
    assert "Documentation-only changes still need every test named in the task's Tests column" in prompt
    assert "check claims,\ncommands and links" in prompt


def test_4_worker_cannot_count_reformatting_as_reduction(worker_brief):
    assert worker_brief.count("Joining lines or removing blank lines never counts as a reduction") == 2


def test_5_both_synced_skills_require_handoff_before_close(repo):
    repo.git("checkout", "-q", "-b", "fix/handoff")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "pytest -q"\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    for host in (".claude", ".codex"):
        skill = (repo.path / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
        assert "Read the worker's final handoff" in skill
        assert "resolve its stated blockers before `forge close`" in skill
