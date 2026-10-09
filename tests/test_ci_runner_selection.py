"""Client CI runner selection and actionable checks queued without a runner."""
from __future__ import annotations

import json
import re
import shutil
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import ROOT, _install
from test_close import GREEN, env, run  # noqa: F401
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, _workers, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401
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
    for state in ("old-queued", "recent-queued", "recent-rerun", "running")
] + [("doctor", "target-event"), ("doctor", "another-head"), ("close", "optional-queued")])
def test_3_queued_checks_without_runner_name_setting_after_several_minutes(env, command, state):
    config = (env.repo.path / "forge.toml").read_text("utf-8") + 'runner = "self-hosted"\n'
    env.commit(env.repo.path, "forge.toml", config, "Select the organisation runner")
    item, where = env.start_fix()
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    env.gh.respond("pr", "list", stdout=json.dumps([
        {"number": 7, "state": "OPEN", "body": "", "isDraft": True, "headRefOid": head}]))
    now = datetime.now(timezone.utc)
    created = now - timedelta(minutes=10 if state != "recent-queued" else 1)
    status = "in_progress" if state == "running" else "queued"
    env.checks([run("tests"), run("forge-pr-check"), run("lint", None, status)]
               if state == "optional-queued" else [run("tests", None, status), run("forge-pr-check")])
    workflow_run = {
        "id": 101, "name": "forge", "status": status, "created_at": created.isoformat(),
        "updated_at": (now - timedelta(minutes=1) if state == "recent-rerun" else created).isoformat(),
        "run_started_at": None if status == "queued" else created.isoformat()}
    if command == "doctor":
        workflow_run["head_sha"] = head
    if state in ("target-event", "another-head"):
        workflow_run["head_sha"] = env.repo.git("rev-parse", "main")
        workflow_run["pull_requests"] = [{"head": {
            "sha": head if state == "target-event" else "0" * 40}}]
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]",
                   stdout=json.dumps(workflow_run) + "\n")
    # Age alone no longer diagnoses a missing runner; no assigned jobs is evidence.
    env.gh.respond("api", "--paginate", "--jq", ".jobs[]", stdout="")
    if command == "close":
        # Closing commits its review before waiting. GitHub returns that current head,
        # rather than the fixture's earlier head, when queried after the push.
        stub = (env.repo.bin / "gh").read_text("utf-8")
        stub = stub.replace('sys.stdout.write(rule["stdout"])', '''
        if args[:4] == ["api", "--paginate", "--jq", ".workflow_runs[]"]:
            import subprocess
            row = json.loads(rule["stdout"])
            row["head_sha"] = subprocess.run(["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True).stdout.strip()
            rule["stdout"] = json.dumps(row) + "\\n"
        sys.stdout.write(rule["stdout"])'''.strip())
        _install(env.repo.bin, "gh", stub)
    result = env.repo.forge(command, *([item] if command == "close" else []), cwd=where)
    output = result.stdout + result.stderr
    if state in ("old-queued", "target-event", "optional-queued"):
        assert result.returncode != 0, output
        assert "queued" in output.lower(), output
        assert "no runner has picked" in output.lower(), output
        assert 'runner = "self-hosted"' in output and "forge.toml" in output, output
        assert "still running" not in output, output
        assert any(call[:4] == ["api", "--paginate", "--jq", ".workflow_runs[]"]
                   for call in env.gh.calls()), output
    else:
        assert "no runner has picked" not in output.lower(), output
        if command == "close":
            expected = "still running" if state == "running" else "still queued"
            assert result.returncode != 0 and expected in output, output


def test_5_missing_check_queries_queued_runs_without_windows_batch_operators(env):
    item, _ = env.start_fix()
    env.checks([run("tests")])
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "forge-pr-check has not reported" in closed.stderr
    queries = [call for call in env.gh.calls()
               if call[:4] == ["api", "--paginate", "--jq", ".workflow_runs[]"]]
    assert queries
    # Windows' gh.cmd shim interprets an unquoted & as a second command.
    # Pagination already follows every page without adding per_page to the URL.
    assert all("&" not in call[-1] for call in queries), queries


@pytest.mark.parametrize("phase", ["close", "merge"])
@pytest.mark.parametrize("answer", ["malformed", "failed"])
def test_7_land_retries_queued_run_lookup_failures_without_a_worker_round(clock, phase, answer):
    # The check-run lookup works; only the separate Actions lookup temporarily fails.
    # Both land's close phase and its merge revalidation must keep their progress wait.
    env = clock
    _agent(env)
    _fix(env, "working", worked=True)
    queued = [run("tests", None, "queued"), run("forge-pr-check")]
    looks = [queued, queued, GREEN] if phase == "close" else [GREEN, queued, queued, GREEN]
    _queue(env, RUNS, *_runs(*looks))
    actions = ["api", "--paginate", "--jq", ".workflow_runs[]"]
    if answer == "failed":
        stub = env.repo.bin / "gh"
        stub.write_text(stub.read_text("utf-8").replace('        answer(out)',
            '        if out == "failed-queued-answer":\n'
            '            answer("GitHub Actions temporarily unavailable", 1)\n'
            '        answer(out)'), encoding="utf-8")
    _queue(env, actions, "{" if answer == "malformed" else "failed-queued-answer", "")
    done = env.repo.forge("land", ITEM)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Merged tidy-readme and removed its worktree" in done.stdout
    assert done.stdout.count(f"Closing {ITEM}.") == 1
    assert len(env.review_calls()) == 1
    assert not _workers(env)
    assert len(env.gh_calls("pr", "merge")) == 1
    assert len(env.gh_calls(*actions)) >= 2
