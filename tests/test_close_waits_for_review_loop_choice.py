"""A stopped review loop needs a recorded human choice before another close or land."""
STORY = "the-review-loop-stop-pauses-only-one-clo"

import shutil
from pathlib import Path

import pytest

from test_close import CLEAN, ROOT, STORY_DOC, blocked, env, finding  # noqa: F401
from test_fix_reviews_always_run_on_codex_so_a_team_wi import _claude_only
from test_hotspot_stop import rounds, saved, seed
from test_setup import _fresh_client

GUIDANCE = (
    "Ask the human to narrow the part, split it, or accept the remaining findings. "
    "Never re-run close or land past this stop until their choice is recorded."
)


def stopped(env, kind="fix"):
    seed(env, "src/a.py")
    item, where = env.start_approved_task(STORY_DOC) if kind == "task" else env.start_fix()
    result = rounds(env, item, where, ["src/a.py"] * 3)
    assert result.stderr.splitlines()[-2:] == [
        f"Review round 3 of {item} still finds serious problems in src/a.py, which an earlier "
        "round flagged too, so Forge stops sending the worker back. Ask the human "
        "to narrow the part, split it, or accept the remaining findings.",
        f'Next: forge close {item} --resolve <narrow|split|accept> --reason "<human\'s choice>"',
    ]
    return item, where


@pytest.mark.parametrize("kind", ["fix", "task", "fix-claude"])
def test_1_close_and_land_wait_for_the_human_choice(env, tmp_path, monkeypatch, kind):
    if kind == "fix-claude":
        _claude_only(tmp_path, monkeypatch, env.repo.bin,
                     (ROOT / "tests/stubs/autoreview").read_text())
    item, where = stopped(env, kind)
    for call in env.review_calls():
        assert call["args"][call["args"].index("--engine") + 1] == (
            "claude" if kind == "fix-claude" else "codex")
    before = len(env.review_calls())
    env.commit(where, "app.py", "print('changed after stop')\n")
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    env.reviews(CLEAN)
    for command in ("close", "land", "close", "land"):
        result = env.repo.forge(command, item)
        assert result.returncode == 1, result.stdout + result.stderr
        assert "narrow the part, split it, or accept the remaining findings" in result.stderr
        assert len(env.review_calls()) == before
        assert env.repo.git("rev-parse", "HEAD", cwd=where) == head
    result = env.repo.forge("next")
    assert "narrow the part, split it, or accept the remaining findings" in result.stdout
    assert "--resolve" in result.stdout


@pytest.mark.parametrize("choice", ["narrow", "split", "accept"])
def test_2_recorded_choice_unlocks_the_item(env, choice):
    item, where = stopped(env)
    before = len(env.review_calls())
    no_reason = env.close(item, "--resolve", choice)
    assert no_reason.returncode == 1
    assert no_reason.stderr == (
        "Record the human's choice only on a stopped review loop, with a non-empty "
        "--reason and no finding dismissals.\n"
        f'Next: forge close {item} --resolve <narrow|split|accept> --reason "<human\'s choice>"\n'
    )
    reason = "The human chose this after reading the remaining findings"
    result = env.close(item, "--resolve", choice, "--reason", reason)
    assert result.returncode == 0, result.stderr
    assert len(env.review_calls()) == before
    assert env.close(item, "--resolve", choice, "--reason", reason).returncode == 1
    # Acceptance covers the reviewed code only; narrowing/splitting still needs work.
    if choice == "accept":
        resumed = env.close(item)
        assert resumed.returncode == 0, resumed.stderr
        assert "Ready:" in resumed.stdout
        assert len(env.review_calls()) == before
        checked = env.repo.forge("hook", "pr-check", "--base", "origin/main",
                                 "--head", "HEAD", "--branch", "fix/tidy-readme", cwd=where)
        assert checked.returncode == 0, checked.stderr
        # An upstream edit to a reviewed file also ends acceptance, even if our diff is identical.
        env.commit(env.repo.path, "src/a.py", "print('upstream change')\n")
        env.repo.git("push", "-q", "origin", "main")
        env.reviews(blocked(finding("P1", "Round 3 defect", "src/a.py")))
        changed_base = env.close(item)
        assert changed_base.returncode == 1, changed_base.stdout + changed_base.stderr
        assert "Round 3 defect" in changed_base.stderr
        assert len(env.review_calls()) == before + 1
        before += 1
    else:
        resumed = env.close(item)
        assert resumed.returncode == 1
        assert "The review left serious findings open" in resumed.stderr
    env.commit(where, "app.py", "print('human choice implemented')\n")
    # Even the same finding must be reconsidered after an accepted version changes.
    title = "Round 3 defect" if choice == "accept" else "A new defect"
    env.reviews(blocked(finding("P1", title, "src/a.py")))
    resumed = env.close(item)
    assert resumed.returncode == 1
    assert title in resumed.stderr
    assert len(env.review_calls()) == before + 1


def test_3_acceptance_refuses_code_changed_since_the_stopped_review(env):
    item, where = stopped(env)
    env.commit(where, "app.py", "print('unreviewed')\n")
    result = env.close(item, "--resolve", "accept", "--reason", "Human accepts")
    assert result.returncode == 1
    assert result.stderr == (
        "The code or scope changed since the stopped review, so those findings "
        "cannot be accepted for this version.\n"
        f'Next: forge close {item} --resolve <narrow|split> --reason "<human\'s choice>"\n'
    )
    assert env.close(item).returncode == 1
    assert saved(where, item)["status"] == "hotspot"


@pytest.mark.parametrize("previous", [False, True], ids=["init", "upgrade-sync"])
def test_4_clients_receive_the_human_choice_instructions(repo, gh, tmp_path, previous):
    if previous:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        repo.git("checkout", "-q", "-b", "fix/stop-guide")
        version = repo.forge("--version").stdout.split()[-1]
        config = (repo.path / "forge.toml").read_text()
        repo.write("forge.toml", config.replace('version = "v1.2.2"', f'version = "{version}"'))
        client, result = repo.path, repo.forge("sync")
    else:
        client, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stderr
    for host in (".codex", ".claude"):
        text = (client / host / "skills/forge/SKILL.md").read_text()
        assert GUIDANCE in " ".join(text.split())
        assert '--resolve <narrow|split|accept> --reason "<human\'s choice>"' in text
