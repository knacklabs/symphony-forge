"""One Codex turn for Forge, run by the Codex SDK's own Python; Forge itself never imports the SDK.

Forge sends one JSON request line on stdin: the checkout (cwd), the conversation's name, the prompt,
the sandbox and the kind's settings (config). This prints one JSON line per step, in order: the
app-server's process id, before anything else; the thread; the turn; each event and each declined
request; then the turn's end with its status, error, final text and token usage, only when Codex
reports it. Codex gets two minutes to start, or this prints a refusal and ends.

Forge starts this in its own process group and keeps stdin open while it runs. Once stdin closes,
Forge has gone, and this ends the whole group, itself and the app-server it started, even while
Codex is still starting.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import threading
from typing import Any

from openai_codex import ApprovalMode, Codex, Sandbox
from openai_codex._run import _final_assistant_response_from_items
from openai_codex.models import (ItemCompletedNotification, ThreadTokenUsageUpdatedNotification,
                                 TurnCompletedNotification, UnknownNotification)

LOCK = threading.Lock()
START = 120  # the seconds Codex gets to start: Codex() waits on initialize with no timeout
CLIENT: list[Codex] = []  # the client once it has started, for end() on Windows


def emit(**line: Any) -> None:
    # The handler runs on the SDK's reader thread, so lines take turns.
    with LOCK:
        print(json.dumps(line), flush=True)


def decline(method: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """Forge's answer to every request Codex sends, known or unknown."""
    emit(declined=method)
    return {"decision": "decline"}


def end() -> None:
    """End this driver and everything it started: the process group Forge made for it."""
    if os.name == "nt":  # no group to end: close the client if it has started
        for codex in CLIENT:
            codex.close()
    else:
        os.killpg(0, signal.SIGTERM)
    os._exit(1)


def watch() -> None:
    """End everything once Forge, the calling process, goes away: its end of stdin closes."""
    sys.stdin.read()
    end()


def late() -> None:
    emit(refused="start")
    end()


def main() -> int:
    request = json.loads(sys.stdin.readline())
    sandbox = Sandbox(request["sandbox"])
    threading.Thread(target=watch, daemon=True).start()
    timer = threading.Timer(START, late)
    timer.daemon = True
    timer.start()
    codex = Codex()  # starts `codex app-server`; a failed start stops it again
    timer.cancel()
    CLIENT.append(codex)
    try:
        client = getattr(codex, "_client", None)
        emit(pid=getattr(getattr(client, "_proc", None), "pid", None))
        # ponytail: Codex() takes no handler and its default accepts commands and file changes, so
        # Forge swaps the private one. SDK_PIN keeps it where this looks; a moved one refuses here.
        if not hasattr(client, "_approval_handler"):
            emit(refused="handler")
            return 3
        client._approval_handler = decline
        thread = codex.thread_start(approval_mode=ApprovalMode.deny_all, sandbox=sandbox,
                                    cwd=request["cwd"], config=request["config"] or None)
        emit(thread=thread.id)
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
