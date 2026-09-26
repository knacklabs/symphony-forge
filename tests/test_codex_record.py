"""Codex workers: one forge work per item, and no Codex process left behind it.

forge work and forge doctor run against the stub app-server, which can get stuck: "stall" never
answers initialize, so Codex never starts, and "hold" never answers thread/start. Stuck, it ignores
its stdin, as a server left behind by a crash would.
Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import _install
from test_codex_worker import PIN, _codex_repo, _running, _sent, _stub, sdk_data  # noqa: F401 (a fixture)

STORY = "FORGE-WARM-1"
KILL = getattr(signal, "SIGKILL", signal.SIGTERM)  # on Windows os.kill ends a process either way
# The tool Forge reads a process's start time and command with.
PS = "powershell" if os.name == "nt" else "ps"
# That tool, a second slower: two calls that start together both read a stale lock before either
# takes it.
SLOW = """#!{python}
import subprocess, sys, time
time.sleep(1)
done = subprocess.run([{tool!r}, *sys.argv[1:]], capture_output=True, text=True)
sys.stdout.write(done.stdout)
sys.stderr.write(done.stderr)
sys.exit(done.returncode)
"""
# That tool, slow to read the app-server, the one process it finds that is neither forge nor its
# driver: a second on, it copies the stub app-server's log to {seen}, the messages Codex had sent
# by the time Forge had the app-server's identity.
SLOW_SERVER = """#!{python}
import shutil, subprocess, sys, time
done = subprocess.run([{tool!r}, *sys.argv[1:]], capture_output=True, text=True)
if done.stdout.strip() and not any(own in done.stdout for own in ("forge work", "codex_turn")):
    time.sleep(1)
    shutil.copy({calls!r}, {seen!r})
sys.stdout.write(done.stdout)
sys.stderr.write(done.stderr)
sys.exit(done.returncode)
"""
# The real PowerShell, whose process query fails with an error that PowerShell's default lets the
# script run on past.
QUERY_FAILS = """#!{python}
import subprocess, sys
args = sys.argv[1:]
at = args.index("-Command") + 1
args[at] = "function Get-CimInstance {{ Write-Error 'stub: the query failed' }}; " + args[at]
sys.exit(subprocess.run([{tool!r}, *args]).returncode)
"""
# A ps, and on Windows a PowerShell, that can't read any process.
BLIND = "#!/usr/bin/env python3\nimport sys\nsys.exit('stub: no process can be read')\n"
# A ps that reads every process but Forge's Codex driver.
DRIVER_BLIND = """#!{python}
import subprocess, sys
done = subprocess.run([{ps!r}, *sys.argv[1:]], capture_output=True, text=True)
if "codex_turn" in done.stdout:
    sys.exit("stub: the driver can't be read")
sys.stdout.write(done.stdout)
sys.exit(done.returncode)
"""
# A ps that reads every process but a Codex app-server.
SERVER_BLIND = """#!{python}
import subprocess, sys
done = subprocess.run([{ps!r}, *sys.argv[1:]], capture_output=True, text=True)
if "app-server" in done.stdout:
    sys.exit("stub: the app-server can't be read")
sys.stdout.write(done.stdout)
sys.exit(done.returncode)
"""
# On PYTHONPATH, every Python loads it: the two minutes Codex gets to start pass in a second.
FAST = """import threading

start = threading.Timer.__init__


def fast(self, interval, *args, **kwargs):
    start(self, min(interval, 1), *args, **kwargs)


