"""Ask before a large fix starts; keep unanswered choices above routine advice."""
import json
import re
import shlex
from fnmatch import fnmatchcase
from pathlib import Path

from forge import repo, time_records


def size_choice(top: Path, item: str, state: dict, files: list[str]) -> None:
    """Include the stop in the first published fix commit, before any teammate can pick it up."""
    from forge import githooks, sync

    if not files or state.get("allow_large"):
        return
    files = sorted({path.replace("\\", "/") for path in files})
    patterns = [pattern.removeprefix(":(glob)") for pattern in repo.TEST_PATHS]
    generated = repo.generated_files(top, files) | set(sync.files(top, repo.config(top), check_syntax=False))
    lockfiles = {"uv.lock", "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock", "bun.lockb",
                 "poetry.lock", "Pipfile.lock", "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock"}
    code = sorted(path for path in files if not (
        path.lower().endswith(".md") or path.startswith((".factory/", "plans/")) or path in generated
        or Path(path).name in lockfiles
        or any(fnmatchcase(path, pattern) or fnmatchcase(path, pattern.removeprefix("**/"))
               for pattern in patterns)))
    if len(code) <= githooks.LIMIT:
        return
    question = f"Allow this fix to change {len(code)} code files: {', '.join(code)}?"
    state["stop"] = {"question": question, "predicted_files": code, "at": repo.now(),
                     "wait_id": repo.record_event(top, item, "owner wait start", reason="size", question=question)}


def require_size(top: Path, state: dict) -> None:
    stop = state.get("stop") or {}
    if stop.get("predicted_files") and not state.get("allow_large"):
        raise repo.Refused(stop["question"], f'cd {repo.quote(str(top))} && forge fix allow-large "<reason>"')


def worker_question(top: Path, item: str, pr: dict | None) -> str | None:
    from forge import codex, nextstep

    saved = codex.record(top, item)
    if pr is None:
        return saved.get("question")  # No shared answer: keep a failed or interrupted local round's question.
    recorded = nextstep.wait_records(top, item, pr.get("body") or "")
    asked = [event for event in recorded if event["open"] and event.get("event") == "worker question"]
    if asked:
        return asked[-1].get("question")
    return (None if saved.get("question_id") in {event.get("id") for event in recorded if not event["open"]}
            else saved.get("question"))


def answer_command(top: Path, item: str, state: dict, command: str) -> bool:
    """End only the Question blocks answered by this command, here or on another machine."""
    from forge import close, codex, nextstep, task

    pr = close.branch_pr(top, state) or {}
    question = worker_question(top, item, pr)
    if not question:
        return False
    blocks = [block.strip() for block in re.split(r"\n(?=Question:)", question)]
    remaining = [block for block in blocks if not re.search(r"\b" + re.escape(command) + r"\b", block)]
    if len(remaining) == len(blocks):
        return False
    for wait in nextstep.wait_records(top, item, pr.get("body") or ""):
        if wait["open"] and wait.get("event") == "worker question" and wait.get("question") == question:
            repo.record_event(top, item, "owner wait end", wait_id=wait["id"])
    unanswered = "\n\n".join(remaining) or None
    identity = repo.record_event(top, item, "worker question", question=unanswered) if unanswered else None
    codex._record(codex._item_file(top, item, ".json", "Build"), question=unanswered, question_id=identity)
    if task.unbuilt_fix(item, state, top):
        state["status"] = "started"
    return True


def documents(top: Path, trees: dict[str, Path]) -> list[str]:
    """Use the latest read of each document, rather than inherited copies in older worktrees."""
    from forge import nextstep, records, review, story

    latest, signoff, lines = {}, None, []
    for path in sorted(set(trees.values()) | {top}):
        for folder in ("specs", "decisions"):
            for notes in (path / "docs" / folder).glob("*.read.md"):
                record, _ = story._record(notes.read_text(encoding="utf-8"))
                doc = notes.with_name(notes.name.removesuffix(".read.md") + ".md")
                fields = story._record(story._text(doc))[0]
                rank = (record.get("read_at", ""), int(record.get("round") or 0), bool(record.get("loop_choice")),
                        fields.get("status") == "confirmed", path == top)
                rel = notes.relative_to(path).as_posix()
                if rel not in latest or rank > latest[rel][0]:
                    latest[rel] = rank, path, notes
        saved = json.loads(story._text(path / ".factory/client-signoff.json") or "{}")
        if saved.get("review"):
            rank = (len(saved.get("rounds") or [saved["review"]]), bool(saved.get("choice")),
                    not saved.get("stop"), path == top)
            if signoff is None or rank > signoff[0]:
                signoff = rank, path, saved
    for _, path, notes in latest.values():
        text = notes.read_text(encoding="utf-8")
        doc = notes.with_name(notes.name.removesuffix(".read.md") + ".md")
        if not doc.is_file():
            continue
        record, findings = story._record(text)
        content = doc.read_text(encoding="utf-8")
        fields, body = story._record(content)
        cfg = repo.config(path) if (path / "forge.toml").is_file() else repo.DEFAULTS
        if story.stopped(record, findings, cfg["cold_read_rounds"]):
            lines += nextstep._read_loop(doc.stem, content, text, path)
        elif (doc.parent.name == "specs" and fields.get("status") == "draft" and story.passed(record, findings)
              and record.get("read_hash") == repo.git("hash-object", "--", str(doc), cwd=path)):
            title = re.search(r"^# (.+)$", body, re.M)
            lines += [f"{review.plain(title[1]) if title else doc.stem} is ready for confirmation.", "Confirm this spec?",
                      f'Next: cd {repo.quote(str(path))} && forge spec confirm {doc.stem} --by "<name>"']
    if signoff is not None:
        _, path, saved = signoff
        if saved.get("stop"):
            lines += ["Client sign-off needs your choice.",
                      records.signoff_question(path, saved["review"], sample_data=repo.sample_data(path)),
                      f"Next: cd {repo.quote(str(path))} && {records.SIGNOFF_CHOICE}"]
    return lines


