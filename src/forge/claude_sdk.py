"""The pinned Claude Agent SDK lives in its own Python environment, never in Forge's."""
from __future__ import annotations

import os
from pathlib import Path
import shutil

from forge import repo, sync

SDK_PIN = "0.2.161"
READY = "forge-sdk-ready"
TURN = Path(__file__).with_name("claude_turn.py")
PROBE = ("import importlib.metadata as m; from claude_agent_sdk import ClaudeAgentOptions, query; "
         "ClaudeAgentOptions(model='sonnet', effort='medium', session_id=None, resume=None); "
         "print(m.version('claude-agent-sdk'))")


def sdk_env() -> Path:
    data = (os.environ.get("XDG_DATA_HOME") or os.environ.get("LOCALAPPDATA")
            or Path.home() / ".local" / "share")
    return Path(data) / "forge" / "claude-sdk" / f"claude-agent-sdk-{SDK_PIN}"


def python() -> Path:
    return sdk_env() / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def sdk_problem() -> str:
    """A single sentence explaining why the pinned environment cannot drive a turn."""
    env = sdk_env()
    if not python().is_file() or sync.read(env / READY).strip() != SDK_PIN:
        return f"The Claude Agent SDK {SDK_PIN} isn't installed in {env}."
    done = repo.run(str(python()), "-c", PROBE)
    said = (done.stdout.strip() or done.stderr.strip()
            or f"it exited with status {done.returncode} without output").splitlines()[-1]
    if done.returncode or said != SDK_PIN:
        return f"The Claude Agent SDK in {env} should be {SDK_PIN}, but its Python says: {said}"
    return ""


def install() -> None:
    """Write the ready marker only after uv installs the pinned SDK successfully."""
    env = sdk_env()
    print(f"Installing the Claude Agent SDK {SDK_PIN} into {env} with uv.", flush=True)
    (env / READY).unlink(missing_ok=True)
    shutil.rmtree(env, ignore_errors=True)
    env.parent.mkdir(parents=True, exist_ok=True)
    for step in (["venv", "--python", "3.11", str(env)],
                 ["pip", "install", "--python", str(python()), f"claude-agent-sdk=={SDK_PIN}"]):
        done = repo.run("uv", *step)
        if done.returncode:
            said = (done.stderr or done.stdout or f"exit code {done.returncode}").strip()
            repo.refuse(("uv {step} failed while installing the Claude Agent SDK: {said}",
                         "forge doctor --fix"), step=step[0], said=said)
    (env / READY).write_text(SDK_PIN + "\n", encoding="utf-8")
    print(f"Installed the Claude Agent SDK {SDK_PIN} in {env}.")
