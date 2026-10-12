"""Session-owned reads use the existing item record, lock and machine lane."""
import json
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from typing import Any

from forge import codex, machine, repo

COMMANDS = [{"words": "handback", "run": "handback", "changes_state": True, "position": 36,
             "help": "Record the result of a session subagent",
             "args": [(("item",), {"metavar": "target"}), (("--text",), {}),
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


@contextmanager
def hold(top: Path, item: str, kind: str, models: dict[str, str]) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """The session takes the item's lock and joins the agent line; both stay held until handback,
    and only a failure before the handout gives them back."""
    owner = session()
    command = "read" if kind == "Grill" else "work"
    lock = codex._item_file(top, item, ".lock", kind)
    held = codex._take(lock, owner["process"])
    if held:
        process, alive = held
        repo.refuse(codex.REFUSALS["busy" if alive else "unknown"], pid=process.get("pid"),
                    lock=lock, item=item, command=command)
    entry = None
    try:
        _, unknown = codex._stop_leftover(lock.with_suffix(".json"))
        if unknown:
            repo.refuse(codex.REFUSALS["leftover"], pid=unknown, item=item, command=command)
        with redirect_stdout(sys.stderr):
            entry = machine.join(command, top, item, models.get("model"), models.get("effort"))
        entry.update(native=True, session=owner["id"], process=owner["process"], forge=owner["process"])
        yield owner, entry
    except BaseException:
        if entry:
            machine.leave(entry)
        lock.unlink(missing_ok=True)
        raise


def _start(top: Path, item: str, kind: str, owner: dict[str, Any], entry: dict[str, Any],
           **pending: Any) -> None:
    """The session's process now holds the place, and the item's record names the pending round."""
    lock = codex._item_file(top, item, ".lock", kind)
    entry["round"] = pending["result"]["round"]
    with codex._one_at_a_time(lock):
        machine.started(entry, owner["process"]["pid"])
        codex._record(lock.with_suffix(".json"), native_round=entry["round"],
                      pending={"checkout": top.resolve().as_posix(), "session": owner["id"],
                               "entry": entry, **pending})


def offer(top: Path, target: str, result: dict[str, Any], prompt: str, fresh_prompt: str,
          why: str, models: dict[str, str]) -> int:
    with hold(top, target, "Grill", models) as (owner, entry):
        path = codex._item_file(top, target, ".json", "Grill")
        previous = codex.record(top, target, "Grill").get("native") or {}
        resume = previous.get("subagent") if not why and previous.get("session") == owner["id"] else None
        round_number = max(result["round"], codex._json(path).get("native_round", 0) + 1)
        result = {**result, "round": round_number}
        reason = why or ("continue this session's reader" if resume else
                         "because the session that ran its last round has ended" if previous else
                         "start a reader in this session")
        codex._record(path, **({"claude": None} if result["reader"] == "codex" else
                              {"conversation": None, "start": None}))
        _start(top, target, "Grill", owner, entry, result=result)
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


def resumable(top: Path, item: str, owner: dict[str, Any]) -> tuple[dict[str, Any], str | None, str]:
    """A build round's last subagent record, the subagent to continue, and why it starts fresh."""
    previous = codex.record(top, item).get("native") or {}
    resume = previous.get("subagent") if previous.get("session") == owner["id"] else None
    return previous, resume, ("" if resume or not previous else
                              "because the session that ran its last round has ended")


def hand_out(top: Path, item: str, owner: dict[str, Any], entry: dict[str, Any], round_number: int,
             role: str, brief: str, fresh_brief: str, resume: str | None, why: str,
             chosen: dict[str, str], family: str) -> None:
    """Write the round's briefs beside the item's record, record it pending and say how to run it."""
    short, whole = (codex._item_file(top, item, suffix, "Build") for suffix in (".brief.md", ".fresh.md"))
    whole.write_text(fresh_brief, encoding="utf-8")
    short.write_text(brief, encoding="utf-8")
    run_id = repo.record_event(top, item, "run start", kind="work", round=round_number,
                               family=family, model=chosen.get("model"), effort=chosen.get("effort"))
    _start(top, item, "Build", owner, entry, result={"round": round_number}, role=role,
           head=repo.git("rev-parse", "HEAD", cwd=top), started=time.time(), at=repo.now(),
           model=chosen, run_id=run_id)
    place = top.resolve().as_posix()
    print(f"Run this round as a background {role} subagent of this session, working in {place}.")
    # forge.local.toml can change the model, and role files hold only forge.toml's.
    print(f"Start it on {chosen['model']} at {chosen['effort']} effort, over the role's own model.")
    if resume:
        print(f"Continue subagent {resume} with: Read {short.as_posix()} and follow it.")
        print(f"If this session can't reach it, start a new {role} subagent with: Read "
              f"{whole.as_posix()} and follow it.")
    else:
        print(f"Start a new {role} subagent with: Read {whole.as_posix()} and follow it."
              + (f" ({why})" if why else ""))
    print(f"When it ends: forge handback {item} --round {round_number} --subagent <its id>, "
          "with its last message on stdin.")


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
    path = codex._item_file(top, args.item, ".json", "Build")
    if not codex._json(path).get("pending"):
        path = codex._item_file(top, args.item, ".json", "Grill")
    lock = path.with_suffix(".lock")
    kept = False
    with codex._one_at_a_time(lock):
        pending = codex._json(path).get("pending")
        held = codex._json(lock)
        if not pending or args.round != pending["result"]["round"]:
            raise repo.Refused("That round was stopped or replaced, so Forge recorded nothing.", "")
        if pending["session"] != owner["id"] or any(
                held.get(key) != owner["process"][key] for key in ("pid", "started")):
            what, command = ("build round", "work") if "role" in pending else ("read", "read")
            raise repo.Refused(f"This session has no pending {what} for that target.",
                               f"forge {command} {args.item}")
        if not args.subagent.strip():
            raise repo.Refused("Give the subagent's id with its result.", "")
        live = any(entry["id"] == pending["entry"]["id"] for entry in machine.entries())
        if not live:
            raise repo.Refused("That round was stopped or replaced, so Forge recorded nothing.", "")
        said = (args.text if args.text is not None else sys.stdin.read()).strip()
        try:
            if "role" in pending:
                kept = _work_result(path, args.item, pending, said, owner, args.subagent)
                return 0
            codex._record(path, native={"session": owner["id"], "subagent": args.subagent})
            return story.read_result(Path(pending["checkout"]), args.item, pending["result"], said)
        finally:
            if not kept:
                codex._record(path, pending=None)
                machine.leave(pending["entry"])
                lock.unlink(missing_ok=True)


def _work_result(path: Path, item: str, pending: dict[str, Any], said: str, owner: dict[str, Any],
                 subagent: str) -> bool:
    """What a build round does once its worker ends; True keeps the place for the commit nudge."""
    from forge import task, worker

    top, head = Path(pending["checkout"]), pending["head"]
    state = repo.read_state(item, top) or {}
    worker._restore_settings(item, top, state)
    # A session subagent has no worker guard in the commit hook, so a committed change comes back too.
    if repo.git("diff", "--name-only", head, "HEAD", "--", "forge.toml", cwd=top) and not (
            task.settings_allowed(item, top, state)):
        repo.git("checkout", head, "--", "forge.toml", cwd=top)
        repo.git("commit", "-q", "-m", "Restore forge.toml; settings change in their own fix",
                 "--", "forge.toml", cwd=top)
        print("Restored forge.toml changes committed on this branch; settings change in their own fix.",
              flush=True)
    left = repo.git("status", "--porcelain", "-uall", cwd=top).splitlines()
    if said and left and not pending.get("nudged"):
        codex._record(path, pending={**pending, "nudged": True, "said": said})
        print(f"Send this to subagent {subagent}, then hand back again:\n{worker.COMMIT_NUDGE}")
        return True
    outcome = "completed" if said else "failed"
    asked = worker.questions(pending.get("said", ""), said)
    identity = repo.record_event(top, item, "worker question", question=asked) if asked else None
    codex._record(path, question=asked or None, question_id=identity,
                  **({"native_round": None} if said else {}),  # finished: next offers close
                  native={"session": owner["id"], "subagent": subagent,
                          "head": repo.git("rev-parse", "HEAD", cwd=top),
                          "rounds": pending["result"]["round"], "outcome": outcome})
    repo.record_event(top, item, "run end", kind="work", round=pending["result"]["round"],
                      run_id=pending["run_id"], outcome=outcome)
    if asked:
        print(f"{asked}\nNext: forge work {item} --note \"<answer>\"")
        if worker.is_published(top, item):  # the pull request's record shows the open question
            from forge import close
            close._refresh_record(top, item, state)
    repo.record_timing(top, item, "worker round", pending["at"],
                       time.monotonic() - (time.time() - pending["started"]), outcome, pending["model"])
    if left:
        print("Warning: the worker ended its round with changes left uncommitted, so the review "
              f"won't see them: {', '.join(line.split(maxsplit=1)[1] for line in left)}.")
    if not said:
        raise repo.Refused("The subagent ended with no message, so Forge recorded the round as failed.",
                           f"forge work {item}")
    return False
