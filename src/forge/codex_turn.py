"""Run a Codex turn or chat request in the SDK's Python, away from Forge's own install.

Forge sends one JSON request after recording this driver's process id. The driver records the
app-server and thread ids with Forge before it acts, emits progress as JSON lines, and stops the
app-server if Forge closes stdin. A read, archive or attachment request runs no turn. A worker or
cold-read turn may assign its chat to the main checkout's Codex project after start or resume.
A turn Codex ends as failed because the model is at capacity is sent again, up to three times,
waiting twice as long each time, once Forge has the next turn on record as pending.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
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
# The fields of a hooks/list entry that say where the hook is and its state, not what it runs.
PLACE = {"key", "sourcePath", "source", "pluginId", "displayOrder", "enabled", "isManaged",
         "currentHash", "trustStatus"}
RETRIES = 3  # the times a turn Codex ends as at capacity is sent again, each wait twice the last
# ponytail: the tests' seam, like FORGE_CHECKS_WAIT
RETRY_WAIT = float(os.environ.get("FORGE_CODEX_RETRY_WAIT", "30"))


def emit(**line: Any) -> None:
    # The handler runs on the SDK's reader thread, so lines take turns.
    with LOCK:
        print(json.dumps(line), flush=True)


def overloaded(error: dict[str, Any]) -> bool:
    """Whether a failed turn's error says the model is at capacity, so the turn is worth another go."""
    return (error.get("codexErrorInfo") == "serverOverloaded" or
            re.search(r"at capacity|overloaded", error.get("message", ""), re.I) is not None)


