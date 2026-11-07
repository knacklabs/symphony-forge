"""Accepting review findings publishes the final records in one branch update."""
import json
import stat
from pathlib import Path

import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_two_round_limit import client
from test_reviewchoice_skip import _default_moves_during_checks

STORY = "review-findings-split-from-close-pushes"


@pytest.mark.platform
@pytest.mark.parametrize("previous,moved", [(False, False), (True, False), (False, True)],
                         ids=["new", "earlier-adopted", "default-moves"])
def test_1_acceptance_publishes_once_after_final_review_records(env, previous, moved, tmp_path, monkeypatch):
    client(env, previous)
    item, where = env.start_fix()
    defect = finding("P1", "Greeting needs more detail")
    defect["body"] = "Gain 4, Work 1, Harm 2\nCase: normal use - Readers miss the detail."
    env.reviews(blocked(defect))
    stopped = env.close(item)
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "reached the round limit" in stopped.stderr
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)

    # Observe real remote branch updates only during acceptance, after the stopped review.
    updates = env.tmp / "accepted-heads"
    hook = Path(env.repo.git("remote", "get-url", "origin")) / "hooks" / "post-receive"
    hook.write_text(f'#!/bin/sh\ncat >> "{updates.as_posix()}"\n', encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)
    reason = "Keep this greeting for now"
    if moved:
        _default_moves_during_checks(env, tmp_path, where, False, monkeypatch)

    accepted = env.close(item, "--resolve", "accept", "--reason", reason)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert f"Ready: {item}" in accepted.stdout, accepted.stdout + accepted.stderr
    common = Path(env.repo.git("rev-parse", "--git-common-dir", cwd=where))
    if not common.is_absolute():
        common = where / common
    ready = common / "forge" / "ready" / f"{item}.json"
    assert json.loads(ready.read_text("utf-8"))["commit"] == env.repo.git("rev-parse", "HEAD", cwd=where)
    heads = [line.split()[1] for line in updates.read_text("utf-8").splitlines()
             if line.split()[2] == f"refs/heads/fix/{item}"]
    assert len(heads) == (2 if moved else 1), heads
    assert heads[-1] == env.repo.git("rev-parse", "HEAD", cwd=where)
    published = body(env.gh_calls("pr", "edit")[-1])
    assert "Review: clean, 1 dismissed" in published
    assert f"Human accepted the remaining finding: {reason}" in published
    for field in (".check_runs[]", ".statuses[]"):
        calls = env.gh_calls("api", "--paginate", "--jq", field)
        assert calls and all(any(f"/commits/{head}/" in call[-1] for head in heads) for call in calls)
        assert f"/commits/{heads[-1]}/" in calls[-1][-1]
