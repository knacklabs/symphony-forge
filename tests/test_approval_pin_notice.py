"""Approval notices tell the truth about recording and the release the client needs."""
import json
import shutil
from pathlib import Path

import pytest

from test_story import DOC, GRILL, claude_plan, hook, ready, setup, worktree
from test_setup import _fresh_client

STORY = "skipped-next"


def _waiting(repo, gh, tmp_path, adopted):
    if adopted:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Adopt on the earlier release")
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    # Fixture setup on main precedes the story; the real hook records on its story branch.
    repo.git("config", "core.hooksPath", str(tmp_path / "fixture-hooks"))
    setup(repo, kind="client")
    config = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", config + 'stage = "live"\n')
    repo.git("commit", "-q", "-am", "The client is live")
    repo.git("push", "-q", "origin", "main")
    shop = ready(repo, "SHOP")
    synced = repo.forge("sync", cwd=shop)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    return shop


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-on-v1.2.2"])
def test_1_pin_notice_waits_until_approval_is_recorded(repo, gh, tmp_path, claude_payload, adopted):
    shop = _waiting(repo, gh, tmp_path, adopted)
    (shop / "forge.toml").write_text(
        'version = "v0.0.1"\nrepo = "client"\nstage = "prototype"\n' + GRILL,
        encoding="utf-8")
    head = repo.git("rev-parse", "story/SHOP")
    payload = claude_plan(claude_payload, DOC)

    refused = hook(repo, payload)
    assert refused.returncode == 1
    assert "This client's sign-off isn't recorded yet" in refused.stderr
    assert "recorded anyway" not in refused.stderr
    assert "pins Forge" not in refused.stderr
    assert repo.git("rev-parse", "story/SHOP") == head

    repo.write("docs/decisions/0001-client-signoff.md", "---\nstatus: accepted\n---\n")
    repo.git("add", "-A")
    repo.git("-c", f"core.hooksPath={tmp_path / 'signoff-fixture-hooks'}", "commit", "-q", "-m",
             "The client signed off")
    repo.git("-c", f"core.hooksPath={tmp_path / 'signoff-fixture-hooks'}", "push", "-q", "origin", "main")
    recorded = hook(repo, payload)
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert "Recorded the approval" in recorded.stdout
    assert "pins Forge v0.0.1" in recorded.stderr
    assert "the approval is recorded anyway" in recorded.stderr
    assert repo.git("log", "-1", "--format=%s", "story/SHOP").startswith("Approve the plan")


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-on-v1.2.2"])
def test_2_newer_pin_notice_names_the_pinned_release(repo, gh, tmp_path, claude_payload, adopted):
    shop = _waiting(repo, gh, tmp_path, adopted)
    version = repo.forge("--version").stdout.split()[-1]
    config = (shop / "forge.toml").read_text("utf-8")
    (shop / "forge.toml").write_text(config.replace(version, "v99.0.0"), encoding="utf-8")

    recorded = hook(repo, claude_plan(claude_payload, DOC))
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert "Recorded the approval" in recorded.stdout
    assert "pins Forge v99.0.0" in recorded.stderr
    assert "Ask your agent to install Forge v99.0.0." in recorded.stderr
    assert f"upgrade {repo.path} to {version}" not in recorded.stderr
    assert repo.git("log", "-1", "--format=%s", "story/SHOP").startswith("Approve the plan")


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-on-v1.2.2"])
def test_3_blank_answers_count_as_unanswered(repo, gh, tmp_path, claude_payload, codex_payload, adopted):
    _waiting(repo, gh, tmp_path, adopted)
    started = repo.forge("fix", "start", "Answers", "--done", "Real answers count")
    assert started.returncode == 0, started.stdout + started.stderr
    fix = worktree(repo, "fix/answers")
    questions = {"questions": [{"id": "colour", "question": "Which colour?"}]}
    for make, tool, blank in (
        (claude_payload, "AskUserQuestion", " \t\n"),
        (codex_payload, "request_user_input", {"answers": [" \t\n"]}),
    ):
        result = hook(repo, make("PostToolUse", tool, questions,
                                 {"answers": {"colour": blank}}, cwd=fix))
        assert result.returncode == 0, result.stdout + result.stderr
    context = json.dumps(claude_payload("SessionStart", cwd=fix))
    shown = repo.forge("hook", "context", input=context, cwd=fix)
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "The fix answers (started): 0 human touches so far." in shown.stdout

    for make, tool, answer in (
        (claude_payload, "AskUserQuestion", "Blue"),
        (codex_payload, "request_user_input", {"answers": ["Blue"]}),
    ):
        result = hook(repo, make("PostToolUse", tool, questions,
                                 {"answers": {"colour": answer}}, cwd=fix))
        assert result.returncode == 0, result.stdout + result.stderr
    assert "The fix answers (started): 2 human touches so far." in repo.forge(
        "hook", "context", input=context, cwd=fix).stdout
