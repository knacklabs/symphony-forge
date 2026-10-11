"""A new worker run starts only while the machine's load per core is under 1.5, and a worker's
test runs use at most two test processes, in new repos and in repos adopted on an earlier release."""
import json
import os
import shlex
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, _install, machine_cores
from test_close import env  # noqa: F401
from test_codex_worker import sdk_data  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, lane_adapter, make_work, person, start  # noqa: F401

STORY = "admit-by-load"
BUSY = "This machine is busy (load 2.0 per core), so this work round waits until it is under 1.5."


def _release(env, adopted, lane_adapter="claude"):
    repo = env.repo
    if adopted:
        version = repo.forge("--version").stdout.split()[-1]
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt on the earlier release")
        config = (repo.path / "forge.toml").read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{version}"').replace(
            'workers = "codex"', f'workers = "{lane_adapter}"')
        env.commit(repo.path, "forge.toml", config, "Use the current release")
        repo.git("push", "-q", "origin", "main")


@pytest.mark.parametrize("adopted", [False, True], ids=["new-repo", "existing-repo"])
def test_1_a_work_round_waits_while_load_per_core_is_at_least_one_and_a_half(env, tmp_path, person, adopted):
    repo = env.repo
    _release(env, adopted)
    machine_cores(repo, 4)
    load = tmp_path / "load"
    load.write_text("8.0", "utf-8")
    shim = repo.bin / "forge"
    shim.write_text(shim.read_text("utf-8").replace("from forge.cli import main",
        f"import pathlib\nos.getloadavg = lambda: (float(pathlib.Path({str(load)!r}).read_text()),) * 3\n"
        "from forge.cli import main"), "utf-8")
    first, first_name = make_work(repo, "First typo")
    second, second_name = make_work(repo, "Second typo")
    hold_agents(env)
    processes = []
    try:
        # With no other agent running, waiting would never lower the load, so the first starts.
        processes.append(start(repo.path, tmp_path / "first", repo, "work", first)[0])
        _until(lambda: (repo.bin / f"started-{first_name}").exists(), "the first round")
        process, output = start(repo.path, tmp_path / "second", repo, "work", second)
        processes.append(process)
        _until(lambda: BUSY in output.read_text("utf-8"), "the second round to say it waits")
        assert not (repo.bin / f"started-{second_name}").exists()
        load.write_text("4.0", "utf-8")
        _until(lambda: (repo.bin / f"started-{second_name}").exists(), "the second round to start")
        assert output.read_text("utf-8").count(BUSY) == 1
    finally:
        finish(repo, processes)


def test_2_a_worker_s_test_runs_use_at_most_two_processes(env, tmp_path, person, lane_adapter):
    repo = env.repo
    machine_cores(repo, 8)
    code = "import os; print('Test budget: ' + os.environ['PYTEST_XDIST_AUTO_NUM_WORKERS'])"
    argv = [sys.executable, "-c", code]
    command = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
    config = (repo.path / "forge.toml").read_text("utf-8")
    env.commit(repo.path, "forge.toml", "test = " + json.dumps(command) + "\n" + config, "Report the test budget")
    repo.git("push", "-q", "origin", "main")
    item, name = make_work(repo, "First typo")
    # The worker both runs tests the sanctioned way and calls pytest -n auto directly.
    record = ("_out = __import__('subprocess').run([sys.executable, str(pathlib.Path({bin!r}) / 'forge'), 'test'],\n"
              "    cwd={cwd}, capture_output=True, text=True)\n"
              "(pathlib.Path({bin!r}) / 'worker-tests').write_text(\n"
              "    'direct ' + os.environ.get('PYTEST_XDIST_AUTO_NUM_WORKERS', 'unset') + '\\n' + _out.stdout + _out.stderr)\n")
    _install(repo.bin, "claude", f"#!{sys.executable}\nimport os, pathlib, sys\nsys.stdin.read()\n"
             + record.format(bin=str(repo.bin), cwd="None") + "print('Done.')\n")
    server = ROOT / "tests/stubs/codex-app-server"
    _install(repo.bin, "codex-app-server", server.read_text("utf-8").replace(
        "            turns += 1",
        "".join("            " + line + "\n" for line in
                record.format(bin=str(repo.bin), cwd="cwd").splitlines()) + "            turns += 1"))
    worked = repo.forge("work", item)
    assert (repo.bin / "worker-tests").exists(), worked.stdout + worked.stderr
    report = (repo.bin / "worker-tests").read_text("utf-8")
    assert report.startswith("direct 2\n"), report
    assert "Test budget: 2\n" in report, report
