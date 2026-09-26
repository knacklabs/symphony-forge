"""Codex workers, Forge's side: the pinned Codex SDK in its own environment, checked and installed,
a kind's models as Codex settings, and one turn run through codex_turn.py.

Forge never imports the SDK. It runs the environment's own Python to probe it and to drive a turn,
so the SDK and the Codex program it bundles (about 300 MB) stay out of Forge's own install.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from forge import repo, sync

# The one SDK version Forge drives. Moving it is a deliberate change that reruns the contract and
# smoke tests.
SDK_PIN = "0.156.1"
# Written last by the install, so a half-finished install never looks ready.
READY = "forge-sdk-ready"
# Loads the SDK and makes its client, which starts no server, to see it has the approval handler
# Forge replaces. Then runs its bundled Codex program with --version (a missing program, a failing
# one or a hang raises), and prints both package versions and what the program said.
PROBE = ("import importlib.metadata as m, subprocess, sys, openai_codex, openai_codex.client, "
         "codex_cli_bin; "
         "hasattr(openai_codex.client.CodexClient(), '_approval_handler') or "
         "sys.exit('the SDK client has no _approval_handler for Forge to replace'); "
         "said = subprocess.run([codex_cli_bin.bundled_codex_path(), '--version'], "
         "capture_output=True, text=True, timeout=30, check=True).stdout.split(); "
         "print(*(f'{name} {m.version(name)}' "
         "for name in ('openai-codex', 'openai-codex-cli-bin')), ' '.join(said), sep=', ')")
WANTED = f"openai-codex {SDK_PIN}, openai-codex-cli-bin {SDK_PIN}, codex-cli {SDK_PIN}"
# Both packages at the pin, and the program's output ending in it.
GOOD = re.compile(re.escape(f"openai-codex {SDK_PIN}, openai-codex-cli-bin {SDK_PIN}, ")
                  + rf"(.* )?{re.escape(SDK_PIN)}")

# The driver the SDK's Python runs for one turn.
TURN = Path(__file__).with_name("codex_turn.py")
# The Codex setting each key of a kind's [models] entry overrides. The app-server reads a dotted
# key as a path, as `codex -c` does, so it sets one setting inside [agents] and keeps the rest.
OVERRIDES = {"model": "model", "effort": "model_reasoning_effort",
             "subagents": "agents.default_subagent_model",
             "subagent_effort": "agents.default_subagent_reasoning_effort"}

REFUSALS = {
    "install": ("uv {step} failed while installing the Codex SDK: {said}", "forge doctor --fix"),
    "handler": ("Forge couldn't put in its handler that declines every Codex request, so it "
                "started no conversation.", "forge doctor --fix"),
}


def sdk_env() -> Path:
    """The SDK's environment, with the user's other app data. XDG_DATA_HOME moves it."""
    data = (os.environ.get("XDG_DATA_HOME") or os.environ.get("LOCALAPPDATA")
            or Path.home() / ".local" / "share")
    return Path(data) / "forge" / "codex-sdk" / f"openai-codex-{SDK_PIN}"


def _python(env: Path) -> Path:
    return env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def sdk_problem() -> str:
    """Why the pinned SDK can't be used, in one sentence, or "" when it can."""
    env = sdk_env()
    if not _python(env).is_file() or sync.read(env / READY).strip() != SDK_PIN:
        return f"The Codex SDK {SDK_PIN} isn't installed in {env}."
    done = repo.run(str(_python(env)), "-c", PROBE)
    said = (done.stdout.strip() or done.stderr.strip() or "it printed nothing").splitlines()[-1]
    if done.returncode or not GOOD.fullmatch(said):
        return f"The Codex SDK in {env} should be {WANTED}, but its Python says: {said}"
    return ""


def install() -> None:
    """Install the pinned SDK with uv into a fresh environment; the ready marker goes in last."""
    env = sdk_env()
    print(f"Installing the Codex SDK {SDK_PIN} into {env} with uv (about 300 MB).", flush=True)
    (env / READY).unlink(missing_ok=True)
    shutil.rmtree(env, ignore_errors=True)
    env.parent.mkdir(parents=True, exist_ok=True)
    for step in (["venv", "--python", "3.11", str(env)],
                 ["pip", "install", "--python", str(_python(env)), f"openai-codex=={SDK_PIN}"]):
        done = repo.run("uv", *step)
        if done.returncode:
            repo.refuse(REFUSALS["install"], step=step[0],
                        said=(done.stderr or done.stdout or f"exit code {done.returncode}").strip())
    (env / READY).write_text(SDK_PIN + "\n", encoding="utf-8")
    print(f"Installed the Codex SDK {SDK_PIN} in {env}.")


def settings(cfg: dict[str, Any], kind: str) -> dict[str, str]:
    """The kind's models from forge.toml, as the Codex settings its conversation starts with.

    Everything else comes from Codex's own settings for the checkout, which the thread's folder picks.
    """
    return {OVERRIDES[key]: value for key, value in repo.models(cfg, kind.lower(), "codex").items()}


