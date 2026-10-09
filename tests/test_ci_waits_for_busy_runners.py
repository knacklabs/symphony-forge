"""Queued checks keep CI waiting; doctor diagnoses a week without matching runner activity.

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


def _client(env, history, runner):
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
    env.commit(repo.path, "forge.toml", config + f"runner = {json.dumps(runner)}\n")
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
    "busy-running", "busy-rerun", "busy-case", "busy-days-ago", "missing-case", "wrong-label",
    "old-job", "future-job", "unassigned")])
def test_1_ci_waits_for_busy_pool_and_names_missing_runner(clock, history, command, activity):
    env = clock
    runner = "GPU" if activity in ("busy-case", "missing-case") else "ubuntu-latest"
    _client(env, history, runner)
    if command == "land-merge":
        _agent(env)
    where = _fix(env, "working", worked=True)
    # An old queued run cannot diagnose a missing runner if a matching job from
    # another branch has run in the last week, including an earlier workflow attempt.
    now = datetime.now(timezone.utc)
    queued_at = now - timedelta(days=8)
    queued = {"id": 101, "status": "queued", "head_sha": "current-head",
              "created_at": queued_at.isoformat(), "updated_at": queued_at.isoformat()}
    other = {"id": 102, "status": "completed", "head_sha": "0" * 40,
             "created_at": (now - timedelta(hours=1)).isoformat(), "updated_at": now.isoformat()}
    stub = env.repo.bin / "gh"
    stub.write_text(stub.read_text("utf-8").replace('        answer(out)', '''
        if args[:4] == ["api", "--paginate", "--jq", ".workflow_runs[]"]:
            out = out.replace("current-head", heads().get("refs/heads/fix/tidy-readme") or subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True,
                text=True, check=True).stdout.strip())
        answer(out)'''), "utf-8")
    job = {"status": "completed", "labels": ["ubuntu-latest"], "runner_id": 9,
           "started_at": (now - timedelta(minutes=4)).isoformat()}
    if activity == "busy-running":
        other.update(status="in_progress", updated_at=other["created_at"])
        job["status"] = "in_progress"
        # A running workflow's update time need not advance for each job start.
    elif activity == "busy-rerun":
        other.update(status="queued", run_attempt=2)
    elif activity in ("busy-case", "missing-case"):
        job["labels"] = ["gpu" if activity == "busy-case" else "other"]
    elif activity == "wrong-label":
        job["labels"] = ["self-hosted"]
    elif activity == "busy-days-ago":
        job["started_at"] = (now - timedelta(days=6)).isoformat()
    elif activity == "old-job":
        job["started_at"] = (now - timedelta(days=7, minutes=1)).isoformat()
    elif activity == "future-job":
        job["started_at"] = (now + timedelta(minutes=10)).isoformat()
    elif activity == "unassigned":
        job.update(status="queued", runner_id=0)
    _queue(env, ACTIONS, *_runs([queued, other]))
    for run_id, jobs in ((101, []), (102, [] if activity == "missing" else [job])):
        endpoint = f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs"
        # GitHub defaults to the latest attempt; a queued rerun hides older jobs.
        _queue(env, JOBS + [endpoint + "?per_page=100"],
               *_runs([] if activity == "busy-rerun" else jobs))
        _queue(env, JOBS + [endpoint + "?filter=all"], *_runs(jobs))
    pending = [run("tests", None, "queued"), run("forge-pr-check")]
    looks = [pending, pending, GREEN]
    if command == "land-merge":
        looks.insert(0, GREEN)
    _queue(env, RUNS, *_runs(*looks))
    if command == "doctor":
        env.open_pr("")
        env.gh.respond("pr", "list", stdout=json.dumps([
            {"number": 7, "state": "OPEN", "headRefOid": env.repo.git("rev-parse", "HEAD", cwd=where)}]))
    # Windows cannot remove the worktree while the invoking process uses it as cwd.
    done = env.repo.forge("land" if command == "land-merge" else command,
                          *([] if command == "doctor" else [ITEM]),
                          cwd=env.repo.path if command == "land-merge" else where)
    output = done.stdout + done.stderr
    if command == "doctor" and not activity.startswith("busy"):
        assert done.returncode != 0, output
        assert "likely" in output.lower() and "runner" in output.lower(), output
        assert f"runner = {json.dumps(runner)}" in output and "forge.toml" in output, output
    else:
        assert "likely missing" not in output.lower(), output
        if command != "doctor":
            assert done.returncode == 0, output
            assert "clean review and green checks" in output, output
            assert len(env.gh_calls(*RUNS)) >= len(looks), output
