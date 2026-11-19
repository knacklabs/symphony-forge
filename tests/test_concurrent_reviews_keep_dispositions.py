"""Close keeps independent review findings and dismissals from both machines.

Test-audit: the contract is a real close after two clones commit reviews from the
same product head. A later review that repeats a blocking finding must still block,
and dismissals for separate findings must both reach the next review prompt. Existing
record-merge tests cover steps and round selection, not review-settlement semantics.
Git is real; only GitHub and Autoreview are stubbed at their edges. No production seam
is needed.
"""
import json

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401

STORY = "record-merge-conflicts"
pytestmark = pytest.mark.platform


def _result(commit, findings=(), dismissals=(), review_id="review"):
    saved = [{"title": entry["title"], "priority": entry["priority"], "body": entry["body"],
              "file": entry["code_location"]["file_path"], "line": entry["code_location"]["line"]}
             for entry in findings]
    dismissed = {entry["finding"] for entry in dismissals}
    opened = any(entry["priority"] in ("P0", "P1") and number not in dismissed
                 for number, entry in enumerate(saved, 1))
    return {"id": review_id, "status": "blocked" if opened else "clean", "commit": commit,
            "findings": saved, "dismissals": list(dismissals)}


def _diverge(env, remote_review, local_review):
    repo = env.repo
    item, where = env.start_fix()
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "--allow-empty", "-q", "-m", "Install record merge rules", cwd=where)
    branch = "fix/tidy-readme"
    repo.git("push", "-q", "origin", branch, cwd=where)
    base = repo.git("rev-parse", "HEAD", cwd=where)
    rel = f".factory/fixes/{item}.json"
    remote = env.tmp / "review-machine"
    repo.git("clone", "-q", "--branch", branch, repo.git("remote", "get-url", "origin"), str(remote))

    remote_state = json.loads((remote / rel).read_text("utf-8"))
    remote_state["review"] = remote_review(base)
    env.commit(remote, rel, json.dumps(remote_state, sort_keys=True), "Review on the other machine")
    repo.git("push", "-q", "origin", branch, cwd=remote)

    local_state = json.loads((where / rel).read_text("utf-8"))
    local_state["review"] = local_review(base)
    env.commit(where, rel, json.dumps(local_state, sort_keys=True), "Review on this machine")
    env.commit(where, "app.py", "print('hello again')\n", "Continue the fix")

    # Local Git attributes and configuration do not travel to another machine.
    repo.git("config", "--unset", "merge.forge-record.driver", cwd=where)
    attributes = where / repo.git("rev-parse", "--git-path", "info/attributes", cwd=where)
    attributes.write_text("", encoding="utf-8")
    return item, where


@pytest.mark.parametrize("blocking_side", ["local", "remote"])
def test_3_close_keeps_a_blocking_finding_from_an_independent_review(env, blocking_side):
    issue = finding("P1", "The greeting check is missing")
    blocked_review = lambda commit: _result(commit, [issue], review_id="blocked-review")
    clean_review = lambda commit: _result(commit, review_id="clean-review")
    item, _ = _diverge(
        env,
        blocked_review if blocking_side == "remote" else clean_review,
        blocked_review if blocking_side == "local" else clean_review,
    )
    env.reviews(blocked(issue))

    closed = env.close(item)

    assert closed.returncode != 0, closed.stdout + closed.stderr
    assert "The greeting check is missing" in closed.stdout
    assert "Ready:" not in closed.stdout
    assert "The greeting check is missing" in env.prompt()


def test_9_close_keeps_dismissals_for_separate_findings_from_both_machines(env):
    first = finding("P1", "The first earlier observation")
    second = finding("P1", "The second earlier observation")
    dismiss_first = {"finding": 1, "because": "app.py:1 first observation is already handled"}
    dismiss_second = {"finding": 2, "because": "app.py:2 second observation is already handled"}

    item, _ = _diverge(
        env,
        lambda commit: _result(commit, [first, second], [dismiss_first], "remote-review"),
        lambda commit: _result(commit, [first, second], [dismiss_second], "local-review"),
    )
    env.reviews(CLEAN)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    prompt = env.prompt()
    assert dismiss_first["because"] in prompt
    assert dismiss_second["because"] in prompt
