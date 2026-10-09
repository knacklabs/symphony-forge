"""Busy runners keep CI waiting; only absent runner activity warrants the warning.

Audit: real close, land and doctor commands consume GitHub run/job responses. The
regression is the old age-only refusal; elapsed time and GitHub alone are faked.
"""
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone

import pytest

from conftest import GH_STUB, ROOT, _install
from test_close import GREEN, env, run  # noqa: F401
from test_land import GH, ITEM, RUNS, URL, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401

STORY = "FIX-BUSY-NOT-MISSING"
ACTIONS = ["api", "--paginate", "--jq", ".workflow_runs[]"]
JOBS = ["api", "--paginate", "--jq", ".jobs[]"]


def _client(env, history):
    repo = env.repo
    config = (repo.path / "forge.toml").read_text("utf-8")
    if history == "upgraded":
        repo.git("switch", "-qc", "fix/upgrade-client")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
        env.commit(repo.path, ".factory/fixes/upgrade-client.json", json.dumps({
            "kind": "fix", "branch": "fix/upgrade-client", "why": "Upgrade Forge",
            "done_when": "The client uses this release", "status": "started"}))
    else:
        remote, client = env.tmp / "client.git", env.tmp / "client"
        repo.git("init", "-q", "--bare", "-b", "main", str(remote))
        repo.git("init", "-q", "-b", "main", str(client))
        repo.git("remote", "add", "origin", str(remote), cwd=client)
        env.gh.respond("api", stdout="{}")
        made = repo.forge("init", cwd=client)
        assert made.returncode == 0, made.stderr
        repo.path = client
        _install(repo.bin, "gh", GH.format(python=sys.executable, remote=remote.as_posix(), url=URL)
                 + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
        repo.git("switch", "-qc", "fix/configure-client")
        env.commit(repo.path, ".factory/fixes/configure-client.json", json.dumps({
            "kind": "fix", "branch": "fix/configure-client", "why": "Configure Forge",
            "done_when": "The client is configured", "status": "started"}))
    env.commit(repo.path, "forge.toml", config + 'runner = "ubuntu-latest"\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure this release")
    branch = repo.git("branch", "--show-current")
    repo.git("switch", "main")
    repo.git("merge", "--ff-only", branch)
    remote_url = repo.git("remote", "get-url", "origin")
    checkout = env.tmp / "configured-client"
    repo.git("clone", "-q", str(repo.path), str(checkout))
    repo.path = checkout
    repo.git("remote", "set-url", "origin", remote_url)
    repo.git("push", "-q", "origin", "main")
    env.checks(GREEN)


@pytest.mark.parametrize("history", ["new", "upgraded"])
@pytest.mark.parametrize("command,activity", [
    (command, activity) for command in ("close", "land", "land-merge", "doctor")
    for activity in ("busy", "missing")
] + [("doctor", activity) for activity in (
    "busy-running", "wrong-label", "old-job", "future-job", "unassigned")])
def test_ci_waits_for_busy_pool_and_names_missing_runner(clock, history, command, activity):
    env = clock
    _client(env, history)
    if command == "land-merge":
        _agent(env)
    where = _fix(env, "working", worked=True)
    # The other branch's workflow predates this queue, but one of its jobs starts
    # inside the queue window. Workflow creation time alone cannot detect activity.
    now = datetime.now(timezone.utc)
    queued_at = now - timedelta(minutes=6)
    queued = {"id": 101, "status": "queued", "head_sha": "current-head",
              "created_at": queued_at.isoformat(), "updated_at": queued_at.isoformat()}
    other = {"id": 102, "status": "completed", "head_sha": "0" * 40,
             "created_at": (now - timedelta(hours=1)).isoformat(), "updated_at": now.isoformat()}
    stub = env.repo.bin / "gh"
    stub.write_text(stub.read_text("utf-8").replace('        answer(out)', '''
        if args[:4] == ["api", "--paginate", "--jq", ".workflow_runs[]"]:
            out = out.replace("current-head", subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True,
                text=True, check=True).stdout.strip())
        answer(out)'''), "utf-8")
    job = {"status": "completed", "labels": ["ubuntu-latest"], "runner_id": 9,
           "started_at": (now - timedelta(minutes=4)).isoformat()}
    if activity == "busy-running":
        other.update(status="in_progress", updated_at=other["created_at"])
        job["status"] = "in_progress"
        # A running workflow's update time need not advance for each job start.
    elif activity == "wrong-label":
        job["labels"] = ["self-hosted"]
    elif activity == "old-job":
        job["started_at"] = (queued_at - timedelta(minutes=1)).isoformat()
    elif activity == "future-job":
        job["started_at"] = (now + timedelta(minutes=10)).isoformat()
    elif activity == "unassigned":
        job.update(status="queued", runner_id=0)
    _queue(env, ACTIONS, *_runs([queued, other]))
    _queue(env, JOBS + ["repos/{owner}/{repo}/actions/runs/101/jobs?per_page=100"], "")
    _queue(env, JOBS + ["repos/{owner}/{repo}/actions/runs/102/jobs?per_page=100"],
           *_runs([] if activity == "missing" else [job]))
    pending = [run("tests", None, "queued"), run("forge-pr-check")]
    looks = [pending, pending, GREEN]
    if command == "land-merge":
        looks.insert(0, GREEN)
    _queue(env, RUNS, *_runs(*looks))
    if command == "doctor":
        env.open_pr("")
        env.gh.respond("pr", "list", stdout=json.dumps([
            {"number": 7, "state": "OPEN", "headRefOid": env.repo.git("rev-parse", "HEAD", cwd=where)}]))
    done = env.repo.forge("land" if command == "land-merge" else command,
                          *([] if command == "doctor" else [ITEM]), cwd=where)
    output = done.stdout + done.stderr
    if not activity.startswith("busy"):
        assert done.returncode != 0, output
        assert "no runner has picked" in output, output
        assert 'runner = "ubuntu-latest"' in output and "forge.toml" in output, output
    else:
        assert "no runner has picked" not in output, output
        if command != "doctor":
            assert done.returncode == 0, output
            assert "clean review and green checks" in output, output
            assert len(env.gh_calls(*RUNS)) >= len(looks), output
