"""One Claude turn, run only by the isolated SDK environment's Python."""
import asyncio
from dataclasses import asdict
import json
import sys

from claude_agent_sdk import (
    AssistantMessage, ClaudeAgentOptions, ResultMessage, SystemMessage, TextBlock, ToolUseBlock,
    query,
)


def emit(event):
    if event.get("type") == "result":
        event = {**event, "errors": event.get("errors") or []}
    print(json.dumps(event, ensure_ascii=False), flush=True)


def event(message):
    """Keep the message fields Forge consumes, in the stream format its log already uses."""
    if isinstance(message, SystemMessage):
        return {**message.data, "type": "system", "subtype": message.subtype}
    if isinstance(message, AssistantMessage):
        content = [{"type": "text" if isinstance(block, TextBlock) else "tool_use", **asdict(block)}
                   for block in message.content if isinstance(block, (TextBlock, ToolUseBlock))]
        return {"type": "assistant", "message": {"model": message.model, "content": content}}
    if isinstance(message, ResultMessage):
        return {"type": "result", **asdict(message)}
    return {"type": type(message).__name__, **asdict(message)}


async def turn(request):
    options = ClaudeAgentOptions(
        cwd=request["cwd"], model=request["model"], effort=request["effort"],
        permission_mode=request["permission_mode"], resume=request.get("resume"),
        session_id=request.get("session_id"), add_dirs=request["add_dirs"],
        env={"FORGE_WORKER": "1"},
        system_prompt={"type": "preset", "preset": "claude_code"},
        setting_sources=["user", "project", "local"],
        stderr=lambda line: print(line, file=sys.stderr, flush=True))
    failed = False
    async for message in query(prompt=request["prompt"], options=options):
        if output := event(message):
            emit(output)
        if isinstance(message, ResultMessage):
            failed = failed or message.is_error
    return 1 if failed else 0


if __name__ == "__main__":
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        status = asyncio.run(turn(json.load(sys.stdin)))
    except Exception as error:
        # ResultError retains CLI diagnostics, including a missing resume session.
        if isinstance(getattr(error, "data", None), dict):
            emit({"type": "result", **error.data})
        print(str(error), file=sys.stderr, flush=True)
        status = getattr(error, "exit_code", None) or 1
    sys.exit(status)
