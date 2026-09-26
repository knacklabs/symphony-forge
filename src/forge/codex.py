"""Codex workers, Forge's side: the pinned Codex SDK in its own environment, checked and installed,
a kind's models as Codex settings, one turn run through codex_turn.py, and each item's record and
lock, so one forge work or read runs per item and no Codex process outlives it.

Forge never imports the SDK. It runs the environment's own Python to probe it and to drive a turn,
so the SDK and the Codex program it bundles (about 300 MB) stay out of Forge's own install.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from forge import repo, sync

if os.name == "nt":
    import msvcrt
else:
    import fcntl

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

# The driver the SDK's Python runs for one turn, in a process group of its own, so the driver, the
# app-server it starts and whatever that starts can be stopped together.
TURN = Path(__file__).with_name("codex_turn.py")
GROUP = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
         else {"start_new_session": True})
# The Codex setting each key of a kind's [models] entry overrides. The app-server reads a dotted
# key as a path, as `codex -c` does, so it sets one setting inside [agents] and keeps the rest.
OVERRIDES = {"model": "model", "effort": "model_reasoning_effort",
             "subagents": "agents.default_subagent_model",
             "subagent_effort": "agents.default_subagent_reasoning_effort"}

REFUSALS = {
    "install": ("uv {step} failed while installing the Codex SDK: {said}", "forge doctor --fix"),
    "handler": ("Forge couldn't put in its handler that declines every Codex request, so it "
                "started no conversation.", "forge doctor --fix"),
    "start": ("Codex didn't start within two minutes, so Forge stopped it; its log is {log}.",
              "forge {command} {item}"),
    "driver": ("Forge can't read the start time and command of its Codex driver, process {pid}, "
               "so it stopped the driver before any conversation.", "forge {command} {item}"),
    "server": ("Forge can't read the start time and command of the Codex app-server, process "
               "{pid}, so it stopped Codex before any conversation.", "forge {command} {item}"),
    "busy": ("forge {command} {item} is already running as process {pid}, and only one runs per "
             "item; wait for it to finish.", "forge {command} {item}"),
    "unknown": ("Forge can't read the start time and command of process {pid}, so it can't tell "
                "who holds {lock}; it counts it as held.",
                "delete {lock} once no forge {command} runs on {item}"),
    "leftover": ("Process {pid}, which an earlier forge {command} {item} left, may still be "
                 "running Codex, and Forge can't read its start time and command to be sure, so "
                 "it counts it as running.", "stop process {pid} if it runs, then forge {command} "
                 "{item}"),
    "running": ("Codex says the last turn of {item} is still running, so Forge starts no second "
                "one.", "wait for it to end in the Codex app, then forge {command} {item}"),
    "unread": ("Codex didn't say how the last turn of {item} ended, so Forge starts no second one; "
               "its log is {log}.", "forge {command} {item}"),
    "record": ("Forge couldn't update {record} because another program kept it open.",
               "close whatever reads {record}, then run the command again"),
}
# The token counts an end line carries, blank when Codex reports none.
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens")


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


def record(checkout: Path, item: str) -> dict[str, Any]:
    """The item's record: its Codex processes, conversation, checkout, approval, the commit its
    last turn started from, and HEAD when a turn last ended."""
    return _json(_item_file(checkout, item, ".json", "Fix"))


def conversation(checkout: Path, item: str, approval: str | None) -> tuple[str | None, str]:
    """The item's conversation to continue and "", or None and why Forge starts a new one."""
    saved = record(checkout, item)
    if not saved.get("start"):
        return None, "Forge has no record of its conversation on this machine"
    if saved.get("checkout") != str(checkout):
        return None, f"its conversation was started in another checkout, {saved.get('checkout')}"
    if saved.get("approval") != approval:
        return None, "the story's approval changed after its conversation started"
    for commit in {saved["start"], saved.get("head") or saved["start"]}:
        if repo.run("git", "merge-base", "--is-ancestor", commit, "HEAD", cwd=checkout).returncode:
            return None, "the branch's history was rewritten under its conversation"
    return saved["conversation"], ""


