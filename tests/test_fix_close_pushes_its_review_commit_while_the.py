"""Close judges checks only on the head it pushed, and retries a push that fails.

Each test is named for the fix's Done-when item it proves.
"""
from __future__ import annotations

import stat
import sys
from pathlib import Path

from test_close import env, run  # noqa: F401 (env is a fixture)

STORY = "FIX-CLOSE-PUSHES-ITS-REVIEW-COMMIT-WHILE-THE"


def test_1_close_never_counts_a_check_result_from_an_earlier_head(env):
    item, where = env.start_fix()
    earlier = env.repo.git("rev-parse", "HEAD", cwd=where)
    # GitHub still answers with the previous head's runs: a red forge-pr-check among them.
    env.checks([dict(run("tests"), head_sha=earlier),
                dict(run("forge-pr-check", "failure"), head_sha=earlier)])

    done = env.close(item)

    assert done.returncode == 1
    assert "Checks failed" not in done.stdout + done.stderr
    assert ("The checks are not green yet: tests has not reported; "
            "forge-pr-check has not reported.") in done.stdout + done.stderr
    pushed = env.repo.git("ls-remote", "origin", "fix/tidy-readme").split()[0]
    assert pushed != earlier
    assert all(f"/commits/{pushed}/" in call[-1] for call in env.gh_calls("api")[-2:])


def test_2_close_retries_a_failed_push_before_giving_up(env):
    item, where = env.start_fix()
    # The remote refuses the first two pushes, as a flaky connection would.
    tries = env.tmp / "push-tries"
    hook = env.tmp / "remote.git" / "hooks" / "pre-receive"
    hook.write_text(f'#!/bin/sh\necho x >> "{tries.as_posix()}"\n'
                    f'test "$(wc -l < "{tries.as_posix()}")" -gt 2\n', "utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)

    done = env.close(item)

    assert done.returncode == 0, done.stderr
    assert "Ready: tidy-readme" in done.stdout
    assert len(tries.read_text("utf-8").splitlines()) == 3
    assert (env.repo.git("ls-remote", "origin", "fix/tidy-readme").split()[0]
            == env.repo.git("rev-parse", "HEAD", cwd=where))


def test_3_close_gives_up_after_the_bounded_push_attempts_with_growing_waits(env):
    item, _ = env.start_fix()
    # The remote refuses every push and records when each one arrived.
    tries = env.tmp / "push-times"
    hook = env.tmp / "remote.git" / "hooks" / "pre-receive"
    hook.write_text(f'#!/bin/sh\n"{Path(sys.executable).as_posix()}" -c '
                    f'"import time; print(time.time())" >> "{tries.as_posix()}"\n'
                    'echo "the remote is down" >&2\nexit 1\n', "utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)

    done = env.close(item)

    assert done.returncode == 1
    assert "git push failed" in done.stderr and "the remote is down" in done.stderr
    times = [float(line) for line in tries.read_text("utf-8").splitlines()]
    assert len(times) == 4
    gaps = [later - earlier for earlier, later in zip(times, times[1:])]
    # A normal close waits 1, 2 and 4 seconds between its four attempts. Each gap also holds the
    # push's own time, which on a loaded runner can swamp the waits, so each gap is checked against
    # its own planned wait instead of against the other gaps.
    assert gaps[0] >= 1 and gaps[1] >= 2 and gaps[2] >= 4, gaps
    assert not env.gh_calls("pr", "create")  # nothing was published after the failed push
