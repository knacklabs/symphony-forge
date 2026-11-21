"""CI selects the PR's own changes after a merge; local runs keep incoming coverage.

Test-audit: Real git merges, the synced CI entry point and forge test --change
protect selection and group count. The prior merge test covers test-only changes,
not a two-source-file change or actual picker execution. Removing either mode
condition breaks this regression. No production seam or fake decides selection.
Round 2 audit: Evaluate the generated workflow with a dynamic group count, then
run its selected group. Incoming added or changed tests reach mine through an
unchanged adapter and fail only on the combined code. The old receipt-only
case cannot catch their omission. Extend this owner test without a new seam.
"""
import json
import os
import re
import subprocess
import sys

import pytest

from test_groups_pytest import _branch, _new_client, _settings
from test_ci_limits_pull_requests_to_linux import expression
from test_merged_default_branch_pull_requests_run_normal_groups import _commit
from test_testplace_workflow import _jobs

STORY = "FIX-OWN-CHANGES-ONE-GROUP"


@pytest.mark.parametrize("place", ["ci", "local"])
@pytest.mark.parametrize("main_test", ["none", "added", "changed"])
def test_1_merged_main_keeps_ci_selection_on_own_changes(repo, gh, tmp_path, monkeypatch,
                                                       place, main_test):
    client = _new_client(repo, gh, tmp_path, "client")
    _branch(repo, client, "own-changes")
    settings = (client / "forge.toml").read_text("utf-8")
    settings = re.sub(r"^test_place = .*\n", "", settings, flags=re.M)
    (client / "forge.toml").write_text(f'test_place = "{place}"\n' + settings, "utf-8")
    _settings(client, test=f'"{sys.executable}" -m pytest tests -q --splits {{groups}} --group {{group}}',
              fast_test="forge test --pytest {base}", groups=2)
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    for name in ("mine", "also_mine", "incoming"):
        for path, content in {
            f"src/{name}.py": "VALUE = 1\nLABEL = 0\n",
            f"tests/test_{name}.py": (
                "from pathlib import Path\n"
                f"# src/{name}.py\ndef test_it():\n"
                f"    Path({json.dumps((receipts / name).as_posix())}).touch()\n"),
        }.items():
            target = client / path
            target.parent.mkdir(exist_ok=True)
            target.write_text(content, "utf-8")
    (client / "src/checkout.py").write_text(
        "from src.mine import VALUE\ndef total(): return VALUE\n", "utf-8")
    main_tests = {f"tests/test_checkout_{i}.py" for i in range(6)}
    if main_test == "changed":
        for path in main_tests:
            (client / path).write_text("def test_total(): assert True\n", "utf-8")
    result = repo.forge("sync", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    repo.git("add", "-A", cwd=client)
    synced = repo.git("commit-tree", repo.git("write-tree", cwd=client), "-p",
                      repo.git("rev-parse", "HEAD", cwd=client), "-m", "Sync fixture", cwd=client)
    repo.git("update-ref", "HEAD", synced, cwd=client)
    base = repo.git("rev-parse", "HEAD", cwd=client)
    own = {f"src/{name}.py": "VALUE = 2\nLABEL = 0\n" for name in ("mine", "also_mine")}
    branch = _commit(repo, client, tmp_path, [base], own)
    incoming_files = {"src/incoming.py": "VALUE = 2\nLABEL = 0\n"}
    if main_test != "none":
        incoming_files["src/mine.py"] = "VALUE = 1\nLABEL = 1\n"
        incoming_files.update({path: "from src.checkout import total\n"
                              "def test_total(): assert total() == 1\n" for path in main_tests})
    incoming = _commit(repo, client, tmp_path, [base], incoming_files)
    combined = {**incoming_files, **own}
    if main_test != "none":
        combined["src/mine.py"] = "VALUE = 2\nLABEL = 1\n"
    head = _commit(repo, client, tmp_path, [branch, incoming], combined)
    # Actions checks out a synthetic merge with main as its first parent.
    checkout = _commit(repo, client, tmp_path, [incoming, head], combined)
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
    if place == "ci":
        jobs = _jobs(workflow)
        group_output = re.search(r"^      one-group: (.+)$", jobs["docs-check"], re.M)[1]
        group_output = group_output.replace("steps.docs.outputs.one-group", "github.one_group")
        one_group = expression(group_output, one_group=values["one-group"])
        matrix = re.search(r"^        group: (.+)$", jobs["tests"], re.M)[1]
        matrix = matrix.replace("needs.docs-check.outputs.one-group", "github.one_group")
        groups = expression(matrix, one_group=one_group)
        # Own changes select most of this fixture, so keep both configured groups.
        assert groups == [1, 2], (values, group_output, matrix)
        monkeypatch.setenv("FORGE_GROUPS", str(len(groups)))
        results = []
        for group in groups:
            monkeypatch.setenv("FORGE_GROUP", str(group))
            results.append(repo.forge("test", "--change", cwd=client))
        result = subprocess.CompletedProcess([], max(run.returncode for run in results),
            "".join(run.stdout for run in results), "".join(run.stderr for run in results))
    else:
        result = repo.forge("test", "--change", cwd=client)
    if main_test == "none":
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        assert result.returncode != 0, result.stdout + result.stderr
        for path in main_tests:
            assert path + "::test_total" in result.stdout + result.stderr
    assert {path.name for path in receipts.iterdir()} == (
        {"mine", "also_mine"} if place == "ci" else {"mine", "also_mine", "incoming"})
    assert values["one-group"] == "false"
