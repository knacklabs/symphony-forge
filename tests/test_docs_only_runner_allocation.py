"""Docs-only PRs leave a separate test runner free.

Test-audit: the generated workflow is GitHub's public scheduling contract.
Collapsing one group into its result job takes a fast slot before docs detection.
Existing docs-skip tests check suite execution, not runner allocation. No seam is added.
"""
import json
import os
import re
import shutil
import subprocess
import sys

from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_testplace_workflow import _jobs

STORY = "FIX-DOCS-ONLY-OFF-FAST-RUNNERS"


def test_1_docs_only_pr_keeps_the_test_runner_free(repo, gh, tmp_path, monkeypatch):
    version = repo.forge("--version").stdout.split()[-1]
    client = _new_repo(repo, gh, tmp_path, f'version = "{version}"\n'
        'runner = "ubuntu-24.04"\ntest_runner = "fast-tests"\ngroups = 1\n'
        'test = "make test"\nchecks = ["tests", "forge-pr-check"]\n')
    initialized = repo.forge("init", "--actions", "yes", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.git("switch", "-qc", "fix/docs-runners", cwd=client)
    record = client / ".factory/fixes/docs-runners.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"kind": "fix", "branch": "fix/docs-runners",
        "why": "Keep test runners free", "done_when": "Docs use the regular runner",
        "status": "started"}), "utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Prepare docs runner check", cwd=client)
    for command in (None, "sync"):
        if command:
            synced = repo.forge(command, cwd=client)
            assert synced.returncode == 0, synced.stdout + synced.stderr
        jobs = _jobs((client / ".github/workflows/forge.yml").read_text("utf-8"))
        assert "docs-check" in jobs, "Docs detection must precede allocation of a fast runner"
        assert 'runs-on: "ubuntu-24.04"' in jobs["docs-check"]
        assert 'runs-on: "ubuntu-24.04"' in jobs["tests-passed"]
        assert 'runs-on: "fast-tests"' in jobs["tests"]
        assert "needs: docs-check" in jobs["tests"]
        assert "needs.docs-check.outputs.docs-only != 'true'" in jobs["tests"]
        assert "&& 'tests' || 'tests (other event)'" in jobs["tests-passed"]
        assert "needs: [docs-check, tests]" in jobs["tests-passed"]
        assert "if: always() && github.event_name == 'pull_request'" in jobs["tests-passed"]
    base = repo.git("rev-parse", "HEAD", cwd=client)
    (client / "README.md").write_text("Updated guide\n", "utf-8")
    repo.git("add", "README.md", cwd=client)
    repo.git("commit", "-qm", "Update guide", cwd=client)
    output = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", repo.git("rev-parse", "HEAD", cwd=client))
    excludes = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", jobs["docs-check"], re.M)[1]
    monkeypatch.setenv("DOCS_ONLY_EXCLUDES", excludes)
    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                             capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr
    assert "docs-only=true" in output.read_text("utf-8").splitlines()
    # Execute the emitted required-check rule: failed detection or tests never pass.
    shell = shutil.which("bash")
    assert shell, "The GitHub result job requires bash"
    rule = re.search(r"^        run: (test .*?)$", jobs["tests-passed"], re.M)[1]
    for docs_check, docs_only, tests, passes in [
        ("success", "true", "skipped", True), ("success", "false", "success", True),
        ("success", "true", "failure", False), ("success", "false", "skipped", False),
        ("failure", "true", "skipped", False), ("success", "false", "cancelled", False),
    ]:
        result = subprocess.run([shell, "-c", rule], env={**os.environ,
            "DOCS_CHECK": docs_check, "DOCS_ONLY": docs_only, "TEST_GROUP_RESULT": tests})
        assert (result.returncode == 0) == passes