def recover(checkout: Path, item: str) -> None:
    """After a crash, once its Codex processes are stopped: a turn whose end Forge never logged
    gets an end line with the status Codex now reports, or "lost" when Codex reports none. That
    includes a turn Codex started before Forge logged its "started" line, found as a turn of the
    conversation the log hasn't got. While Codex says a turn still runs, or doesn't answer,
    refuse: two turns never run for one item."""
    turns = _item_file(checkout, item, ".log", "Fix")
    lines = sync.read(turns).splitlines()
    last = json.loads(lines[-1]) if lines else {"status": None}
    path = _item_file(checkout, item, ".json", "Fix")
    saved = _json(path)
    pending = saved.get("pending")  # a turn about to start, until its "started" line is logged
    if "status" in last and not pending:
        return
    conversation = saved["conversation"] if "status" in last else last["conversation"]
    said = run(checkout, item, (pending or last)["kind"], "", "", "read-only", conversation,
               read=True)
    if "read" not in said:
        repo.refuse(REFUSALS["unread"], item=item, command="work", log=repo.work_log(checkout, item))
    reported = dict(said["read"])
    if "status" in last:
        logged = {(entry.get("conversation"), entry.get("turn"))
                  for entry in map(json.loads, lines)}
        unlogged = [turn for turn in reported if (conversation, turn) not in logged]
        if not unlogged:  # the crash came before Codex started the turn
            _record(path, pending=None)
            return
        last = {"conversation": conversation, "turn": unlogged[-1], "kind": pending["kind"],
                "started": None}
    if reported.get(last["turn"]) == "inProgress":
        repo.refuse(REFUSALS["running"], item=item, command="work")
    status = reported.get(last["turn"]) or "lost"
    begun = pending or saved
    _append(turns, {**last, "continued": begun.get("continued"),
                    "fresh_start": begun.get("fresh_start"), "status": status,
                    "ended": repo.now(), **dict.fromkeys(TOKENS)})
    if pending:  # the turn started, so the next one's changes count from where it started
        _record(path, start=pending["start"], continued=pending["continued"],
                fresh_start=pending["fresh_start"], pending=None)
    print(f"Forge never saw the last turn end; Codex reports it {status}." if status != "lost" else
          "Forge never saw the last turn end, and Codex reports no status for it: it is logged "
          "as lost.", flush=True)


