"""Codex workers: forge work builds a task or fix as one turn on a new, named Codex conversation.

The pinned SDK runs for real, without its 300 MB Codex program: the stub app-server in
tests/stubs/codex-app-server stands in for it, found through CODEX_BIN.
Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from conftest import _install
from test_task import story

STORY = "FORGE-WARM-1"
PIN = "0.156.1"
ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-26T10:00:00+00:00"
DECLINE = {"decision": "decline"}
KNOWN, UNKNOWN = "item/commandExecution/requestApproval", "item/stubFuture/requestSomething"

# The SDK finds its Codex program through the codex_cli_bin package, which the test environment
# replaces with this: the program is whatever CODEX_BIN names, here the stub app-server.
PROGRAM = """import os
from pathlib import Path


def bundled_codex_path():
    return Path(os.environ["CODEX_BIN"])
"""

# A later SDK that keeps its approval handler under another name. On PYTHONPATH, every Python
# loads it; only the SDK's has openai_codex.
MOVED = """try:
    from openai_codex import client
except ImportError:
    pass
else:
    start = client.CodexClient.__init__

    def moved(self, *args, **kwargs):
        start(self, *args, **kwargs)
        self._request_handler = self.__dict__.pop("_approval_handler")

    client.CodexClient.__init__ = moved
"""


@pytest.fixture(scope="session")
def sdk_data(pytestconfig: pytest.Config) -> Path:
    """An XDG_DATA_HOME holding Forge's SDK environment: the pinned SDK and the libraries its
    METADATA requires, but not its Codex program. Built once, then kept in pytest's cache."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is missing, so the Codex SDK test environment can't be built")
    data = pytestconfig.cache.mkdir(f"codex-sdk-{PIN}")
    env = data / "forge" / "codex-sdk" / f"openai-codex-{PIN}"
    if (env / "forge-sdk-ready").is_file():
        return data
    build = env.with_name(f"building-{uuid.uuid4().hex}")  # parallel workers each build their own
    build.parent.mkdir(parents=True, exist_ok=True)
    python = build / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([uv, "venv", "-q", "--python", "3.11", str(build)], check=True)
    subprocess.run([uv, "pip", "install", "-q", "--python", str(python), "--no-deps",
                    f"openai-codex=={PIN}"], check=True)
    site = Path(subprocess.run([python, "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
                               capture_output=True, text=True, check=True).stdout.strip())
    metadata = (next(site.glob("openai_codex-*.dist-info")) / "METADATA").read_text(encoding="utf-8")
    needs = [line.split(":", 1)[1].strip() for line in metadata.splitlines()
             if line.startswith("Requires-Dist:") and "openai-codex-cli-bin" not in line]
    subprocess.run([uv, "pip", "install", "-q", "--python", str(python), *needs], check=True)
    (site / "codex_cli_bin.py").write_text(PROGRAM, encoding="utf-8")
    info = site / f"openai_codex_cli_bin-{PIN}.dist-info"
    info.mkdir()
    (info / "METADATA").write_text(f"Name: openai-codex-cli-bin\nVersion: {PIN}\n", encoding="utf-8")
    (build / "forge-sdk-ready").write_text(f"{PIN}\n", encoding="utf-8")
    try:
        build.rename(env)
    except OSError:  # another worker got there first
        shutil.rmtree(build, ignore_errors=True)
    return data


def _codex_repo(repo, monkeypatch, sdk_data: Path) -> tuple[Path, Path]:
    """Codex workers on, story BOARD approved and BOARD/PAGE started. Returns the task's folder
    and the stub app-server's log."""
    _install(repo.bin, "codex-app-server",
             (ROOT / "tests" / "stubs" / "codex-app-server").read_text(encoding="utf-8"))
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    monkeypatch.setenv("FORGE_NOW", NOW)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "codex"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge with Codex workers")
    repo.git("push", "-q", "origin", "main")
    story(repo)
    started = repo.forge("task", "start", "BOARD/PAGE")
    assert started.returncode == 0, started.stderr
    return repo.path.parent / "repo-BOARD-PAGE", repo.bin / "codex-app-server.jsonl"


def _stub(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []


def _sent(log: Path, method: str) -> list[dict]:
    """The params of each call the SDK made to the stub app-server with this method."""
    return [call["params"] for call in _stub(log) if call.get("method") == method]


def _running(pid: int) -> bool:
    if os.name == "nt":
        listed = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True,
                                text=True).stdout
        return str(pid) in listed.split()
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_1_codex_builds_on_a_named_conversation(repo, monkeypatch, sdk_data, tmp_path):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)

    # Without the pinned SDK, forge work refuses before it records any status.
    head = repo.git("rev-parse", "HEAD", cwd=folder)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "no-sdk"))
    missing = repo.forge("work", "BOARD/PAGE")
    env = tmp_path / "no-sdk" / "forge" / "codex-sdk" / f"openai-codex-{PIN}"
    assert missing.stderr == (f"The Codex SDK {PIN} isn't installed in {env}.\n"
                              "Next: forge doctor --fix\n")
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and not calls.exists()
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))

    built = repo.forge("work", "BOARD/PAGE")
    assert built.returncode == 0, built.stdout + built.stderr

    # One new conversation in the task's folder, with full access and approvals "never", named
    # after the task; one turn with the same, carrying the same brief a Claude worker gets.
    [start] = _sent(calls, "thread/start")
    assert Path(start["cwd"]).resolve() == folder.resolve()
    assert (start["sandbox"], start["approvalPolicy"]) == ("danger-full-access", "never")
    assert [named["name"] for named in _sent(calls, "thread/name/set")] == [
        "Build · BOARD/PAGE · The page"]
    [turn] = _sent(calls, "turn/start")
    assert (turn["sandboxPolicy"], turn["approvalPolicy"]) == ({"type": "dangerFullAccess"}, "never")
    brief = turn["input"][0]["text"]
    assert "You are the worker." in brief and "| PAGE | The page | The board page |" in brief

    # Progress shows in the terminal and in the work log, and the task is working.
    expected = ["Codex app-server: process", 'Codex conversation "Build · BOARD/PAGE · The page": '
                "thr-stub-1", "stub codex: built it with null", "$ touch ran-stub-ask-1 (declined)",
                "Changed web/board.py (declined)", "Codex ended the turn: completed"]
    log = (repo.path / ".git" / "forge" / "work-BOARD-PAGE.log").read_text(encoding="utf-8")
    for text in expected:
        assert text in built.stdout and text in log, text
    assert "Warning" not in log and "Traceback" not in log
    state = json.loads((folder / ".factory/stories/BOARD/tasks/PAGE.json").read_text("utf-8"))
    assert state["status"] == "working"
    assert repo.git("status", "--porcelain", "--ignored", cwd=folder) == ""

    # A fix gets a Lite conversation named after the fix and its why.
    fixed = repo.forge("fix", "start", "Fix the login typo", "--done", "The login page says Log in")
    assert fixed.returncode == 0, fixed.stderr
    built = repo.forge("work", "fix-the-login-typo")
    assert built.returncode == 0, built.stdout + built.stderr
    assert _sent(calls, "thread/name/set")[-1]["name"] == (
        "Lite · fix-the-login-typo · Fix the login typo")
    assert "Why: Fix the login typo" in _sent(calls, "turn/start")[-1]["input"][0]["text"]


