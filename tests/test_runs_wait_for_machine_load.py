"""Tests and reviews wait for external machine load, including after an upgrade."""
import json
import os
import shutil
import sys

import pytest

from conftest import Repo, _install, machine_cores
from test_close import GREEN, env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, start
from test_lanes_tests import shell
from test_setup import _fresh_client
from test_worker_runs_wait_for_machine_load import BUSY, _release

STORY = "load-check-all-runs"


def client(env, tmp_path, adopted):
    if adopted:
        _release(env, True)
        env.repo.git("checkout", "-qb", "fix/upgrade-load-check")
        synced = env.repo.forge("sync")
    else:
        folder, synced = _fresh_client(env.repo, env.gh, tmp_path)
        env.repo = Repo(folder, env.repo.bin)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    # Init queried protection through the shared gh stub; close needs CI answers again.
    env.checks(GREEN)
    env.repo.git("config", "core.hooksPath", str(tmp_path / "fixture-hooks"))
    if adopted:
        env.repo.git("add", "-A")
        env.repo.git("commit", "-qm", "Sync the upgraded client")
        env.repo.git("checkout", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/upgrade-load-check")
    return env.repo


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
@pytest.mark.parametrize("kind", ["test", "review"])
def test_1_tests_and_reviews_wait_for_high_load_then_start(env, tmp_path, adopted, kind):
    repo = client(env, tmp_path, adopted)
    marker = repo.bin / ("test-started" if kind == "test" else "started-review")
    command = shell([sys.executable, "-c",
                     f"from pathlib import Path; Path({marker.as_posix()!r}).touch()"])
    cfg = (repo.path / "forge.toml").read_text("utf-8")
    cfg = "\n".join(line for line in cfg.splitlines()
                    if line.partition("=")[0].strip() not in ("test", "fast_test"))
    env.commit(repo.path, "forge.toml", 'test = ' + json.dumps(command) + "\n" + cfg)
    repo.git("push", "-q", "origin", "main")
    item, folder = env.start_fix({"README.md": "Check the review under load\n"})
    if kind == "review":
        hold_agents(env)
    machine_cores(repo, 4, system_count=64)
    load = tmp_path / "load"
    load.write_text("6.0", "utf-8")
    shim = repo.bin / "forge"
    shim.write_text(shim.read_text("utf-8").replace("from forge.cli import main",
        "import pathlib\n"
        f"os.getloadavg = lambda: (float(pathlib.Path({load.as_posix()!r}).read_text()),) * 3\n"
        "from forge.cli import main"), "utf-8")
    processes = []
    try:
        args = ("test",) if kind == "test" else ("close", item)
        process, output = start(folder, tmp_path / "run", repo, *args)
        processes.append(process)
        _until(lambda: BUSY in output.read_text("utf-8") or process.poll() is not None,
               "the run to wait for machine load")
        assert BUSY in output.read_text("utf-8"), output.read_text("utf-8")
        assert process.poll() is None
        assert not marker.exists()
        load.write_text("5.9", "utf-8")
        _until(marker.exists, "the run to start after load falls")
        assert output.read_text("utf-8").count(BUSY) == 1
    finally:
        load.write_text("0.0", "utf-8")
        finish(repo, processes)
    assert process.returncode == 0, output.read_text("utf-8")


@pytest.mark.skipif(os.name == "nt", reason="The Mac/Linux load diagnostic uses ps; Windows has no load average")
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
def test_2_doctor_warns_that_self_hosted_runner_cpus_count_against_load(env, tmp_path, adopted):
    repo = client(env, tmp_path, adopted)
    listing = runner_process_list(repo)
    warning = ("Warning: a GitHub Actions self-hosted runner runs on this machine. "
               "Its CPUs count against Forge's load limit.")
    for commands, expected in [
        ("/opt/actions-runner/bin/Runner.Listener run", True),
        ("/bin/bash /opt/actions-runner/run.sh", True),
        ("/opt/actions-runner/run.sh", True),
        ("/opt/other/run.sh\npython unrelated.py", False),
        ("/opt/not-actions-runner/run.sh", False),
        ("python inspect.py /opt/actions-runner/bin/Runner.Listener run\n"
         "python inspect.py /opt/actions-runner/run.sh", False),
        ("", False),
    ]:
        listing.write_text(commands, "utf-8")
        result = repo.forge("doctor")
        assert (warning in result.stdout) is expected, result.stdout + result.stderr


def runner_process_list(repo):
    """Control only the OS process inventory; process identity queries still use real ps."""
    real_ps = shutil.which("ps")
    listing = repo.bin / "process-list"
    _install(repo.bin, "ps", f'''#!{sys.executable}
import pathlib, subprocess, sys
if sys.argv[1:] == ["-axo", "command="]:
    print(pathlib.Path({listing.as_posix()!r}).read_text("utf-8"))
else:
    sys.exit(subprocess.call([{real_ps!r}, *sys.argv[1:]]))
''')
    return listing
