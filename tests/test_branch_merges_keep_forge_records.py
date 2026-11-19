"""Forge combines concurrent records rather than leaving Git's text conflict.

Test-audit: the contract is close completing a real divergent remote merge while
preserving both machines' observations. Existing divergence tests change product
files, never the same record on both sides. Git is real; only remote services
use the shared edge stubs. No production test seam is needed.
"""
import json

import pytest

from test_close import STORY_DOC, env  # noqa: F401
from test_worker import calls, install_claude

STORY = "record-merge-conflicts"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("local_round,remote_round", [(2, 3), (3, 2)])
@pytest.mark.parametrize("kind", ["fix", "task"])
def test_1_close_merges_records_with_the_higher_round_and_both_histories(env, local_round, remote_round, kind):
    repo = env.repo
    item, where = env.start_fix() if kind == "fix" else env.start_approved_task(STORY_DOC)
    branch = "fix/tidy-readme" if kind == "fix" else "task/SHOP-T1"
    rel = (f".factory/fixes/{item}.json" if kind == "fix" else
           ".factory/stories/SHOP/tasks/T1.json")
    state = json.loads((where / rel).read_text("utf-8"))
    state.update(round=1, steps=[{"step": "start", "at": "2026-11-18T10:00:00Z"}])
    env.commit(where, rel, json.dumps(state), "Start the first build round")
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-qm", "Install merge rules", cwd=where)
    base = repo.git("rev-parse", "HEAD", cwd=where)

    def review(title):
        return {"status": "clean", "commit": base, "dismissals": [], "findings": [{
            "priority": "P2", "title": title, "file": "app.py", "line": 1,
            "body": "Gain 1, Work 1, Harm 1. Keep this earlier observation."}]}

    remote = {**state, "round": remote_round, "steps": state["steps"] + [
        {"step": "review", "at": "2026-11-18T12:00:00Z"}],
        "review": review("Remote machine observation")}
    repo.git("push", "-q", "origin", branch, cwd=where)
    other = env.tmp / "other-machine"
    repo.git("clone", "-q", "--branch", branch,
             repo.git("remote", "get-url", "origin"), str(other))
    remote_head = env.commit(other, rel, json.dumps(remote), "Remote round")
    repo.git("push", "-q", "origin", branch, cwd=other)
    # The other machine continued from the shared base, without the remote round.
    local = {**state, "round": local_round, "steps": state["steps"] + [
        {"step": "review", "at": "2026-11-18T11:00:00Z"}],
        "review": review("Local machine observation")}
    env.commit(where, rel, json.dumps(local), "Local round")
    env.commit(where, "app.py", "print('hello again')\n", "Finish the greeting")
    # Local attributes and Git config do not travel to another machine.
    repo.git("config", "--unset", "merge.forge-record.driver", cwd=where)
    attributes = where / repo.git("rev-parse", "--git-path", "info/attributes", cwd=where)
    attributes.write_text("", encoding="utf-8")

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert f"Ready: {item}" in closed.stdout
    assert repo.git("diff", "--name-only", "--diff-filter=U", cwd=where) == ""
    repo.git("merge-base", "--is-ancestor", remote_head, "HEAD", cwd=where)
    merged = json.loads((where / rel).read_text("utf-8"))
    # Steps are the append-only Git record promised by the merge driver. The
    # worker command below proves which build round Forge actually resumes.
    assert all(step in merged["steps"] for step in local["steps"] + remote["steps"])
    assert "Remote machine observation" in env.prompt()
    assert "Local machine observation" in env.prompt()
    assert repo.git("status", "--porcelain", cwd=where) == ""
    log = install_claude(repo)
    resumed = repo.forge("work", item)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert "Fix round 4 on " in calls(log)[-1]["brief"]
