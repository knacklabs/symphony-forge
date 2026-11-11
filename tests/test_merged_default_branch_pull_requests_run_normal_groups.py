"""A pull request whose branch merged the default branch in runs the normal test groups.

Test-audit: `forge test --change` widens its selection to what a merged-in default branch
brought, so one group would run past its time limit. This runs the shipped CI script on the
checkout GitHub gives a pull request (a merge of the branch into the base) and reads the groups
the generated workflow starts. No fake decides the selection.
"""
import json
import os
import re
import subprocess
import sys

import pytest

from test_ci_limits_pull_requests_to_linux import expression
from test_groups_pytest import PYTEST, _adopted_client, _branch, _new_client, _settings
from test_testplace_workflow import _jobs

STORY = "FIX-BUG-1522-THE-ONE-GROUP-RUN-WIDENS-ITS-TE"


def _commit(repo, client, tmp_path, parents, files):
    """Make a commit with git plumbing: the hooks refuse commits off a Forge branch."""
    env = {**os.environ, "GIT_INDEX_FILE": str(tmp_path / "plumbing-index")}

    def git(*args, text=None):
        return subprocess.run(["git", *args], cwd=client, env=env, input=text, check=True,
                              capture_output=True, text=True).stdout.strip()

    git("read-tree", parents[0])
    for name, text in files.items():
        git("update-index", "--add", "--cacheinfo", f"100644,{git('hash-object', '-w', '--stdin', text=text)},{name}")
    flags = [flag for parent in parents for flag in ("-p", parent)]
    return repo.git("commit-tree", git("write-tree"), *flags, "-m", "Commit", cwd=client)


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
@pytest.mark.parametrize("change", ["test", "docs-with-required-tests"])
def test_1_pull_request_that_merged_the_default_branch_runs_normal_groups(
        repo, gh, tmp_path, adopted, change):
    client = (_adopted_client(repo, tmp_path, "client") if adopted
              else _new_client(repo, gh, tmp_path, "client"))
    if not adopted:
        # A new repo starts with one group; the pull request needs several to show the fan-out.
        _branch(repo, client, "merged-default")
        _settings(client, test=PYTEST, groups=2)
    ignore = client / ".gitignore"
    ignore.write_text((ignore.read_text("utf-8") if ignore.exists() else "")
                      + "\n__pycache__/\n", encoding="utf-8")
    (client / "tests").mkdir(exist_ok=True)
    (client / "docs").mkdir(exist_ok=True)
    for name in ("tests/test_mine.py", "tests/test_theirs.py", "docs/overview.md"):
        (client / name).write_text("def test_it(): assert True\n", encoding="utf-8")
    (client / ".forge").mkdir(exist_ok=True)
    (client / ".forge/always-tests.txt").write_text("tests/test_theirs.py\n", encoding="utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Set up", cwd=client)
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Sync", "--allow-empty", cwd=client)
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    excludes = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", workflow, re.M)[1]
    matrix = re.search(r"^        group: (.+)$", _jobs(workflow)["tests"], re.M)[1]
    matrix = matrix.replace("needs.docs-check.outputs.test-only", "github.test_only")
    main = repo.git("rev-parse", "HEAD", cwd=client)
    mine = ({"tests/test_mine.py": "def test_it(): assert True\n# Mine\n"} if change == "test"
            else {"docs/overview.md": "Mine\n"})
    branch = _commit(repo, client, tmp_path, [main], mine)
    incoming = _commit(repo, client, tmp_path, [main],
                       {"tests/test_theirs.py": "def test_it(): assert True\n# Incoming\n"})

    def groups(base, head):
        """GitHub checks out a merge of the pull request head into the base."""
        checkout = _commit(repo, client, tmp_path, [base, head], mine)
        repo.git("checkout", "-q", "--detach", checkout, cwd=client)
        output = tmp_path / "outputs"
        output.write_text("", encoding="utf-8")
        done = subprocess.run(
            [sys.executable, ".forge/review-tests.py"], cwd=client,
            env={**os.environ, "BASE_SHA": base, "HEAD_SHA": head, "DOCS_ONLY_EXCLUDES": excludes,
                 "GITHUB_OUTPUT": str(output)},
            capture_output=True, text=True, timeout=30)
        assert done.returncode == 0, done.stdout + done.stderr
        values = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
        assert values.get("docs-only") != "true", values
        return expression(matrix, test_only=values["test-only"])

    everything = list(range(1, 7)) if adopted else [1, 2]
    # The branch merged nothing in: one group runs the pull request's own test or required tests.
    assert groups(main, branch) == [1]
    # The branch merged the default branch in: the normal groups run.
    merged = _commit(repo, client, tmp_path, [branch, incoming],
                     {"tests/test_theirs.py": "def test_it(): assert True\n# Incoming\n"})
    assert groups(incoming, merged) == everything