threading.Timer.__init__ = fast
"""


def _codex_repo_direct(repo, monkeypatch, sdk_data: Path) -> tuple[Path, Path]:
    """_codex_repo, with the stub app-server run by this Python itself. Codex's own program runs as
    it started, but `#!/usr/bin/env python3` execs twice more (env, then a macOS framework Python
    re-execs itself), so the command Forge records at its start could change under it, and Forge
    would rightly take the process for another one."""
    made = _codex_repo(repo, monkeypatch, sdk_data)
    stub = repo.bin / "codex-app-server"
    stub.write_text(f"#!{sys.executable}\n" + stub.read_text(encoding="utf-8").split("\n", 1)[1],
                    encoding="utf-8")
    return made


def _saved(path: Path) -> dict:
    return json.loads(path.read_text("utf-8")) if path.exists() else {}


def _up(pid: int) -> bool:
    """Whether the process runs; a finished one its parent hasn't collected yet doesn't."""
    if os.name == "nt":
        return _running(pid)
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True,
                          text=True).stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def _down(pid: int) -> bool:
    """Whether the process has gone, or goes within ten seconds: stopping takes a moment."""
    for _ in range(100):
        if not _up(pid):
            return True
        time.sleep(0.1)
    return False


def _held(repo, calls: Path, record: Path, status: str, *args: str,
          cwd: Path | None = None) -> tuple[subprocess.Popen, dict, int]:
    """A forge call (work BOARD/PAGE unless args say another) whose stub app-server is stuck
    ("stall" or "hold"). Returns the call, its record once the stub is stuck and on record, and
    the stub's process id (on Windows the record's app-server is the .cmd that started it)."""
    stuck = {"stall": "initialize", "hold": "thread/start"}[status]
    servers = len([call for call in _stub(calls) if "pid" in call])
    work = subprocess.Popen([sys.executable, str(repo.bin / "forge"),
                             *(args or ("work", "BOARD/PAGE"))], cwd=cwd or repo.path,
                            env={**os.environ, "STUB_CODEX_STATUS": status},
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    for _ in range(600):
        try:  # the stub may be halfway through a line
            said = _stub(calls)
        except ValueError:
            said = []
        pids = [call["pid"] for call in said if "pid" in call]
        saved = _saved(record)
        if len(pids) > servers and said[-1].get("method") == stuck and saved.get("app_server"):
            return work, saved, pids[-1]
        time.sleep(0.05)
    work.kill()
    pytest.fail(f"the forge call never got stuck: {work.communicate()[1]}")


def _freeze(pid: int) -> None:
    """Leave the process unable to act: SIGSTOP, and on Windows, which has none, suspend it and
    every process it started."""
    if os.name != "nt":
        os.kill(pid, signal.SIGSTOP)
        return
    import ctypes
    listed = subprocess.run(["powershell", "-NoProfile", "-Command",
                             "Get-CimInstance Win32_Process | ForEach-Object "
                             "{ \"$($_.ProcessId) $($_.ParentProcessId)\" }"],
                            capture_output=True, text=True, check=True).stdout.split()
    parents = dict(zip(map(int, listed[0::2]), map(int, listed[1::2])))
    tree = {pid}
    for _ in parents:  # add each generation of children until none is new
        tree |= {child for child, parent in parents.items() if parent in tree}
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    for each in tree:
        handle = kernel32.OpenProcess(0x0800, False, each)  # PROCESS_SUSPEND_RESUME
        if handle:
            ctypes.windll.ntdll.NtSuspendProcess(ctypes.c_void_p(handle))
            kernel32.CloseHandle(ctypes.c_void_p(handle))


def _crash(work: subprocess.Popen, saved: dict) -> None:
    """Kill forge work while its driver can't act, as a crash might: its group is left behind."""
    _freeze(saved["driver"]["pid"])
    work.kill()
    work.communicate()


