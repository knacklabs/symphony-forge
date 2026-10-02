"""`forge next` and the session-start context hook: where things stand, and the exact next commands.

It reads each story from its own worktree (or from the default branch once it landed), each task
from its worktree (merged once its state is on the default branch) and each fix from its worktree.
A spec's success check is read from the default branch as landed, and listed first. With nothing
in progress and an empty roadmap, it offers discovery until a problem card is filled.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from forge import approval, board, close, codex, records, repo, review, story

COMMANDS = [
    {
        "words": "next", "run": "next_step", "changes_state": False,
        "help": "Say where things stand and give the exact next command",
        "args": [], "position": 50,
        "listing": "| `forge next` | Says where things stand and gives the exact next command |",
    },
    {
        "words": "hook context", "run": "context_hook", "changes_state": False,
        "help": "Session start: print forge next and the story state",
        "args": [], "position": 240,
        "listing": "| `forge hook context` | Session start: prints `forge next` and the story's state |",
    },
    {
        "words": "hook handoff", "run": "handoff_hook", "changes_state": False,
        "help": "Before compaction: save forge next beside the agent's decisions and lessons",
        "args": [], "position": 245,
        "listing": "| `forge hook handoff` | Saves current state before context compaction |",
    },
]

GROUP_HELP = {
    "hook": "Internal: the one entry point that git hooks, host hooks and CI call",
}

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

DISCOVERY = "docs/product/DISCOVERY.md"
# A problem card's six fields; a card is filled once any of them reads something other than unknown.
CARD_FIELD = re.compile(r"^- (?:Job|Workaround|Cost|Who feels it|How often|Evidence):(.*)$", re.M)
MUST_ANSWER_TOPICS = ("Sign-off person", "Demo workflow", "Users and roles",
                      "Existing systems", "Sign-in", "Personal data", "Production host")
ANSWER_TOPICS = (*MUST_ANSWER_TOPICS, "Data import", "Email or SMS", "Domain",
                 "Backups and uptime", "Log retention")
ANSWER_LINE = re.compile(r"^- [^:]+: (.+) \(([^(),]+), (\d{4}-\d{2}-\d{2})\)$")
LATER_LINE = re.compile(r"^- [^:]+: later, when (\S.*)$")


def parse_answers(top: Path) -> dict[str, list[tuple[str, str] | None]]:
    """Read topic entries from this checkout's answers section; None marks a malformed entry."""
    page = top / "docs/product/BRIEF.md"
    text = page.read_text(encoding="utf-8") if page.is_file() else ""
    found: dict[str, list[tuple[str, str] | None]] = {}
    in_answers = False
    for line in text.splitlines():
        if line == "## Answers":
            in_answers = True
            continue
        if line.startswith("#") and re.match(r"^#{1,6} ", line):
            in_answers = False
        if not in_answers:
            continue
        topic = next((name for name in ANSWER_TOPICS
                      if line == f"- {name}" or line.startswith((f"- {name}:", f"- {name} "))), None)
        if topic is None:
            continue
        if line[2:].partition(":")[0] != topic:
            found.setdefault(topic, []).append(None)
            continue
        answer = ANSWER_LINE.fullmatch(line)
        later = LATER_LINE.fullmatch(line)
        if later:
            found.setdefault(topic, []).append(("later", ""))
        elif answer and answer[1].strip() and answer[2].strip():
            try:
                date.fromisoformat(answer[3])
            except ValueError:
                found.setdefault(topic, []).append(None)
            else:
                found.setdefault(topic, []).append((answer[1], answer[2]))
        else:
            found.setdefault(topic, []).append(None)
    return found


def open_must_answer_topics(top: Path) -> list[str]:
    """Topics that cannot be treated as one settled answer before client sign-off."""
    answers = parse_answers(top)
    return [topic for topic in MUST_ANSWER_TOPICS
            if len(answers.get(topic, [])) != 1 or answers[topic][0] is None
            or answers[topic][0][0] in ("ask the client", "later")]


def next_step(args: Any) -> int:
    print("\n".join(_report(repo.root())[0]))
    return 0


def context_hook(args: Any) -> int:
    lines, states = _report(repo.root())
    print("\n".join(lines + states))
    return 0


def handoff_hook(args: Any) -> int:
    top = repo.root()
    path = repo.forge_dir(top) / "handoff.md"
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    heading = "## Decisions and lessons\n"
    notes = old[old.index(heading):] if heading in old else heading
    current = "\n".join(_report(top)[0])
    temp = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                       prefix="handoff-", suffix=".tmp", delete=False)
    try:
        with temp:
            temp.write(f"# Forge handoff\n\n## Current state ({repo.now()[:10]})\n\n"
                       f"{current}\n\n{notes}")
        os.replace(temp.name, path)
    finally:
        Path(temp.name).unlink(missing_ok=True)
    return 0


