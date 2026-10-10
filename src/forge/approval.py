"""v1 approval: one human approval binds a story doc's "What changes for you" and "Done when".

`forge hook approval` runs after Claude Code's ExitPlanMode and AskUserQuestion and after Codex's
request_user_input. It keeps today's trust checks (docs/specs/plan-approval.md), applied to the
section hash: a completed call, the exact digest, the runtime, the tool, a stable session and event
identity, replay refusal and exactly one story waiting for that digest. It also holds the client
sign-off gate, and counts every answered question as a human touch of the item being worked on.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from forge import __version__, machine, repo, story

REFUSALS = {
    "bad_payload": ("The hook input is not a JSON object.", "forge doctor"),
    "wrong_runtime": ("{tool} is not {runtime}'s approval tool, so nothing was recorded.", "forge next"),
    "not_completed": ("The approval question was cancelled or failed, so nothing was recorded.",
                      "forge next"),
    "unsupported": ("The approval doesn't match the approval contract, so nothing was recorded.",
                    "forge next"),
    "not_approved": ('The answer was "{answer}", not "Approve plan", so nothing was recorded.',
                     "forge next"),
    "no_identity": ("The approval has no session or event id to guard against a replay, so nothing "
                    "was recorded.", "forge next"),
    "replay": ("This approval was already recorded once; a replay records nothing.", "forge next"),
    "no_match": ("The approved plan matches no story doc waiting for approval; it may have changed "
                 "since it was shown.", "forge next"),
    "several": ("The approved plan matches {count} story docs, so nothing was recorded.",
                'give each a different "What changes for you" or "Done when", then forge next'),
    "no_signoff": ("This client's sign-off isn't recorded yet, so the approval was not recorded.",
                   'forge decision new client-signoff, then forge decision accept client-signoff '
                   '--by "<client name>"'),
}
OTHER_VERSION = ("{repo} pins Forge {pinned}, but {installed} is installed; the approval is recorded "
                 "anyway. {advice}")

TOOLS = {"claude": "ExitPlanMode", "codex": "request_user_input"}
QUESTIONS = ("AskUserQuestion", "request_user_input")
SUCCESS = {"success", "succeeded", "completed"}
CHOICES = ["Approve plan", "Request changes", "Stop"]


def ships(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    from forge import sync

    return {".claude/skills/remote-approval/SKILL.md":
            sync._synced_text(".claude/skills/remote-approval/SKILL.md",
                              "skills/remote-approval/SKILL.md")}


def hook(args: Any) -> int:
    try:
        payload = json.loads(sys.stdin.read() or "null")
    except ValueError:
        payload = None
    if not isinstance(payload, dict):
        repo.refuse(REFUSALS["bad_payload"])
    tool, answered = payload.get("tool_name"), _answered(payload)
    approving = tool == "ExitPlanMode" or (tool == "request_user_input" and _asks_approval(payload))
    if not approving and not (tool in QUESTIONS and answered):
        return 0  # any other tool (forge doctor's sample among them) records nothing
    cwd = payload.get("cwd")
    top = repo.root(cwd if isinstance(cwd, str) and Path(cwd).is_dir() else None)
    if approving:
        try:
            _approve(top, payload, tool)
        except repo.Refused as refusal:
            if answered:
                _touch(top)
            last_refusal(top).write_text(str(refusal).partition("\nNext: ")[0], encoding="utf-8")
            raise
        last_refusal(top).unlink(missing_ok=True)
    else:
        _touch(top)
    return 0


def waiting_digest(key: str, top: Path) -> str | None:
    """The story doc's section hash when the story waits for a first or renewed approval."""
    state, doc = repo.read_state(key, top), top / "plans" / f"{key}.md"
    if state is None or not doc.is_file():
        return None
    digest = story.approval_hash(doc.read_text(encoding="utf-8"))
    return None if (state.get("approval") or {}).get("hash") == digest else digest


def last_refusal(top: Path) -> Path:
    """Why the last approval recorded nothing, for `forge next`. Local, never committed."""
    return repo.forge_dir(top) / "approval-refused.txt"