def test_5_one_worker_per_item(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo_direct(repo, monkeypatch, sdk_data)
    threads = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD"
    record, lock = threads / "PAGE.json", threads / "PAGE.lock"
    tool = shutil.which(PS)  # the real one, before any stand-in

    if os.name != "nt":  # no SIGINT to send on Windows
        # The driver, then the app-server, are on record by id, start time and command before
        # Codex has started and before any conversation: here the app-server never answers
        # initialize.
        work, saved, stub = _held(repo, calls, record, "stall")
        driver, server = saved["driver"], saved["app_server"]
        assert saved == {"driver": driver, "app_server": server}
        assert sorted(driver) == ["command", "pid", "started"] and "codex_turn" in driver["command"]
        assert sorted(server) == ["command", "pid", "started"] and server["pid"] == stub

        # While it runs, a second forge work on the item refuses and says to wait, from another
        # worktree too, since the lock is in git's shared folder; it commits nothing.
        head = repo.git("rev-parse", "HEAD", cwd=folder)
        busy = repo.forge("work", "BOARD/PAGE", cwd=folder)
        assert busy.stderr == (f"forge work BOARD/PAGE is already running as process {work.pid}, "
                               "and only one runs per item; wait for it to finish.\n"
                               "Next: forge work BOARD/PAGE\n")
        assert repo.git("rev-parse", "HEAD", cwd=folder) == head

        # Ctrl-C lets the lock go, and every process of the call with it.
        work.send_signal(signal.SIGINT)
        work.communicate(timeout=30)
        assert not lock.exists() and _down(stub) and _down(driver["pid"])

        # A driver Forge can't identify is stopped before it hears the request: no Codex starts.
        _install(repo.bin, "ps", DRIVER_BLIND.format(python=sys.executable, ps=shutil.which("ps")))
        servers = len([call for call in _stub(calls) if "pid" in call])
        unknown = repo.forge("work", "BOARD/PAGE")
        (repo.bin / "ps").unlink()
        assert unknown.stderr.startswith(
            "Forge can't read the start time and command of its Codex driver, process ")
        assert unknown.stderr.endswith(", so it stopped the driver before any conversation.\n"
                                       "Next: forge work BOARD/PAGE\n")
        assert len([call for call in _stub(calls) if "pid" in call]) == servers
        assert not lock.exists()

        # An app-server Forge can't identify is stopped, with its driver, before any conversation.
        _install(repo.bin, "ps", SERVER_BLIND.format(python=sys.executable, ps=shutil.which("ps")))
        before = len(_sent(calls, "thread/start"))
        unknown = repo.forge("work", "BOARD/PAGE")
        (repo.bin / "ps").unlink()
        stub = [call["pid"] for call in _stub(calls) if "pid" in call][-1]
        assert unknown.stderr == ("Forge can't read the start time and command of the Codex "
                                  f"app-server, process {stub}, so it stopped Codex before any "
                                  "conversation.\nNext: forge work BOARD/PAGE\n")
        assert len(_sent(calls, "thread/start")) == before and _down(stub)
        assert _saved(record)["app_server"] is None and not lock.exists()

    # The app-server, the conversation, and HEAD once the turn ends, join the record.
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    saved = _saved(record)
    assert "codex_turn" in saved["driver"]["command"]
    assert (saved["conversation"], saved["head"]) == ("thr-stub-1",
                                                      repo.git("rev-parse", "HEAD", cwd=folder))

    # Codex waits for Forge to record the app-server: while Forge is slow to read its identity,
    # no conversation starts.
    seen = repo.path.parent / "seen.jsonl"
    before = len(_sent(calls, "thread/start"))
    _install(repo.bin, PS, SLOW_SERVER.format(python=sys.executable, tool=tool,
                                              calls=str(calls), seen=str(seen)))
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    for fake in [*repo.bin.glob("ps*"), *repo.bin.glob("powershell*")]:
        fake.unlink()
    assert (len(_sent(seen, "thread/start")), len(_sent(calls, "thread/start"))) == (before,
                                                                                    before + 1)

    # When Forge can't read who holds the lock, the owner counts as running: forge work refuses,
    # naming the lock.
    lock.write_text(json.dumps({"pid": os.getpid(), "started": "long ago",
                                "command": "forge work BOARD/PAGE"}), encoding="utf-8")
    for name in ("ps", "powershell"):
        _install(repo.bin, name, BLIND)
    blind = repo.forge("work", "BOARD/PAGE")
    assert blind.stderr == (f"Forge can't read the start time and command of process {os.getpid()}"
                            f", so it can't tell who holds {lock}; it counts it as held.\n"
                            f"Next: delete {lock} once no forge work runs on BOARD/PAGE\n")
    if os.name == "nt":  # a query that fails, where PowerShell runs on past the error, can't tell
        _install(repo.bin, "powershell", QUERY_FAILS.format(python=sys.executable, tool=tool))
        assert repo.forge("work", "BOARD/PAGE").stderr == blind.stderr

    # Once it can, a lock whose process id now belongs to another process is stale and cleared.
    for fake in [*repo.bin.glob("ps*"), *repo.bin.glob("powershell*")]:
        fake.unlink()
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert not lock.exists()

    # Two calls that find one stale lock together: one clears it and runs, and the other then
    # finds the new lock and refuses, rather than clearing that one too.
    lock.write_text(json.dumps({"pid": os.getpid(), "started": "long ago",
                                "command": "forge work BOARD/PAGE"}), encoding="utf-8")
    _install(repo.bin, PS, SLOW.format(python=sys.executable, tool=shutil.which(PS)))
    both = [subprocess.Popen([sys.executable, str(repo.bin / "forge"), "work", "BOARD/PAGE"],
                             cwd=repo.path, env={**os.environ, "STUB_CODEX_STATUS": "hold"},
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            for _ in range(2)]
    for _ in range(600):
        done = [call for call in both if call.poll() is not None]
        if done:
            break
        time.sleep(0.05)
    for call in both:
        call.kill()
    said = [call.communicate()[1] for call in done]
    assert len(said) == 1 and said[0].startswith("forge work BOARD/PAGE is already running as "
                                                 "process "), said


def _exec_driver_is_stopped(repo) -> None:
    # A driver recorded just after it started, that then execs into another command (as `env` or a
    # macOS framework Python does): same id and start time, new command. Doctor still stops it.
    flag = repo.path / "go"
    proc = subprocess.Popen(["sh", "-c", 'while [ ! -e "$1" ]; do sleep 0.05; done; exec sleep "$((20+10))"',
                            "codex_turn", str(flag)], start_new_session=True)
    try:
        def ps(field: str) -> str:
            return subprocess.run(["ps", "-ww", "-o", f"{field}=", "-p", str(proc.pid)],
                                  capture_output=True, text=True).stdout.strip()
        # ps pads a single-digit day ("Oct  1"); Forge records the start with one space between words.
        record = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD" / "EXEC.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps({"driver": {"pid": proc.pid, "started": " ".join(ps("lstart").split()),
                                                 "command": ps("command")}}), encoding="utf-8")
        flag.touch()
        for _ in range(200):
            if "sleep 30" in ps("command"):
                break
            time.sleep(0.05)
        else:
            pytest.fail("the shell never exec'd")
        assert ("- Stopped the Codex processes that a crashed forge work BOARD/EXEC left.\n"
                in repo.forge("doctor").stdout)
        assert _down(proc.pid)
    finally:
        proc.kill()
        proc.wait()


def test_6_nothing_left_running(repo, monkeypatch, sdk_data, tmp_path):
    folder, calls = _codex_repo_direct(repo, monkeypatch, sdk_data)
    threads = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD"
    record, lock = threads / "PAGE.json", threads / "PAGE.lock"

    # Killing forge work while Codex is still starting leaves nothing: the driver sees Forge go
    # and ends its whole process group, or on Windows the app-server's process tree.
    work, saved, stub = _held(repo, calls, record, "stall")
    work.kill()
    work.communicate()
    assert _down(stub) and _down(saved["driver"]["pid"])

    if os.name != "nt":  # Ctrl-C is SIGINT, which Windows can't send to one process
        # Ctrl-C while the driver can't act (stopped, here): forge work still returns, ends the
        # driver's group itself, and lets the lock go.
        work, saved, stub = _held(repo, calls, record, "stall")
        _freeze(saved["driver"]["pid"])
        work.send_signal(signal.SIGINT)
        work.communicate(timeout=30)
        assert not lock.exists() and _down(stub) and _down(saved["driver"]["pid"])

    # While forge work runs, doctor says so and leaves it alone. An error: the driver dies, and
    # forge work stops the app-server it recorded before it ends.
    work, saved, stub = _held(repo, calls, record, "hold")
    owner = _saved(lock)["pid"]  # forge work's own process, behind any Windows launcher
    assert (f"- forge work BOARD/PAGE is running as process {owner}, so doctor leaves its "
            "Codex process alone.\n") in repo.forge("doctor").stdout
    assert _up(stub) and _up(owner)
    os.kill(saved["driver"]["pid"], KILL)
    assert "Codex never reported its end" in work.communicate(timeout=30)[1]
    assert _down(stub)

    # A crash that leaves the driver unable to act (stopped, here) leaves its process group and a
    # stale lock. Doctor clears the lock, and stops the Codex processes only once the record
    # names them: not under another start time.
    work, saved, stub = _held(repo, calls, record, "stall")
    _crash(work, saved)
    record.write_text(json.dumps({key: {**saved[key], "started": "another"}
                                  for key in ("driver", "app_server")}), encoding="utf-8")
    assert "Stopped" not in repo.forge("doctor").stdout and _up(stub)
    assert not lock.exists()
    record.write_text(json.dumps(saved), encoding="utf-8")
    assert ("- Stopped the Codex processes that a crashed forge work BOARD/PAGE left.\n"
            in repo.forge("doctor").stdout)
    assert _down(stub) and _down(saved["driver"]["pid"])

    # After another crash, the next forge work stops the leftover group by identity, and runs.
    work, saved, stub = _held(repo, calls, record, "stall")
    _crash(work, saved)
    assert lock.exists()
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _down(stub) and _down(saved["driver"]["pid"])

    # A crash that kills the driver while Codex is starting, and forge work before it can act,
    # leaves only the app-server: the next forge work stops it by the identity on record.
    work, saved, stub = _held(repo, calls, record, "stall")
    _freeze(work.pid)
    os.kill(saved["driver"]["pid"], KILL)
    work.kill()
    work.communicate()
    assert _down(saved["driver"]["pid"])
    if os.name != "nt":
        # While Forge can't identify that app-server, it counts as running: forge work refuses and
        # keeps it on record, and doctor says so and leaves it alone.
        _install(repo.bin, "ps", SERVER_BLIND.format(python=sys.executable, ps=shutil.which("ps")))
        blind = repo.forge("work", "BOARD/PAGE")
        assert blind.stderr == (f"Process {stub}, which an earlier forge work BOARD/PAGE left, may "
                                "still be running Codex, and Forge can't read its start time and "
                                "command to be sure, so it counts it as running.\n"
                                f"Next: stop process {stub} if it runs, then forge work BOARD/PAGE\n")
        assert (f"- Process {stub}, which a crashed forge work BOARD/PAGE left, may still be running "
                "Codex, and Forge can't read its start time and command to be sure, so doctor "
                "leaves it alone; stop it if it runs.\n") in repo.forge("doctor").stdout
        (repo.bin / "ps").unlink()
        assert _saved(record) == saved and _up(stub)
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _down(stub)

    if os.name != "nt":  # the stand-in Python is a shell script
        # A macOS framework Python starts itself again under another command right after it
        # starts; here the SDK's Python is a script that does so a second on. Forge still knows
        # its driver by the command it runs under, and the next forge work after a crash stops it.
        real = sdk_data / "forge" / "codex-sdk" / f"openai-codex-{PIN}"
        env = tmp_path / "data" / "forge" / "codex-sdk" / real.name
        (env / "bin").mkdir(parents=True)
        shutil.copy(real / "forge-sdk-ready", env)
        (env / "bin" / "python").write_text(f'#!/bin/sh\nsleep 1\nexec "{real}/bin/python" "$@"\n',
                                            encoding="utf-8")
        (env / "bin" / "python").chmod(0o755)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        work, saved, stub = _held(repo, calls, record, "stall")
        _crash(work, saved)
        assert repo.forge("work", "BOARD/PAGE").returncode == 0
        assert _down(stub) and _down(saved["driver"]["pid"])
        monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))

    # Codex that never starts gets two minutes (a second here); then the driver ends its group,
    # and forge work refuses with the log's path.
    (tmp_path / "fast").mkdir()
    (tmp_path / "fast" / "sitecustomize.py").write_text(FAST, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "fast"))
    monkeypatch.setenv("STUB_CODEX_STATUS", "stall")
    late = repo.forge("work", "BOARD/PAGE")
    log = repo.path / ".git" / "forge" / "work-BOARD-PAGE.log"
    assert late.stderr == (f"Codex didn't start within two minutes, so Forge stopped it; its log "
                           f"is {log}.\nNext: forge work BOARD/PAGE\n")
    assert _down([call["pid"] for call in _stub(calls) if "pid" in call][-1])

    if os.name != "nt":  # exec is POSIX
        _exec_driver_is_stopped(repo)

