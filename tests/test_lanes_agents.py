"""CPU budget and FIFO admission through work, read, close and stop.

Only the model providers wait at their edge; Forge owns admission and cancellation.
"""
import os
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import _install, machine_cores
from test_codex_worker import sdk_data, _running  # noqa: F401
from test_close import env  # noqa: F401
from test_story import worktree
from test_fix_agent_runs_wait_in_line import (
    HOLDING_CLAUDE, HOLDING_AUTOREVIEW, _other_repo, _until,
)

STORY = "FORGE-LANES-1"


@pytest.fixture(params=["claude", "codex"])
def lane_adapter(env, tmp_path, monkeypatch, request, sdk_data):
    family = request.param
    if family == "codex":
        monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
        monkeypatch.setenv("CODEX_BIN", str(env.repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")))
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
        home = tmp_path / "codex-home"
        home.mkdir()
        (home / "config.toml").write_text("\n".join(
            f'[projects.{json.dumps(str(path))}]\ntrust_level = "trusted"'
            for path in (env.repo.path, tmp_path / "other")), "utf-8")
        monkeypatch.setenv("CODEX_HOME", str(home))
        config = (env.repo.path / "forge.toml").read_text("utf-8").replace(
            'workers = "claude"', 'workers = "codex"').replace('model = "opus"', 'model = "gpt-6-sol"')
        env.commit(env.repo.path, "forge.toml", config, "Use Codex workers")
        env.repo.git("push", "-q", "origin", "main")
    return family


def alive(pid):
    return _running(pid) and (os.name == "nt" or not subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip().startswith("Z"))


@pytest.fixture
def person(monkeypatch):
    # A worker may start this suite; stop commands in the test represent its person.
    monkeypatch.delenv("FORGE_WORKER", raising=False)


def hold_agents(env):
    _install(env.repo.bin, "claude", HOLDING_CLAUDE.format(python=sys.executable).replace(
        'while not (here / f"go-{name}").exists():',
        'while not (here / f"go-{name}").exists() and not (here / "go-all").exists():'))
    server = Path(__file__).parent / "stubs/codex-app-server"
    _install(env.repo.bin, "codex-app-server", server.read_text("utf-8").replace(
        '            turns += 1',
        '            here = pathlib.Path(__file__).resolve().parent\n'
        '            name = pathlib.Path(cwd).name\n'
        '            (here / f"started-{name}").touch()\n'
        '            while not (here / f"go-{name}").exists() and not (here / "go-all").exists():\n'
        '                time.sleep(0.05)\n'
        '            turns += 1'))
    helper = Path(os.environ["AUTOREVIEW"])
    real = helper.with_name("autoreview-real")
    helper.rename(real)
    helper.write_text(HOLDING_AUTOREVIEW.format(bin=str(env.repo.bin), real=str(real)).replace(
        '.exists():', f'.exists() and not (pathlib.Path({str(env.repo.bin)!r}) / "go-all").exists():'), "utf-8")


def make_work(repo, name):
    made = repo.forge("fix", "start", name, "--done", "The typo is corrected")
    assert made.returncode == 0, made.stderr
    item = name.lower().replace(" ", "-")
    return item, worktree(repo, "fix/" + item).name


def start(where, directory, repo, *args):
    directory.mkdir(exist_ok=True)
    output = directory / f"{args[0]}.out"
    with output.open("w", encoding="utf-8") as sink:
        process = subprocess.Popen([sys.executable, str(repo.bin / "forge"), *args], cwd=where,
            stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT)
    return process, output


def finish(repo, processes):
    (repo.bin / "go-all").touch()
    for marker in repo.bin.glob("started-*"):
        marker.with_name(marker.name.replace("started-", "go-", 1)).touch()
    for process in processes:
        try:
            process.wait(timeout=30)
        except Exception:
            process.kill()
            process.wait(timeout=10)
            raise


def test_1_half_the_cores_admit_work_read_and_review_in_fifo_order(env, tmp_path, person, lane_adapter):
    repo = env.repo
    machine_cores(repo, 6)
    first, first_name = make_work(repo, "First typo")
    closing, _ = env.start_fix()
    other = _other_repo(tmp_path, repo.bin)
    if lane_adapter == "codex":
        config = (other.path / "forge.toml").read_text("utf-8").replace(
            'model = "opus"', 'model = "gpt-6-sol"').replace('grill.claude', 'grill.codex')
        folder = worktree(other, "story/SHOP")
        (folder / "forge.toml").write_text(config, "utf-8")
    read_name = worktree(other, "story/SHOP").name
    queued = [make_work(repo, name) for name in ("Fourth typo", "Fifth typo", "Sixth typo")]
    hold_agents(env)
    started = lambda name: (repo.bin / f"started-{name}").exists()
    processes = []
    try:
        for where, command, item, marker in (
            (repo.path, "work", first, first_name),
            (other.path, "read", "SHOP", read_name),
            (repo.path, "close", closing, "review"),
        ):
            process, _ = start(where, tmp_path / str(len(processes)), repo, command, item)
            processes.append(process)
            _until(lambda: started(marker), f"{command} agent")
        for place, (item, marker) in enumerate(queued, 1):
            process, output = start(repo.path, tmp_path / f"waiting-{place}", repo, "work", item)
            processes.append(process)
            _until(lambda: f"number {place} in line." in output.read_text("utf-8"), "queue position")
            assert not started(marker)
        (repo.bin / f"go-{first_name}").touch()
        assert processes[0].wait(timeout=30) == 0
        _until(lambda: started(queued[0][1]), "the first waiting agent")
        assert not started(queued[1][1]) and not started(queued[2][1])
        stopped = repo.forge("stop", queued[1][0])
        assert stopped.returncode == 0, stopped.stderr
        _until(lambda: "number 1 in line." in (tmp_path / "waiting-3/work.out").read_text("utf-8"), "updated position")
        (repo.bin / f"go-{read_name}").touch()
        assert processes[1].wait(timeout=30) == 0
        _until(lambda: started(queued[2][1]), "the last waiting agent")
        assert not started(queued[1][1])
        assert processes[4].wait(timeout=30) != 0
        cancelled = (tmp_path / "waiting-2/work.out").read_text("utf-8")
        assert cancelled.splitlines()[-1] == "This run was stopped while waiting; it will not start."
        assert "Traceback" not in cancelled
    finally:
        finish(repo, processes)