def decline(method: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """Forge's answer to every request Codex sends in a read-only turn, known or unknown."""
    emit(declined=method)
    return {"decision": "decline"}


def accept(method: str, params: dict[str, Any] | None) -> dict[str, Any]:
    """Forge's answer to every request Codex sends in a full-access turn: no human is there to ask."""
    emit(accepted=method)
    return {"decision": "accept"}


class Client(CodexClient):
    """The SDK's client, which prints the app-server's id as soon as it starts, before Codex()
    waits on initialize, so Forge has it on record even when Codex never answers."""

    def start(self) -> None:
        with STARTING:
            super().start()
            SERVER.append(self._proc.pid)
        emit(pid=self._proc.pid)
        RECORDED.acquire()

    def close(self) -> None:
        if os.name == "nt" and self._proc is not None:
            # The SDK stops only the .cmd launcher; stop its app-server child first.
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self._proc.pid)],
                           capture_output=True)
        super().close()


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
        client._approval_handler = accept if sandbox is Sandbox.full_access else decline
        if request.get("archive"):
            codex.thread_archive(request["thread"])
            emit(archived=True)
            return 0
        if request.get("attach"):
            try:
                client._request_raw("thread/attachment/add", {
                    "threadId": request["thread"], "attachmentType": "pull_request",
                    "identityKey": request["identity"],
                    "payload": request["payload"]})
                emit(attached=True)
            except Exception as error:
                emit(attachment_failed=str(error))
            return 0
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
        # deny_all is the SDK's approval policy "never" with no reviewer: Codex never asks and its
        # automatic reviewer isn't used. The SDK's only other mode, auto_review, uses it.
        settings = {"approval_mode": ApprovalMode.deny_all, "sandbox": sandbox,
                    "cwd": request["cwd"], "config": request["config"] or None}
        # Codex skips a project hook it doesn't trust, and any change to one un-trusts it. Forge
        # trusts its own hooks for this thread by their current hash (decision 0102) and starts
        # nothing while any other project hook waits for the user's review.
        state = {}
        for entry in client._request_raw("hooks/list", {"cwds": [request["cwd"]]})["data"]:
            for hook in entry["hooks"]:
                if hook["source"] != "project" or hook["trustStatus"] in ("trusted", "managed"):
                    continue
                # The whole definition, every field but where and how Codex found it, so a field
                # Forge doesn't know (or a changed timeout) makes the hook not Forge's.
                if {key: value for key, value in hook.items()
                        if key not in PLACE} not in request["hooks"]:
                    emit(refused="hook", hook=f'{hook["eventName"]} hook "{hook.get("command")}"',
                         path=hook["sourcePath"])
                    return 3
                state[hook["key"]] = {"trusted_hash": hook["currentHash"]}
        if state:  # nested: a hook's key holds dots, which a dotted override would split
            settings["config"] = {**(settings["config"] or {}), "hooks": {"state": state}}
        # The SDK's high-level Thread discards these settings; null effort follows the model.
        request_raw = client._request_raw
        def selected_request(method, params=None):
            response = request_raw(method, params)
            if method in ("thread/start", "thread/resume"):
                effort, cursor = response.get("reasoningEffort"), None
                while effort is None:
                    page = request_raw("model/list", {"includeHidden": True, "cursor": cursor})
                    effort = next((model["defaultReasoningEffort"] for model in page["data"]
                                   if model["model"] == response["model"]), None)
                    cursor = page.get("nextCursor")
                    if not cursor:
                        break
                emit(selection={"model": response["model"], "effort": effort})
            return response
        client._request_raw = selected_request
        resumed = None
        if request.get("thread"):
            try:
                resumed = codex.thread_resume(request["thread"], **settings)
            except JsonRpcError as error:
                reason = error.message
                if "already has an active writer" in reason:
                    time.sleep(2)
                    try:
                        resumed = codex.thread_resume(request["thread"], **settings)
                    except JsonRpcError as retry_error:
                        reason = retry_error.message
                if resumed is None:
                    emit(fresh=f"Codex couldn't resume its conversation: {reason}")
        if request.get("ephemeral"):
            settings["ephemeral"] = True
        thread = resumed or codex.thread_start(**settings)
        emit(thread=thread.id, continued=resumed is not None)
        RECORDED.acquire()
        if not request.get("ephemeral"):
            try:
                matches = set()
                cursor = None
                root = Path(request["root"]).resolve()
                while True:
                    page = client._request_raw("project/list", {"cursor": cursor} if cursor else {})
                    for project in page["data"]:
                        if any(Path(path).resolve() == root for path in project.get("roots", [])):
                            matches.add(project["id"])
                    cursor = page.get("nextCursor")
                    if not cursor:
                        break
                if len(matches) == 1:
                    project_id = next(iter(matches))
                    client._request_raw("thread/metadata/update", {
                        "threadId": thread.id, "projectId": project_id})
                    emit(project=project_id)
                else:
                    emit(project_skipped="no matching project" if not matches else
                         "several matching projects")
            except Exception as error:
                emit(project_skipped=f"Codex could not update the chat project: {error}. "
                     "Check Codex and try again")
        if not request.get("ephemeral") and resumed is None:
            thread.set_name(request["name"])
        prompt = (request["prompt"] if resumed is not None else
                  request.get("fresh_prompt", request["prompt"]))
        for attempt in range(RETRIES + 1):
            turn = thread.turn(prompt, approval_mode=ApprovalMode.deny_all, sandbox=sandbox)
            emit(turn=turn.id)
            usage, items, busy = None, [], False
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
                    busy = payload.turn.status.value == "failed" and overloaded(
                        params["turn"].get("error") or {})
                    # The same final text as the SDK's TurnResult.final_response.
                    emit(status=payload.turn.status.value, error=error and error.message,
                         text=_final_assistant_response_from_items(items), usage=usage)
            if not busy or attempt == RETRIES:
                break
            wait = RETRY_WAIT * 2 ** attempt
            emit(retry=wait, attempt=attempt + 2, of=RETRIES + 1)
            RECORDED.acquire()  # the next turn is on record as pending before it starts
            time.sleep(wait)
        return 0
    finally:
        codex.close()


if __name__ == "__main__":
    sys.exit(main())