def _approve(top: Path, payload: dict[str, Any], tool: str) -> None:
    runtime = "codex" if "turn_id" in payload else "claude"  # ponytail: only Codex payloads carry turn_id
    if tool != TOOLS[runtime]:
        repo.refuse(REFUSALS["wrong_runtime"], tool=tool, runtime=runtime.capitalize())
    if not _completed(payload):
        repo.refuse(REFUSALS["not_completed"])
    digest = _claude_digest(payload) if runtime == "claude" else _codex_digest(payload)
    session, event = _text(payload.get("session_id")), _text(payload.get("tool_use_id"))
    if not session or not event:
        repo.refuse(REFUSALS["no_identity"])
    marker = hashlib.sha256(f"{runtime}\0{session}\0{event}".encode("utf-8")).hexdigest()
    chat_used = repo.forge_dir(top) / "approvals" / marker
    if chat_used.exists():
        repo.refuse(REFUSALS["replay"])
    checkouts = dict.fromkeys([machine.main_checkout(top), *machine.remembered()])
    matches = [(key, path) for checkout in checkouts
               for key, path in story.stories_here(checkout).items()
               if waiting_digest(key, path) == digest]
    if not matches:
        repo.refuse(REFUSALS["no_match"])
    if len(matches) > 1:
        repo.refuse(REFUSALS["several"], count=len(matches))
    key, path = matches[0]
    pinned = repo.config(path)["version"]
    story_used = repo.forge_dir(path) / "approvals" / marker
    if story_used.exists():
        repo.refuse(REFUSALS["replay"])
    story.check_read(key, path)
    if repo.is_prototype(path):
        repo.refuse(REFUSALS["no_signoff"])
    state = repo.read_state(key, path) or {}
    notes = story._record(story._text(path / "plans" / f"{key}.read.md"))[0]  # pyright: ignore[reportPrivateUsage]
    # The round it passed, so the story keeps needing a passing round even if its notes go.
    approval = {"by": f"human-via-{runtime.capitalize()}", "at": repo.now(), "hash": digest,
                "runtime": runtime, "session": session, "event": event,
                "round": int(notes.get("round") or 1)}
    state.update(status="approved", approval=approval, touches=state.get("touches", 0) + 1)
    rel = repo.write_state(key, repo.add_step(state, "approved"), path)
    title = state.get("title") or key
    repo.commit_state(f"Approve the plan: {title}", f"plans/{key}.md", f"plans/{key}.read.md", rel,
                      top=path)
    for used in dict.fromkeys((chat_used, story_used)):
        used.parent.mkdir(exist_ok=True)
        used.write_text(json.dumps(approval), encoding="utf-8")
    print(f"Recorded the approval of {title}.")
    # A version mismatch warns only after the approval is recorded.
    if pinned.removeprefix("v") != __version__:
        from forge import upgrade

        installed, checkout = f"v{__version__}", machine.main_checkout(path)
        advice = (f"Ask your agent to install Forge {pinned}."
                  if upgrade._numbers(pinned) > upgrade._numbers(installed)  # pyright: ignore[reportPrivateUsage]
                  else f"Ask your agent to upgrade {checkout} to {installed}.")
        print(OTHER_VERSION.format(repo=checkout, pinned=pinned, installed=installed,
                                   advice=advice), file=sys.stderr)
    # Tasks start from origin, so the approval must reach it; a failed push never undoes the approval.
    if repo.run("git", "remote", "get-url", "origin", cwd=path).returncode == 0 and repo.run(
            "git", "push", "-q", "origin", f"story/{key}", cwd=path).returncode:
        print(f"Forge couldn't push story/{key}; run git push origin story/{key} so tasks see "
              "this approval.")
    _to_promoted(key, path)