def _report(top: Path) -> tuple[list[str], list[str]]:
    """The lines `forge next` prints, and one state line per story and fix with its human touches."""
    lines: list[str] = []
    states: list[str] = []
    refusals: dict[Path, str] = {}
    trees = story.worktrees(top)
    merged_prs = {pr["headRefName"] for pr in _prs(top, "merged", "headRefName")} if trees else set()
    prs = {pr["headRefName"]: pr for pr in _prs(top, "open", "headRefName,url,statusCheckRollup,isDraft")
           if isinstance(pr.get("url"), str)} if trees else {}
    for key, (path, state, text) in sorted(_stories(top).items()):
        if state.get("status") == "done":
            continue
        title = state.get("title") or key
        found, tasks = _story(top, key, path, text, title, trees, merged_prs, prs, refusals)
        lines += found
        touches = state.get("touches", 0) + sum(task.get("touches", 0) for task in tasks)
        states.append(f"{title} ({state.get('status', 'planning')}): {_touches(touches)} so far.")
    for branch, path in sorted(trees.items()):
        kind, _, name = branch.partition("/")  # forge/<name> is migrate's fix
        state = (repo.read_state(name, path) if kind in ("fix", "forge")
                 and re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) else None)
        if state is not None:
            if branch in merged_prs:
                state = {**state, "status": "merged"}
            lines += _item(name, f"The fix {name}", state, top, path, prs, refusals)
            states.append(f"The fix {name} ({state.get('status', 'started')}): "
                          f"{_touches(state.get('touches', 0))} so far.")
    lines = _due(top) + (lines or _idle(top))
    if (top / "forge.toml").is_file():
        cfg = _report_config(top, refusals)
        if repo.is_prototype(top, cfg):
            open_topics = open_must_answer_topics(top)
            if open_topics:
                notice = ["Open before sign-off in docs/product/BRIEF.md:",
                          *(f"- {topic}" for topic in open_topics),
                          "Next: answer these topics in docs/product/BRIEF.md, then forge next"]
                lines = notice + lines if len(trees) > 1 else lines + notice
    if _needs_demo_address(top):
        lines += ["Next: connect the repo on our deploy platform, pick a subdomain, and record its "
                  "address in docs/product/BRIEF.md under ## Demo as - Address: <url>."]
    if repo.now()[:10] >= board.CHECK_DATE:  # the three success numbers, from the check date on
        lines.append(board.numbers_line(top, _report_config(top, refusals)["checks"]))
    lines += [f"{path}: {reason}" for path, reason in refusals.items()]
    return lines, states


def _needs_demo_address(top: Path) -> bool:
    """Read the fetched default branch, not a demo address still being edited here."""
    if not (top / "forge.toml").is_file():
        return False
    ref = story.landed_ref(top)
    if story.show(top, ref, "Dockerfile") is None:
        return False
    if not repo.is_prototype(top, repo.default_config(top), (ref,)):
        return False
    brief = story.show(top, ref, "docs/product/BRIEF.md") or ""
    demo = re.search(r"^## Demo\s*$([\s\S]*?)(?=^## |\Z)", brief, re.M)
    return not demo or not re.search(r"^- Address: https?://\S+\s*$", demo[1], re.M)


def _report_config(path: Path, refusals: dict[Path, str]) -> dict[str, Any]:
    try:
        return repo.config(path)
    except repo.Refused as refusal:
        refusals[path] = str(refusal).splitlines()[0]
        return repo.DEFAULTS


def _due(top: Path) -> list[str]:
    """A success check for each spec whose check date has come and whose stories are all done."""
    ref = story.landed_ref(top)
    items = story.json_of(story.show(top, ref, records.ROADMAP)).get("items")
    keys: dict[str, list[str]] = {}
    for item in items if isinstance(items, list) else []:
        if (isinstance(item, dict) and isinstance(item.get("spec"), str)
                and re.fullmatch(r"[A-Z][A-Z0-9-]*", str(item.get("key")))
                and item.get("status") != "superseded"):  # a replaced story never finishes
            keys.setdefault(item["spec"], []).append(item["key"])
    lines: list[str] = []
    for rel, spec_keys in sorted(keys.items()):
        if not all(story.json_of(story.show(top, ref, repo.state_path(key))).get("status") == "done"
                   for key in spec_keys):
            continue
        found = records.due_check(story.show(top, ref, rel) or "", repo.now()[:10])
        if found:
            slug = Path(rel).stem
            lines += [f"Every story from the {found[0] or slug} spec is done and its check date has "
                      f"passed; measure {found[1]}.",
                      f'Next: forge fix start "Record the {slug} success result" --done "The {slug} '
                      'spec records its result"',
                      f'Next: forge spec measure {slug} --result "<measured result>"']
    return lines


