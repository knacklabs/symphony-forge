"""Client CI runner selection and doctor diagnostics after a week without runner activity."""
from __future__ import annotations

import json
import re
import shutil
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import GREEN, env, run  # noqa: F401
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_migrate import _copied_client

STORY = "FIX-RUNNER-SETTING"


def test_4_copied_client_migration_keeps_default_ci_runner(repo, gh, tmp_path, monkeypatch):
    # Migration inventories generated adapters before forge.toml exists, then writes the jobs.
    _copied_client(repo, tmp_path, monkeypatch)
    migrated = repo.forge("migrate")
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    workflow = repo.git("show", "forge/migrate-v1:.github/workflows/forge.yml")
    labels = re.findall(r"^    runs-on: (.+)$", workflow, re.M)
    assert [json.loads(label) if label.startswith('"') else label for label in labels] == [
        "ubuntu-latest", "ubuntu-latest"]


def _jobs(client: Path) -> tuple[str, str]:
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    tests, check = workflow.split("\n  tests:\n", 1)[1].split("\n  forge-pr-check:\n", 1)
    return tests, check


def _runner(job: str) -> str:
    value = re.search(r"^    runs-on: (.+)$", job, re.M)[1]
    return json.loads(value) if value.startswith('"') else value


def _tool_bootstrap(jobs: tuple[str, str]) -> None:
    # The generated workflow is a public execution contract, independent of renderer structure.
    # Setup actions supply Python >=3.11 for tomllib, uv and Node on a plain runner.
    for job in jobs:
        assert "uses: astral-sh/setup-uv@" in job
        assert "uses: actions/setup-python@" in job
        assert "python-version: '3.11'" in job
        for line in job.splitlines():
            if re.search(r"(?:run: |\| )python3?\b", line):
                assert job.index("uses: actions/setup-python@") < job.index(line)
        assert job.index("uses: astral-sh/setup-uv@") < job.index("- run:")
    tests = jobs[0]
    assert "uses: actions/setup-node@" in tests
    assert "node-version:" in tests or "node-version-file:" in tests
    assert tests.index("uses: actions/setup-node@") < tests.rindex("- run:")


