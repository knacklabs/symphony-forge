"""Pull request test machines are independent of the other CI machines."""
import json
import re
import shutil
from datetime import datetime, timedelta, timezone

import pytest

from conftest import ROOT
from test_close import env, run  # noqa: F401
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_ci_limits_pull_requests_to_linux import expression

STORY = "FIX-TEST-RUNNER-SETTING"


@pytest.mark.parametrize("history,groups,runner,test_runner", [
    ("new", 1, "ubuntu-24.04", "windows-latest"),
    ("new", 3, "ubuntu-24.04", "windows-latest"),
    ("new", 3, "windows-latest", "self-hosted"),
    ("adopted", 1, "ubuntu-24.04", None),
])
def test_1_only_pull_request_tests_use_the_optional_machine(repo, gh, tmp_path, history, groups, runner, test_runner):
    # Public workflow contract: init/sync must keep each job on its intended event and machine.
    # A wrong label or event guard breaks CI; no test-only production seam is needed.
    version = repo.forge("--version").stdout.split()[-1]
    if history == "adopted":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt an earlier release")
        client = repo.path
        config = (client / "forge.toml").read_text("utf-8")
        config = config.replace('version = "v1.2.2"', f'version = "{version}"')
        before = (ROOT / "tests/fixtures/before-test-runner/forge.yml").read_text("utf-8").replace("v1.2.33", version)
        path = client / ".github/workflows/forge.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(before, encoding="utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Keep the workflow from before test_runner")
    else:
        client = _new_repo(repo, gh, tmp_path)
        initialized = repo.forge("init", "--actions", "yes", cwd=client)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        config = (client / "forge.toml").read_text("utf-8")
        config = "\n".join(line for line in config.splitlines()
                           if line.partition("=")[0].strip() not in {"test", "fast_test", "groups", "runner"})
        config = (f'runner = {json.dumps(runner)}\ntest_runner = {json.dumps(test_runner)}\n'
                  f'groups = {groups}\ntest = "vitest run --shard={{group}}/{{groups}}"\n' + config + "\n")
    repo.git("checkout", "-qb", "fix/test-machines", cwd=client)
    (client / "forge.toml").write_text(config, encoding="utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    jobs = dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)", workflow.split("\njobs:\n", 1)[1], re.M | re.S))
    expected_jobs = {"tests", "forge-pr-check", "full-suite", "full-suite-result"}
    if history == "new" and groups > 1:
        expected_jobs |= {"docs-check", "tests-passed"}
    assert set(jobs) == expected_jobs
    for name, job in jobs.items():
        selected = json.loads(re.search(r"^    runs-on: (.+)$", job, re.M)[1])
        expected = "ubuntu-24.04" if history == "adopted" else test_runner if name == "tests" else runner
        assert selected == expected
    condition = re.search(r"^    if: (.+)$", jobs["tests"], re.M)[1]
    condition = condition.replace("needs.docs-check.outputs.docs-only", "'false'")
    for event in ("pull_request", "pull_request_target", "schedule", "workflow_dispatch"):
        assert bool(expression("${{ " + condition + " }}", event_name=event)) == (event == "pull_request")
    if test_runner is None:
        assert re.findall(r"^    runs-on: (.+)$", workflow, re.M) == re.findall(
            r"^    runs-on: (.+)$", before, re.M)


@pytest.mark.parametrize("check_name,queued_label,started_label,missing", [
    ("tests", "paid-tests", "ubuntu-24.04", True),
    ("test group 1 of 3", "paid-tests", "ubuntu-24.04", True),
    ("tests", "paid-tests", None, True),
    ("tests", "paid-tests", "paid-tests", False),
    ("forge-pr-check", "ubuntu-24.04", "paid-tests", True),
    ("tests", "ubuntu-24.04", "paid-tests", True),
])
def test_2_doctor_checks_the_machine_for_the_queued_job(env, monkeypatch, check_name, queued_label, started_label, missing):
    # Doctor's public advice must name the blocked pool. Started jobs on the other pool
    # cannot prove it available. Existing doctor tests use one pool, and cannot catch this.
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", 'runner = "ubuntu-24.04"\ntest_runner = "paid-tests"\n' + config)
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    env.gh.respond("pr", "list", stdout=json.dumps([
        {"number": 7, "state": "OPEN", "headRefOid": head}]))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    monkeypatch.setenv("FORGE_NOW", now.isoformat())
    queued_at = (now - timedelta(minutes=10)).isoformat()
    env.checks([{**run(check_name, None, "queued"), "started_at": queued_at}, run("lint")])
    env.gh.respond("api", "--jq", ".workflow_runs[]", stdout=json.dumps({
        "id": 101, "head_sha": head, "status": "in_progress", "created_at": queued_at}))
    jobs = [{"status": "queued", "name": check_name, "runner_id": 0, "labels": [queued_label]}]
    if started_label:
        jobs.append({"status": "completed", "name": "docs-check", "runner_id": 9,
                     "labels": [started_label], "started_at": queued_at})
    env.gh.respond("api", "--jq", ".jobs[]", "repos/{owner}/{repo}/actions/runs/101/jobs?per_page=100",
                   stdout="\n".join(json.dumps(job) for job in jobs))
    result = env.repo.forge("doctor", cwd=where)
    output = result.stdout + result.stderr
    assert ("likely missing runner" in output) == missing, output
    if missing:
        setting = f'{"runner" if queued_label == "ubuntu-24.04" else "test_runner"} = {json.dumps(queued_label)}'
        assert setting in output, output
        assert "correct the setting in forge.toml" in output, output