def _idle(top: Path) -> list[str]:
    """Nothing in progress: discovery while the roadmap is empty and no card is filled, then its spec."""
    ref = story.landed_ref(top)
    items = story.json_of(story.show(top, ref, records.ROADMAP)).get("items")
    if isinstance(items, list) and any(
            not isinstance(item, dict) or item.get("status") != "superseded" for item in items):
        return ["No story or fix is in progress.",
                'Next: forge story new <KEY> "<title>" for an item on plans/roadmap.json',
                'Next: forge fix start "<why>" --done "<done when>"']
    fields = CARD_FIELD.findall(story.show(top, ref, DISCOVERY) or "")
    if any(value.strip().lower() not in ("", "unknown") for value in fields):
        return ["No story or fix is in progress and the roadmap is empty; the discovery notes hold "
                "a problem card, so write its spec.",
                'Next: forge fix start "Write the spec for the chosen problem" --done "A confirmed '
                'spec whose Why names the problem card"',
                "Next: forge spec save <slug>"]
    return ["No story or fix is in progress and the roadmap is empty, so start with discovery, as "
            "the Forge skill's Discovery section says.",
            'Next: forge fix start "Find the problem to solve" --done "The discovery notes hold a '
            'filled problem card and the brief names it"']


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
           title: str, trees: dict[str, Path], merged_prs: set[str], prs: dict[str, dict[str, Any]],
           refusals: dict[Path, str]
           ) -> tuple[list[str], list[dict[str, Any]]]:
    """A story's lines, and its tasks' states."""
    notes, doc_hash, required = "", "", False
    if path is None:  # like forge task start: the story branch's copy while it exists
        for ref in (f"story/{key}", story.landed_ref(top)):
            notes = story.show(top, ref, f"plans/{key}.read.md") or ""
            required = story.rounds(notes, story.show(top, ref, repo.state_path(key)))
            if required:
                text = story.show(top, ref, f"plans/{key}.md") or text
                doc_hash = repo.run("git", "rev-parse", f"{ref}:plans/{key}.md", cwd=top).stdout.strip()
                break
    elif (path / "plans" / f"{key}.md").is_file():
        notes = story._text(path / "plans" / f"{key}.read.md")  # pyright: ignore[reportPrivateUsage]
        doc_hash = repo.git("hash-object", "--", f"plans/{key}.md", cwd=path)
        required = story.rounds(notes, story._text(path / repo.state_path(key)))  # pyright: ignore[reportPrivateUsage]
    try:
        doc = story.parse(text, top)
    except ValueError as exc:
        return [f"The story doc of {title} is malformed: {exc}.",
                f"Next: edit plans/{key}.md, then run forge next"], []
    digest = approval.waiting_digest(key, path) if path else None
    if digest:
        return _approval(top, key, path, title, digest, refusals, "\n## For the builders" in text), []
    states = {task["id"]: _task(top, key, task["id"], trees, merged_prs)
              for task in doc["tasks"]}
    merged = {task for task, state in states.items() if state.get("status") == "merged"}
    cleanup = [line for task in doc["tasks"]
               if (tree := trees.get(f"task/{key}-{task['id']}")) and task["id"] in merged
               for line in _item(f"{key}/{task['id']}", f"{key}/{task['id']}",
                                 states[task["id"]], top, tree, prs, refusals)]
    behind = story.plan_behind(top, key, story.landed_ref(top))  # the rows here are old
    if states and len(merged) == len(states) and not behind:
        if f"fix/{key.lower()}-done" in trees:  # its outcome fix is open; the fix's lines say so
            return cleanup, list(states.values())
        return cleanup + [f"Every part of {title} is merged; record its outcome.",
                f'Next: forge story done {key} "<outcome sentence>"'], list(states.values())
    lines: list[str] = cleanup
    busy = [task["scope"] for task in doc["tasks"] if states[task["id"]] and task["id"] not in merged]
    for task in doc["tasks"]:
        if states[task["id"]] and task["id"] not in merged:
            item = f"{key}/{task['id']}"
            lines += _item(item, item, states[task["id"]], top,
                           trees.get(f"task/{key}-{task['id']}"), prs, refusals)
    if behind:
        return lines + [behind], list(states.values())
    merged |= {after for task in doc["tasks"] for after in task["after"] if "/" in after
               and _task(top, *after.split("/"), trees, merged_prs).get("status") == "merged"}
    waits = {task["id"]: [after if "/" in after else f"{key}/{after}" for after in task["after"]
                          if after not in merged] for task in doc["tasks"] if not states[task["id"]]}
    ready = [task["id"] for task in doc["tasks"] if waits.get(task["id"]) == []
             and not any(story.overlaps(task["scope"], scope) for scope in busy)]
    # A task held back by another story's task would wait out of sight, so say which.
    waiting = [f"{key}/{task} waits for {', '.join(deps)} to merge first." for task, deps in waits.items()
               if any(not dep.startswith(f"{key}/") for dep in deps)]
    reread = _next_round(key, notes, doc_hash, title, required)
    if reread:  # a doc changed after approval gets a round before its next task starts
        return lines + reread, list(states.values())
    if ready:
        lines += [f"{len(ready)} part{'s' if len(ready) != 1 else ''} of {title} can start now"
                  f"{'; start them together.' if len(ready) > 1 else '.'}",
                  *(f"Next: forge task start {key}/{task}" for task in ready)]
    if waiting:
        lines += waiting + ([] if ready else ["Next: git fetch origin, then forge next"])
    return lines or [f"{title} is approved; its other parts wait for earlier parts to merge.",
                     "Next: git fetch origin, then forge next"], list(states.values())


