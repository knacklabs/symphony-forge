"""A repo can supply full-run proof without a second scheduled suite.

Test-audit: generated workflow and real release/sign-off gates own this contract.
An ignored setting restores the duplicate run or points the user at the wrong workflow.
Existing full-run cases have no external workflow setting. Only GitHub is faked;
no production seam is needed.
"""
import json
import re
import shutil
import tomllib

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_githooks import hooked
from test_proto_signoff import SOL_HIGH, _client, _decision
from test_testplace_fullrun import _set_status
from test_testplace_workflow import _jobs

STORY = "external-full-suite"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-external", "adopted-default"])
def test_1_repo_workflow_replaces_only_the_optional_full_suite(repo, gh, adopted):
    # Audit: preserve an earlier release's settings and workflow through a pin-only
    # upgrade. PR trigger/job eligibility is a generated GitHub contract, distinct
    # from merely retaining a test command somewhere in the file.
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        old = (repo.path / "forge.toml").read_text("utf-8").replace("v1.2.2", "v1.2.33")
        repo.write("forge.toml", old)
        repo.write(".github/workflows/forge.yml", (
            ROOT / "tests/fixtures/before-test-runner/forge.yml").read_text("utf-8"))
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Client on the earlier release")
        repo.git("push", "-q", "origin", "main")
        repo.git("switch", "-q", "-c", "fix/full-suite")
        upgraded = old.replace('version = "v1.2.33"', f'version = "{version}"')
        repo.write("forge.toml", upgraded)
    else:
        hooked(repo)
        repo.git("switch", "-q", "-c", "fix/full-suite")
        repo.write("forge.toml", f'version = "{version}"\ntest = "make test"\n'
                   'checks = ["tests", "forge-pr-check"]\n'
                   'full_suite_workflow = "nightly.yml"\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    if adopted:
        assert (repo.path / "forge.toml").read_text("utf-8") == upgraded
        assert tomllib.loads(upgraded) == {**tomllib.loads(old), "version": version}
    workflow = (repo.path / ".github/workflows/forge.yml").read_text("utf-8")
    for entry in ("schedule:", "workflow_dispatch:", "  full-suite:", "  full-suite-result:"):
        assert (entry in workflow) == adopted
    assert re.search(r"^  pull_request:\s*$", workflow, re.M)
    tests_job = _jobs(workflow.split("\njobs:\n", 1)[1])["tests"]
    assert "    if: github.event_name == 'pull_request'\n" in tests_job
    assert '- run: "forge test --change"' in tests_job

    sha = repo.git("rev-parse", "origin/main")
    tag_input = f"refs/tags/v1.0.0 {sha} refs/tags/v1.0.0 {'0' * 40}\n"
    _set_status(gh, sha, None)
    refused = repo.forge("hook", "pre-push", input=tag_input)
    assert refused.returncode != 0
    expected = "forge.yml" if adopted else "nightly.yml"
    assert f"gh workflow run {expected} --ref main" in refused.stderr
    _set_status(gh, sha, "success")
    accepted = repo.forge("hook", "pre-push", input=tag_input)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr


def test_2_signoff_accepts_the_repo_workflows_commit_status(repo, gh, tmp_path, monkeypatch, env):
    tools = tmp_path / "signoff-tools"
    tools.mkdir()
    fix, answers, queue = _client(repo, tools, monkeypatch)
    page = _decision(fix, answers)
    settings = fix / "forge.toml"
    settings.write_text(settings.read_text("utf-8") + '\nfull_suite_workflow = "nightly.yml"\n',
                        encoding="utf-8")
    repo.git("add", "forge.toml", cwd=fix)
    repo.git("commit", "-q", "-m", "Use the repo full-suite workflow", cwd=fix)
    sha = repo.git("rev-parse", "origin/main")
    _set_status(gh, sha, None)
    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert refused.returncode == 1
    assert "gh workflow run nightly.yml --ref main" in refused.stderr
    _set_status(gh, sha, "success")
    queue.write_text(json.dumps([{"say": SOL_HIGH, "report": {
        "review_status": "scoped-clean", "findings": []}}] * 2), encoding="utf-8")
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "status: accepted" in page.read_text("utf-8")


def test_3_next_tracks_the_configured_workflows_manual_failure_and_retry(repo, gh, monkeypatch):
    # Audit: real next must show manual failures and clear older nightly failures
    # after a successful retry. Existing cases query forge.yml only. Fake only
    # GitHub run lists/logs; no production seam or internal cache reads are needed.
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\n'
               'checks = ["tests", "forge-pr-check"]\nfull_suite_workflow = "nightly.yml"\n')
    scheduled = {"id": 17, "workflow_id": 2, "name": "Nightly tests", "event": "schedule",
                 "path": ".github/workflows/nightly.yml", "head_branch": "main",
                 "conclusion": "failure", "created_at": "2030-01-01T03:00:00Z"}
    manual = {**scheduled, "id": 18, "event": "workflow_dispatch",
              "created_at": "2030-01-01T04:00:00Z"}
    gh.respond("api", "repos/{owner}/{repo}/actions/runs",
               stdout=json.dumps({"workflow_runs": [scheduled]}))
    gh.respond("api", "repos/{owner}/{repo}/actions/workflows/nightly.yml/runs",
               stdout=json.dumps({"workflow_runs": [manual]}))
    gh.respond("run", "view", "17", "--log-failed",
               stdout="tests\trun\tFAILED tests/test_old.py::test_nightly - boom")
    gh.respond("run", "view", "18", "--log-failed",
               stdout="tests\trun\tFAILED tests/test_manual.py::test_suite - boom")
    monkeypatch.setenv("FORGE_NOW", "2030-01-01T05:00:00+00:00")
    failed = repo.forge("next")
    assert failed.returncode == 0, failed.stdout + failed.stderr
    assert "The latest manual Nightly tests (nightly.yml) run on main failed" in failed.stdout
    assert "tests/test_manual.py::test_suite" in failed.stdout
    assert "tests/test_old.py::test_nightly" not in failed.stdout
    gh.respond("api", "repos/{owner}/{repo}/actions/workflows/nightly.yml/runs",
               stdout=json.dumps({"workflow_runs": [{**manual, "conclusion": "success"}]}))
    monkeypatch.setenv("FORGE_NOW", "2030-01-01T05:11:00+00:00")
    retried = repo.forge("next")
    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert "Nightly tests (nightly.yml) run on main failed" not in retried.stdout
    assert "tests/test_old.py::test_nightly" not in retried.stdout