def _record_in_process(tmp_path, refuse: str, seed: bool = True):
    """Run codex._record on a record in a fresh process whose os.replace is refused as Windows
    refuses it while another process has the file open. `refuse` is an expression of the count
    of renames so far and the seconds since the first one; when true, the rename is refused."""
    script = ("import os, sys, time; sys.path.insert(0, sys.argv[1])\n"
              "from pathlib import Path\n"
              "from forge import codex, repo\n"
              "real, seen, first = os.replace, [], time.monotonic()\n"
              "def replace(a, b):\n"
              "    seen.append(a)\n"
              f"    if {refuse}: raise PermissionError(5, 'Access is denied')\n"
              "    real(a, b)\n"
              "os.replace = replace\n"
              "try:\n"
              "    codex._record(Path(sys.argv[2]), b=2)\n"
              "except repo.Refused as refusal:\n"
              "    print(refusal)\n"
              "print(len(seen))\n")
    record = tmp_path / "PAGE.json"
    if seed:
        record.write_text('{"a": 1}\n')
    src = Path(__file__).resolve().parent.parent / "src"
    done = subprocess.run([sys.executable, "-c", script, str(src), str(record)],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return record, done.stdout


def test_7_record_retries_while_another_reader_holds_it(tmp_path):
    # Windows refuses the rename ("Access is denied") while another process has the file open;
    # here the first three renames are refused.
    record, out = _record_in_process(tmp_path, "len(seen) <= 3", seed=False)
    assert out.strip() == "4"
    assert json.loads(record.read_text()) == {"b": 2}


def test_8_record_refuses_when_another_reader_never_lets_go(tmp_path):
    # A reader that never releases the file ends in a plain refusal, not a PermissionError.
    record, out = _record_in_process(tmp_path, "True")
    assert out.startswith(f"Forge couldn't update {record} because another program kept it open.")
    assert json.loads(record.read_text()) == {"a": 1} and not record.with_suffix(".tmp").exists()


def test_9_record_waits_for_a_reader_to_release_an_existing_record(tmp_path):
    # The replace stays refused until a reader lets go half a second later: a loop that never
    # waited would use up its attempts first.
    record, out = _record_in_process(tmp_path, "time.monotonic() - first < 0.5")
    assert json.loads(record.read_text()) == {"a": 1, "b": 2}
