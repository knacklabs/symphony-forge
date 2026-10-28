"""The test harness: a temp repo with a bare remote, a stub gh, and hook payload builders.

Tests drive the real `forge` command and look only at its output, git, the files a
human reads and the calls the stubs recorded (spec criterion 4).
"""
from __future__ import annotations

import faulthandler
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, TypeVar

import pytest
import _pytest.pathlib
import _pytest.tmpdir

ROOT = Path(__file__).resolve().parents[1]
REAL_UV = shutil.which("uv")  # Capture before any test adds a command stub to PATH.
REAL_CODEX_HOME = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")

_deadline_log = None


def pytest_configure(config: pytest.Config) -> None:
    """Windows CI needs a native deadline even outside the per-test timeout."""
    global _deadline_log
    seconds = float(os.environ.get("PYTEST_SESSION_DEADLINE") or "0")
    if not seconds:
        return
    # Keep a descriptor outside pytest capture: a stuck capture flush must not hide
    # the stacks or prevent the native watchdog from terminating the process.
    _deadline_log = os.fdopen(os.dup(sys.stderr.fileno()), "w", encoding="utf-8")
    if hasattr(config, "workerinput"):
        seconds -= min(60, seconds / 2)  # Workers dump before the controller exits.
    faulthandler.dump_traceback_later(seconds, file=_deadline_log, exit=True)


def pytest_runtest_logstart(nodeid: str, location: tuple) -> None:
    if _deadline_log is not None:
        print(f"Test started: {nodeid}", file=_deadline_log, flush=True)

IDLE_MACHINE = """from forge import machine
machine.memory = lambda: dict(total_bytes=16_000_000_000, available_bytes=8_000_000_000)
machine.busy_runners = lambda: 0
"""

# `forge` on PATH runs this checkout's src/forge, whatever else is installed.
FORGE_SHIM = """#!{python}
import os, signal, sys
# Work rounds wait while the machine is busy; tests that need a load set their own.
if hasattr(os, "getloadavg"):
    os.getloadavg = lambda: (0.0, 0.0, 0.0)
signal.signal(signal.SIGINT, signal.default_int_handler)
sys.path.insert(0, {src!r})
from forge.cli import main
sys.exit(main())
""".replace("from forge.cli import main", IDLE_MACHINE + "from forge.cli import main")


def machine_cores(repo, count, system_count=None):
    """Report a machine's CPU count at the command boundary, without a production test flag."""
    override = (f"import os\nos.cpu_count = lambda: {count if system_count is None else system_count!r}\n"
                f"os.process_cpu_count = lambda: {count!r}\n")
    shim = repo.bin / "forge"
    source = shim.read_text("utf-8")
    shim.write_text(source.replace("from forge.cli import main",
        override + "from forge.cli import main"), "utf-8")
    # Inline Python test commands inherit PYTHONPATH, but do not use the Forge launcher.
    startup = repo.bin / "sitecustomize.py"
    startup.write_text((startup.read_text("utf-8") if startup.exists() else "") + override, "utf-8")


def machine_runners(repo, count: int | Path = 0):
    """Supply runner inventory to inline Python too; keep process identity queries real."""
    command = "tasklist" if os.name == "nt" else "ps"
    real = shutil.which(command)
    args = ["/FO", "CSV", "/NH"] if os.name == "nt" else ["-axo", "comm="]
    reading = (f"int(pathlib.Path({count.as_posix()!r}).read_text('utf-8'))"
               if isinstance(count, Path) else repr(count))
    worker = ('"Runner.Worker.exe","101","Console","1","100 K"\n'
              if os.name == "nt" else "/runner/bin/Runner.Worker\n")
    _install(repo.bin, command, f'''#!{sys.executable}
import pathlib, subprocess, sys
if sys.argv[1:] == {args!r}:
    sys.stdout.write({worker!r} * {reading})
else:
    sys.exit(subprocess.call([{json.dumps(real)}, *sys.argv[1:]], timeout=60))
''')

