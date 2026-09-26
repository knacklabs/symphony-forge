"""Codex workers, Forge's side: the pinned Codex SDK in its own environment, checked and installed,
the per-kind settings, and one turn run through codex_turn.py.

Forge never imports the SDK. It runs the environment's own Python to probe it and to drive a turn,
so the SDK and the Codex program it bundles (about 300 MB) stay out of Forge's own install.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from forge import repo, sync

# The one SDK version Forge drives. Moving it is a deliberate change that reruns the contract and
# smoke tests.
SDK_PIN = "0.156.1"
# Written last by the install, so a half-finished install never looks ready.
READY = "forge-sdk-ready"
# Loads the SDK, runs its bundled Codex program with --version (a missing program, a failing one or
# a hang raises), then prints both package versions and what the program said.
PROBE = ("import importlib.metadata as m, subprocess, openai_codex, codex_cli_bin; "
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
# All a per-kind settings file, .codex/<kind>.config.toml, may set.
SETTINGS = ("model", "model_reasoning_effort", "model_verbosity")

REFUSALS = {
    "install": ("uv {step} failed while installing the Codex SDK: {said}", "forge doctor --fix"),
    "bad_settings": ("{path} is not valid TOML: {problem}.", "fix {path}"),
    "setting": ("{path} may set only model, model_reasoning_effort and model_verbosity, "
                "but it sets {key}.", "remove {key} from {path}"),
    "handler": ("Forge couldn't put in its handler that declines every Codex request, so it "
                "started no conversation.", "forge doctor --fix"),
    "turn": ("The Codex turn didn't complete: {why}; its log is {log}.", "forge work {item}"),
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


def settings(checkout: Path, kind: str) -> dict[str, Any]:
    """The kind's own settings in the checkout, read fresh; {} when it has no file.

    Everything else comes from Codex's own settings for the checkout, which the thread's folder picks.
    """
    rel = f".codex/{kind.lower()}.config.toml"
    path = checkout / rel
    if not path.is_file():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        repo.refuse(REFUSALS["bad_settings"], path=rel, problem=exc)
    for key in data:
        if key not in SETTINGS:
            repo.refuse(REFUSALS["setting"], path=rel, key=key)
    return data


def run(checkout: Path, item: str, kind: str, name: str, prompt: str, sandbox: str) -> None:
    """Run the prompt as one turn on a new conversation named `name`, in the checkout.

    `sandbox` is the SDK's name for it: "full-access" or "read-only". Approvals are always "never",
    and every request Codex sends is declined. Events go to the terminal and the item's work log.
    The item's turn log gets a "started" line when the turn starts, and an end line only when Codex
    reports the end. Refuses unless Codex reports the turn completed.
    """
    request = {"cwd": str(checkout), "name": name, "prompt": prompt, "sandbox": sandbox,
               "config": settings(checkout, kind)}
    slug = item.replace("/", "-")
    log = repo.forge_dir(checkout) / f"work-{slug}.log"
    turns = log.parent / "threads" / f"{slug}.log"
    turns.parent.mkdir(exist_ok=True)
    started: dict[str, Any] = {}
    status, refused = "", False
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
                text = f'Codex conversation "{name}": {said["thread"]}'
            elif "turn" in said:
                started = {"turn": said["turn"], "kind": kind, "started": repo.now()}
                _append(turns, started)
                text = ""
            elif "declined" in said:
                text = f"Declined Codex's request {said['declined']}"
            elif "status" in said:
                status, usage = said["status"], said.get("usage") or {}
                _append(turns, {**started, "continued": False, "status": status,
                                "ended": repo.now(), "input_tokens": usage.get("inputTokens"),
                                "cached_input_tokens": usage.get("cachedInputTokens"),
                                "output_tokens": usage.get("outputTokens")})
                text = f"Codex ended the turn: {status}"
                text += f" ({said['error']})" if said.get("error") else ""
            else:
                text = _event(said)
            if text:
                print(text, flush=True)
                out.write(text + "\n")
    if refused:
        repo.refuse(REFUSALS["handler"])
    if status != "completed":
        why = (f"Codex reported it {status}" if status else
               f"the driver stopped with exit code {driver.returncode} before Codex reported its end")
        repo.refuse(REFUSALS["turn"], why=why, log=log, item=item)


def _event(said: dict[str, Any]) -> str:
    """The readable line of a finished item: a message, a command or changed files; else ""."""
    if said.get("event") != "item/completed":
        return ""
    item = (said.get("params") or {}).get("item") or {}
    if item.get("type") == "agentMessage":
        return item.get("text", "")
    if item.get("type") == "commandExecution":
        return f"$ {item.get('command')} ({item.get('status')})"
    if item.get("type") == "fileChange":
        paths = ", ".join(change.get("path", "") for change in item.get("changes") or [])
        return f"Changed {paths} ({item.get('status')})"
    return ""


def _append(path: Path, line: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(line) + "\n")