def first(top: Path, lines: list[str], prs: list[dict] | None = None) -> list[str]:
    """Move complete existing question blocks, with their commands, ahead of routine advice.

    The report already decides which choices are pending and supplies their exact wording.
    This pass changes only order and adds elapsed time from the shared wait history.
    """
    from forge import nextstep, story

    choices, rest = [], []
    index = 0
    while index < len(lines):
        line = lines[index]
        pending = (" is waiting for approval" in line or "asked a question. Ask the human:" in line
                   or line.startswith("Forge stopped ") or "Forge asks the owner." in line
                   or "is ready for confirmation." in line or line == "Client sign-off needs your choice."
                   or line.startswith("Close stopped ") and "round limit" in line)
        if not pending:
            rest.append(line)
            index += 1
            continue
        block = [line]
        index += 1
        while index < len(lines):
            block.append(lines[index])
            index += 1
            if block[-1].startswith("Next: "):
                if index < len(lines) and lines[index].startswith("Next: in Codex,"):
                    block.append(lines[index])
                    index += 1
                break
        command = block[-1]
        target = re.search(r"forge (?:close|work|read|spec confirm|decision accept) ([A-Za-z0-9/-]+)", command)
        plan = re.search(r"plans/([A-Z0-9-]+)\.md", command)
        size = re.search(r"The fix ([a-z0-9-]+)\.", line)
        item = target[1] if target else plan[1] if plan else size[1] if size else ""
        branches = {f"fix/{item}", f"forge/{item}", f"task/{item.replace('/', '-')}"}
        pr = next((pr for pr in prs or [] if pr.get("headRefName") in branches), {})
        body = pr.get("body") or ""
        waits = [event for event in nextstep.wait_records(top, item, body) if event["open"]] if item else []
        location = re.match(r"Next: cd (.+?) && ", command)
        where = (Path(shlex.split(location[1])[0]) if location else next(
            (path for branch, path in story.worktrees(top).items() if branch in branches or branch == f"story/{item}"), top))
        branch = pr.get("headRefName") or (f"task/{item.replace('/', '-')}" if "/" in item else f"fix/{item}")
        state = (repo.read_state(item, where) or nextstep.remote_state(top, item, branch, pr)) if item else {}
        stop = state.get("stop") or {}
        if item == "client-signoff":
            stop = json.loads(story._text(where / ".factory/client-signoff.json") or "{}").get("owner_wait") or {}
        reason = ("approval" if plan else "sign-off" if item == "client-signoff" else
                  "confirmation" if "spec confirm" in command else "read" if "cold read" in line else
                  "size" if stop.get("predicted_files") else "stuck" if "question" in stop else "review loop")
        selected = next((event for event in reversed(waits) if event.get("id") == stop.get("wait_id")), None)
        if selected is None:
            selected = next((event for event in reversed(waits) if event.get("reason") == reason
                             or event.get("event") == "worker question" and event.get("question") in block), None)
        since = selected.get("at") if selected else stop.get("at")
        if since is None and item and (plan or reason in ("read", "confirmation")):
            candidates = ([where / f"plans/{item}.read.md"] if plan or item.isupper() else
                          [where / f"docs/{folder}/{item}.read.md" for folder in ("specs", "decisions")])
            notes = next((path.read_text(encoding="utf-8") for path in candidates if path.is_file()), "")
            since = story._record(notes)[0].get("read_at")
        if since is None and reason == "sign-off":
            events = nextstep.board._event_history(top)[1].get(item, [])
            since = next((event.get("at") for event in reversed(events)
                          if event.get("event") == "run end" and event.get("kind") == "review"), None)
        started, now = time_records.when(since), time_records.when(repo.now())
        wait = (f"Waited {time_records.plain((now - started).total_seconds())}."
                if started and now else "Wait time is not recorded.")
        choices += [wait, *block]
    return choices + rest
