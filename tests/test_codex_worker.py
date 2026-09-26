"""Codex workers: forge work builds a task or fix as one turn on a new, named Codex conversation.

The pinned SDK runs for real, without its 300 MB Codex program: the stub app-server in
tests/stubs/codex-app-server stands in for it, found through CODEX_BIN.
Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from conftest import _install
from test_task import story
from test_worker import calls as claude_calls, install_claude

STORY = "FORGE-WARM-1"
PIN = "0.156.1"
ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-26T10:00:00+00:00"
DECLINE = {"decision": "decline"}
KNOWN, UNKNOWN = "item/commandExecution/requestApproval", "item/stubFuture/requestSomething"
SOL = {"model": "gpt-6-sol", "effort": "medium", "subagents": "gpt-6-luna", "subagent_effort": "max"}
MODELS = {"build": SOL, "fix": SOL, "lite": {"model": "gpt-6-sol", "effort": "low"}}
# What [models.build] becomes on the new conversation: Codex's own names for those settings.
BUILD = {"model": "gpt-6-sol", "model_reasoning_effort": "medium",
         "agents.default_subagent_model": "gpt-6-luna",
         "agents.default_subagent_reasoning_effort": "max"}
MODELS_REFUSAL = ("forge.toml's [models] table is not usable: {}.\n"
                  "Next: ask your agent to fix forge.toml's [models] table\n")

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


def _toml(version: str, workers: str, models: dict[str, dict]) -> str:
    """A forge.toml with these workers and this [models] table."""
    lines = [f'version = "{version}"', f'workers = "{workers}"']
    for kind, keys in models.items():
        lines += ["", f"[models.{kind}]", *(f"{key} = {json.dumps(value)}" for key, value in keys.items())]
    return "\n".join(lines) + "\n"


def _codex_repo(repo, monkeypatch, sdk_data: Path) -> tuple[Path, Path]:
    """Codex workers with the models table, a project Codex trusts, story BOARD approved and
    BOARD/PAGE started. Returns the task's folder and the stub app-server's log."""
    _install(repo.bin, "codex-app-server",
             (ROOT / "tests" / "stubs" / "codex-app-server").read_text(encoding="utf-8"))
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    monkeypatch.setenv("FORGE_NOW", NOW)
    codex_home = repo.path.parent / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    repo.write("forge.toml", _toml(repo.forge("--version").stdout.split()[-1], "codex", MODELS))
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


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


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
    # Output to a Windows pipe starts in its legacy code page; here on every OS. Forge's output,
    # the names' "·" included, must still reach its reader as UTF-8.
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")

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
                "thr-stub-1", "stub codex: built it with", "$ touch ran-stub-ask-1 (declined)",
                "Changed web/board.py (declined)", "Codex ended the turn: completed"]
    log = (repo.path / ".git" / "forge" / "work-BOARD-PAGE.log").read_text(encoding="utf-8")
    for text in expected:
        assert text in built.stdout and text in log, text
    assert "Warning" not in log and "Traceback" not in log
    # A finished command's output follows it, its last 40 lines, so a failing test shows why; the
    # streamed deltas don't.
    run = log.split("$ pytest -q (failed)\n", 1)[1].splitlines()
    assert run[:2] == ["(… 5 earlier lines in Codex's own log)", "stub test line 6"]
    assert run[40] == "FAILED stub diagnostic" and "FAILED stub diagnostic" in built.stdout
    assert "stub test line 5\n" not in log and "stub delta chunk" not in log
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

    # An SDK whose handler moved: forge work refuses before it records any status, and before
    # it starts Codex at all.
    moved = tmp_path / "moved"
    moved.mkdir()
    (moved / "sitecustomize.py").write_text(MOVED, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(moved))
    head, before = repo.git("rev-parse", "HEAD", cwd=folder), len(_stub(calls))
    refused = repo.forge("work", "BOARD/PAGE")
    env = sdk_data / "forge" / "codex-sdk" / f"openai-codex-{PIN}"
    assert refused.stderr == (
        f"The Codex SDK in {env} should be openai-codex {PIN}, openai-codex-cli-bin {PIN}, "
        f"codex-cli {PIN}, but its Python says: the SDK client has no _approval_handler for Forge "
        "to replace\nNext: forge doctor --fix\n")
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head
    assert len(_stub(calls)) == before


def test_3_models_per_kind(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    version = repo.forge("--version").stdout.split()[-1]
    toml = folder / "forge.toml"
    head = repo.git("rev-parse", "HEAD", cwd=folder)

    # A table that isn't right, in the item's own checkout, refuses and says what to fix, before
    # any status or any Codex call. An unused kind (fix, here) is checked too.
    lite = MODELS["lite"]
    for models, problem in (
            ({**MODELS, "lite": {**lite, "sandbox": "read-only"}}, "models.lite can't set sandbox"),
            ({**MODELS, "lite": {**lite, "effort": 3}}, "models.lite.effort must be a string"),
            ({**MODELS, "lite": {"model": "gpt-6-sol"}}, "models.lite has no effort"),
            ({**MODELS, "fix": {**lite, "subagents": "gpt-6-luna"}},
             "models.fix sets only one of subagents and subagent_effort; set both or neither"),
            ({**MODELS, "debug": lite},
             "debug is not a kind of work; the kinds are build, fix, lite, grill and review"),
            ({"lite": lite}, "it has no [models.build], which this work uses")):
        toml.write_text(_toml(version, "codex", models), encoding="utf-8")
        refused = repo.forge("work", "BOARD/PAGE")
        assert refused.stderr == MODELS_REFUSAL.format(problem), refused.stderr
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and not calls.exists()

    # The kind's models, subagents included, reach the new conversation as its settings. They are
    # read again on every call, from the item's checkout; the caller's forge.toml is another. The
    # second call is a fix round, on the fix kind's models; this stub can't resume a conversation,
    # so it starts a new one.
    toml.write_text(_toml(version, "codex", MODELS), encoding="utf-8")
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _sent(calls, "thread/start")[-1]["config"] == BUILD
    nova = {"model": "gpt-6-nova", "effort": "high"}
    toml.write_text(_toml(version, "codex", {"build": nova, "fix": nova}), encoding="utf-8")
    again = repo.forge("work", "BOARD/PAGE")
    assert again.returncode == 0, again.stdout + again.stderr
    config = {"model": "gpt-6-nova", "model_reasoning_effort": "high"}
    assert _sent(calls, "thread/start")[-1]["config"] == config
    assert f"stub codex: built it with {json.dumps(config, sort_keys=True)}" in again.stdout
    assert "gpt-6-nova" not in (repo.path / "forge.toml").read_text(encoding="utf-8")

    # A fix uses the lite kind.
    assert repo.forge("fix", "start", "Fix the login typo", "--done", "It says Log in").returncode == 0
    assert repo.forge("work", "fix-the-login-typo").returncode == 0
    assert _sent(calls, "thread/start")[-1]["config"] == {"model": "gpt-6-sol",
                                                          "model_reasoning_effort": "low"}

    # Claude workers take the kind's model and effort, and refuse subagents.
    claude = install_claude(repo)
    toml.write_text(_toml(version, "claude", MODELS), encoding="utf-8")
    refused = repo.forge("work", "BOARD/PAGE")
    assert refused.stderr == MODELS_REFUSAL.format(
        "Claude workers take model and effort, so [models.build] can't set subagents")
    assert claude_calls(claude) == []
    toml.write_text(_toml(version, "claude", {"build": {"model": "opus", "effort": "high"}}),
                    encoding="utf-8")
    built = repo.forge("work", "BOARD/PAGE")
    assert built.returncode == 0, built.stdout + built.stderr
    assert claude_calls(claude)[-1]["args"][:5] == ["-p", "--model", "opus", "--effort", "high"]


def test_4_turn_log(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    turns = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD" / "PAGE.log"
    work_log = repo.path / ".git" / "forge" / "work-BOARD-PAGE.log"
    started = {"conversation": "thr-stub-1", "turn": "turn-stub-1", "kind": "Build",
               "started": NOW}
    ended = {"conversation": "thr-stub-1", "turn": "turn-stub-1", "kind": "Build",
             "continued": False, "fresh_start": "first turn", "status": "completed",
             "started": NOW, "ended": NOW, "input_tokens": 1200, "cached_input_tokens": 1000,
             "output_tokens": 300}

    # A "started" line when the turn starts, and the end line when Codex reports the end. The
    # driver reports the Codex process first, and none is left once forge work returns.
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _lines(turns) == [started, ended]
    pid = int(re.fullmatch(r"Codex app-server: process (\d+)",
                           work_log.read_text("utf-8").splitlines()[1])[1])
    stub = [call["pid"] for call in _stub(calls) if "pid" in call][-1]
    # On Windows the stub runs through its .cmd shim, so the process the client started, and the
    # driver reports, is the shim's cmd.exe rather than the stub; the real Codex is its own .exe.
    assert pid == stub if os.name != "nt" else pid not in (stub, os.getpid())
    assert not _running(pid)

    # A fix's turn log sits in its own folder.
    assert repo.forge("fix", "start", "Fix the login typo", "--done", "It says Log in").returncode == 0
    assert repo.forge("work", "fix-the-login-typo").returncode == 0
    fix = repo.path / ".git" / "forge" / "threads" / "fix" / "fix-the-login-typo.log"
    assert [line["kind"] for line in _lines(fix)] == ["Lite", "Lite"]

    # A failed turn is logged as Codex reported it, with blank tokens when it reports none, and
    # forge work stops with the log's path. It is a fix round, and this stub can't resume the
    # conversation, so it started a new one and says why.
    monkeypatch.setenv("STUB_CODEX_STATUS", "failed")
    monkeypatch.setenv("STUB_CODEX_NO_USAGE", "1")
    failed = repo.forge("work", "BOARD/PAGE")
    assert failed.stderr == (f"The Codex turn didn't complete: Codex reported it failed; its log is "
                             f"{work_log}.\nNext: forge work BOARD/PAGE\n")
    assert "Codex ended the turn: failed (stub codex: the model gave up)" in failed.stdout
    started, ended = {**started, "kind": "Fix"}, {
        **ended, "kind": "Fix",
        "fresh_start": "Codex couldn't resume its conversation: stub: no thread/resume"}
    assert _lines(turns)[2:] == [started, {**ended, "status": "failed", "input_tokens": None,
                                           "cached_input_tokens": None, "output_tokens": None}]

    # When Codex goes away before the turn ends, the turn log keeps only its "started" line:
    # Forge never writes a status Codex didn't report.
    monkeypatch.setenv("STUB_CODEX_STATUS", "vanish")
    vanished = repo.forge("work", "BOARD/PAGE")
    assert vanished.stderr == (f"The Codex turn didn't complete: Codex never reported its end; its "
                               f"log is {work_log}.\nNext: forge work BOARD/PAGE\n")
    assert _lines(turns)[4:] == [started]
    reported = [int(line.rpartition(" ")[2]) for log in work_log.parent.glob("work-*.log")
                for line in log.read_text("utf-8").splitlines()
                if line.startswith("Codex app-server: process ")]
    assert len(reported) == 4 and not any(_running(pid) for pid in reported)