def _approval(top: Path, key: str, path: Path, title: str, digest: str,
              refusals: dict[Path, str], builders: bool) -> list[str]:
    """Planning, read or waiting for approval: what's missing, or how to ask for approval."""
    notes = story._text(path / "plans" / f"{key}.read.md")  # pyright: ignore[reportPrivateUsage]
    reread = _next_round(key, notes, repo.git("hash-object", "--", f"plans/{key}.md", cwd=path), title,
                         story.rounds(notes))
    if reread:
        return reread
    try:
        story.check_read(key, path)
    except repo.Refused as refusal:
        problem, _, step = str(refusal).partition("\nNext: ")
        return [f"Planning {title}: {problem}", f"Next: {step}"]
    if repo.is_prototype(path, _report_config(path, refusals)):
        return [f"{title} can't be approved until the client's sign-off is recorded.",
                f"Next: {approval.REFUSALS['no_signoff'][1]}"]
    why = story._text(approval.last_refusal(top)).strip().rstrip(".")  # pyright: ignore[reportPrivateUsage]
    shown = f"plans/{key}.md" + (" from its title down to ## For the builders" if builders else "")
    return [f"{title} is waiting for approval" + (f" (the last answer was not recorded: {why})." if why
                                                  else "."),
            f"Next: in Claude Code, show {shown} in Plan Mode and exit Plan Mode with it as the plan",
            f"Next: in Codex, show {shown}, then ask request_user_input with id approve_plan_{digest}, "
            'question "Approve this plan?", header "Approve plan" and choices "Approve plan", '
            '"Request changes", "Stop"']


def _next_round(key: str, text: str, doc_hash: str, title: str, required: bool) -> list[str]:
    """The next round of a read in rounds (`required`) whose latest round had findings or whose doc
    changed: `text` is the notes, `doc_hash` the doc's git hash."""
    notes = f"plans/{key}.read.md"
    record, findings = story._record(text)  # pyright: ignore[reportPrivateUsage]
    done, number = int(record.get("round") or 1), story.undisposed(findings)
    if not required:
        return []
    if not record.get("round"):
        return [f"Planning {title}: {notes} has no round of cold read.", f"Next: forge read {key}"]
    if not story.passed(record, findings):
        why = f"round {done} of its cold read had findings"
    elif record.get("read_hash") != doc_hash:
        why = f"plans/{key}.md changed after round {done} of its cold read"
    else:
        return []
    nudge = " It isn't converging: ask the human whether to split the story instead of reading on."
    return [f"Planning {title}: {why}, so round {done + 1} is next.{nudge if done + 1 >= 4 else ''}",
            f"Next: {f'give finding {number} in {notes} a disposition, then ' if number else ''}"
            f"forge read {key}"]


def _task(top: Path, key: str, task: str, trees: dict[str, Path],
          merged_prs: set[str]) -> dict[str, Any]:
    """A task's state: merged on the default branch or GitHub, else from its worktree."""
    item = f"{key}/{task}"
    text = story.show(top, story.landed_ref(top), repo.state_path(item))
    if text is not None:
        return {**story.json_of(text), "status": "merged"}
    branch = f"task/{key}-{task}"
    path = trees.get(branch)
    state = (repo.read_state(item, path) if path else None) or {}
    return {**state, "status": "merged"} if branch in merged_prs else state