GH_STUB = """#!{python}
# Stub gh: records each call's arguments; the newest matching response answers.
import json, pathlib, subprocess, sys
from json_log import append_json
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
append_json(here / "gh-calls.jsonl", args)
if "--body-file" in args:  # the body as sent: the next call may rewrite the same file
    path = args[args.index("--body-file") + 1]
    body = sys.stdin.read() if path == "-" else pathlib.Path(path).read_text("utf-8")
    append_json(here / "gh-bodies.jsonl", body)
responses = here / "gh-responses.json"
for rule in reversed(json.loads(responses.read_text("utf-8")) if responses.exists() else []):
    if args[:len(rule["args"])] == rule["args"]:
        sys.stdout.write(rule["stdout"])
        sys.stderr.write(rule["stderr"])
        sys.exit(rule["exit"])
if args[:2] == ["pr", "view"] and args[-2] == "--json" and args[-1] in (
        "mergeable,headRefOid", "mergeable,headRefOid,number,headRefName"):
    # Ordinary close fixtures have a mergeable pull request on the real pushed head.
    # Explicit responses above still own API errors and conflicting/unknown states.
    head = subprocess.check_output(["git", "ls-remote", "--heads", "origin",
                                    "refs/heads/" + args[2]], text=True,
                                   stdin=subprocess.DEVNULL, timeout=60).split()[0]
    sys.stdout.write(json.dumps({{"mergeable": "MERGEABLE", "headRefOid": head,
                                 "number": 7, "headRefName": args[2]}}))
    sys.exit(0)
sys.stderr.write("stub gh: no response for: gh " + " ".join(args) + "\\n")
sys.exit(1)
"""


def _install(bin_dir: Path, name: str, text: str) -> None:
    path = bin_dir / name
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    if os.name == "nt":  # Windows finds commands by extension; a .cmd hands off to Python.
        (bin_dir / f"{name}.cmd").write_text(f'@"{sys.executable}" "%~dp0{name}" %*\n',
                                             encoding="utf-8")


def _sdk_ready(env: Path) -> bool:
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if (env / "forge-sdk-ready").is_file():
        try:
            return subprocess.run([python, "-I", "-c", "pass"], capture_output=True,
                                  timeout=10).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass  # A restart can remove the Python that this cached venv points to.
    return False


@contextmanager
def _cached_sdk(env: Path, pin: str):
    """Build privately; only the publisher may replace a cache that is still broken."""
    if _sdk_ready(env):
        yield None
        return
    env.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="building-", dir=env.parent) as folder:
        build = Path(folder)
        yield build
        (build / "forge-sdk-ready").write_text(pin + "\n", encoding="utf-8")
        # Keep the lock outside the directory being replaced, and never unlink it:
        # other workers must lock the same file even after a publication.
        with env.with_suffix(".lock").open("a+b") as lock:
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                if not _sdk_ready(env):
                    if env.exists():
                        shutil.rmtree(env)
                    build.rename(env)
            finally:
                if os.name == "nt":
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)


def _claude_sdk_env(data: Path, pin: str = "0.2.161") -> None:
    """The Claude Agent SDK's separate Python environment under this XDG_DATA_HOME."""
    env = data / "forge" / "claude-sdk" / f"claude-agent-sdk-{pin}"
    with _cached_sdk(env, pin) as build:
        if build is not None:
            subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(build)], check=True,
                           stdin=subprocess.DEVNULL, timeout=120)


def _install_claude_sdk(bin_dir: Path, data: Path) -> None:
    """A separate Python environment, with only the SDK's external edge replaced."""
    pin = "0.2.161"
    _claude_sdk_env(data, pin)
    package = bin_dir / "claude_agent_sdk"
    package.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "tests/stubs/claude_agent_sdk.py", package / "__init__.py")
    metadata = bin_dir / f"claude_agent_sdk-{pin}.dist-info"
    metadata.mkdir(exist_ok=True)
    (metadata / "METADATA").write_text(
        f"Metadata-Version: 2.1\nName: claude-agent-sdk\nVersion: {pin}\n", encoding="utf-8")


T = TypeVar("T")


_inside = threading.local()


def patient(action: Callable[[], T]) -> T:
    """Run a file action, retrying a PermissionError for up to five seconds: on Windows a process
    renaming a file over this one, or a moment late to exit, holds it briefly. An action inside
    another's retry runs once, since the outer one retries it."""
    if getattr(_inside, "retrying", False):
        return action()
    _inside.retrying = True
    try:
        for _ in range(100):
            try:
                return action()
            except PermissionError:
                time.sleep(0.05)
        return action()
    finally:
        _inside.retrying = False