def run(checkout: Path, item: str, kind: str, name: str, prompt: str, sandbox: str,
        thread: str | None = None) -> dict[str, Any]:
    """Run the prompt as one turn on a new conversation named `name`, in the checkout.

    `kind` is Build, Lite, Fix or Grill; its models come from the checkout's forge.toml, read now.
    `sandbox` is the SDK's name for it: "full-access" or "read-only". Approvals are always "never",
    and every request Codex sends is declined. Events go to the terminal and the item's work log.
    The item's turn log gets a "started" line when the turn starts, and an end line only when Codex
    reports the end. Returns the conversation and turn ids, and the status, final text and token
    usage Codex reported; status, text and usage are None when it reported no end.
    """
    # ponytail: `thread` is RESUME's, which continues that conversation; BUILD always starts one.
    request = {"cwd": str(checkout), "name": name, "prompt": prompt, "sandbox": sandbox,
               "config": settings(repo.config(checkout), kind)}
    log = repo.work_log(checkout, item)
    # A cold read's item is its story key or spec slug, so reads get their own folder: a spec and
    # a fix of one name never share a conversation.
    folder = "read" if kind == "Grill" else "task" if "/" in item else "fix"
    base = repo.forge_dir(checkout) / "threads" / folder / item
    turns = base.with_name(f"{base.name}.log")
    turns.parent.mkdir(parents=True, exist_ok=True)
    started: dict[str, Any] = {}
    result: dict[str, Any] = {"conversation": None, "turn": None, "status": None, "text": None,
                              "usage": None}
    refused = False
    # Codex writes any Unicode, and whoever reads this (a console, an agent, a test) reads UTF-8.
    # A Windows pipe's legacy code page would print the names' "·" as a byte UTF-8 can't read.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    with log.open("a", encoding="utf-8") as out, subprocess.Popen(
            [str(_python(sdk_env())), str(TURN)], cwd=checkout, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace") as driver:
        out.write(f"--- forge work {item} at {repo.now()}\n")
        driver.stdin.write(json.dumps(request))
        driver.stdin.close()
        for line in driver.stdout:
            try:
                said = json.loads(line)
            except ValueError:
                said = None
            if not isinstance(said, dict):  # the driver's own output, such as a traceback
                text = line.rstrip("\n")
            elif "pid" in said:
                text = f"Codex app-server: process {said['pid']}"
            elif "refused" in said:
                refused, text = True, ""
            elif "thread" in said:
                result["conversation"] = said["thread"]
                text = f'Codex conversation "{name}": {said["thread"]}'
            elif "turn" in said:
                result["turn"] = said["turn"]
                started = {"conversation": result["conversation"], "turn": said["turn"],
                           "kind": kind, "started": repo.now()}
                _append(turns, started)
                text = ""
            elif "declined" in said:
                text = f"Declined Codex's request {said['declined']}"
            elif "status" in said:
                usage = said.get("usage") or {}
                result.update(status=said["status"], text=said.get("text"), usage={
                    "input_tokens": usage.get("inputTokens"),
                    "cached_input_tokens": usage.get("cachedInputTokens"),
                    "output_tokens": usage.get("outputTokens")})
                _append(turns, {"conversation": result["conversation"], "turn": result["turn"],
                                "kind": kind, "continued": False, "fresh_start": "first turn",
                                "status": said["status"], "started": started.get("started"),
                                "ended": repo.now(), **result["usage"]})
                text = f"Codex ended the turn: {said['status']}"
                text += f" ({said['error']})" if said.get("error") else ""
            else:
                text = _event(said)
            if text:
                print(text, flush=True)
                out.write(text + "\n")
    if refused:
        repo.refuse(REFUSALS["handler"])
    return result


def _event(said: dict[str, Any]) -> str:
    """The readable line of a finished item: a message, a command or changed files; else ""."""
    if said.get("event") != "item/completed":
        return ""
    item = (said.get("params") or {}).get("item") or {}
    if item.get("type") == "agentMessage":
        return item.get("text", "")
    if item.get("type") == "commandExecution":
        # The output as a whole once the command ends (its deltas are dropped): the last 40 lines,
        # enough to show why a test failed.
        output = (item.get("aggregatedOutput") or "").rstrip("\n").splitlines()
        cut = [f"(… {len(output) - 40} earlier lines in Codex's own log)"] if len(output) > 40 else []
        return "\n".join([f"$ {item.get('command')} ({item.get('status')})", *cut, *output[-40:]])
    if item.get("type") == "fileChange":
        paths = ", ".join(change.get("path", "") for change in item.get("changes") or [])
        return f"Changed {paths} ({item.get('status')})"
    return ""


def _append(path: Path, line: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(line) + "\n")
