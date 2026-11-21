"""The generated CI command chooses groups by related test share.

Test-audit: Central imports defeat the old source-count rule. Existing tests
vary source counts rather than selection size. Real commits and the shipped
command cover this contract without a new production seam.
"""
import os
import re
import subprocess
import sys

from conftest import ROOT
from test_groups_pytest import PYTEST, _branch, _new_client, _settings
from test_merged_default_branch_pull_requests_run_normal_groups import _commit

STORY = "FIX-ONE-GROUP-BY-SELECTION"


def test_1_selected_test_share_chooses_groups(repo, gh, tmp_path):
    client = _new_client(repo, gh, tmp_path, "client")
    _branch(repo, client, "selected-groups")
    _settings(client, test=PYTEST + " --splits {groups} --group {group}", groups=4)
    (client / "src").mkdir(exist_ok=True)
    (client / "tests").mkdir(exist_ok=True)
    for name in ("central", "leaf", "quarter", "other"):
        (client / f"src/{name}.py").write_text("VALUE = 1\n", "utf-8")
    for i in range(12):
        imports = "from central import VALUE\n"
        if i < 2:
            imports += "from leaf import VALUE as LEAF\n"
        if i < 3:
            imports += "from quarter import VALUE as QUARTER\n"
        (client / f"tests/test_case_{i}.py").write_text(
            imports + "def test_it(): assert VALUE\n", "utf-8")
    result = repo.forge("sync", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    repo.git("add", "-A", cwd=client)
    setup = repo.git("commit-tree", repo.git("write-tree", cwd=client), "-p",
                     repo.git("rev-parse", "HEAD", cwd=client), "-m", "Set up selection", cwd=client)
    repo.git("update-ref", "HEAD", setup, cwd=client)
    base = repo.git("rev-parse", "HEAD", cwd=client)
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    excludes = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", workflow, re.M)[1]
    for name, isolated, expected in (("leaf", False, "true"),
                                     ("quarter", False, "false"),
                                     ("central", False, "false"),
                                     ("leaf", True, "false")):
        head = _commit(repo, client, tmp_path, [base], {
            f"src/{name}.py": "VALUE = 2\n", "src/other.py": "VALUE = 2\n"})
        repo.git("checkout", "-q", "--detach", head, cwd=client)
        output = tmp_path / "outputs"
        output.write_text("", "utf-8")
        command = [sys.executable, *(["-I", "-S"] if isolated else []), ".forge/review-tests.py"]
        result = subprocess.run(command, cwd=client,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "BASE_SHA": base,
                 "HEAD_SHA": head, "DOCS_ONLY_EXCLUDES": excludes,
                 "GITHUB_OUTPUT": output.as_posix()}, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        values = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
        assert values["one-group"] == expected, values