def _patiently(owner: Any, name: str) -> None:
    real = getattr(owner, name)

    def retried(*args: Any, **kwargs: Any) -> Any:
        return patient(lambda: real(*args, **kwargs))
    setattr(owner, name, retried)


# Every test helper reads, writes, copies and deletes files through these, so each one waits out a
# lock. copytree copies each file with the retried copy2 instead of retrying the whole tree.
for _owner, _names in ((Path, ("read_text", "read_bytes", "write_text", "write_bytes", "touch",
                               "unlink", "rename", "replace", "chmod")),
                       (shutil, ("copy", "copy2", "copyfile", "move")),
                       (os, ("unlink", "remove", "rename", "replace", "chmod"))):
    for _name in _names:
        _patiently(_owner, _name)
_copytree = shutil.copytree


def _copy_tree(src: Any, dst: Any, *args: Any, **kwargs: Any) -> Any:
    if len(args) < 3:  # copytree passes copy_function by position to its subfolders
        kwargs.setdefault("copy_function", shutil.copy2)
    return _copytree(src, dst, *args, **kwargs)


shutil.copytree = _copy_tree


_rmtree = shutil.rmtree


def _remove_tree(path: Any, ignore_errors: bool = False, *args: Any, **kwargs: Any) -> Any:
    if not ignore_errors:
        return patient(lambda: _rmtree(path, ignore_errors, *args, **kwargs))
    # Best-effort cleanup must not wait five seconds for every read-only or locked file.
    nested = getattr(_inside, "retrying", False)
    _inside.retrying = True
    try:
        return _rmtree(path, ignore_errors, *args, **kwargs)
    finally:
        _inside.retrying = nested


shutil.rmtree = _pytest.tmpdir.rmtree = _remove_tree
_rm_error = _pytest.pathlib.on_rm_rf_error


def _skip_locked(func: Any, path: Any, excinfo: Any, **kwargs: Any) -> Any:
    try:
        error = excinfo if isinstance(excinfo, BaseException) else excinfo[1]
        if isinstance(error, PermissionError) and func in (os.unlink, os.remove):
            mode = os.lstat(path).st_mode
            if stat.S_ISREG(mode) and not mode & stat.S_IWUSR:
                # Windows Git objects need only their own read-only bit cleared.
                # Pytest's fallback chmods every ancestor for each object.
                try:
                    os.chmod(path, mode | stat.S_IWUSR)
                    func(path)
                    return True
                except PermissionError:
                    pass  # Retain pytest's parent-permission recovery when needed.
        return _rm_error(func, path, excinfo, **kwargs)
    except FileNotFoundError:
        return False
    except PermissionError:
        # Pytest already retries read-only files after chmod; a persistent lock is skipped.
        return False


_pytest.pathlib.on_rm_rf_error = _skip_locked

class Repo:
    """A git repo on main whose origin is a bare remote, with forge and a stub gh on PATH."""

    def __init__(self, path: Path, bin_dir: Path):
        self.path, self.bin = path, bin_dir

    def git(self, *args: str, cwd: Path | None = None) -> str:
        try:
            return subprocess.run(["git", *args], cwd=cwd or self.path, check=True, capture_output=True,
                                  text=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=60).stdout.strip()
        except subprocess.CalledProcessError as error:
            error.add_note(error.stdout + error.stderr)
            raise

    def forge(self, *args: str, input: str = "", cwd: Path | None = None,
              timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        """Run the real forge command; stdin is empty unless given. Windows gets four minutes: its
        heaviest commands (init, migrate, close) start hundreds of git processes, and on a hosted
        Windows runner under a parallel run's load one took past two minutes."""
        return subprocess.run([sys.executable, str(self.bin / "forge"), *args],
                              cwd=cwd or self.path, input=input, capture_output=True, text=True,
                              encoding="utf-8", timeout=timeout or (240 if os.name == "nt" else 60))

    def write(self, rel: str, text: str) -> Path:
        path = self.path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class StubGh:
    """Tell the stub gh what to answer, and read back the calls it got."""

    def __init__(self, bin_dir: Path):
        self.responses, self.log = bin_dir / "gh-responses.json", bin_dir / "gh-calls.jsonl"

    def respond(self, *args: str, stdout: str = "", stderr: str = "", exit: int = 0) -> None:
        """Answer any call starting with args. The newest matching response wins."""
        rules = json.loads(self.responses.read_text("utf-8")) if self.responses.exists() else []
        rules.append({"args": list(args), "stdout": stdout, "stderr": stderr, "exit": exit})
        self.responses.write_text(json.dumps(rules), encoding="utf-8")

    def calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text("utf-8").splitlines()]


