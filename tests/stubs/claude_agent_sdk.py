"""Anthropic's SDK edge, without a model or the Claude program."""
import asyncio
import dataclasses
import json
import os
from pathlib import Path
import subprocess
import sys


@dataclasses.dataclass
class ClaudeAgentOptions:
    model: str | None = None
    effort: str | None = None
    session_id: str | None = None
    resume: str | None = None
    cwd: str | None = None
    cli_path: str | None = None
    permission_mode: str | None = None
    add_dirs: list = dataclasses.field(default_factory=list)
    env: dict = dataclasses.field(default_factory=dict)
    system_prompt: dict | None = None
    setting_sources: list | None = None
    stderr: object = None


@dataclasses.dataclass
class SystemMessage:
    subtype: str
    data: dict


@dataclasses.dataclass
class TextBlock:
    text: str


@dataclasses.dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict


@dataclasses.dataclass
class AssistantMessage:
    content: list
    model: str


@dataclasses.dataclass
class ResultMessage:
    subtype: str = "success"
    num_turns: int = 1
    is_error: bool = False
    session_id: str = ""
    result: str | None = None
    errors: list[str] | None = None
    usage: dict = dataclasses.field(default_factory=lambda: {
        "input_tokens": 10, "output_tokens": 5})


async def query(*, prompt, options):
    here = Path(__file__).resolve().parent.parent
    values = {key: value for key, value in vars(options).items() if key != "stderr"}
    log = here / "claude-sdk-calls.jsonl"
    session = options.resume or options.session_id
    with log.open("a", encoding="utf-8") as out:
        out.write(json.dumps({"options": values, "prompt": prompt, "cwd": os.getcwd(),
                              "worker": os.environ.get("FORGE_WORKER"),
                              "session_id": session}) + "\n")
    store = here / "claude-sdk-sessions.json"
    legacy = here / "claude-sessions.json"
    source = store if store.exists() else legacy
    sessions = json.loads(source.read_text("utf-8")) if source.exists() else {}
    if options.resume and session not in sessions:
        missing = f"No conversation found with session ID: {session}"
        if os.environ.get("STUB_CLAUDE_LOST_ERRORS"):
            yield ResultMessage(subtype="error_during_execution", is_error=True,
                                num_turns=0, result=None,
                                errors=["Diagnostic before the error", missing])
        else:
            options.stderr(missing)
        raise RuntimeError("Resume failed")
    sessions[session] = os.getcwd()
    store.write_text(json.dumps(sessions), encoding="utf-8")
    yield SystemMessage("init", {"session_id": session, "model": options.model})
    if os.environ.get("STUB_CLAUDE_SDK_HOLD"):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
        try:
            Path(os.environ["STUB_CLAUDE_SDK_STARTED"]).write_text(
                json.dumps({"driver": os.getpid(), "child": child.pid}), encoding="utf-8")
            while not Path(os.environ["STUB_CLAUDE_SDK_HOLD"]).exists():
                await asyncio.sleep(0.01)
        finally:
            child.terminate()
            child.wait()
    if os.environ.get("STUB_CLAUDE_LEAVE"):
        Path(os.environ["STUB_CLAUDE_LEAVE"]).write_text("half done\n", encoding="utf-8")
    if len(log.read_text("utf-8").splitlines()) >= int(
            os.environ.get("STUB_CLAUDE_COMMIT_FROM") or 0) > 0:
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Worker round"], check=True)
    yield AssistantMessage([TextBlock("SDK worker output")], options.model)
    yield ResultMessage(session_id=session, result=os.environ.get(
        "STUB_CLAUDE_RESULT", "stub claude: built it\n"))
    status = int(os.environ.get("STUB_CLAUDE_EXIT", "0"))
    if status:
        sys.exit(status)
