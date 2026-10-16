"""A new worker run starts only while the machine's load per core is under 1.5, and a worker's
test runs use at most two test processes, in new repos and in repos adopted on an earlier release."""
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install, machine_cores
from test_close import env  # noqa: F401
from test_codex_worker import sdk_data  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, lane_adapter, make_work, person, start  # noqa: F401

STORY = "admit-by-load"
BUSY = "This machine is busy (load 1.5 per core), so this work round waits until it is under 1.5."


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
    # Load counts against the cores Forge may use, not the host's 64.
    machine_cores(repo, 4, system_count=64)
    load = tmp_path / "load"
    load.write_text("6.0", "utf-8")  # exactly 1.5 per core: busy
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
        load.write_text("5.9", "utf-8")
        _until(lambda: (repo.bin / f"started-{second_name}").exists(), "the second round to start")
        assert output.read_text("utf-8").count(BUSY) == 1
    finally:
        finish(repo, processes)


PROBE = """import os, pathlib, time
import pytest


@pytest.mark.parametrize("n", range(8))
def test_probe(n):
    time.sleep(0.3)
    out = pathlib.Path(os.environ["PROBE_OUT"])
    out.mkdir(exist_ok=True)
    (out / os.environ.get("PYTEST_XDIST_WORKER", "main")).touch()
"""


@pytest.mark.parametrize("adopted", [False, True], ids=["new-repo", "existing-repo"])
def test_2_a_worker_s_test_runs_use_at_most_two_processes(env, tmp_path, person, lane_adapter, adopted):
    repo = env.repo
    _release(env, adopted, lane_adapter)
    machine_cores(repo, 8)
    pytest_args = ["-m", "pytest", "-q", "-p", "no:cacheprovider", "probe"]
    argv = [sys.executable, *pytest_args, "-n", "4"]  # a fixed count the budget must still cap
    command = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
    lines = (repo.path / "forge.toml").read_text("utf-8").splitlines()
    config = "test = " + json.dumps(command) + "\n" + "\n".join(
        line for line in lines if line.partition("=")[0].strip() != "test") + "\n"
    repo.write("probe/test_probe.py", PROBE)
    env.commit(repo.path, "forge.toml", config, "Run the process probe")
    repo.git("push", "-q", "origin", "main")
    item, name = make_work(repo, "First typo")
    # The worker runs tests the sanctioned way, then calls pytest -n auto directly; each probe
    # test records the xdist process it ran in.
    record = ("_bin = pathlib.Path({bin!r})\n"
              "_out = __import__('subprocess').run([{python!r}, str(_bin / 'forge'), 'test'], cwd={cwd},\n"
              "    env=dict(os.environ, PROBE_OUT=str(_bin / 'via-forge')), capture_output=True, text=True)\n"
              "_direct = __import__('subprocess').run([{python!r}, *{args!r}, '-n', 'auto'], cwd={cwd},\n"
              "    env=dict(os.environ, PROBE_OUT=str(_bin / 'direct')), capture_output=True)\n"
              "(_bin / 'worker-tests').write_text(_out.stdout + _out.stderr)\n"
              "assert _out.returncode == 0, _out.stdout + _out.stderr\n"
              "assert _direct.returncode == 0, _direct.stdout + _direct.stderr\n")
    # The SDK's interpreter owns only the provider. The test client has pytest
    # in its own environment, and real worker-launched tests must run there.
    sdk = repo.bin / "claude_agent_sdk" / "__init__.py"
    sdk_record = record.format(bin=repo.bin.as_posix(), cwd="None", args=pytest_args,
                               python=Path(sys.executable).as_posix()).replace("pathlib.Path", "Path")
    sdk.write_text(sdk.read_text("utf-8").replace(
        '    yield AssistantMessage([TextBlock("SDK worker output")], options.model)',
        "".join("    " + line + "\n" for line in sdk_record.splitlines()) +
        '    yield AssistantMessage([TextBlock("SDK worker output")], options.model)'), "utf-8")
    server = ROOT / "tests/stubs/codex-app-server"
    _install(repo.bin, "codex-app-server", server.read_text("utf-8").replace(
        "            turns += 1",
        "".join("            " + line + "\n" for line in
                record.format(bin=repo.bin.as_posix(), cwd="cwd", args=pytest_args,
                              python=Path(sys.executable).as_posix()).splitlines())
        + "            turns += 1"))
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert (repo.bin / "worker-tests").exists(), worked.stdout + worked.stderr
    report = (repo.bin / "worker-tests").read_text("utf-8")
    for run in ("via-forge", "direct"):
        assert (repo.bin / run).is_dir(), report
        assert sorted(path.name for path in (repo.bin / run).iterdir()) == ["gw0", "gw1"], report
