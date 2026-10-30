"""Small selections share the test budget, replacing the earlier five-file bypass."""
import json
import shutil
import sys

import pytest

from conftest import ROOT, machine_cores
from test_close import Forge, env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import start
from test_lanes_tests import accepted, configure, reap, release_server, shell  # noqa: F401

STORY = "reviews-skip-agent-line"


@pytest.mark.parametrize("adopted,file_count,compound,other_suite,doctest", [
    (adopted, *case)
    for adopted in (False, True)
    for case in ((5, False, False, False), (6, False, False, False), (5, True, False, False),
                 (5, False, True, False), (5, False, False, "command"),
                 (5, False, False, "config"))
    if not adopted or case in ((5, False, False, False), (6, False, False, False))
])
def test_2_related_test_selections_share_the_test_budget(env, tmp_path, release_server, monkeypatch,
                                                      adopted, file_count, compound, other_suite, doctest):
    server, connections = release_server
    repo = env.repo
    if adopted:
        # A client adopted on an earlier release gets this on upgrade, with no setting to change.
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        version = repo.forge("--version").stdout.split()[-1]
        config = (repo.path / "forge.toml").read_text("utf-8").replace('version = "v1.2.2"', f'version = "{version}"')
        repo.write("forge.toml", "\n".join(line for line in config.splitlines() if not line.startswith("test =")) + "\n")
    # The holder must fill the shared process budget before we check admission.
    machine_cores(repo, 4)  # two test processes, both reserved by the holder
    other = _other_repo(tmp_path, repo.bin)
    holder_home = tmp_path / "holder"
    holder_home.mkdir()
    holder = Forge(other, env.gh, holder_home)
    configure(holder, server)
    _, held = holder.start_fix()
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    repo.write("app.py", "VALUE = 1\n")
    repo.write("pyproject.toml", '[project]\nname = "lane-client"\nversion = "0.0.0"\n')
    # FORGE-BUDGET-1 counts every run, including five files, compound commands and doctests.
    for index in range(file_count):
        repo.write(f"tests/test_app_{index}.py", "from app import VALUE\n"
                   "def test_current_app():\n    assert VALUE == 2\n")
    picker = "forge test --pytest {base}"
    test_command = shell([sys.executable, "-m", "pytest", "tests", "-q",
                          *(["--doctest-modules"] if doctest == "command" else [])])
    if doctest == "config":
        repo.write("pytest.ini", "[pytest]\naddopts = --doctest-modules\n")
    if compound:
        picker += " && " + test_command
    if other_suite:
        # A standalone picker used to admit the unrestricted Node suite in its test command.
        repo.write("package.json", json.dumps({"scripts": {"test": "node --test tests/full-suite.cjs"}}))
        repo.write("tests/full-suite.cjs", 'const {test} = require("node:test");\n'
                   'const assert = require("node:assert/strict");\n'
                   'test("full Node suite", () => assert.match(\n'
                   '  require("node:fs").readFileSync("app.py", "utf8"), /VALUE = 2/));\n')
        test_command += " && npm test"
    repo.write("forge.toml", "test = " + json.dumps(test_command)
               + "\nfast_test = " + json.dumps(picker) + "\n" + (repo.path / "forge.toml").read_text("utf-8"))
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure a pytest client")
    repo.git("push", "-q", "origin", "main")
    _, folder = env.start_fix()
    monkeypatch.setenv("PYTHONPATH", str(folder))
    (folder / "app.py").write_text("VALUE = 2\n", "utf-8")
    # These are the item's tests even when the broad-selection bound applies;
    # both five-file and six-file selections must respect the shared process budget.
    for path in (folder / "tests").glob("test_app_*.py"):
        path.write_text(path.read_text("utf-8") + "\n# Worker test change\n", "utf-8")
    processes = []
    try:
        holding, output = start(held, tmp_path / "holding", repo, "test")
        processes.append(holding)
        accepted(server, connections, held, holding, output)
        small, small_output = start(folder, tmp_path / "small", repo, "test")
        processes.append(small)
        _until(lambda: "in line" in small_output.read_text("utf-8") or small.poll() is not None,
               "the selected tests to wait for the shared test budget")
        assert small.poll() is None, small_output.read_text("utf-8")
        assert "in line" in small_output.read_text("utf-8")
        assert holding.poll() is None
        connections[0].sendall(b"x")
        assert holding.wait(timeout=60) == 0, output.read_text("utf-8")
        status = small.wait(timeout=60)
        said = small_output.read_text("utf-8")
        assert status == 0, said
        assert f"{file_count} passed" in said
        if other_suite:
            assert "full Node suite" in said
    finally:
        reap(processes, server, connections)