def test_2_every_request_is_declined(repo, monkeypatch, sdk_data, tmp_path):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    built = repo.forge("work", "BOARD/PAGE")
    assert built.returncode == 0, built.stdout + built.stderr

    # The stub asked to run a command and sent a method no SDK knows: both got a decline, and
    # neither ran. Each decline is logged.
    answers = [(call["answered"], call["result"], call["ran"]) for call in _stub(calls)
               if "answered" in call]
    assert answers == [(KNOWN, DECLINE, False), (UNKNOWN, DECLINE, False)]
    assert not list(folder.glob("ran-*"))
    log = (repo.path / ".git" / "forge" / "work-BOARD-PAGE.log").read_text(encoding="utf-8")
    for method in (KNOWN, UNKNOWN):
        assert f"Declined Codex's request {method}" in built.stdout
        assert f"Declined Codex's request {method}" in log

    # An SDK whose handler moved: Codex starts, but forge work refuses before any conversation.
    moved = tmp_path / "moved"
    moved.mkdir()
    (moved / "sitecustomize.py").write_text(MOVED, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(moved))
    before = len(_stub(calls))
    refused = repo.forge("work", "BOARD/PAGE")
    assert refused.returncode == 1
    assert refused.stderr == ("Forge couldn't put in its handler that declines every Codex request, "
                              "so it started no conversation.\nNext: forge doctor --fix\n")
    after = [call.get("method") for call in _stub(calls)[before:]]
    assert "initialize" in after and "thread/start" not in after and "turn/start" not in after