def _to_promoted(key: str, path: Path) -> None:
    """Merge the story branch into a task promoted from a fix, so the approved doc, its notes, the
    story's state and its roadmap entry reach that task's pull request. On any failure, leave the
    task as it was and name the merge to finish."""
    folder = story.worktrees(path).get(f"task/{key}-SPEC")
    state = repo.read_state(f"{key}/SPEC", folder) if folder else None
    if not state or "done_when" not in state:  # only a promoted fix's state has a done-when
        return
    if repo.run("git", "rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=folder).returncode == 0:
        print(f"{key}/SPEC's folder has a merge in progress, so Forge left it untouched.\n"
              f"Next: in {folder}, finish that merge, then git merge story/{key}")
        return
    merged = repo.run("git", "merge", "-q", "--no-edit", "-m", "Bring in the approved plan",
                      f"story/{key}", cwd=folder)
    if merged.returncode:
        if repo.run("git", "rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=folder).returncode == 0:
            repo.run("git", "merge", "--abort", cwd=folder)
        print(f"Forge couldn't bring the approved plan into {key}/SPEC's branch.\n"
              f"Next: in {folder}, git merge story/{key}, then forge close {key}/SPEC")


def _completed(payload: dict[str, Any]) -> bool:
    """The call finished: it didn't fail or get cancelled, and any status it gives is a success."""
    response = payload.get("tool_response")
    response = response if isinstance(response, dict) else {}
    if any(part.get("is_error") is True or part.get("cancelled") is True for part in (payload, response)):
        return False
    return response.get("status") is None or _text(response.get("status")).lower() in SUCCESS


def _answered(payload: dict[str, Any]) -> bool:
    """The human answered: the call completed with a response, and a question's response holds an
    answer. A plan that ExitPlanMode completed was accepted by the human."""
    response = payload.get("tool_response")
    if not _completed(payload) or not isinstance(response, dict):
        return False
    if payload.get("tool_name") == "ExitPlanMode":
        return True
    answers = response.get("answers")
    if not isinstance(answers, dict):
        return False
    for answer in answers.values():
        choices = answer.get("answers") if isinstance(answer, dict) else [answer]
        if isinstance(choices, list) and any(isinstance(choice, str) and choice.strip()
                                            for choice in choices):
            return True
    return False


def _claude_digest(payload: dict[str, Any]) -> str:
    """The section hash of the plan text a successful ExitPlanMode showed."""
    response, tool_input = payload.get("tool_response"), payload.get("tool_input")
    if not isinstance(response, dict):
        repo.refuse(REFUSALS["unsupported"])
    plan = tool_input.get("plan") if isinstance(tool_input, dict) else None
    if plan is None:  # a no-argument ExitPlanMode has the plan only in its response
        plan = response.get("plan")
    documented = response.get("plan") == plan and isinstance(response.get("isAgent"), bool)
    if not isinstance(plan, str) or not plan or (response.get("status") is None and not documented):
        repo.refuse(REFUSALS["unsupported"])
    digest = story.approval_hash(plan)
    if digest is None:
        repo.refuse(REFUSALS["no_match"])
    return digest


def _codex_digest(payload: dict[str, Any]) -> str:
    """The digest a completed Codex approval question carries in its id, when it follows the contract."""
    tool_input, response = payload.get("tool_input"), payload.get("tool_response")
    questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    answers = response.get("answers") if isinstance(response, dict) else None
    if (payload.get("async") is True or not isinstance(questions, list) or len(questions) != 1
            or not isinstance(questions[0], dict) or not isinstance(answers, dict)):
        repo.refuse(REFUSALS["unsupported"])
    question = questions[0]
    qid = _text(question.get("id"))
    match = re.fullmatch(r"approve_plan_([0-9a-f]{64})", qid)
    options = question.get("options")
    labels = ([option.get("label") if isinstance(option, dict) else option for option in options]
              if isinstance(options, list) else None)
    if (match is None or labels != CHOICES or _text(question.get("question")) != "Approve this plan?"
            or _text(question.get("header")) != "Approve plan" or set(answers) != {qid}):
        repo.refuse(REFUSALS["unsupported"])
    chosen = answers[qid].get("answers") if isinstance(answers[qid], dict) else None
    if not isinstance(chosen, list) or len(chosen) != 1 or not isinstance(chosen[0], str):
        repo.refuse(REFUSALS["unsupported"])
    if chosen[0] != "Approve plan":
        repo.refuse(REFUSALS["not_approved"], answer=chosen[0])
    return match[1]


def _asks_approval(payload: dict[str, Any]) -> bool:
    tool_input = payload.get("tool_input")
    questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    return isinstance(questions, list) and any(
        isinstance(question, dict) and _text(question.get("id")).startswith("approve_plan_")
        for question in questions)


def _touch(top: Path) -> None:
    """Add a human touch to the story, task or fix this checkout works on; elsewhere, nothing."""
    item = _item_here(top)
    state = repo.read_state(item, top) if item else None
    if state is not None:
        state["touches"] = state.get("touches", 0) + 1
        repo.write_state(item, state, top)


def _item_here(top: Path) -> str:
    kind, _, name = repo.current_branch(top).partition("/")
    if kind == "task":  # KEY and TASK both hold hyphens, so match the task state files here
        return next((f"{path.parent.parent.name}/{path.stem}"
                     for path in (top / ".factory" / "stories").glob("*/tasks/*.json")
                     if f"{path.parent.parent.name}-{path.stem}" == name), "")
    ok = {"story": story.KEY, "fix": re.compile(r"[a-z0-9][a-z0-9-]*")}.get(kind)
    return name if ok and ok.fullmatch(name) else ""


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


COMMANDS = [{
    "words": "hook approval", "run": "hook", "changes_state": True,
    "help": "After a plan or question tool: record approvals and count human touches",
    "args": [], "position": 250,
    "listing": "| `forge hook approval` | After the plan and question tools: records approvals and counts human touches |",
}]
