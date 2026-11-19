"""Forge combines concurrent records rather than leaving Git's text conflict.

Test-audit: the contract is close completing a real divergent remote merge while
preserving both machines' observations. Existing divergence tests change product
files, never the same record on both sides. Git is real; only remote services
use the shared edge stubs. No production test seam is needed.
"""
import json

import pytest

from test_close import env  # noqa: F401

STORY = "record-merge-conflicts"


@pytest.mark.parametrize("local_round,remote_round", [(2, 3), (3, 2)])
def test_1_close_merges_records_with_the_higher_round_and_both_histories(env, local_round, remote_round):
    repo = env.repo
    item, where = env.start_fix(round=1, steps=[{"step": "start", "at": "2026-11-18T10:00:00Z"}])
    extra_records = (".factory/stories/RECORD/story.json", ".factory/stories/RECORD/tasks/BUILD.json")
    for rel in extra_records:
        env.commit(where, rel, json.dumps({"round": 1, "steps": []}), "Shared record")
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-qm", "Install merge rules", cwd=where)
    base = repo.git("rev-parse", "HEAD", cwd=where)
    rel = f".factory/fixes/{item}.json"
    state = json.loads((where / rel).read_text("utf-8"))

    def review(title):
        return {"status": "clean", "commit": base, "dismissals": [], "findings": [{
            "priority": "P2", "title": title, "file": "app.py", "line": 1,
            "body": "Gain 1, Work 1, Harm 1. Keep this earlier observation."}]}

    remote = {**state, "round": remote_round, "steps": state["steps"] + [
        {"step": "review", "at": "2026-11-18T12:00:00Z"}],
        "review": review("Remote machine observation")}
    repo.git("push", "-q", "origin", "fix/tidy-readme", cwd=where)
    other = env.tmp / "other-machine"
    repo.git("clone", "-q", "--branch", "fix/tidy-readme",
             repo.git("remote", "get-url", "origin"), str(other))
    for path in extra_records:
        (other / path).write_text(json.dumps(remote), encoding="utf-8")
    remote_head = env.commit(other, rel, json.dumps(remote), "Remote round")
    repo.git("push", "-q", "origin", "fix/tidy-readme", cwd=other)
    # The other machine continued from the shared base, without the remote round.
    local = {**state, "round": local_round, "steps": state["steps"] + [
        {"step": "review", "at": "2026-11-18T11:00:00Z"}],
        "review": review("Local machine observation")}
    for path in extra_records:
        (where / path).write_text(json.dumps(local), encoding="utf-8")
    env.commit(where, rel, json.dumps(local), "Local round")
    env.commit(where, "app.py", "print('hello again')\n", "Finish the greeting")
    # Local attributes and Git config do not travel to another machine.
    repo.git("config", "--unset", "merge.forge-record.driver", cwd=where)
    attributes = where / repo.git("rev-parse", "--git-path", "info/attributes", cwd=where)
    attributes.write_text("", encoding="utf-8")

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready: tidy-readme" in closed.stdout
    assert repo.git("diff", "--name-only", "--diff-filter=U", cwd=where) == ""
    repo.git("merge-base", "--is-ancestor", remote_head, "HEAD", cwd=where)
    merged = json.loads((where / rel).read_text("utf-8"))
    assert merged["round"] == 3
    assert all(step in merged["steps"] for step in local["steps"] + remote["steps"])
    assert "Remote machine observation" in env.prompt()
    assert "Local machine observation" in env.prompt()
    for path in extra_records:
        record = json.loads((where / path).read_text("utf-8"))
        assert record["round"] == 3
        assert record["review"] == (remote if remote_round > local_round else local)["review"]
        assert all(step in record["steps"] for step in local["steps"] + remote["steps"])
    assert repo.git("status", "--porcelain", cwd=where) == ""
