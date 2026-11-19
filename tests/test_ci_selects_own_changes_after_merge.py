"""CI selects the PR's own changes after a merge; local runs keep incoming coverage.

Test-audit: Real git merges, the synced CI entry point and forge test --change
protect selection and group count. The prior merge test covers test-only changes,
not a two-source-file change or actual picker execution. Removing either mode
condition breaks this regression. No production seam or fake decides selection.
"""
import json
import os
import re
import subprocess
import sys

import pytest

from test_groups_pytest import _branch, _new_client, _settings
from test_merged_default_branch_pull_requests_run_normal_groups import _commit

STORY = "FIX-OWN-CHANGES-ONE-GROUP"


@pytest.mark.parametrize("place", ["ci", "local"])
def test_1_merged_main_keeps_ci_selection_on_own_changes(repo, gh, tmp_path, place):
    client = _new_client(repo, gh, tmp_path, "client")
    _branch(repo, client, "own-changes")
    settings = (client / "forge.toml").read_text("utf-8")
    settings = re.sub(r"^test_place = .*\n", "", settings, flags=re.M)
    (client / "forge.toml").write_text(f'test_place = "{place}"\n' + settings, "utf-8")
    _settings(client, test="pytest tests -q", fast_test="forge test --pytest {base}", groups=2)
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    for name in ("mine", "also_mine", "incoming"):
        for path, content in {
            f"src/{name}.py": "VALUE = 1\n",
            f"tests/test_{name}.py": (
                "from pathlib import Path\n"
                f"# src/{name}.py\ndef test_it():\n"
                f"    Path({json.dumps((receipts / name).as_posix())}).touch()\n"),
        }.items():
            target = client / path
            target.parent.mkdir(exist_ok=True)
            target.write_text(content, "utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Set up", cwd=client)
    result = repo.forge("sync", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    repo.git("add", "-A", cwd=client)
    synced = repo.git("commit-tree", repo.git("write-tree", cwd=client), "-p",
                      repo.git("rev-parse", "HEAD", cwd=client), "-m", "Sync fixture", cwd=client)
    repo.git("update-ref", "HEAD", synced, cwd=client)
    base = repo.git("rev-parse", "HEAD", cwd=client)
    own = {f"src/{name}.py": "VALUE = 2\n" for name in ("mine", "also_mine")}
    branch = _commit(repo, client, tmp_path, [base], own)
    incoming_files = {"src/incoming.py": "VALUE = 2\n"}
    incoming = _commit(repo, client, tmp_path, [base], incoming_files)
    head = _commit(repo, client, tmp_path, [branch, incoming], incoming_files)
    # Actions checks out a synthetic merge with main as its first parent.
    checkout = _commit(repo, client, tmp_path, [incoming, head], own)
    repo.git("checkout", "-q", "--detach", checkout, cwd=client)
    repo.git("update-ref", "refs/remotes/origin/main", incoming, cwd=client)
    repo.git("remote", "set-head", "origin", "main", cwd=client)
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    # Local-mode repos have no CI test job, but the classifier is still shipped.
    excludes = (re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", workflow, re.M)[1]
                if place == "ci" else "[]")
    output = tmp_path / "outputs"
    result = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
        env={**os.environ, "BASE_SHA": incoming, "HEAD_SHA": head,
             "DOCS_ONLY_EXCLUDES": excludes, "GITHUB_OUTPUT": output.as_posix()},
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    values = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    result = repo.forge("test", "--change", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    assert {path.name for path in receipts.iterdir()} == (
        {"mine", "also_mine"} if place == "ci" else {"mine", "also_mine", "incoming"})
    assert values["one-group"] == ("true" if place == "ci" else "false")
