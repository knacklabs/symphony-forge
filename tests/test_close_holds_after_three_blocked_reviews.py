"""Close keeps both review-loop holds and their owner choices after init or upgrade."""
STORY = "any-file-hold"

import shutil
from pathlib import Path

import pytest

from test_close import CLEAN, GREEN, blocked, env, finding  # noqa: F401
from test_setup import _fresh_client
from test_worker import calls, install_claude


RULE = (
    "Close holds the fourth review after three consecutive rounds blocked by serious findings, "
    "whatever files they were in. The existing same-file stop still applies from the third round."
)
PATHS = ["docs/product/BRIEF.md", "docs/specs/README.md", "forge.toml"]


def client_item(env, tmp_path, previous):
    if previous:
        # Land the earlier release's plain-text adoption fixture before it installs git hooks.
        for path in PATHS[:-1]:
            env.repo.write(path, "# Existing client document\n")
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        env.repo.path, dirs_exist_ok=True)
        env.repo.git("add", "-A")
        env.repo.git("commit", "-q", "-m", "Client adopted on an earlier release")
        env.repo.git("push", "-q", "origin", "main")
    else:
        client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        env.repo.path = client
    item, where = env.start_fix()
    if previous:
        version = env.repo.forge("--version").stdout.split()[-1]
        config = (where / "forge.toml").read_text("utf-8")
        env.commit(where, "forge.toml", config.replace('version = "v1.2.2"',
                                                       f'version = "{version}"'))
        synced = env.repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stderr
        env.commit(where, "app.py", "print('upgraded client')\n")
    # Init's branch-protection responses must not stand in for the actual CI responses.
    env.checks(GREEN)
    return item, where


@pytest.mark.parametrize("previous,same_file,choice", [
    (False, False, "narrow"), (True, False, "split"),
    (False, False, "accept"), (True, False, "accept"),
    (False, True, "narrow"), (True, True, "split"),
], ids=["init-any-narrow", "upgrade-any-split", "init-any-accept", "upgrade-any-accept",
        "init-same-narrow", "upgrade-same-split"])
def test_1_close_holds_after_three_blocked_reviews_before_a_fourth_reviewer(
        env, tmp_path, previous, same_file, choice):
    item, where = client_item(env, tmp_path, previous)
    paths = [PATHS[0]] * 3 if same_file else PATHS
    for number, path in enumerate(paths, 1):
        env.commit(where, "app.py", f"print('round {number}')\n")
        env.reviews(blocked(finding("P1", f"Round {number} defect", path)))
        result = env.close(item)
        assert result.returncode == 1, result.stdout + result.stderr
        if number < 3 or not same_file:
            assert "The review left serious findings open:" in result.stderr
        assert len(env.review_calls()) == number
    round_number = 3 if same_file else 4
    if not same_file:
        # Unlike the existing same-file stop, this hold refuses before spending a fourth review.
        env.commit(where, "app.py", "print('attempt fourth review')\n")
        env.reviews(CLEAN)
        result = env.close(item)
    assert result.stderr.splitlines()[-2:] == [
        f"Review round {round_number} of {item} still finds serious problems in {paths[-1]}, "
        "which an earlier round flagged too, so Forge stops sending the worker back. "
        "Ask the human to narrow the part, split it, or accept the remaining findings.",
        f'Next: forge close {item} --resolve <narrow|split|accept> --reason "<human\'s choice>"',
    ]
    assert len(env.review_calls()) == 3
    next_step = env.repo.forge("next")
    assert next_step.returncode == 0, next_step.stderr
    assert "narrow the part, split it, or accept the remaining findings" in next_step.stdout
    assert f'forge close {item} --resolve <narrow|split|accept>' in next_step.stdout
    for command in ("close", "land"):
        waiting = env.repo.forge(command, item)
        assert waiting.returncode == 1, waiting.stdout + waiting.stderr
        assert waiting.stderr.splitlines()[-2:] == result.stderr.splitlines()[-2:]
        assert len(env.review_calls()) == 3
    reason = "The human chose this after reading the remaining findings"
    chosen = env.close(item, "--resolve", choice, "--reason", reason)
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    assert len(env.review_calls()) == 3
    if choice == "accept":
        assert "Ready:" in chosen.stdout
    else:
        assert f"{choice.capitalize()} the part as agreed" in chosen.stdout
        env.commit(where, "app.py", "print('human choice implemented')\n")
        env.reviews(CLEAN)
        resumed = env.close(item)
        assert resumed.returncode == 0, resumed.stdout + resumed.stderr
        assert "Ready:" in resumed.stdout
        assert len(env.review_calls()) == 4
    for host in (".codex", ".claude"):
        guide = (where / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert RULE in " ".join(guide.split())


def test_2_fresh_and_resumed_workers_receive_the_review_loop_hold_rule(env):
    item, _ = env.start_fix()
    log = install_claude(env.repo)
    for _ in range(2):
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        assert RULE in " ".join(calls(log)[-1]["brief"].split())
    assert "--resume" in calls(log)[-1]["args"]


@pytest.mark.parametrize("interruption", ["clean", "dismissed"])
def test_3_only_consecutive_serious_blocked_reviews_hold_the_next_reviewer(env, interruption):
    # New branch files avoid the separate existing same-file hotspot rule.
    item, where = env.start_fix(changes={"app.py": "print('work')\n"})
    for number in range(1, 6):
        env.commit(where, "app.py", f"print('round {number}')\n")
        clean = number == 5 or number == 2 and interruption == "clean"
        env.reviews(CLEAN if clean else blocked(
            finding("P1", f"Round {number} defect", "app.py")))
        result = env.close(item)
        assert result.returncode == (0 if clean else 1), result.stdout + result.stderr
        assert len(env.review_calls()) == number
        if number == 2 and interruption == "dismissed":
            dismissed = env.close(item, "--dismiss", "1", "--because", "app.py:1 Proven safe")
            assert dismissed.returncode == 0, dismissed.stdout + dismissed.stderr
            assert len(env.review_calls()) == number
    assert "Ready:" in result.stdout
