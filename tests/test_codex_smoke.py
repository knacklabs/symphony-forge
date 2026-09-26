"""The real pinned Codex SDK, with its own Codex program and the user's Codex login: Forge's driver
starts a conversation, names it and continues it, Forge's handler declines a request to write a
file, events stream, and nothing is left running.

It runs wherever Forge's SDK environment exists, and costs a few small turns on the user's Codex
account. Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import uuid
from pathlib import Path

import pytest

STORY = "FORGE-WARM-1"
PIN = "0.156.1"
ROOT = Path(__file__).resolve().parents[1]
TURN = ROOT / "src" / "forge" / "codex_turn.py"
# Where forge doctor --fix installs the SDK, marked ready once the install finished.
ENV = (Path(os.environ.get("XDG_DATA_HOME") or os.environ.get("LOCALAPPDATA")
            or Path.home() / ".local" / "share") / "forge" / "codex-sdk" / f"openai-codex-{PIN}")
PYTHON = ENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
# Low effort keeps the turns quick and cheap; the model is the user's Codex default.
CONFIG = {"model_reasoning_effort": "low"}
WAIT = 600  # seconds a step gets before the test ends its driver, as Forge would on Ctrl-C

# The name each conversation shows under in the Codex app.
NAMED = """import json, sys
from openai_codex import Codex
codex = Codex()
try:
    found = codex.thread_list(search_term=sys.argv[1]).data
    print(json.dumps([[thread.id, thread.name] for thread in found]))
finally:
    codex.close()
"""
# Forge's own handler on a read-only turn that may ask to write. Forge's turns never ask ("never"),
# so this one alone asks the user, which here is the handler.
DECLINED = """import json, sys
from openai_codex import Codex, Sandbox, Thread, api
plain = api.CodexClient
sys.path.insert(0, sys.argv[1])
import codex_turn
api.CodexClient = plain  # Forge's client waits on Forge's own protocol, which this doesn't speak
codex = Codex()
try:
    codex._client._approval_handler = codex_turn.decline
    started = codex._client.thread_start({
        "cwd": sys.argv[2], "sandbox": "read-only", "approvalPolicy": "on-request",
        "approvalsReviewer": "user", "config": json.loads(sys.argv[3])})
    turn = Thread(codex._client, started.thread.id).turn(sys.argv[4], sandbox=Sandbox.read_only)
    for event in turn.stream():
        print(json.dumps({"event": event.method}), flush=True)
finally:
    codex.close()
"""


def _drive(cwd: Path, name: str, prompt: str, thread: str | None = None) -> list[dict]:
    """One read-only turn through Forge's driver, answering it as Forge does: the request once the
    driver runs, and "recorded" for the app-server and the conversation. Its lines, in order."""
    request = {"cwd": str(cwd), "name": name, "prompt": prompt, "sandbox": "read-only",
               "config": CONFIG, "thread": thread}
    driver = subprocess.Popen([str(PYTHON), str(TURN)], cwd=cwd, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              encoding="utf-8", start_new_session=os.name != "nt")
    # Closing stdin is Forge going away: the driver then ends itself and its app-server.
    timer = threading.Timer(WAIT, driver.stdin.close)
    timer.start()
    lines = []
    try:
        for line in driver.stdout:
            try:
                said = json.loads(line)
            except ValueError:
                said = {"output": line.rstrip("\n")}  # a traceback, say, shown if a check fails
            lines.append(said)
            if "driver" in said:
                driver.stdin.write(json.dumps(request) + "\n")
            elif "pid" in said or "thread" in said:
                driver.stdin.write("recorded\n")
            else:
                continue
            driver.stdin.flush()
    finally:
        timer.cancel()
        driver.stdin.close()
        driver.wait()
    assert driver.returncode == 0, lines
    return lines


def _sdk(*args: str) -> str:
    done = subprocess.run([str(PYTHON), "-c", *args], capture_output=True, text=True,
                          encoding="utf-8", timeout=WAIT)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def _gone(pid: int) -> bool:
    if os.name == "nt":  # os.kill on Windows would end it
        listed = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True,
                                text=True).stdout
        return str(pid) not in listed
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def _one(lines: list[dict], key: str) -> dict:
    found = [said for said in lines if key in said]
    assert len(found) == 1, lines
    return found[0]


@pytest.mark.skipif(not (ENV / "forge-sdk-ready").is_file(),
                    reason=f"the Codex SDK {PIN} isn't installed in {ENV}; forge doctor --fix installs it")
def test_12_the_real_sdk_starts_names_resumes_declines_streams_and_stops(tmp_path):
    word = f"smoke-{uuid.uuid4().hex[:8]}"
    name = f"Smoke · Forge SDK check · {word}"

    # 1. Start: a new conversation, whose app-server Forge's driver reports before Codex starts.
    first = _drive(tmp_path, name, f"Remember the word {word}. Reply with just OK.")
    thread = _one(first, "thread")
    assert thread["continued"] is False, first
    end = _one(first, "status")
    assert end["status"] == "completed", first
    print(f"start: conversation {thread['thread']}, turn {_one(first, 'turn')['turn']}, "
          f"{end['status']}, usage {end['usage']}")

    # 2. Naming: the conversation shows under its name, to another process.
    found = json.loads(_sdk(NAMED, word))
    assert [thread["thread"], name] in found, found
    print(f"naming: {name!r} lists as {thread['thread']}")

    # 3. Resume: a second driver continues the same conversation, which remembers the word.
    second = _drive(tmp_path, name, "What word did I ask you to remember? Reply with just the word.",
                    thread["thread"])
    again = _one(second, "thread")
    assert again == {"thread": thread["thread"], "continued": True}, second
    resumed = _one(second, "status")
    assert resumed["status"] == "completed" and word in resumed["text"], second
    print(f"resume: same conversation, recalled {resumed['text']!r}, usage {resumed['usage']}")

    # 4. A declined request: Forge's handler declines the write, and the file isn't written.
    target = tmp_path / "smoke.txt"
    declined = [json.loads(line) for line in _sdk(
        DECLINED, str(TURN.parent), str(tmp_path), json.dumps(CONFIG),
        f"Create a file named {target.name} in the current folder containing the word {word}, "
        "with the apply_patch tool. This folder is read-only for you, so ask for approval to "
        "write it. If the request is declined, stop and don't try another way.").splitlines()]
    asked = [said["declined"] for said in declined if "declined" in said]
    assert asked, declined
    assert not target.exists()
    print(f"declined: {asked}, and {target.name} was not written")

    # 5. Events: each turn streams its items, its token usage and its end.
    for lines in (first, second):
        events = {said["event"] for said in lines if "event" in said}
        assert {"item/completed", "thread/tokenUsage/updated", "turn/completed"} <= events, events
        assert _one(lines, "status")["usage"]["inputTokens"], lines
    print(f"events: {sorted({said['event'] for said in first if 'event' in said})}")

    # 6. Shutdown: once each driver ends, so has its app-server.
    servers = [_one(lines, "pid")["pid"] for lines in (first, second)]
    assert all(_gone(pid) for pid in servers), servers
    print(f"shutdown: app-servers {servers} have ended")