@pytest.fixture(autouse=True)
def isolated_forge_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Every Forge subprocess must write its per-machine repo list inside this test's temp folder.
    monkeypatch.setenv("APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME",
                       str(tmp_path / "config"))


def _left(tmp_path: Path) -> list[str]:
    """This test's processes still running or stopped: every process a test starts names its temp
    folder in its command/environment or records its identity before it can outlive the worker."""
    recorded = []
    markers = [Path(folder, name) for folder, _, names in os.walk(tmp_path)  # skips vanished folders
               for name in names if name.endswith(".owned-process.json")]
    for marker in markers:
        from test_lanes_agents import alive

        try:
            process = json.loads(marker.read_text("utf-8"))
        except FileNotFoundError:  # its test removed it while this scan ran
            continue
        # Windows process creation times use 100-nanosecond ticks since 1601; Python 3.11's clock
        # there moves in 15.6 ms steps, so allow one step before the recorded time.
        before = (process["at_ns"] // 100 + 116444736000000000 + 160_000 if os.name == "nt"
                  else process["at_ns"] // 1000000000)
        if process["pid"] != os.getpid() and alive(process["pid"], before):
            recorded.append(f'{process["pid"]} {marker}')
    if os.name == "nt":
        return recorded
    listed = subprocess.run(["ps", "axeww", "-o", "pid=,stat=,command="], capture_output=True,
                            text=True, env={"PATH": "/bin:/usr/bin"}).stdout  # ps's own env is clean
    mark = f"{tmp_path}{os.sep}"
    return recorded + [" ".join(line.split()[:1] + line.split()[2:]) for line in listed.splitlines()
            if mark in line and not line.split()[1].startswith("Z")
            and int(line.split()[0]) != os.getpid()]


def _end_left(path: Path) -> list[str]:
    """Wait for the processes that name path to go, end any still there, and return those."""
    grace_seconds = float(os.environ.get("PYTEST_PROCESS_GRACE_SECONDS", "10"))
    for _ in range(int(grace_seconds * 2)):  # a process the test just ended may take a moment to go
        left = _left(path)
        if not left:
            return []
        time.sleep(0.5)
    for line in left:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", line.split()[0]],
                               capture_output=True, timeout=10)
            else:
                os.kill(int(line.split()[0]), signal.SIGKILL)  # SIGKILL ends a stopped process too
        except ProcessLookupError:
            pass
    for _ in range(20):
        if not _left(path):
            break
        time.sleep(0.05)
    return left


