"""A repo can supply full-run proof without a second scheduled suite.

Test-audit: generated workflow and real release/sign-off gates own this contract.
An ignored setting restores the duplicate run or points the user at the wrong workflow.
Existing full-run cases have no external workflow setting. Only GitHub is faked;
no production seam is needed.
"""
import json
import shutil

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_githooks import hooked
from test_proto_signoff import SOL_HIGH, _client, _decision
from test_testplace_fullrun import _set_status

STORY = "external-full-suite"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-external", "adopted-default"])
def test_1_repo_workflow_replaces_only_the_optional_full_suite(repo, gh, adopted):
    hooked(repo)
    repo.git("switch", "-q", "-c", "fix/full-suite")
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "make test"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               + ('' if adopted else 'full_suite_workflow = "nightly.yml"\n'))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text("utf-8")
    for entry in ("schedule:", "workflow_dispatch:", "  full-suite:", "  full-suite-result:"):
        assert (entry in workflow) == adopted
    assert "forge test --change" in workflow

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
