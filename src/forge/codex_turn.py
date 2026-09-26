"""One Codex turn for Forge, run by the Codex SDK's own Python; Forge itself never imports the SDK.

Forge sends one JSON request on stdin: the checkout (cwd), the conversation's name, the prompt, the
sandbox and the kind's settings (config). This prints one JSON line per step, in order: the
app-server's process id, before anything else; the thread; the turn; each event and each declined
request; then the turn's end with its status, error, final text and token usage, only when Codex
reports it.
"""
from __future__ import annotations

import json
import sys
import threading
from typing import Any

from openai_codex import ApprovalMode, Codex, Sandbox
from openai_codex._run import _final_assistant_response_from_items
from openai_codex.models import (ItemCompletedNotification, ThreadTokenUsageUpdatedNotification,
                                 TurnCompletedNotification, UnknownNotification)

LOCK = threading.Lock()


def emit(**line: Any) -> None:
    # The handler runs on the SDK's reader thread, so lines take turns.
    with LOCK:
        print(json.dumps(line), flush=True)


def decline(method: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """Forge's answer to every request Codex sends, known or unknown."""
    emit(declined=method)
    return {"decision": "decline"}


def main() -> int:
    request = json.load(sys.stdin)
    sandbox = Sandbox(request["sandbox"])
    codex = Codex()  # starts `codex app-server`; a failed start stops it again
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