def _item(item: str, label: str, state: dict[str, Any], top: Path,
          path: Path | None, prs: dict[str, dict[str, Any]] | None,
          refusals: dict[Path, str]) -> list[str]:
    status = state.get("status") or "started"
    ready = repo.ready_path(item, top)
    try:
        receipt = json.loads(ready.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        receipt = {}
    if not isinstance(receipt, dict):
        receipt = {}
    if receipt.get("tidied") is True:
        return []
    if status == "merged" and path:
        if repo.merge_setting(top) == "agent" and receipt.get("review") == "clean":
            return [f"{label} is merged; Forge needs to finish tidying up.",
                    f"Next: forge merge {item}"]
        return [f"{label} is merged; clean up its worktree.",
                f"Next: git worktree remove {shlex.quote(str(path))}"]
    if ready.is_file():
        branch = state.get("branch")
        if (branch and receipt.get("review") == "clean" and
                repo.run("git", "rev-parse", "--verify", branch, cwd=top).stdout.strip()
                == receipt.get("commit")):
            status = "ready"
    sentence, step = STATUS.get(status, ("{label} is {status}.", "forge close {item}"))
    # forge work holds the item's lock, recording its own process, until its round ends.
    lock = codex._item_file(top, item, ".lock", "Build")
    if status == "working" and (not lock.exists() or codex._alive(codex._json(lock)) is False):
        sentence, step = "{label}'s worker has stopped.", "forge close {item}"
    switch = (state.get("why"), state.get("done_when")) == (close.WHY, close.DONE)
    if (status == "ready" and state.get("kind") != "migrate" and not switch
            and repo.merge_setting(top) == "agent"):
        sentence, step = "{label} is ready to merge.", "forge merge {item}"
    if status == "started" and state.get("kind") == "story-done":  # Forge made the change already
        sentence, step = "{label} records a finished story's outcome.", "forge close {item}"
    if status == "started" and switch:
        sentence, step = "{label} is started.", "the repo owner runs forge merge enable in their own terminal"
    if status == "started" and state.get("kind") == "migrate":  # forge migrate made it already
        sentence, step = "{label} moves this repo to the new Forge.", "forge close {item}"
    values = {"item": item, "label": label, "status": status,
              "reason": str(state.get("reason") or "it has serious findings or red checks").rstrip(".")}
    if status == "fixing":
        findings = [f.get("title", "a serious finding") for _, f in
                    review.blocking(state.get("review") or {}) if isinstance(f, dict)]
        if findings:
            values["reason"] = "; ".join(findings)
    pr = (prs or {}).get(state.get("branch", "")) or {}
    checks = (_report_config(path or top, refusals)["checks"]
              if pr and status == "waiting for checks" else [])
    ready = status == "ready" or (status == "waiting for checks" and checks
                                  and board._green_at(pr, checks) and not pr.get("isDraft"))
    if status == "ready" and not pr.get("url") and state.get("branch") and shutil.which("gh"):
        # The bulk list missed it (GitHub can time out on it); ask for this branch's link alone.
        view = repo.run("gh", "pr", "view", state["branch"], "--json", "url", "--jq", ".url", cwd=top)
        pr = {"url": view.stdout.strip()} if view.returncode == 0 and view.stdout.strip() else pr
    if ready and (url := pr.get("url")):
        if status == "waiting for checks" and not switch and repo.merge_setting(top) == "agent":
            return [f"{label}'s checks passed; finish preparing its automatic merge.",
                    f"Next: forge close {item}"]
        next_step = (step.format(**values) if step == "forge merge {item}"
                     else f"merge {url}, then forge next")
        return [f"{label} is ready to merge: {url}", f"Next: {next_step}"]
    return [sentence.format(**values), f"Next: {step.format(**values)}"]


def _prs(top: Path, state: str, fields: str) -> list[dict[str, Any]]:
    """GitHub's pull requests in a state, when gh is available; git's landed state still works offline."""
    if not shutil.which("gh"):
        return []
    done = repo.run("gh", "pr", "list", "--state", state, "--limit", "1000", "--json", fields, cwd=top)
    try:
        prs = json.loads(done.stdout) if done.returncode == 0 else []
    except ValueError:
        return []
    return [pr for pr in prs if isinstance(pr, dict) and isinstance(pr.get("headRefName"), str)
            ] if isinstance(prs, list) else []


def _touches(count: int) -> str:
    return f"{count} human touch{'es' if count != 1 else ''}"