def run(checkout: Path, item: str, kind: str, name: str, prompt: str, sandbox: str,
        thread: str | None = None, fresh: str = "first turn", approval: str | None = None,
        read: bool = False) -> dict[str, Any]:
    """Run the prompt as one turn in the checkout: on the conversation `thread` when Codex can
    resume it, else on a new one, and name the conversation `name`. `fresh` says why a new one
    starts, and the conversation is recorded with the story's `approval`. With `read`, run no
    turn: read back each turn of `thread` with its status, returned as "read" ([] when Codex has
    no such conversation).

    `kind` is Build, Lite, Fix or Grill; its models come from the checkout's forge.toml, read now.
    `sandbox` is the SDK's name for it: "full-access" or "read-only". Approvals are always "never",
    and every request Codex sends is declined. Events go to the terminal and the item's work log.
    The item's record gets the driver's identity as soon as it starts, before Codex does, then the
    app-server's, the conversation with its checkout and approval and the turn about to start
    (pending until its "started" line is logged), the commit the turn starts from, and HEAD when
    the turn ends. The driver waits for each of the
    app-server and the conversation to be on record before it goes on. The item's turn log gets a
    "started" line when the turn starts, and an end line only when Codex reports the end. Returns
    the conversation and turn ids, and the status, final text and token usage Codex reported;
    status, text and usage are None when it reported no end.
    """
    request = {"cwd": str(checkout), "name": name, "prompt": prompt, "sandbox": sandbox,
               "config": settings(repo.config(checkout), kind), "thread": thread, "read": read}
    log = repo.work_log(checkout, item)
    record, turns = (_item_file(checkout, item, suffix, kind) for suffix in (".json", ".log"))
    command = "read" if kind == "Grill" else "work"
    started: dict[str, Any] = {}
    continued: dict[str, Any] = {}
    result: dict[str, Any] = {"conversation": None, "turn": None, "status": None, "text": None,
                              "usage": None}
    refused, server = "", None
    # Codex writes any Unicode, and whoever reads this (a console, an agent, a test) reads UTF-8.
    # A Windows pipe's legacy code page would print the names' "·" as a byte UTF-8 can't read.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    with log.open("a", encoding="utf-8") as out, subprocess.Popen(
            [str(_python(sdk_env())), str(TURN)], cwd=checkout, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace", **GROUP) as driver:
        out.write(f"--- forge work {item} at {repo.now()}\n")
        started_by: dict[str, Any] | None = None

        def recorded() -> None:
            """Tell the driver the id it sent is on record, so it goes on."""
            with contextlib.suppress(OSError):  # a driver that has gone waits for nothing
                driver.stdin.write("recorded\n")
                driver.stdin.flush()
        try:
            for line in driver.stdout:
                try:
                    said = json.loads(line)
                except ValueError:
                    said = None
                if not isinstance(said, dict):  # the driver's own output, such as a traceback
                    text = line.rstrip("\n")
                elif "driver" in said:
                    # The driver on record before it hears the request, so its group can always be
                    # stopped. Read once it says it runs: a macOS framework Python starts itself
                    # again under another command first, and the first one would match nothing.
                    started_by = identity(driver.pid)
                    if "command" not in (started_by or {}):
                        driver.kill()  # it hasn't read the request, so it has started nothing yet
                        refused = "driver"
                        break
                    _record(record, driver=started_by, app_server=None)
                    # One line, and stdin stays open: the driver ends its group once Forge's closes.
                    driver.stdin.write(json.dumps(request) + "\n")
                    driver.stdin.flush()
                    text = ""
                elif "pid" in said:
                    server = said["pid"]
                    found = identity(server)
                    if "command" not in (found or {}):  # nothing to stop it by after a crash
                        _stop(started_by, group=True)  # the group has the app-server too
                        refused = "server"
                        break
                    _record(record, app_server=found)
                    recorded()
                    text = f"Codex app-server: process {server}"
                elif "refused" in said:
                    refused, text = said["refused"], ""
                elif "read" in said:
                    result["read"], text = said["read"], ""
                elif "fresh" in said:  # Codex couldn't resume the conversation
                    fresh, text = said["fresh"], ""
                elif "thread" in said:
                    result["conversation"] = said["thread"]
                    continued = {"continued": said["continued"],
                                 "fresh_start": None if said["continued"] else fresh}
                    # Codex may start the turn before Forge logs it, so a crash between the two
                    # leaves this for recover() to find the turn by. The turn starts from HEAD now,
                    # before Codex can commit anything. A new conversation drops the old one's
                    # ending HEAD, which a rewritten history may no longer hold.
                    begun = repo.git("rev-parse", "HEAD", cwd=checkout)
                    ended = {} if said["continued"] else {"head": None}
                    _record(record, conversation=said["thread"], checkout=str(checkout),
                            approval=approval, pending={"kind": kind, "start": begun, **continued},
                            **ended)
                    recorded()
                    text = f'Codex conversation "{name}": {said["thread"]}'
                    if not said["continued"] and fresh != "first turn":
                        text = f"Starting a new Codex conversation, because {fresh}.\n{text}"
                elif "turn" in said:
                    result["turn"] = said["turn"]
                    started = {"conversation": result["conversation"], "turn": said["turn"],
                               "kind": kind, "started": repo.now()}
                    _append(turns, started)
                    _record(record, start=begun, pending=None, **continued)
                    text = ""
                elif "declined" in said:
                    text = f"Declined Codex's request {said['declined']}"
                elif "status" in said:
                    usage = said.get("usage") or {}
                    result.update(status=said["status"], text=said.get("text"), usage={
                        "input_tokens": usage.get("inputTokens"),
                        "cached_input_tokens": usage.get("cachedInputTokens"),
                        "output_tokens": usage.get("outputTokens")})
                    _append(turns, {**started, **continued, "status": said["status"],
                                    "ended": repo.now(), **result["usage"]})
                    _record(record, head=repo.git("rev-parse", "HEAD", cwd=checkout))
                    text = f"Codex ended the turn: {said['status']}"
                    text += f" ({said['error']})" if said.get("error") else ""
                else:
                    text = _event(said)
                if text:
                    print(text, flush=True)
                    out.write(text + "\n")
        finally:  # on an error or Ctrl-C too: the driver ends its group once stdin closes
            with contextlib.suppress(OSError):  # a driver that has gone already can't be told
                driver.stdin.close()
            driver.stdout.close()
            try:
                driver.wait(timeout=5)
            except subprocess.TimeoutExpired:  # it can't act (stopped, say): end its group here
                _stop_leftover(record)
                driver.kill()  # not on record yet, it has started nothing
                driver.wait()
            if os.name != "nt":
                # The group is Forge's own, and outlives its leader while anything runs in it, so
                # this reaches an app-server the record can't name (a start time or command read
                # wrong under load) after a driver that died without ending it.
                stuck = False
                with contextlib.suppress(OSError):
                    os.killpg(driver.pid, signal.SIGKILL)
                    for _ in range(300):  # SIGKILL only asks: wait until the group has no member
                        os.killpg(driver.pid, 0)  # raises once none is left
                        time.sleep(0.1)
                    stuck = True  # thirty seconds on, a member still runs: don't claim it ended
                if stuck:
                    repo.refuse(REFUSALS["leftover"], pid=driver.pid, item=item, command=command)
    if refused:
        repo.refuse(REFUSALS[refused], log=log, item=item, command=command,
                    pid=driver.pid if refused == "driver" else server)
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


