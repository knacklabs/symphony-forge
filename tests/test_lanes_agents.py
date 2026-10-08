"""CPU budget and FIFO admission through work, read, close and stop.

Only the model providers wait at their edge; Forge owns admission and cancellation.
"""
import os
import json
import subprocess
import shutil
import threading
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install, machine_cores
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


def start(where, directory, repo, *args, launcher=None):
    directory.mkdir(exist_ok=True)
    output = directory / f"{args[0]}.out"
    with output.open("w", encoding="utf-8") as sink:
        process = subprocess.Popen([sys.executable, str(launcher or repo.bin / "forge"), *args], cwd=where,
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


@pytest.mark.parametrize("cancel_between", [False, True], ids=["nudge", "stop-between"])
def test_1_half_the_cores_admit_work_read_and_review_in_fifo_order(env, tmp_path, person, lane_adapter, cancel_between):
    repo = env.repo
    machine_cores(repo, 6)
    first, first_name = make_work(repo, "First typo")
    # Windows's venv redirector can have a different pid from the Forge interpreter.
    parent_pid = tmp_path / "forge-parent-pid"
    launcher = repo.bin / "forge"
    launcher.write_text(launcher.read_text("utf-8").replace("from forge.cli import main",
        "import os, pathlib\n"
        f"if sys.argv[1:] == ['work', {first!r}]:\n"
        f"    pathlib.Path({str(parent_pid)!r}).write_text(str(os.getpid()))\n"
        "from forge.cli import main"), "utf-8")
    # Exercise a redirecting launcher on every OS, rather than only Windows CI.
    redirector = tmp_path / "redirector.py"
    redirector.write_text("import subprocess, sys\n"
        f"raise SystemExit(subprocess.call([sys.executable, {str(launcher)!r}, *sys.argv[1:]]))\n", "utf-8")
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
    legacy = None
    if cancel_between and os.name != "nt":
        # The supported base checker really launches an ungrouped reviewer.
        source = tmp_path / "base-src"
        shutil.copytree(ROOT / "src/forge", source / "forge", ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("close.py", "review.py", "prcheck.py", "templates/review.md"):
            shutil.copy(ROOT / "tests/fixtures/pr-check-before-branch-diff" / name, source / "forge" / name)
        legacy = tmp_path / "base-forge"
        # Keep the same simulated six-core OS boundary for the older checker.
        legacy.write_text((repo.bin / "forge").read_text("utf-8").replace(
            str(ROOT / "src"), str(source)), "utf-8")
    # A dirty first turn forces a second model launch in the same work round.
    # Hold Git between launches: a per-launch reservation must not admit a waiter.
    for provider in ("claude", "codex-app-server"):
        stub = repo.bin / provider
        source = stub.read_text("utf-8")
        indent = "            " if provider == "codex-app-server" else ""
        source = source.replace('name = pathlib.Path(cwd).name' if indent else
                                'name = pathlib.Path.cwd().name',
            ('name = pathlib.Path(cwd).name' if indent else 'name = pathlib.Path.cwd().name') +
            f'\n{indent}if name == {first_name!r} and (here / "first-ended").exists():\n'
            f'{indent}    name += "-nudge"')
        marker = '            turns += 1' if indent else 'print("No findings.")'
        source = source.replace(marker,
            f'{indent}if name == {first_name!r}:\n'
            f'{indent}    pathlib.Path({str(worktree(repo, "fix/" + first) / "dirty.txt")!r}).write_text("needs committing")\n'
            f'{indent}    (here / "first-ended").touch()\n' + marker)
        stub.write_text(source, "utf-8")
    started = lambda name: (repo.bin / f"started-{name}").exists()
    processes = []
    try:
        for where, command, item, marker in (
            (repo.path, "work", first, first_name),
            (other.path, "read", "SHOP", read_name),
            (repo.path, "close", closing, "review"),
        ):
            process, _ = start(where, tmp_path / str(len(processes)), repo, command, item,
                               launcher=redirector if command == "work" else legacy if command == "close" else None)
            processes.append(process)
            _until(lambda: started(marker), f"{command} agent")
        for place, (item, marker) in enumerate(queued, 1):
            process, output = start(repo.path, tmp_path / f"waiting-{place}", repo, "work", item)
            processes.append(process)
            _until(lambda: f"number {place} in line." in output.read_text("utf-8"), "queue position")
            assert not started(marker)
        def entries():
            board = repo.forge("board", "--json")
            assert board.returncode == 0, board.stderr
            return json.loads(board.stdout)["lanes"]["agents"]["entries"]
        rows = entries()
        admitted = next(e for e in rows if e["item"] == first)
        if legacy:
            old_review = next(e for e in rows if e["kind"] == "review")
            assert os.getpgid(old_review["process"]["pid"]) != old_review["process"]["pid"]
        if lane_adapter == "codex" and os.name != "nt":
            # A process can exit between two queue liveness reads. Replay its last
            # real OS snapshot once at the gap, then let ps report that it is gone.
            real_ps = shutil.which("ps")
            ps_args = ["-ww", "-o", "lstart=,command=", "-p", str(admitted["process"]["pid"])]
            snapshot = subprocess.run([real_ps, *ps_args], capture_output=True, text=True, check=True).stdout
        waiting = lambda rows: {e["item"]: (e["id"], e["started_at"]) for e in rows
                                if e["item"] in {q[0] for q in queued}}
        waiters = waiting(rows)
        assert len(waiters) == len(queued) and all(start is None for _, start in waiters.values())
        real_git = shutil.which("git")
        _install(repo.bin, "git", f'''#!{sys.executable}
import os, pathlib, signal, subprocess, sys, time
here = pathlib.Path(__file__).resolve().parent
if sys.argv[1:] == ["status", "--porcelain", "-uall"] and pathlib.Path.cwd().name == {first_name!r} and (here / "first-ended").exists() and not (here / "between-launches").exists():
    if {cancel_between!r}:
        if os.name != "nt": signal.signal(signal.SIGTERM, signal.SIG_IGN)
        child = subprocess.Popen([sys.executable, "-c", "import os, signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN) if os.name != 'nt' else None; time.sleep(600)"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (here / "git-tree").write_text(str(os.getpid()) + " " + str(child.pid))
    (here / "between-launches").touch()
    while not (here / "go-between").exists() and not (here / "go-all").exists():
        time.sleep(0.05)
sys.exit(subprocess.call([{real_git!r}, *sys.argv[1:]]))
''')
        (repo.bin / f"go-{first_name}").touch()
        _until(lambda: (repo.bin / "between-launches").exists(), "between model launches")
        if lane_adapter == "codex" and os.name != "nt":
            _install(repo.bin, "ps", f'''#!{sys.executable}
import pathlib, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
if sys.argv[1:] == {ps_args!r} and not (here / "last-process-snapshot").exists():
    (here / "last-process-snapshot").touch()
    sys.stdout.write({snapshot!r})
else:
    sys.exit(subprocess.call([{real_ps!r}, *sys.argv[1:]]))
''')
            sampled = entries()
            assert next(e for e in sampled if e["item"] == first)["id"] == admitted["id"]
            assert waiting(sampled) == waiters
        rows = entries()
        between = next(e for e in rows if e["item"] == first)
        assert between["id"] == admitted["id"] and between["joined_at"] == admitted["joined_at"]
        assert between["process"]["pid"] == int(parent_pid.read_text("utf-8"))
        assert waiting(rows) == waiters
        assert all(not started(marker) for _, marker in queued)
        # cmd.exe resumes the .cmd after Python returns: keep this live launcher.
        # The one-shot marker makes subsequent Git calls forward without holding.
        if cancel_between:
            tree = [int(pid) for pid in (repo.bin / "git-tree").read_text("utf-8").split()]
            reaper = threading.Thread(target=processes[0].wait, daemon=True)
            reaper.start()
            stopped = repo.forge("stop", "--id", admitted["id"])
            assert stopped.returncode == 0, stopped.stderr
            assert all(not alive(pid) for pid in tree), "stop freed admission while Git or its hook still ran"
            reaper.join(timeout=30)
            assert not started(first_name + "-nudge")
        else:
            (repo.bin / "go-between").touch()
            _until(lambda: started(first_name + "-nudge"), "commit nudge model")
            rows = entries()
            nudging = next(e for e in rows if e["item"] == first)
            assert nudging["id"] == admitted["id"] and nudging["joined_at"] == admitted["joined_at"]
            assert nudging["process"]["pid"] != int(parent_pid.read_text("utf-8"))
            assert waiting(rows) == waiters
            assert all(not started(marker) for _, marker in queued)
            (repo.bin / f"go-{first_name}-nudge").touch()
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
        if legacy:
            stopped = repo.forge("stop", "--id", old_review["id"])
            assert stopped.returncode == 0, stopped.stderr
            assert not alive(old_review["process"]["pid"])
    finally:
        if cancel_between and (repo.bin / "git-tree").exists():
            for pid in map(int, (repo.bin / "git-tree").read_text("utf-8").split()):
                if alive(pid):
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
                    else:
                        os.kill(pid, 9)
        finish(repo, processes)
