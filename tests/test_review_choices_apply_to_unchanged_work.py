"""Owner choices cover the item's reviewed work, not Forge's subsequent records."""
import json
import shutil
from pathlib import Path

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_close_waits_for_review_loop_choice import stopped
from test_hotspot_stop import saved, seed
from test_setup import _fresh_client

STORY = "the-owner-s-review-loop-choice-often-can"


def test_1_accept_uses_the_stopped_reviews_merge_base(env):
    item, where = stopped(env)
    reviewed = saved(where, item)["review"]["commit"]
    # The default branch advances through the reviewed work; our worktree is unchanged.
    env.repo.git("merge", "-q", "--ff-only", reviewed)
    env.commit(env.repo.path, "NEWS.md", "Other work landed\n")
    env.repo.git("push", "-q", "origin", "main")
    result = env.close(item, "--resolve", "accept", "--reason", "Owner accepts this work")
    assert result.returncode == 0, result.stdout + result.stderr
    assert saved(where, item)["stop"]["choice"] == "accept"
    assert len(env.review_calls()) == 3


def _records_stop(env):
    seed(env, "src/a.py")
    item, where = env.start_fix(done_when="The .factory/fixes/tidy-readme.json record describes the result")
    record = f".factory/fixes/{item}.json"
    for number in range(1, 4):
        env.commit(where, "app.py", f"print({number})\n")
        env.reviews(blocked(finding("P1", f"Round {number} defect", "src/a.py"),
                            finding("P1", "Record needs explanation", record)))
        assert env.close(item).returncode == 1
    assert saved(where, item)["status"] == "hotspot"
    return item, where


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
def test_2_accept_ignores_forge_records_even_when_named_or_cited(env, previous):
    client(env, previous)
    item, where = _records_stop(env)
    result = env.close(item, "--resolve", "accept", "--reason", "Owner accepts the records")
    assert result.returncode == 0, result.stdout + result.stderr
    result = env.close(item)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Ready:" in result.stdout
    assert len(env.review_calls()) == 3


@pytest.mark.parametrize("default_moved", [None, "absorbed", "base-only"],
                         ids=["records", "default-and-records", "reused-review"])
def test_3_dismiss_after_recording_a_choice_ignores_forge_records(env, default_moved):
    item, where = _records_stop(env)
    if default_moved:
        if default_moved == "absorbed":
            env.repo.git("merge", "-q", "--ff-only", saved(where, item)["review"]["commit"])
        env.commit(env.repo.path, "NEWS.md", "Other work landed\n")
        env.repo.git("push", "-q", "origin", "main")
    choice = env.close(item, "--resolve", "narrow", "--reason", "Owner keeps this small")
    assert choice.returncode == 0, choice.stderr
    result = env.close(item, "--dismiss", "1", "--because", "src/a.py:1 Proven safe",
                       "--dismiss", "2", "--because", "app.py:1 The result is implemented")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Ready:" in result.stdout
    assert len(env.review_calls()) == (4 if default_moved == "absorbed" else 3)
    again = env.close(item, "--dismiss", "1", "--because", "src/a.py:1 Proven safe")
    assert again.returncode == 0, again.stdout + again.stderr


def test_4_a_clean_review_clears_an_unanswered_stop(env):
    item, where = stopped(env)
    assert env.close(item, "--resolve", "narrow", "--reason", "Owner narrows the part").returncode == 0
    env.commit(where, "app.py", "print('fixed')\n")
    env.reviews(CLEAN)
    assert env.close(item).returncode == 0
    state = saved(where, item)
    # The recorded answer is history, not an unanswered hold.
    # An existing client may retain an unanswered hold beside its later clean result.
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
        client, result = repo.path, repo.forge("sync")
    else:
        client, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stderr
    for host in (".codex", ".claude"):
        text = " ".join((client / host / "skills/forge/SKILL.md").read_text().split())
        assert "review's merge base" in text
        assert "ignores files under `.factory/`" in text
        assert "A clean review clears an unanswered review-loop stop" in text
        assert "`--dismiss` after a recorded choice" in text
        assert "Reviews recorded before upgrading also keep valid choices" in text
