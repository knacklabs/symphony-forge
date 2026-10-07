"""The owner's acceptance dismisses the latest findings and carries on after changes."""
import json
import shutil
from pathlib import Path

import pytest

from test_close import CLEAN, blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_close_waits_for_review_loop_choice import stopped
from test_hotspot_stop import saved, seed
from test_setup import _fresh_client

STORY = "the-owner-s-review-loop-choice-often-can"


def _stop_with_remaining_findings(env):
    seed(env, "src/a.py")
    item, where = env.start_fix()
    safe = finding("P1", "Already proved safe", "src/a.py")
    env.reviews(blocked(safe))
    assert env.close(item).returncode == 1
    assert env.close(item, "--dismiss", "1", "--because", "src/a.py:1 Proven safe").returncode == 0
    for number in (2, 3):
        env.commit(where, "app.py", f"print({number})\n")
        env.reviews(blocked(safe, finding("P1", "Remaining defect", "src/a.py"),
                            finding("P2", "Remaining advice", "src/a.py")))
        assert env.close(item).returncode == 1
    assert saved(where, item)["status"] == "hotspot"
    return item, where


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
@pytest.mark.parametrize("drift", ["code", "default", "records"])
def test_1_owner_accept_dismisses_every_remaining_finding_and_carries_on(env, previous, drift):
    # The amended contract makes the owner's choice authoritative even after changes.
    # Advice remains a finding; prior evidence dismissals keep their own reason.
    client(env, previous)
    item, where = _stop_with_remaining_findings(env)
    if drift == "default":
        env.repo.git("merge", "-q", "--ff-only", saved(where, item)["review"]["commit"])
        env.commit(env.repo.path, "NEWS.md", "Other work landed\n")
        env.repo.git("push", "-q", "origin", "main")
    elif drift == "code":
        env.commit(where, "app.py", "print('changed after review')\n")
    else:
        env.commit(where, ".factory/owner-note.txt", "Owner reviewed the remaining risk\n")
    before = len(env.review_calls())
    reason = "Owner accepts the remaining risk"
    result = env.close(item, "--resolve", "accept", "--reason", reason)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Ready:" in result.stdout
    assert len(env.review_calls()) == before
    shown = body(env.gh_calls("pr", "edit")[-1])
    assert "Already proved safe" in shown and "dismissed because src/a.py:1 Proven safe" in shown
    for title in ("Remaining defect", "Remaining advice"):
        line = next(line for line in shown.splitlines() if title in line)
        assert "dismissed because" in line and reason in line
    checked = env.repo.forge("hook", "pr-check", "--base", "origin/main", "--head", "HEAD",
                             "--branch", "fix/tidy-readme", cwd=where)
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_4_a_clean_review_clears_an_unanswered_stop(env):
    item, where = stopped(env)
    assert env.close(item, "--resolve", "narrow", "--reason", "Owner narrows the part").returncode == 0
    env.commit(where, "app.py", "print('fixed')\n")
    env.reviews(CLEAN)
    assert env.close(item).returncode == 0
    state = saved(where, item)
    # Earlier clients may retain an unanswered hold beside a later clean result.
    state["stop"] = {"file": "src/a.py"}
    env.commit(where, f".factory/fixes/{item}.json", json.dumps(state), "An old hold remains")
    result = env.close(item)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "stop" not in saved(where, item)
    assert len(env.review_calls()) == 4
    assert "--resolve" not in env.repo.forge("next").stdout


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption"])
def test_5_clients_receive_the_choice_and_clean_review_rules(repo, gh, tmp_path, previous):
    if previous:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        repo.git("checkout", "-q", "-b", "fix/choice-guide")
        version = repo.forge("--version").stdout.split()[-1]
        config = (repo.path / "forge.toml").read_text()
        repo.write("forge.toml", config.replace('version = "v1.2.2"', f'version = "{version}"'))
        folder, result = repo.path, repo.forge("sync")
    else:
        folder, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stderr
    for host in (".codex", ".claude"):
        text = " ".join((folder / host / "skills/forge/SKILL.md").read_text(encoding="utf-8").split())
        assert "every remaining finding" in text
        assert "owner's reason" in text
        assert "without checking whether code or the default branch changed" in text
        assert "A clean review clears an unanswered review-loop stop" in text
