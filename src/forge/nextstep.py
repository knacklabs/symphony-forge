"""`forge next` and the session-start context hook: where things stand, and the exact next commands.

It reads each story from its own worktree (or from the default branch once it landed), each task
from its worktree (merged once its state is on the default branch) and each fix from its worktree.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from forge import approval, repo, story

# A task's or fix's status, as WORK and CLOSE write it: what it means and what to run next.
STATUS = {
    "started": ("{label} is started; its worker hasn't run yet.", "forge work {item}"),
    "working": ("A worker is building {label}.", "wait for it to finish, then forge close {item}"),
    "reviewing": ("{label} is being reviewed.", "wait for the review, then forge close {item}"),
    "fixing": ("Close stopped on {label}: {reason}.", "forge work {item}"),
    "waiting for checks": ("{label} is waiting for its checks.", "forge close {item}"),
    "ready": ("{label} is ready and waiting for someone to merge it.",
              "merge its pull request, then forge next"),
}


def next_step(args: Any) -> int:
    print("\n".join(_report(repo.root())[0]))
    return 0


def context_hook(args: Any) -> int:
    lines, states = _report(repo.root())
    print("\n".join(lines + states))
    return 0


def _report(top: Path) -> tuple[list[str], list[str]]:
    """The lines `forge next` prints, and one state line per story and fix with its human touches."""
    lines: list[str] = []
    states: list[str] = []
    for key, (path, state, text) in sorted(_stories(top).items()):
        if state.get("status") == "done":
            continue
        title = state.get("title") or key
        found, tasks = _story(top, key, path, text, title)
        lines += found
        touches = state.get("touches", 0) + sum(task.get("touches", 0) for task in tasks)
        states.append(f"{title} ({state.get('status', 'planning')}): {_touches(touches)} so far.")
    for branch, path in sorted(story.worktrees(top).items()):
        name = branch.removeprefix("fix/")
        state = repo.read_state(name, path) if re.fullmatch(r"fix/[a-z0-9][a-z0-9-]*", branch) else None
        if state is not None:
            lines += _item(name, f"The fix {name}", state)
            states.append(f"The fix {name} ({state.get('status', 'started')}): "
                          f"{_touches(state.get('touches', 0))} so far.")
    if not lines:
        lines = ["No story or fix is in progress.",
                 'Next: forge story new <KEY> "<title>" for an item on plans/roadmap.json',
                 'Next: forge fix start "<why>" --done "<done when>"']
    return lines, states


def _stories(top: Path) -> dict[str, tuple[Path | None, dict[str, Any], str]]:
    """Each story's worktree (None once it is only on the default branch), state and doc text."""
    found: dict[str, tuple[Path | None, dict[str, Any], str]] = {}
    ref = story.landed_ref(top)
    listing = repo.git("ls-tree", "-r", "--name-only", ref, "--", ".factory/stories/", cwd=top)
    for key in re.findall(r"^\.factory/stories/([A-Z][A-Z0-9-]*)/story\.json$", listing, re.M):
        found[key] = (None, story.json_of(story.show(top, ref, repo.state_path(key))),
                      story.show(top, ref, f"plans/{key}.md") or "")
    for key, path in story.stories_here(top).items():
        state, doc = repo.read_state(key, path), path / "plans" / f"{key}.md"
        if state is not None and found.get(key, (None, {}, ""))[1].get("status") != "done":
            found[key] = (path, state, doc.read_text(encoding="utf-8") if doc.is_file() else "")
    return found


def _story(top: Path, key: str, path: Path | None, text: str,
           title: str) -> tuple[list[str], list[dict[str, Any]]]:
    """A story's lines, and its tasks' states."""
    try:
        doc = story.parse(text)
    except ValueError as exc:
        return [f"The story doc of {title} is malformed: {exc}.",
                f"Next: edit plans/{key}.md, then run forge next"], []
    digest = approval.waiting_digest(key, path) if path else None
    if digest:
        return _approval(top, key, path, title, digest), []
    trees = story.worktrees(top)
    states = {task["id"]: _task(top, key, task["id"], trees) for task in doc["tasks"]}
    merged = {task for task, state in states.items() if state.get("status") == "merged"}
    if states and len(merged) == len(states):
        if f"fix/{key.lower()}-done" in trees:  # its outcome fix is open; the fix's lines say so
            return [], list(states.values())
        return [f"Every part of {title} is merged; record its outcome.",
                f'Next: forge story done {key} "<outcome sentence>"'], list(states.values())
    lines: list[str] = []
    busy = [task["scope"] for task in doc["tasks"] if states[task["id"]] and task["id"] not in merged]
    for task in doc["tasks"]:
        if states[task["id"]] and task["id"] not in merged:
            item = f"{key}/{task['id']}"
            lines += _item(item, item, states[task["id"]])
    ready = [task["id"] for task in doc["tasks"]
             if not states[task["id"]] and set(task["after"]) <= merged
             and not any(story.overlaps(task["scope"], scope) for scope in busy)]
    if ready:
        lines += [f"{len(ready)} part{'s' if len(ready) != 1 else ''} of {title} can start now.",
                  *(f"Next: forge task start {key}/{task}" for task in ready)]
    return lines or [f"{title} is approved; its other parts wait for earlier parts to merge.",
                     "Next: git fetch origin, then forge next"], list(states.values())


def _approval(top: Path, key: str, path: Path, title: str, digest: str) -> list[str]:
    """Planning, read or waiting for approval: what's missing, or how to ask for approval."""
    try:
        story.check_read(key, path)
    except repo.Refused as refusal:
        problem, _, step = str(refusal).partition("\nNext: ")
        return [f"Planning {title}: {problem}", f"Next: {step}"]
    if not approval.signed_off(path):
        return [f"{title} can't be approved until the client's sign-off is recorded.",
                f"Next: {approval.REFUSALS['no_signoff'][1]}"]
    last = approval.last_refusal(top)
    why = last.read_text(encoding="utf-8").strip().rstrip(".") if last.is_file() else ""
    return [f"{title} is waiting for approval" + (f" (the last answer was not recorded: {why})." if why
                                                  else "."),
            f"Next: in Claude Code, show plans/{key}.md in Plan Mode and exit Plan Mode with it as the plan",
            f"Next: in Codex, ask request_user_input with id approve_plan_{digest}, question "
            '"Approve this plan?", header "Approve plan" and choices "Approve plan", '
            '"Request changes", "Stop"']


def _task(top: Path, key: str, task: str, trees: dict[str, Path]) -> dict[str, Any]:
    """A task's state: merged once on origin/<default>, else from its worktree, else {}."""
    item = f"{key}/{task}"
    text = story.show(top, story.landed_ref(top), repo.state_path(item))
    if text is not None:
        return {**story.json_of(text), "status": "merged"}
    path = trees.get(f"task/{key}-{task}")
    return (repo.read_state(item, path) if path else None) or {}


def _item(item: str, label: str, state: dict[str, Any]) -> list[str]:
    status = state.get("status") or "started"
    sentence, step = STATUS.get(status, ("{label} is {status}.", "forge close {item}"))
    if status == "started" and state.get("kind") == "story-done":  # Forge made the change already
        sentence, step = "{label} records a finished story's outcome.", "forge close {item}"
    values = {"item": item, "label": label, "status": status,
              "reason": str(state.get("reason") or "it has serious findings or red checks").rstrip(".")}
    return [sentence.format(**values), f"Next: {step.format(**values)}"]


def _touches(count: int) -> str:
    return f"{count} human touch{'es' if count != 1 else ''}"
