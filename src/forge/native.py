"""Session-owned reads use the existing item record, lock and machine lane."""
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from forge import codex, machine, repo

COMMANDS = [{"words": "handback", "run": "handback", "changes_state": True, "position": 36,
             "help": "Record the result of a session subagent",
             "args": [(("target",), {}), (("--text",), {}),
                      (("--round",), {"type": int, "required": True}),
                      (("--subagent",), {"required": True})],
             "listing": "| `forge handback <target>` | Records a session subagent result and frees its held place |"}]


def session() -> dict[str, Any]:
    """Find the host above shell/uv wrappers; its identity outlives each forge command."""
    tool = repo.coordinator()
    if tool is None:
        raise repo.Refused("Run this command from the coordinating Claude Code or Codex session.", "")
    if os.name == "nt":
        listed = repo.run("powershell", "-NoProfile", "-NonInteractive", "-Command",
                          "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId "
                          "| ConvertTo-Json -Compress")
        listed.check_returncode()
        parents = {row["ProcessId"]: row["ParentProcessId"] for row in json.loads(listed.stdout)}
    else:
        listed = repo.run("ps", "-axo", "pid=,ppid=")
        listed.check_returncode()
        parents = {int(pid): int(parent) for pid, parent in
                   (line.split() for line in listed.stdout.splitlines())}
    pid, seen = os.getppid(), set()
    owner = node = None
    while pid > 1 and pid not in seen:
        seen.add(pid)
        candidate = codex.identity(pid)
        command = (candidate or {}).get("command", "").replace("\\", "/")
        name = Path(command if os.name == "nt" else command.split()[0]).name.lower() if command else ""
        if name.startswith(tool):
            owner = candidate
            break
        if node is None and name in ("node", "node.exe"):
            node = candidate
        pid = parents.get(pid, 0)
    owner = owner or node
    if not owner or "started" not in owner or "command" not in owner:
        app = "Claude Code" if tool == "claude" else "Codex"
        raise repo.Refused(f"Forge cannot find the coordinating {app} session; nothing ran.", "")
    return {"id": f"{tool}:{owner['pid']}:{owner['started']}", "process": owner}


def offer(top: Path, target: str, result: dict[str, Any], prompt: str, fresh_prompt: str,
          why: str, models: dict[str, str]) -> int:
    owner = session()
    lock = codex._item_file(top, target, ".lock", "Grill")
    path = lock.with_suffix(".json")
    held = codex._take(lock, owner["process"])
    if held:
        process, alive = held
        repo.refuse(codex.REFUSALS["busy" if alive else "unknown"], pid=process.get("pid"),
                    lock=lock, item=target, command="read")
    entry = None
    try:
        _, unknown = codex._stop_leftover(path)
        if unknown:
            repo.refuse(codex.REFUSALS["leftover"], pid=unknown, item=target, command="read")
        previous = codex.record(top, target, "Grill").get("native") or {}
        resume = previous.get("subagent") if not why and previous.get("session") == owner["id"] else None
        round_number = max(result["round"], codex._json(path).get("native_round", 0) + 1)
        result = {**result, "round": round_number}
        reason = why or ("continue this session's reader" if resume else
                         "because the session that ran its last round has ended" if previous else
                         "start a reader in this session")
        with redirect_stdout(sys.stderr):
            entry = machine.join("read", top, target, models.get("model"), models.get("effort"))
        entry.update(native=True, session=owner["id"], round=round_number,
                     process=owner["process"], forge=owner["process"])
        with codex._one_at_a_time(lock):
            machine.started(entry, owner["process"]["pid"])
            codex._record(path, **({"claude": None} if result["reader"] == "codex" else
                                  {"conversation": None, "start": None}), native_round=round_number,
                          pending={"checkout": top.resolve().as_posix(), "session": owner["id"],
                                   "entry": entry, "result": result})
    except BaseException:
        if entry:
            machine.leave(entry)
        lock.unlink(missing_ok=True)
        raise
    instruction = ("Continue the named reader with the short brief as a background subagent.\n"
                   "Start fresh with the whole brief if this session cannot reach that subagent."
                   if resume else "Start a reader as a background subagent with the whole brief.")
    instruction += (f"\nChange no files. Hand its final message and id back with forge handback {target} "
                    f"--round {round_number} --subagent <id> --text <message>.")
    print(json.dumps({"target": target, "role": "reader", "tool": result["reader"],
                      "checkout": top.resolve().as_posix(), **models, "round": round_number,
                      "prompt": prompt if resume else fresh_prompt, "fresh_prompt": fresh_prompt,
                      "subagent": resume, "reason": reason, "instruction": instruction}))
    return 0


def cancel(entry: dict[str, Any]) -> None:
    """Free only this handout; a later round may already hold the same item."""
    top = Path(entry["checkout_root"])
    path = codex._item_file(top, entry["item"], ".json", "Grill" if entry["kind"] == "read" else "Build")
    lock = path.with_suffix(".lock")
    with codex._one_at_a_time(lock):
        pending = codex._json(path).get("pending") or {}
        machine.leave(entry)
        if pending.get("entry", {}).get("id") == entry["id"]:
            codex._record(path, pending=None)
            if all(codex._json(lock).get(key) == entry["process"].get(key) for key in ("pid", "started")):
                lock.unlink(missing_ok=True)


def handback(args: Any) -> int:
    from forge import story

    owner, top = session(), repo.root()
    path = codex._item_file(top, args.target, ".json", "Grill")
    lock = path.with_suffix(".lock")
    with codex._one_at_a_time(lock):
        pending = codex._json(path).get("pending")
        held = codex._json(lock)
        if not pending or args.round != pending["result"]["round"]:
            raise repo.Refused("That round was stopped or replaced, so Forge recorded nothing.", "")
        if pending["session"] != owner["id"] or any(
                held.get(key) != owner["process"][key] for key in ("pid", "started")):
            raise repo.Refused("This session has no pending read for that target.", "forge read " + args.target)
        if not args.subagent.strip():
            raise repo.Refused("Give the reader subagent's id with its result.", "")
        live = any(entry["id"] == pending["entry"]["id"] for entry in machine.entries())
        if not live:
            raise repo.Refused("That round was stopped or replaced, so Forge recorded nothing.", "")
        try:
            codex._record(path, native={"session": owner["id"], "subagent": args.subagent})
            return story.read_result(Path(pending["checkout"]), args.target, pending["result"],
                                     (args.text if args.text is not None else sys.stdin.read()).strip())
        finally:
            codex._record(path, pending=None)
            machine.leave(pending["entry"])
            lock.unlink(missing_ok=True)
