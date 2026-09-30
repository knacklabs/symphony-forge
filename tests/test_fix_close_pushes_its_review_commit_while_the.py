"""Close judges checks only on the head it pushed, and retries a push that fails.

Each test is named for the fix's Done-when item it proves.
"""
from __future__ import annotations

import stat

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
