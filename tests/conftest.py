"""The test harness: a temp repo with a bare remote, a stub gh, and hook payload builders.

Tests drive the real `forge` command and look only at its output, git, the files a
human reads and the calls the stubs recorded (spec criterion 4).
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parents[1]
REAL_CODEX_HOME = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")

# `forge` on PATH runs this checkout's src/forge, whatever else is installed.
FORGE_SHIM = """#!{python}
import sys
sys.path.insert(0, {src!r})
from forge.cli import main
sys.exit(main())
"""

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


class Repo:
    """A git repo on main whose origin is a bare remote, with forge and a stub gh on PATH."""

    def __init__(self, path: Path, bin_dir: Path):
        self.path, self.bin = path, bin_dir

    def git(self, *args: str, cwd: Path | None = None) -> str:
        return subprocess.run(["git", *args], cwd=cwd or self.path, check=True, capture_output=True,
                              text=True, encoding="utf-8").stdout.strip()

    def forge(self, *args: str, input: str = "", cwd: Path | None = None,
              ) -> subprocess.CompletedProcess[str]:
        """Run the real forge command; stdin is empty unless given. Windows gets two minutes: its
        heaviest commands (init, migrate, close) start hundreds of git processes, and starting a
        process there under a parallel run's load took one past a minute."""
        return subprocess.run([sys.executable, str(self.bin / "forge"), *args],
                              cwd=cwd or self.path, input=input, capture_output=True, text=True,
                              encoding="utf-8", timeout=120 if os.name == "nt" else 60)

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
    folder in its command or its environment, which holds the XDG_CONFIG_HOME set above."""
    listed = subprocess.run(["ps", "axeww", "-o", "pid=,stat=,command="], capture_output=True,
                            text=True, env={"PATH": "/bin:/usr/bin"}).stdout  # ps's own env is clean
    mark = f"{tmp_path}{os.sep}"
    return [" ".join(line.split()[:1] + line.split()[2:]) for line in listed.splitlines()
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
            os.kill(int(line.split()[0]), signal.SIGKILL)  # SIGKILL ends a stopped process too
        except ProcessLookupError:
            pass
    return left


@pytest.fixture(autouse=True)
def no_process_left(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    # Autouse, so it runs its check after the test's own fixtures have cleaned up.
    yield
    if os.name == "nt":  # ponytail: no ps on Windows; add a process-tree walk if leaks show there
        return
    left = _end_left(tmp_path)
    if left:
        pytest.fail(f"{request.node.name} left processes running: "
                    + "; ".join(line[:200] for line in left), pytrace=False)


def pytest_sessionfinish(session: pytest.Session) -> None:
    """At the end of the run, once more over every test's temp folder: a test whose worker crashed
    never reached its own check. Each folder is named after its test."""
    if os.name == "nt" or hasattr(session.config, "workerinput"):  # the controller checks once
        return
    base = session.config._tmp_path_factory.getbasetemp()  # type: ignore[attr-defined]
    left = _end_left(base)
    if not left:
        return
    folder = re.compile(re.escape(f"{base}{os.sep}") + r"(?:popen-gw\d+/)?([^/\s]+)")
    report = session.config.pluginmanager.get_plugin("terminalreporter")
    report.line("")
    for line in left:
        found = folder.search(line)
        report.line(f"The test with temp folder {found[1] if found else base} left processes "
                    f"running: {line[:200]}")
    session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
    for name in list(os.environ):  # GIT_DIR and friends leak in when tests run inside a git hook.
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)
    monkeypatch.delenv("CLAUDECODE", raising=False)  # set when tests run under Claude Code
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = Forge Test\n\temail = forge-test@example.com\n"
                         "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n",
                         encoding="utf-8")
    # The cold read runs on the family that isn't coordinating, which Forge tells from the variable
    # each app sets. Tests run as if Codex coordinates, so a read runs on the stub claude.
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "thr-test-coordinator")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install(bin_dir, "forge", FORGE_SHIM.format(python=sys.executable, src=str(ROOT / "src")))
    _install(bin_dir, "gh", GH_STUB.format(python=sys.executable))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    # Host hooks find forge through uv's tool folders, so those name this one too.
    monkeypatch.setenv("XDG_BIN_HOME", str(bin_dir))
    monkeypatch.delenv("UV_TOOL_BIN_DIR", raising=False)

    remote, path = tmp_path / "remote.git", tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    made = Repo(path, bin_dir)
    made.write("README.md", "# A test repo\n")
    made.git("add", "README.md")
    made.git("commit", "-q", "-m", "First commit")
    made.git("remote", "add", "origin", str(remote))
    made.git("push", "-q", "-u", "origin", "main")
    made.git("remote", "set-head", "origin", "main")
    return made


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