def _item_file(checkout: Path, item: str, suffix: str, kind: str) -> Path:
    """The item's record (.json), lock (.lock) or turn log (.log), in git's folder that every
    worktree shares: threads/task/<STORY>/<TASK>, threads/fix/<name> or threads/read/<item>."""
    # A cold read's item is its story key or spec slug, so reads get their own folder: a spec and
    # a fix of one name never share a conversation.
    folder = "read" if kind == "Grill" else "task" if "/" in item else "fix"
    path = repo.forge_dir(checkout) / "threads" / folder / f"{item}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _json(path: Path) -> dict[str, Any]:
    """A record or lock, or {} when it is missing or unreadable."""
    try:
        data = json.loads(sync.read(path) or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _record(path: Path, **fields: Any) -> None:
    """Add fields to the item's record through a temporary file and a rename, so it stays whole."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({**_json(path), **fields}, indent=2) + "\n", encoding="utf-8")
    for wait in (0.05,) * 40 + (0,):  # Windows refuses the rename while a reader has the file open
        try:
            return os.replace(tmp, path)
        except PermissionError:
            if not wait:  # nothing unwritten counts as recorded: refuse, and let the caller clean up
                tmp.unlink(missing_ok=True)
                repo.refuse(REFUSALS["record"], record=path)
            time.sleep(wait)


def identity(pid: int) -> dict[str, Any] | None:
    """A running process by its id, start time and command, so a reused id never passes for it.

    None when no process has the id. Only the id when Forge can't read the rest: that matches no
    record, and its owner counts as running.
    """
    if os.name == "nt":
        # Every error stops the script (exit 1), so only a query that finds no process exits 3.
        done = repo.run("powershell", "-NoProfile", "-Command", "$ErrorActionPreference = 'Stop'; "
                        f"$p = Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; "
                        "if (!$p) { exit 3 }; $p.CreationDate.ToString('o'); $p.CommandLine")
        gone = done.returncode == 3
        started, _, command = done.stdout.strip().partition("\n")
    else:
        done = repo.run("ps", "-ww", "-o", "lstart=,command=", "-p", str(pid))  # -ww: whole command
        gone = done.returncode == 1 and not (done.stdout + done.stderr).strip()
        *start, command = done.stdout.split(None, 5) or [""]  # lstart is five words
        started = " ".join(start)
    if gone:
        return None
    if done.returncode or not started.strip() or not command.strip():
        return {"pid": pid}
    return {"pid": pid, "started": started.strip(), "command": command.strip()}


def _alive(recorded: dict[str, Any]) -> bool | None:
    """Whether the recorded process still runs: False once its id is free or another process has
    it, None when Forge can't tell, which counts as running. It goes by id and start time: a
    program that starts itself again (`env`, a macOS framework Python) keeps both but changes its
    command, so a record made right after it started must still match once it runs."""
    pid = recorded.get("pid")
    now = identity(pid) if isinstance(pid, int) else {}
    if now is not None and "command" not in now:
        return None
    return now is not None and now["started"] == recorded.get("started")


def _stop_leftover(record: Path) -> tuple[bool, int | None]:
    """Stop what the item's last call left running: its driver's whole process group when the
    driver still runs as recorded, and its app-server when that does. Returns whether it stopped
    any, and the id of one Forge can't confirm has gone, which counts as running and stays on
    record."""
    saved = _json(record)
    stopped, unknown = False, None
    for key, runs, group in (("driver", "codex_turn", True), ("app_server", "app-server", False)):
        recorded = saved.get(key) or {}
        if runs not in str(recorded.get("command")):
            continue
        alive = _alive(recorded)
        if alive:
            _stop(recorded, group)
            stopped, alive = True, _alive(recorded)
        if alive is not False:
            unknown = recorded["pid"]
    return stopped, unknown


def _stop(recorded: dict[str, Any], group: bool) -> None:
    """Stop a process, with its process group when `group`, and wait until it has gone: SIGTERM,
    then SIGKILL five seconds on. On Windows taskkill ends it and everything it started."""
    pid = recorded["pid"]
    for sig in (signal.SIGTERM, getattr(signal, "SIGKILL", signal.SIGTERM)):
        with contextlib.suppress(OSError):  # it may have ended on its own meanwhile
            if os.name == "nt":
                repo.run("taskkill", "/T", "/F", "/PID", str(pid))
            elif group:
                os.killpg(pid, sig)
                os.killpg(pid, signal.SIGCONT)  # a stopped member acts on it too
            else:
                os.kill(pid, sig)
        for _ in range(50):
            if _alive(recorded) is False:
                return
            time.sleep(0.1)


@contextlib.contextmanager
def hold(checkout: Path, item: str, kind: str) -> Iterator[None]:
    """One forge work, or cold read, per item: take the item's lock, which holds this process's
    identity, stop the Codex processes an earlier call left, and on the way out stop this call's
    if any still run and give the lock back. A lock whose owner is gone is cleared; a live one
    refuses."""
    lock, record = (_item_file(checkout, item, suffix, kind) for suffix in (".lock", ".json"))
    command = "read" if kind == "Grill" else "work"
    held = _take(lock, identity(os.getpid()) or {"pid": os.getpid()})
    if held:
        owner, alive = held
        repo.refuse(REFUSALS["busy" if alive else "unknown"], pid=owner.get("pid"), lock=lock,
                    item=item, command=command)
    try:
        _, unknown = _stop_leftover(record)
        if unknown:  # its record stays, so a later call can still stop it
            repo.refuse(REFUSALS["leftover"], pid=unknown, item=item, command=command)
        yield
    finally:
        _stop_leftover(record)
        lock.unlink(missing_ok=True)


def _take(lock: Path, me: dict[str, Any]) -> tuple[dict[str, Any], bool | None] | None:
    """Take the lock for `me` by an exclusive create, clearing a stale one first. None once taken;
    else the owner keeping it, and True, or None when Forge can't tell, which counts as running."""
    with _one_at_a_time(lock):
        if lock.exists():
            owner = _json(lock)
            alive = _alive(owner)
            if alive is not False:
                return owner, alive
            lock.unlink(missing_ok=True)
        if "command" not in me:  # a lock no one else could check would pass for a stale one
            return me, None
        with lock.open("x", encoding="utf-8") as out:  # created only if it isn't there
            json.dump(me, out)
        return None


@contextlib.contextmanager
def _one_at_a_time(lock: Path) -> Iterator[None]:
    """Hold the lock's guard file while a call checks, clears or takes the lock, so two calls that
    find one stale lock never both clear it, and one clears another's new lock. The system lets
    go of the guard when its holder ends, however it ends, so it is never stale itself."""
    with lock.with_suffix(".guard").open("ab") as guard:
        if os.name != "nt":
            fcntl.flock(guard, fcntl.LOCK_EX)
            yield
            return
        guard.seek(0)
        while True:  # LK_LOCK gives up after ten seconds
            with contextlib.suppress(OSError):
                msvcrt.locking(guard.fileno(), msvcrt.LK_LOCK, 1)
                break
        try:
            yield
        finally:
            guard.seek(0)
            msvcrt.locking(guard.fileno(), msvcrt.LK_UNLCK, 1)


def tidy(checkout: Path) -> list[str]:
    """For forge doctor, whatever the workers, since a record exists only where Codex ran: under
    each item's lock, clear what a crashed call left. An item whose lock is held is running, and
    is left alone. A line for each item stopped or left alone."""
    threads = repo.forge_dir(checkout) / "threads"
    bases = sorted({path.with_suffix("") for path in threads.rglob("*.*")})
    me = (identity(os.getpid()) or {"pid": os.getpid()}) if bases else {}
    said = []
    for base in bases:
        folder, item = base.relative_to(threads).as_posix().split("/", 1)
        command = "read" if folder == "read" else "work"
        lock = base.with_suffix(".lock")
        held = _take(lock, me)
        if held:
            said.append(f"forge {command} {item} is running as process {held[0].get('pid')}, so "
                        "doctor leaves its Codex process alone.")
            continue
        try:
            stopped, unknown = _stop_leftover(base.with_suffix(".json"))
            if stopped:
                said.append(f"Stopped the Codex processes that a crashed forge {command} {item} "
                            "left.")
            if unknown:
                said.append(f"Process {unknown}, which a crashed forge {command} {item} left, may "
                            "still be running Codex, and Forge can't read its start time and "
                            "command to be sure, so doctor leaves it alone; stop it if it runs.")
        finally:
            lock.unlink(missing_ok=True)
    return said
