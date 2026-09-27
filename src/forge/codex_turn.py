"""One Codex turn for Forge, run by the Codex SDK's own Python; Forge itself never imports the SDK.

This prints its own process id first, and once Forge has it on record, Forge sends one JSON
request line on stdin: the checkout (cwd), the conversation's name, the prompt, the sandbox, the
kind's settings (config), and the conversation to continue (thread), if any. This then prints one
JSON line per step, in order: the app-server's process id, before Codex starts; why a new
conversation starts when Codex can't resume that one; the thread, and whether it continued; the
turn; each event and each declined request; then the turn's end with its status, error, final text
and token usage, only when Codex reports it. With read, this runs no turn: after the app-server's
id it prints each turn of the conversation with its status as Codex reports it. After the
app-server's id and after the thread's, this waits for Forge to answer with a line saying it has
them on record, so nothing starts that Forge hasn't recorded. Codex gets two minutes to start, or
this prints a refusal and ends.

Forge starts this in its own process group and keeps stdin open while it runs. Once stdin closes,
Forge has gone, and this ends the whole group, itself and the app-server it started, even while
Codex is still starting. Windows has no such group, so there this ends the app-server's process
tree by the id it kept when the app-server started.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
from typing import Any

from openai_codex import ApprovalMode, Codex, Sandbox, api
from openai_codex.client import CodexClient
from openai_codex.errors import InvalidRequestError, JsonRpcError
from openai_codex._run import _final_assistant_response_from_items
from openai_codex.models import (ItemCompletedNotification, ThreadTokenUsageUpdatedNotification,
                                 TurnCompletedNotification, UnknownNotification)

LOCK = threading.Lock()
START = 120  # the seconds Codex gets to start: Codex() waits on initialize with no timeout
STARTING = threading.Lock()  # end() never falls between the app-server starting and SERVER
SERVER: list[int] = []  # the app-server's process id once it has started, for end() on Windows
RECORDED = threading.Semaphore(0)  # a release per line Forge sends once it has recorded an id


def emit(**line: Any) -> None:
    # The handler runs on the SDK's reader thread, so lines take turns.
    with LOCK:
        print(json.dumps(line), flush=True)


def decline(method: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """Forge's answer to every request Codex sends, known or unknown."""
    emit(declined=method)
    return {"decision": "decline"}


class Client(CodexClient):
    """The SDK's client, which prints the app-server's id as soon as it starts, before Codex()
    waits on initialize, so Forge has it on record even when Codex never answers."""

    def start(self) -> None:
        with STARTING:
            super().start()
            SERVER.append(self._proc.pid)
        emit(pid=self._proc.pid)
        RECORDED.acquire()


# ponytail: Codex() makes its client from this module global and takes no other; SDK_PIN keeps it.
api.CodexClient = Client


def end() -> None:
    """End this driver and everything it started: the process group Forge made for it."""
    with STARTING:
        if os.name == "nt":  # no group to end: end the app-server's process tree
            for pid in SERVER:
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.killpg(0, signal.SIGTERM)
        os._exit(1)


def watch() -> None:
    """Pass on each line saying Forge recorded an id, and end everything once Forge, the calling
    process, goes away: its end of stdin closes."""
    for _ in sys.stdin:
        RECORDED.release()
    end()


def late() -> None:
    emit(refused="start")
    end()


def main() -> int:
    emit(driver=os.getpid())  # Forge records this process, as it now runs, before it sends a request
    request = json.loads(sys.stdin.readline())
    sandbox = Sandbox(request["sandbox"])
    threading.Thread(target=watch, daemon=True).start()
    timer = threading.Timer(START, late)
    timer.daemon = True
    timer.start()
    codex = Codex()  # starts `codex app-server`; a failed start stops it again
    timer.cancel()
    try:
        client = getattr(codex, "_client", None)
        # ponytail: Codex() takes no handler and its default accepts commands and file changes, so
        # Forge swaps the private one. SDK_PIN keeps it where this looks; a moved one refuses here.
        if not hasattr(client, "_approval_handler"):
            emit(refused="handler")
            return 3
        client._approval_handler = decline
        if request.get("read"):  # after a crash: how the turns Forge never saw end, ended
            try:
                turns = client.thread_read(request["thread"], include_turns=True).thread.turns
            except InvalidRequestError as error:
                # Only Codex saying it has no such conversation means it reports no status. Its
                # other failures, such as history it can't load, name the id too but prove
                # nothing, so they end this with no read line and Forge refuses.
                if error.message != f"thread not loaded: {request['thread']}":
                    raise
                turns = []
            emit(read=[[turn.id, turn.status.value] for turn in turns])
            return 0
        settings = {"approval_mode": ApprovalMode.deny_all, "sandbox": sandbox,
                    "cwd": request["cwd"], "config": request["config"] or None}
        resumed = None
        if request.get("thread"):
            try:
                resumed = codex.thread_resume(request["thread"], **settings)
            except JsonRpcError as error:
                emit(fresh=f"Codex couldn't resume its conversation: {error.message}")
        thread = resumed or codex.thread_start(**settings)
        emit(thread=thread.id, continued=resumed is not None)
        RECORDED.acquire()
        thread.set_name(request["name"])
        turn = thread.turn(request["prompt"], approval_mode=ApprovalMode.deny_all, sandbox=sandbox)
        emit(turn=turn.id)
        usage, items = None, []
        for event in turn.stream():
            payload = event.payload
            # warnings=False: the SDK's own models warn about their own union and enum fields.
            params = (payload.params if isinstance(payload, UnknownNotification) else
                      payload.model_dump(mode="json", by_alias=True, exclude_none=True,
                                         warnings=False))
            emit(event=event.method, params=params)
            if isinstance(payload, ItemCompletedNotification):
                items.append(payload.item)
            elif isinstance(payload, ThreadTokenUsageUpdatedNotification):
                usage = params["tokenUsage"]["last"]
            elif isinstance(payload, TurnCompletedNotification):
                error = payload.turn.error
                # The same final text as the SDK's TurnResult.final_response.
                emit(status=payload.turn.status.value, error=error and error.message,
                     text=_final_assistant_response_from_items(items), usage=usage)
        return 0
    finally:
        codex.close()


if __name__ == "__main__":
    sys.exit(main())
