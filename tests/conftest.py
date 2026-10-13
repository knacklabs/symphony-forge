"""The test harness: a temp repo with a bare remote, a stub gh, and hook payload builders.

Tests drive the real `forge` command and look only at its output, git, the files a
human reads and the calls the stubs recorded (spec criterion 4).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, TypeVar

import pytest
import _pytest.pathlib
import _pytest.tmpdir

ROOT = Path(__file__).resolve().parents[1]
REAL_UV = shutil.which("uv")  # Capture before any test adds a command stub to PATH.
REAL_CODEX_HOME = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")

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
"""


def machine_cores(repo, count, system_count=None):
    """Report a machine's CPU count at the command boundary, without a production test flag."""
    shim = repo.bin / "forge"
    source = shim.read_text("utf-8")
    shim.write_text(source.replace("from forge.cli import main",
        f"import os\nos.cpu_count = lambda: {count if system_count is None else system_count!r}\n"
        f"os.process_cpu_count = lambda: {count!r}\nfrom forge.cli import main"), "utf-8")

GH_STUB = """#!{python}
# Stub gh: records each call's arguments; the newest matching response answers.
import json, pathlib, sys
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
with open(here / "gh-calls.jsonl", "a", encoding="utf-8") as calls:
    calls.write(json.dumps(args) + "\\n")
responses = here / "gh-responses.json"
for rule in reversed(json.loads(responses.read_text("utf-8")) if responses.exists() else []):
    if args[:len(rule["args"])] == rule["args"]:
        sys.stdout.write(rule["stdout"])
        sys.stderr.write(rule["stderr"])
        sys.exit(rule["exit"])
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
        return _rm_error(func, path, excinfo, **kwargs)
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
                                  text=True, encoding="utf-8").stdout.strip()
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
    for _ in range(20):  # a process the test just ended may take a moment to go
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
    for name in list(os.environ):
        if name.startswith(("GIT_", "FORGE_")) and name != "FORGE_LIVE_CODEX" or name in (
                "CLAUDECODE", "CODEX_BIN", "CLAUDE_BIN", "AUTOREVIEW"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("CODEX_THREAD_ID", "thr-test-coordinator")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
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
    # Host hooks find forge through uv's tool folders, so those name this one too.
    monkeypatch.setenv("XDG_BIN_HOME", str(bin_dir))
    monkeypatch.delenv("UV_TOOL_BIN_DIR", raising=False)

    remote, path = tmp_path / "remote.git", tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    made = Repo(path, bin_dir)
    # The stub Codex's accepted requests write these; a worker would not leave them uncommitted.
    (path / ".git" / "info" / "exclude").write_text("ran-stub-ask-*\n", encoding="utf-8")
    made.write("README.md", "# A test repo\n")
    made.git("add", "README.md")
    made.git("commit", "-q", "-m", "First commit")
    made.git("remote", "add", "origin", str(remote))
    made.git("push", "-q", "-u", "origin", "main")
    made.git("remote", "set-head", "origin", "main")
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