@pytest.mark.parametrize("runner", [None, "self-hosted"], ids=["default", "self-hosted"])
def test_1_new_client_init_selects_runner_and_bootstraps_tools(repo, gh, tmp_path, runner):
    client = _new_repo(repo, gh, tmp_path)
    args = ("--runner", runner) if runner else ()
    initialized = repo.forge("init", *args, cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    settings = tomllib.loads((client / "forge.toml").read_text("utf-8"))
    selected = runner or "ubuntu-latest"
    assert settings.get("runner", "ubuntu-latest") == selected
    jobs = _jobs(client)
    assert [_runner(job) for job in jobs] == [selected, selected]
    _tool_bootstrap(jobs)


def test_2_earlier_release_adoption_sync_keeps_selected_runner_and_sets_up_unpinned_node(repo):
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    config = (repo.path / "forge.toml").read_text("utf-8")
    assert tomllib.loads(config)["version"] == "v1.2.2"
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Adopt Forge on an earlier release")
    repo.git("checkout", "-qb", "fix/select-ci-runner")
    current = repo.forge("--version").stdout.split()[-1]
    config = 'runner = "self-hosted"\n' + config.replace('version = "v1.2.2"', f'version = "{current}"')
    (repo.path / "forge.toml").write_text(config, "utf-8")
    # A Node client without engines still needs a version installed by setup-node.
    repo.write("package.json", json.dumps({"scripts": {"test": "node --test"}}))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert (repo.path / "forge.toml").read_text("utf-8") == config
    jobs = _jobs(repo.path)
    assert [_runner(job) for job in jobs] == ["self-hosted", "self-hosted"]
    _tool_bootstrap(jobs)
    second = repo.forge("sync")
    assert second.returncode == 0 and "Nothing to change" in second.stdout


@pytest.mark.parametrize("runner", ["", "   "])
def test_6_sync_refuses_blank_runner_label(repo, runner):
    repo.git("checkout", "-qb", "fix/select-ci-runner")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrunner = {json.dumps(runner)}\n')
    result = repo.forge("sync")
    assert result.returncode != 0
    assert "runner must name a GitHub Actions runner label" in result.stderr
    assert not (repo.path / ".github/workflows/forge.yml").exists()


@pytest.mark.parametrize("command,state", [
    (command, state) for command in ("doctor", "close")
    for state in ("recent-queued", "recent-rerun", "running")
] + [("doctor", "target-event"), ("doctor", "another-head"), ("close", "optional-queued")])
def test_3_only_doctor_names_a_likely_missing_runner_after_a_five_minute_queue(env, command, state, monkeypatch):
    config = (env.repo.path / "forge.toml").read_text("utf-8") + 'runner = "self-hosted"\n'
    env.commit(env.repo.path, "forge.toml", config, "Select the organisation runner")
    item, where = env.start_fix()
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    env.gh.respond("pr", "list", stdout=json.dumps([
        {"number": 7, "state": "OPEN", "body": "", "isDraft": True, "headRefOid": head}]))
    now = datetime.now(timezone.utc)
    # Keep job timestamps before the fixed, second-resolution observation clock.
    monkeypatch.setenv("FORGE_NOW", now.replace(microsecond=0).isoformat())
    created = now - timedelta(minutes=1 if state in ("recent-queued", "recent-rerun") else 10)
    status = "in_progress" if state == "running" else "queued"
    pending = {**run("lint" if state == "optional-queued" else "tests", None, status),
               "created_at": created.isoformat()}
    env.checks([run("tests"), run("forge-pr-check"), pending]
               if state == "optional-queued" else [pending, run("forge-pr-check")])
    workflow_run = {
        "id": 101, "name": "forge", "status": status, "created_at": created.isoformat(),
        "updated_at": created.isoformat(),
        "run_started_at": None if status == "queued" else created.isoformat()}
    if state == "recent-rerun":
        workflow_run["run_attempt"] = 2
    if command == "doctor":
        workflow_run["head_sha"] = head
    if state in ("target-event", "another-head"):
        workflow_run["head_sha"] = env.repo.git("rev-parse", "main")
        workflow_run["pull_requests"] = [{"head": {
            "sha": head if state == "target-event" else "0" * 40}}]
    # Current check demand is independent of workflow head routing.
    env.gh.respond("api", "--jq", ".workflow_runs[]",
                   stdout=json.dumps(workflow_run) + "\n")
    env.gh.respond("api", "--jq", ".jobs[]",
                   "repos/{owner}/{repo}/actions/runs/101/jobs?per_page=100",
                   stdout=json.dumps({"status": status, "labels": ["self-hosted"],
                                      "runner_id": 9 if status == "in_progress" else 0,
                                      "started_at": created.isoformat() if status == "in_progress" else None}) + "\n")
    result = env.repo.forge(command, *([item] if command == "close" else []), cwd=where)
    output = result.stdout + result.stderr
    if command == "doctor" and state in ("target-event", "another-head"):
        assert result.returncode != 0, output
        assert "likely" in output.lower() and "runner" in output.lower(), output
        assert 'runner = "self-hosted"' in output and "forge.toml" in output, output
        assert "still running" not in output, output
        assert any(call[:3] == ["api", "--jq", ".workflow_runs[]"]
                   for call in env.gh.calls()), output
    else:
        assert "likely missing" not in output.lower(), output
        if command == "close":
            expected = "still running" if state == "running" else "still queued"
            assert result.returncode != 0 and expected in output, output


def test_5_missing_check_does_not_diagnose_a_missing_runner(env):
    item, _ = env.start_fix()
    env.checks([run("tests")])
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "forge-pr-check has not reported" in closed.stderr
    queries = [call for call in env.gh.calls()
               if call[:3] == ["api", "--jq", ".workflow_runs[]"]]
    assert not queries
    assert "missing runner" not in closed.stderr.lower()