def test_3_settings_from_the_checkout(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    settings = folder / ".codex" / "build.config.toml"
    settings.parent.mkdir()
    head = repo.git("rev-parse", "HEAD", cwd=folder)

    # A key outside the three, or a file that isn't TOML, refuses before any status commit or Codex.
    settings.write_text('model = "gpt-test"\nsandbox_mode = "read-only"\n', encoding="utf-8")
    refused = repo.forge("work", "BOARD/PAGE")
    assert refused.stderr == (
        ".codex/build.config.toml may set only model, model_reasoning_effort and model_verbosity, "
        "but it sets sandbox_mode.\nNext: remove sandbox_mode from .codex/build.config.toml\n")
    settings.write_text("model = \n", encoding="utf-8")
    broken = repo.forge("work", "BOARD/PAGE")
    assert broken.returncode == 1
    assert broken.stderr.startswith(".codex/build.config.toml is not valid TOML: ")
    assert broken.stderr.endswith(".\nNext: fix .codex/build.config.toml\n")
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head
    assert not calls.exists()

    # The three keys reach the new conversation as its settings, read again on every call.
    settings.write_text('model = "gpt-test"\nmodel_reasoning_effort = "high"\n'
                        'model_verbosity = "low"\n', encoding="utf-8")
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _sent(calls, "thread/start")[-1]["config"] == {
        "model": "gpt-test", "model_reasoning_effort": "high", "model_verbosity": "low"}
    settings.write_text('model = "gpt-other"\n', encoding="utf-8")
    again = repo.forge("work", "BOARD/PAGE")
    assert again.returncode == 0, again.stdout + again.stderr
    assert _sent(calls, "thread/start")[-1]["config"] == {"model": "gpt-other"}
    assert 'stub codex: built it with {"model": "gpt-other"}' in again.stdout
    settings.unlink()
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert "config" not in _sent(calls, "thread/start")[-1]

    # A fix reads the Lite file in its own checkout.
    assert repo.forge("fix", "start", "Fix the login typo", "--done", "It says Log in").returncode == 0
    lite = repo.path.parent / "repo-fix-fix-the-login-typo" / ".codex" / "lite.config.toml"
    lite.parent.mkdir()
    lite.write_text('model_reasoning_effort = "low"\n', encoding="utf-8")
    assert repo.forge("work", "fix-the-login-typo").returncode == 0
    assert _sent(calls, "thread/start")[-1]["config"] == {"model_reasoning_effort": "low"}


def test_4_turn_log(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    turns = repo.path / ".git" / "forge" / "threads" / "BOARD-PAGE.log"
    work_log = repo.path / ".git" / "forge" / "work-BOARD-PAGE.log"
    started = {"turn": "turn-stub-1", "kind": "Build", "started": NOW}
    ended = {**started, "continued": False, "status": "completed", "ended": NOW,
             "input_tokens": 1200, "cached_input_tokens": 1000, "output_tokens": 300}

    # A "started" line when the turn starts, and the end line when Codex reports the end. The
    # driver reports the Codex process first, and none is left once forge work returns.
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert [json.loads(line) for line in turns.read_text("utf-8").splitlines()] == [started, ended]
    pids = [call["pid"] for call in _stub(calls) if "pid" in call]
    assert work_log.read_text("utf-8").splitlines()[1] == f"Codex app-server: process {pids[-1]}"
    assert not _running(pids[-1])

    # A failed turn is logged as Codex reported it, with blank tokens when it reports none, and
    # forge work stops with the log's path.
    monkeypatch.setenv("STUB_CODEX_STATUS", "failed")
    monkeypatch.setenv("STUB_CODEX_NO_USAGE", "1")
    failed = repo.forge("work", "BOARD/PAGE")
    assert failed.returncode == 1
    assert failed.stderr == (f"The Codex turn didn't complete: Codex reported it failed; its log is "
                             f"{work_log}.\nNext: forge work BOARD/PAGE\n")
    assert "Codex ended the turn: failed (stub codex: the model gave up)" in failed.stdout
    lines = [json.loads(line) for line in turns.read_text("utf-8").splitlines()]
    assert lines[2:] == [started, {**ended, "status": "failed", "input_tokens": None,
                                   "cached_input_tokens": None, "output_tokens": None}]

    # When Codex goes away before the turn ends, the turn log keeps only its "started" line:
    # Forge never writes a status Codex didn't report.
    monkeypatch.setenv("STUB_CODEX_STATUS", "vanish")
    vanished = repo.forge("work", "BOARD/PAGE")
    assert vanished.returncode == 1
    assert vanished.stderr.startswith("The Codex turn didn't complete: the driver stopped with "
                                      "exit code 1 before Codex reported its end; its log is ")
    assert [json.loads(line) for line in turns.read_text("utf-8").splitlines()][4:] == [started]
    pids = [call["pid"] for call in _stub(calls) if "pid" in call]
    assert len(pids) == 3 and not any(_running(pid) for pid in pids)