@pytest.fixture(autouse=True)
def no_process_left(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    # Autouse, so it runs its check after the test's own fixtures have cleaned up.
    yield
    left = _end_left(tmp_path)
    if left:
        pytest.fail(f"{request.node.name} left processes running: "
                    + "; ".join(line[:200] for line in left), pytrace=False)


def pytest_sessionfinish(session: pytest.Session) -> None:
    """At the end of the run, once more over every test's temp folder: a test whose worker crashed
    never reached its own check. Each folder is named after its test."""
    if hasattr(session.config, "workerinput"):  # the controller checks once
        return
    base = session.config._tmp_path_factory.getbasetemp()  # type: ignore[attr-defined]
    left = _end_left(base)
    if not left:
        return
    folder = re.compile(re.escape(f"{base}{os.sep}")
                        + rf"(?:popen-gw\d+{re.escape(os.sep)})?([^/\\\s]+)")
    report = session.config.pluginmanager.get_plugin("terminalreporter")
    report.line("")
    for line in left:
        found = folder.search(line)
        report.line(f"The test with temp folder {found[1] if found else base} left processes "
                    f"running: {line[:200]}")
    session.exitstatus = pytest.ExitCode.TESTS_FAILED


# The environment Forge reads at run time, pinned for every test so none inherits it from the
# shell, a git hook or the agent session running the suite:
# - Codex coordinates: CODEX_THREAD_ID is set and CLAUDECODE is unset. `forge read` needs a
#   coordinating app, and from Codex a cold read runs on the stub claude, as most tests expect.
#   A Codex round would run as the session's own subagent, so a test that builds on Codex through
#   the kit says so with the `claude_session` fixture; a test that needs no session deletes both.
# - No Forge run around it: every FORGE_ variable (worker marker, test budget, pinned release,
#   checkout forwarding, waits) is unset; a test that needs one sets it. FORGE_LIVE_CODEX stays:
#   it is the real-Codex opt-in, set only by the codex-smoke workflow.
# - No tool overrides: CODEX_BIN, CLAUDE_BIN and AUTOREVIEW are unset; a stub sets its own.
# - No outer git: every GIT_ variable is unset (they leak in when tests run inside a git hook);
#   the `repo` fixture gives git its own config.
# - Machine lanes: the forge shim reports an idle machine; `machine_cores` sets a core count.
# Time zones need no pin: Forge writes UTC times and runs `ps` with TZ=UTC itself.
@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # Outer test-selection flags must not change a client's own pytest command.
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    # The checkout launcher exposes src through PYTHONPATH; clients and released tools must not.
    monkeypatch.delenv("PYTHONPATH", raising=False)
    for name in list(os.environ):
        if name.startswith(("GIT_", "FORGE_")) and name != "FORGE_LIVE_CODEX" or name in (
                "CLAUDECODE", "CODEX_BIN", "CLAUDE_BIN", "AUTOREVIEW"):
            monkeypatch.delenv(name)
    # cmd.exe expands %CI% in a .cmd stub's arguments, case-insensitively: git's
    # --format=%x00%cI%x00 would reach git as %x00truex00 on CI runners.
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "thr-test-coordinator")


@pytest.fixture(scope="session")
def seed_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("seed-repo")
    remote, path = folder / "remote.git", folder / "repo"
    path.mkdir()
    (path / "README.md").write_text("# A test repo\n", encoding="utf-8")
    # Session fixtures run before per-test isolation. Ignore the host's Git config
    # and any outer hook/worktree variables while constructing this plain repo.
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    for args in (
        ["init", "-q", "--bare", "-b", "main", str(remote)],
        ["init", "-q", "-b", "main", str(path)],
        ["add", "README.md"],
        ["commit", "-q", "-m", "First commit"],
        ["remote", "add", "origin", str(remote)],
        ["push", "-q", "-u", "origin", "main"],
        ["remote", "set-head", "origin", "main"],
    ):
        subprocess.run(["git", "-c", "user.name=Forge Test", "-c",
                        "user.email=forge-test@example.com", "-c", "commit.gpgsign=false", *args],
                       cwd=path, env=env, check=True, capture_output=True,
                       stdin=subprocess.DEVNULL, timeout=60)
    # The stub Codex's accepted requests write these; a worker would not leave them uncommitted.
    (path / ".git" / "info" / "exclude").write_text("ran-stub-ask-*\n", encoding="utf-8")
    return folder


