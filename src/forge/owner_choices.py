"""Ask before a large fix starts; keep unanswered choices above routine advice."""
import re
from fnmatch import fnmatchcase
from pathlib import Path

from forge import repo, time_records


def size_choice(top: Path, item: str, files: list[str]) -> bool:
    from forge import githooks

    state = repo.read_state(item, top) or {}
    patterns = [pattern.removeprefix(":(glob)") for pattern in repo.TEST_PATHS]
    code = sorted(path for path in {path.replace("\\", "/") for path in files} if not (
        path.lower().endswith(".md") or path.startswith((".factory/", "plans/"))
        or any(fnmatchcase(path, pattern) or fnmatchcase(path, pattern.removeprefix("**/"))
               for pattern in patterns)))
    if len(code) <= githooks.LIMIT or state.get("allow_large"):
        return False
    question = f"Allow this fix to change {len(code)} code files: {', '.join(code)}?"
    state["stop"] = {"question": question, "predicted_files": code, "at": repo.now(),
                     "wait_id": repo.record_event(top, item, "owner wait start", reason="size", question=question)}
    repo.commit_state("Ask for the size allowance before work", repo.write_state(item, state, top), top=top)
    print(f'Ask the owner: {question} Record the choice with forge fix allow-large "<reason>".')
    print(f'Next: cd {repo.quote(str(top))} && forge fix allow-large "<reason>"')
    return True


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
        target = re.search(r"forge (?:close|work|read) ([A-Za-z0-9/-]+)", command)
        plan = re.search(r"plans/([A-Z0-9-]+)\.md", command)
        size = re.search(r"The fix ([a-z0-9-]+)\.", line)
        item = target[1] if target else plan[1] if plan else size[1] if size else ""
        branches = {f"fix/{item}", f"forge/{item}", f"task/{item.replace('/', '-')}"}
        body = next((pr.get("body") or "" for pr in prs or [] if pr.get("headRefName") in branches), "")
        waits = [event for event in nextstep.wait_records(top, item, body) if event["open"]] if item else []
        since = next((event.get("at") for event in reversed(waits)
                      if event.get("reason") != "merge"), None)
        if since is None and item:
            ref = story.plan_ref(top, item) if plan or "cold read" in line else ""
            if ref:
                path = story.worktrees(top).get(f"story/{item}", top) / f"plans/{item}.read.md"
                notes = (path.read_text(encoding="utf-8") if path.is_file()
                         else story.show(top, ref, f"plans/{item}.read.md") or "")
                since = story._record(notes)[0].get("read_at")
            if since is None and "cold read" in line:
                for path in story.worktrees(top).values():
                    notes_path = path / f"docs/specs/{item}.read.md"
                    if notes_path.is_file():
                        since = story._record(notes_path.read_text(encoding="utf-8"))[0].get("read_at")
                        break
        started, now = time_records.when(since), time_records.when(repo.now())
        wait = (f"Waited {time_records.plain((now - started).total_seconds())}."
                if started and now else "Wait time is not recorded.")
        choices += [wait, *block]
    return choices + rest
