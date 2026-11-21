"""The generated CI command chooses groups by related test share.

Test-audit: Central imports defeat the old source-count rule. Existing tests
vary source counts rather than selection size. Real commits and the shipped
command cover this contract without a new production seam.
"""
import os
import re
import shutil
import subprocess

import pytest

from conftest import ROOT
from test_groups_pytest import PYTEST, _branch, _new_client, _settings
from test_merged_default_branch_pull_requests_run_normal_groups import _commit

STORY = "FIX-ONE-GROUP-BY-SELECTION"


@pytest.mark.parametrize("command", ["picker", "automatic", "full", "mixed", "required"])
def test_1_selected_test_share_chooses_groups(repo, gh, tmp_path, command):
    client = _new_client(repo, gh, tmp_path, "client")
    _branch(repo, client, "selected-groups")
    fast = {"picker": "forge test --pytest {base}", "automatic": "",
            "full": PYTEST, "mixed": "forge test --pytest {base} && vitest run",
            "required": "forge test --pytest {base}"}[command]
    _settings(client, test=PYTEST, fast_test=fast, groups=4,
              always_test=[f"tests/test_case_{i}.py" for i in range(3)] if command == "required" else [])
    config = (client / "forge.toml").read_text("utf-8")
    config = re.sub(r'^repo = .*\n', '', config, flags=re.M)
    (client / "forge.toml").write_text('repo = "forge-source"\n' + config, "utf-8")
    # Exercise the generated source-install command in its real isolated environment.
    shutil.copytree(ROOT / "src/forge", client / "src/forge", ignore=shutil.ignore_patterns("__pycache__"))
    (client / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
        '[project]\nname = "symphony-forge"\nversion = "0.0.0"\n'
        'requires-python = ">=3.11"\ndependencies = ["pillow>=12.3.0"]\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/forge"]\n'
        '[dependency-groups]\ndev = ["pytest", "pytest-split"]\n', "utf-8")
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
    (client / "examples").mkdir()
    for i in range(48):
        (client / f"examples/test_example_{i}.py").write_text("def test_it(): pass\n", "utf-8")
    result = repo.forge("sync", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    repo.git("add", "-A", cwd=client)
    setup = repo.git("commit-tree", repo.git("write-tree", cwd=client), "-p",
                     repo.git("rev-parse", "HEAD", cwd=client), "-m", "Set up selection", cwd=client)
    repo.git("update-ref", "HEAD", setup, cwd=client)
    base = repo.git("rev-parse", "HEAD", cwd=client)
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    excludes = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", workflow, re.M)[1]
    from test_ci_limits_pull_requests_to_linux import expression
    from test_testplace_workflow import _jobs
    job = _jobs(workflow)["docs-check"]
    select = re.search(r"^        run: (.+)$", job, re.M)[1]
    matrix = re.search(r"^        group: (.+)$", _jobs(workflow)["tests"], re.M)[1]
    matrix = matrix.replace("needs.docs-check.outputs.one-group", "github.one_group")
    group_output = re.search(r"^      one-group: (.+)$", job, re.M)[1]
    group_output = group_output.replace("steps.docs.outputs.one-group", "github.one_group")
    for name, isolated, expected in (("leaf", False, "true"),
                                     ("quarter", False, "false"),
                                     ("central", False, "false"),
                                     ("leaf", True, "false")):
        head = _commit(repo, client, tmp_path, [base], {
            f"src/{name}.py": "VALUE = 2\n", "src/other.py": "VALUE = 2\n"})
        repo.git("checkout", "-q", "--detach", head, cwd=client)
        output = tmp_path / "outputs"
        output.write_text("", "utf-8")
        invocation = select.split(" || ", 1)[1] if isolated else select
        environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        result = subprocess.run(invocation, shell=True, cwd=client,
            env={**environment, "BASE_SHA": base,
                 "HEAD_SHA": head, "DOCS_ONLY_EXCLUDES": excludes,
                 "GITHUB_OUTPUT": output.as_posix()}, capture_output=True, text=True, timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        values = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
        if command in {"full", "mixed", "required"}:
            expected = "false"
        assert values["one-group"] == expected, values
        one = expression(group_output, one_group=values["one-group"])
        assert expression(matrix, one_group=one) == ([1] if expected == "true" else [1, 2, 3, 4])