@pytest.fixture(scope="session")
def empty_claude_sdk(tmp_path_factory: pytest.TempPathFactory) -> Path:
    data = tmp_path_factory.mktemp("empty-claude-sdk")
    _claude_sdk_env(data)
    return data


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seed_repo: Path,
         empty_claude_sdk: Path) -> Repo:
    # A launcher's marker and test budget, again: a module fixture may set them as a launcher would.
    monkeypatch.delenv("FORGE_WORKER", raising=False)
    monkeypatch.delenv("FORGE_TEST_CPUS", raising=False)
    gitconfig = tmp_path / "gitconfig"
    # Wait for automatic GC and maintenance (which uses gc.autoDetach as its fallback) before
    # a helper removes a temporary clone; detached maintenance can still write its objects.
    gitconfig.write_text("[user]\n\tname = Forge Test\n\temail = forge-test@example.com\n"
                         "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n"
                         "[gc]\n\tautoDetach = false\n[core]\n\tlongpaths = true\n",
                         encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shutil.copyfile(ROOT / "tests/stubs/json_log.py", bin_dir / "json_log.py")
    _install(bin_dir, "forge", FORGE_SHIM.format(python=sys.executable, src=str(ROOT / "src")))
    _install(bin_dir, "gh", GH_STUB.format(python=sys.executable))
    # Sync manages Claude's user-scope plugins. Never let a command test touch
    # the developer's real plugin install or contact its marketplace.
    _install(bin_dir, "claude", f'''#!{sys.executable}
import sys
args = sys.argv[1:]
if args == ["--version"]:
    print("2.1.291 (Claude Code)")
elif args == ["plugin", "marketplace", "list", "--json"]:
    print('[{{"name":"forge"}}]')
elif args == ["plugin", "list", "--json"]:
    print('[{{"id":"forge@forge","scope":"user","enabled":true,"version":"1.2.6"}}]')
''')
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    data = tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    # Preserve the venv's interpreter links, but copy all writable SDK files.
    # Direct SDK setup/recovery callers still use _claude_sdk_env's fresh-build path.
    shutil.copytree(empty_claude_sdk, data, symlinks=True)
    _install_claude_sdk(bin_dir, data)
    monkeypatch.setenv("PYTHONPATH", str(bin_dir) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    # Host hooks find forge through uv's tool folders, so those name this one too.
    monkeypatch.setenv("XDG_BIN_HOME", str(bin_dir))
    monkeypatch.delenv("UV_TOOL_BIN_DIR", raising=False)

    remote, path = tmp_path / "remote.git", tmp_path / "repo"
    # copytree uses independent files, including Git objects; no clone hardlinks.
    shutil.copytree(seed_repo / "remote.git", remote)
    shutil.copytree(seed_repo / "repo", path)
    made = Repo(path, bin_dir)
    made.git("remote", "set-url", "origin", str(remote))
    return made


@pytest.fixture
def claude_session(repo: Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    """Claude Code coordinates instead: Codex workers run through the kit, a cold read on Codex."""
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")


@pytest.fixture
def gh(repo: Repo) -> StubGh:
    return StubGh(repo.bin)


def _payload(event: str, cwd: Path, tool: str | None, tool_input: dict[str, Any] | None,
             tool_response: dict[str, Any] | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"session_id": uuid.uuid4().hex, "cwd": str(cwd),
                               "transcript_path": str(cwd / "transcript.jsonl"),
                               "hook_event_name": event}
    if event == "SessionStart":
        payload["source"] = "startup"
    if tool:
        payload.update(tool_name=tool, tool_use_id=uuid.uuid4().hex, tool_input=tool_input or {})
    if tool_response is not None:
        payload["tool_response"] = tool_response
    return payload


Builder = Callable[..., dict[str, Any]]


@pytest.fixture
def isolated_codex_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "isolated-codex-home"
    home.mkdir(mode=0o700)
    monkeypatch.setenv("CODEX_HOME", str(home))
    return home


@pytest.fixture
def claude_payload(repo: Repo) -> Builder:
    """A Claude Code hook payload: claude_payload("PreToolUse", "Bash", {"command": "ls"})."""
    def build(event: str, tool: str | None = None, tool_input: dict[str, Any] | None = None,
              tool_response: dict[str, Any] | None = None, cwd: Path | None = None,
              ) -> dict[str, Any]:
        return _payload(event, cwd or repo.path, tool, tool_input, tool_response)
    return build


@pytest.fixture
def codex_payload(repo: Repo) -> Builder:
    """A Codex hook payload: codex_payload("PostToolUse", "request_user_input", {...}, {...})."""
    def build(event: str, tool: str | None = None, tool_input: dict[str, Any] | None = None,
              tool_response: dict[str, Any] | None = None, cwd: Path | None = None,
              ) -> dict[str, Any]:
        payload = _payload(event, cwd or repo.path, tool, tool_input, tool_response)
        payload["model"] = "gpt-5-codex"
        if tool:
            payload["turn_id"] = uuid.uuid4().hex
        return payload
    return build
