"""Nightly groups have a bounded budget and publish only their combined result.

Test-audit gate:
1. Protect the generated workflow's matrix, time budget and one default-branch status.
2. An unsplit full run, missing timeout or successful partial status breaks this contract.
3. Existing full-run tests cover unsplit runs, not group execution and status aggregation.
4. Drive init/sync, real grouped pytest and the generated status script. No new seam is needed.

Use Bash from PATH explicitly: Windows otherwise launches System32's WSL shim.
"""
import os
import re
import shutil
import subprocess
import textwrap

import pytest

from test_groups_pytest import _adopted_client, _new_client, _settings, _write_related_tests
from test_testplace_workflow import _jobs

STORY = "FIX-A-REPO-WITH-TEST-GROUPS-STILL-RUNS-ITS-N"


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_nightly_groups_share_the_pr_budget_and_record_one_result(
        repo, gh, tmp_path, monkeypatch, adopted):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    client = (_adopted_client(repo, tmp_path, "nightly-client") if adopted else
              _new_client(repo, gh, tmp_path, "nightly-client"))
    if not adopted:
        repo.git("checkout", "-qb", "fix/nightly-groups", cwd=client)
    _settings(client, test="python -m pytest tests -q", groups=2)
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    _write_related_tests(client, receipts, assert_source=False)
    (client / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    jobs = _jobs((client / ".github/workflows/forge.yml").read_text(encoding="utf-8"))
    full = jobs["full-suite"]
    assert "group: [1, 2]" in full
    assert "fail-fast: false" in full
    budget = re.search(r"^    timeout-minutes: (\d+)$", jobs["tests"], re.M)
    assert budget and 0 < int(budget[1]) < 360
    assert f"    timeout-minutes: {budget[1]}\n" in full
    assert "FORGE_GROUP: ${{ matrix.group }}" in full
    assert "FORGE_GROUPS: '2'" in full

    # Publish fixture data on its remote default branch, as Actions would see it.
    hooks = tmp_path / "empty-hooks"
    hooks.mkdir()
    repo.git("config", "core.hooksPath", hooks.as_posix(), cwd=client)
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Configure nightly groups", cwd=client)
    repo.git("push", "-q", "origin", "HEAD:main", cwd=client)
    repo.git("remote", "set-head", "origin", "main", cwd=client)
    repo.git("checkout", "-q", "--detach", "origin/main", cwd=client)
    sha = repo.git("rev-parse", "HEAD", cwd=client)
    gh.respond("api", "--method", "POST", stdout="{}")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/project")
    monkeypatch.setenv("FORGE_GROUPS", "2")
    assert "      - run: forge test --full\n" in full
    before = len(gh.calls())
    for group in (1, 2):
        monkeypatch.setenv("FORGE_GROUP", str(group))
        ran = repo.forge("test", "--full", cwd=client)
        assert ran.returncode == 0, ran.stdout + ran.stderr
    assert sorted(path.read_text("utf-8").strip() for path in receipts.iterdir()) == ["a:1", "b:2"]
    assert not [call for call in gh.calls()[before:] if call[:3] == ["api", "--method", "POST"]]

    report = jobs["full-suite-result"]
    assert "needs: full-suite" in report
    assert "if: always()" in report
    assert "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'" in report
    assert "github.ref == format('refs/heads/{0}', github.event.repository.default_branch)" in report
    assert "FULL_RESULT: ${{ needs.full-suite.result }}" in report
    assert "HEAD_SHA: ${{ github.sha }}" in report
    script = textwrap.dedent(re.search(r"        run: \|\n((?:          .*\n)+)", report)[1])
    bash = shutil.which("bash")
    assert bash, "The generated result step needs Bash (Git Bash on Windows)."
    for outcome in ("success", "failure", "cancelled", "skipped"):
        before = len(gh.calls())
        ran = subprocess.run([bash, "-e", "-c", script], cwd=client, capture_output=True,
                             text=True, encoding="utf-8", timeout=30,
                             env={**os.environ, "FULL_RESULT": outcome, "HEAD_SHA": sha,
                                  "GITHUB_SERVER_URL": "https://github.example"})
        assert ran.returncode == (0 if outcome == "success" else 1), ran.stdout + ran.stderr
        [posted] = [call for call in gh.calls()[before:] if call[:3] == ["api", "--method", "POST"]]
        assert f"repos/owner/project/statuses/{sha}" in posted
        assert "context=forge-full-suite" in posted
        assert f"state={'success' if outcome == 'success' else 'failure'}" in posted
        assert "target_url=https://github.example/owner/project/actions/runs/123" in posted
    gh.respond("api", "--method", "POST", exit=1, stderr="GitHub unavailable")
    unavailable = subprocess.run(
        [bash, "-e", "-c", script], cwd=client, capture_output=True,
        text=True, encoding="utf-8", timeout=30,
        env={**os.environ, "FULL_RESULT": "success", "HEAD_SHA": sha,
             "GITHUB_SERVER_URL": "https://github.example"})
    assert unavailable.returncode == 1
