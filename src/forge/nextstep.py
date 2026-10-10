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
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from forge import __version__, approval, board, close, codex, records, repo, review, spotted, story, upgrade
from forge.task import _overlap, _started, developer, github_login, start_base

COMMANDS = [
    {
        "words": "next", "run": "next_step", "changes_state": False,
        "help": "Say where things stand and give the exact next command",
        "args": [(('--json',), {"action": "store_true", "help": "Print the machine view"})], "position": 50,
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
    "checks failed": ("{label}'s checks failed.", "forge work {item}"),
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
    top = repo.root()
    notice = upgrade.release_notice(top)
    history = board._machine_history(top) if args.json else None
    lines = _report(top, history)[0]
    print(json.dumps({**board.machine_board(top, history), "next": machine_next(lines)})
          if args.json else "\n".join(notice + lines))
    return 0


def machine_next(lines: list[str]) -> dict[str, str | None]:
    """Only the first Next line can be offered as a runnable step."""
    line = next((line for line in lines if line.startswith("Next: ")), None)
    command = line.removeprefix("Next: ") if line else ""
    try:
        words = shlex.split(command, comments=True)
    except ValueError:
        words = []
    # Treat shell operators outside quotes as syntax, but allow quoted titles containing them.
    lexer = shlex.shlex(command, posix=False, punctuation_chars=";&|<>`$()")
    lexer.whitespace_split = True
    try:
        syntax = list(lexer)
    except ValueError:
        syntax = [";"]
    unsafe = any(token and all(c in ";&|<>`$()" for c in token) for token in syntax)
    runnable = (len(words) >= 2 and words[0] == "forge" and not unsafe
                and not any(token in ("then", "or") for token in syntax)
                and not re.search(r"<[^>]*>|\$\(|`|[\r\n]", command))
    if runnable:
        from forge.cli import _parser
        try:
            _parser().parse_args(words[1:])
        except repo.Refused:
            runnable = False
    # A trailing shell comment explains the worker; it is not part of the command.
    if runnable:
        command = shlex.join(words) if "#" in command else command
    return {"command": command if runnable else None,
            "line": next((text for text in lines if not text.startswith("Next: ")),
                         "Nothing in progress.")}


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


def _report(top: Path, history: dict[str, Any] | None = None) -> tuple[list[str], list[str]]:
    """The lines `forge next` prints, and one state line per story and fix with its human touches."""
    lines: list[str] = []
    states: list[str] = []
    refusals: dict[Path, str] = {}
    trees = story.worktrees(top)
    merged_prs = {pr["headRefName"] for pr in _prs(top, "merged", "headRefName")} if trees else set()
    prs = {pr["headRefName"]: pr for pr in _prs(top, "open", "headRefName,url,isDraft")
           if isinstance(pr.get("url"), str)} if trees else {}
    if trees:
        prs.update({pr["headRefName"]: pr for pr in board._machine_prs(top)
                    if isinstance(pr.get("headRefName"), str)})
    for key, (path, state, text) in sorted(_stories(top, history).items()):
        if state.get("status") == "done":
            continue
        title = state.get("title") or key
        found, tasks = _story(top, key, path, text, title, trees, merged_prs, prs, refusals, history)
        lines += found
        touches = state.get("touches", 0) + sum(task.get("touches", 0) for task in tasks)
        states.append(f"{title} ({state.get('status', 'planning')}): {_touches(touches)} so far.")
    for branch, path in sorted(trees.items()):
        kind, _, name = branch.partition("/")  # forge/<name> is migrate's fix
        state = (repo.read_state(name, path) if kind in ("fix", "forge")
                 and re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) else None)
        if state is not None:
            if history is not None and repo.state_path(name) in history["expired"]:
                continue
            if branch in merged_prs:
                state = {**state, "status": "merged"}
            lines += _item(name, f"The fix {name}", state, top, path, prs, refusals)
            states.append(f"The fix {name} ({state.get('status', 'started')}): "
                          f"{_touches(state.get('touches', 0))} so far.")
    lines = _refresh(top, trees) + (lines or _idle(top))
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
    # Appended statistics never enter machine_next's first line or command.
    if history is None and repo.now()[:10] >= board.CHECK_DATE:
        lines.append(board.numbers_line(top, _report_config(top, refusals)["checks"]))
    lines += [f"{path}: {reason}" for path, reason in refusals.items()]
    return _due(top, history) + _hotspots(top, trees) + lines, states


def _hotspots(top: Path, trees: dict[str, Path]) -> list[str]:
    """Hotspots on the default branch, unless their fix already has a worktree."""
    ref = story.landed_ref(top)
    try:
        items = spotted.read(top, ref)
    except spotted.Unreadable as problem:
        return [f"{spotted.PATH} on the default branch can't be read, so no hotspots are "
                f"listed: {problem}."]
    hotspots = spotted.hotspots(items)
    if not hotspots:
        return []
    files = set(repo.git("ls-tree", "-r", "-z", "--name-only", ref, cwd=top).split("\0"))
    whys = {(repo.read_state(branch.partition("/")[2], path) or {}).get("why")
            for branch, path in trees.items()
            if re.fullmatch(r"(?:fix|forge)/[a-z0-9][a-z0-9-]*", branch)}
    lines = []
    for hotspot in hotspots:
        path, count = hotspot["path"], hotspot["count"]
        why, done = spotted.fix_text(path, hotspot["texts"])
        if path not in files or why in whys:
            continue
        reason = (f"{count} noted problems are open there." if hotspot["reason"] == "open"
                  else f"{count} changes had the same kind of serious review finding there.")
        lines += [f"{path} keeps breaking: {reason}",
                  f'Next: forge fix start "{why}" --done "{done}"']
    return lines


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


def _due(top: Path, history: dict[str, Any] | None = None) -> list[str]:
    """A success check for each spec whose check date has come and whose stories are all done."""
    ref = story.landed_ref(top)
    items = story.json_of(story.show(top, ref, records.ROADMAP)).get("items")
    keys: dict[str, list[str]] = {}
    for item in items if isinstance(items, list) else []:
        if (isinstance(item, dict) and isinstance(item.get("spec"), str)
                and re.fullmatch(r"[A-Z][A-Z0-9-]*", str(item.get("key")))
                and item.get("status") != "superseded"):  # a replaced story never finishes
            keys.setdefault(item["spec"], []).append(item["key"])
    specs = board._blob_texts(top, [f"{ref}:{rel}" for rel in keys])
    lines: list[str] = []
    for rel, spec_keys in sorted(keys.items()):
        if not all((history["stories"].get(key, {}) if history is not None else
                    story.completed(top, key, ref)).get("status") == "done"
                   for key in spec_keys):
            continue
        found = records.due_check(specs.get(f"{ref}:{rel}", ""), repo.now()[:10])
        if found:
            slug = Path(rel).stem
            lines += [f"Every story from the {found[0] or slug} spec is done and its check date has "
                      f"passed; measure {found[1]}.",
                      f'Next: forge fix start "Record the {slug} success result" --done "The {slug} '
                      'spec records its result"',
                      f'Next: forge spec measure {slug} --result "<measured result>"']
    return lines


LOCKFILES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock", "uv.lock",
             "poetry.lock", "Cargo.lock", "go.sum"}
REFRESH = "refresh-dependencies"


def _refresh(top: Path, trees: dict[str, Path]) -> list[str]:
    """A refresh fix once the default branch's lockfiles and Dockerfiles are a week old by git log.
    fix start numbers a name already used, so a later refresh is refresh-dependencies-2, -3."""
    if any(re.fullmatch(rf"fix/{REFRESH}(-\d+)?", branch) for branch in trees):
        return []
    ref = story.landed_ref(top)
    names = repo.git("ls-tree", "-r", "--name-only", ref, cwd=top).splitlines()
    locks = [name for name in names if Path(name).name in LOCKFILES]
    if not locks:
        return []
    docker = [name for name in names if Path(name).name == "Dockerfile"
              or Path(name).name.startswith("Dockerfile.") or name.endswith(".Dockerfile")]
    # ponytail: a refresh that changed no lockfile is offered again; a week later that is fine
    last = repo.git("log", "-1", "--format=%cI", ref, "--", *locks, *docker, cwd=top)
    if datetime.fromisoformat(repo.now()) - datetime.fromisoformat(last) <= timedelta(days=7):
        return []
    return ["The dependencies and base images haven't been refreshed in over a week; refresh them.",
            'Next: forge fix start "Dependencies and base images are over a week old, so new '
            'security advisories fail the image scan" --done "Lockfiles and base images are updated '
            f'within their allowed ranges, the image builds and the test command passes" --slug {REFRESH}']


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


def _stories(top: Path, history: dict[str, Any] | None = None) -> dict[str, tuple[Path | None, dict[str, Any], str]]:
    """Each story's worktree (None once it is only on the default branch), state and doc text."""
    found: dict[str, tuple[Path | None, dict[str, Any], str]] = {}
    ref = story.landed_ref(top)
    if history is None:
        listing = repo.git("ls-tree", "-r", "--name-only", ref, "--", ".factory/stories/", cwd=top)
        states = {key: story.completed(top, key, ref) for key in
                  re.findall(r"^\.factory/stories/([A-Z][A-Z0-9-]*)/story\.json$", listing, re.M)}
    else:
        states = {key: state for key, state in history["stories"].items()
                  if repo.state_path(key) not in history["expired"]}
    for key, state in states.items():
        found[key] = (None, state,
                      story.show(top, ref, f"plans/{key}.md") or "")
    for key, path in story.stories_here(top).items():
        if history is not None and repo.state_path(key) in history["expired"]:
            continue
        state, doc = repo.read_state(key, path), path / "plans" / f"{key}.md"
        if state is not None and found.get(key, (None, {}, ""))[1].get("status") != "done":
            found[key] = (path, state, doc.read_text(encoding="utf-8") if doc.is_file() else "")
    for branch in repo.git("for-each-ref", "--format=%(refname:strip=3)",
                           "refs/remotes/origin/story/", cwd=top).splitlines():
        key = branch.removeprefix("story/")
        if history is not None and repo.state_path(key) in history["expired"]:
            continue
        if found.get(key, (None, {}, ""))[1].get("status") == "done":
            continue
        ref = story.plan_ref(top, key, history)
        state = story.json_of(story.show(top, ref, repo.state_path(key)))
        if state:
            found[key] = (story.stories_here(top).get(key), state, story._plan(top, key, history=history))
    return found


def _story(top: Path, key: str, path: Path | None, text: str,
           title: str, trees: dict[str, Path], merged_prs: set[str], prs: dict[str, dict[str, Any]],
           refusals: dict[Path, str], history: dict[str, Any] | None = None,
           readiness: dict[str, Any] | None = None
           ) -> tuple[list[str], list[dict[str, Any]]]:
    """A story's lines, and its tasks' states."""
    if readiness is not None:
        readiness.update(stage="planning", parts={}, waits={})
    if any(run.get("kind") == "read" for run in board.active_runs(top, key)):
        return [f"A reader is reading {title}.", "Next: wait for the reader to finish"], []
    ref = story.plan_ref(top, key, history)
    if ref != story.landed_ref(top):
        text = story._plan(top, key, history=history)
    notes = story.show(top, ref, f"plans/{key}.read.md") or ""
    required = story.rounds(notes, story.show(top, ref, repo.state_path(key)))
    if path and ref == f"story/{key}" and (path / "plans" / f"{key}.md").is_file():
        notes = story._text(path / "plans" / f"{key}.read.md")  # pyright: ignore[reportPrivateUsage]
        required = story.rounds(notes, story._text(path / repo.state_path(key)))  # pyright: ignore[reportPrivateUsage]
    doc_hash = repo.run("git", "hash-object", "--stdin", cwd=top, input=text).stdout.strip()
    try:
        doc = story.parse(text, top, history=history)
    except ValueError as exc:
        return [f"The story doc of {title} is malformed: {exc}.",
                f"Next: edit plans/{key}.md, then run forge next"], []
    digest = approval.waiting_digest(key, path) if path else None
    if readiness is not None:
        readiness["parts"] = {task["id"]: "Not started" for task in doc["tasks"]}
    if digest:
        return _approval(top, key, path, title, digest, refusals, text, readiness), []
    if readiness is not None:
        readiness["stage"] = "building"
    states = {task["id"]: _task(top, key, task["id"], trees, merged_prs, history)
              for task in doc["tasks"]}
    merged = {task for task, state in states.items() if state.get("status") == "merged"}
    cleanup = [line for task in doc["tasks"]
               if (tree := trees.get(f"task/{key}-{task['id']}")) and task["id"] in merged
               and (history is None or repo.state_path(f"{key}/{task['id']}") not in history["expired"])
               for line in _item(f"{key}/{task['id']}", f"{key}/{task['id']}",
                                 states[task["id"]], top, tree, prs, refusals)]
    behind = story.plan_behind(top, key, story.landed_ref(top)) if ref != story.landed_ref(top) else ""
    if states and len(merged) == len(states) and not behind:
        if f"fix/{key.lower()}-done" in trees:  # its outcome fix is open; the fix's lines say so
            return cleanup, list(states.values())
        return cleanup + [f"Every part of {title} is merged; record its outcome.",
                f'Next: git fetch origin, then forge story done {key} "<outcome sentence>"'], list(states.values())
    lines: list[str] = cleanup
    part_statuses: dict[str, str] = {}
    for task in doc["tasks"]:
        if states[task["id"]] and task["id"] not in merged:
            item = f"{key}/{task['id']}"
            lines += _item(item, item, states[task["id"]], top,
                           trees.get(f"task/{key}-{task['id']}"), prs, refusals,
                           part_statuses if readiness is not None else None)
    if behind:
        if readiness is not None:
            readiness["stage"] = "planning"
        return lines + [behind], list(states.values())
    merged |= {after for task in doc["tasks"] for after in task["after"] if "/" in after
               and _task(top, *after.split("/"), trees, merged_prs, history).get("status") == "merged"}
    waits = {task["id"]: [after if "/" in after else f"{key}/{after}" for after in task["after"]
                          if after not in merged] for task in doc["tasks"] if not states[task["id"]]}
    busy = _started(story.landed_ref(top), top, history)
    overlapping: set[str] = set()
    for task in doc["tasks"]:
        if task["id"] in waits:
            blockers = [item for item, scope in busy.items()
                        if any(_overlap(a, b) for a in task["scope"] for b in scope)]
            if blockers:
                overlapping.add(task["id"])
            waits[task["id"]] += [item for item in blockers if item not in waits[task["id"]]]
    ready = [task["id"] for task in doc["tasks"] if waits.get(task["id"]) == []]
    if any(developer(task) for task in doc["tasks"] if task["id"] in ready):
        login = github_login(top)
        if login:
            ready = [task["id"] for task in doc["tasks"] if task["id"] in ready
                     and (not (assigned := developer(task)) or assigned.casefold() == login.casefold())]
    waiting = [f"{key}/{task} waits for {', '.join(deps)} to merge first." for task, deps in waits.items()
               if task in overlapping or any(not dep.startswith(f"{key}/") for dep in deps)]
    reread = _next_round(key, notes, doc_hash, title, required, text)
    if readiness is not None:
        readiness["waits"] = waits
    if reread:  # a doc changed after approval gets a round before its next task starts
        if readiness is not None:
            readiness["stage"] = "planning"
        return lines + reread, list(states.values())
    if readiness is not None:
        readiness["parts"].update({name: "Waiting" if deps else "Can start now"
                                   for name, deps in waits.items()})
        remaining = [f"{key}/{name}" for name in states if name not in merged]
        if remaining and all(part_statuses.get(item) == "ready" for item in remaining):
            readiness["stage"] = "ready to merge"
    if ready:
        rows = {task["id"]: task for task in doc["tasks"]}
        landed = story.landed_ref(top)
        builds = {}
        for name in ready:
            # A task takes forge.toml from the branch forge task start branches it from.
            settings = story.show(top, start_base(landed, key, rows[name]), "forge.toml")
            try:
                cfg = (repo._config_text(settings) if settings  # pyright: ignore[reportPrivateUsage]
                       else _report_config(top, refusals))
            except repo.Refused:  # unreadable there: what forge next reads here
                cfg = _report_config(top, refusals)
            # The worker beside each task, as a shell comment so the line still pastes as a command.
            builds[name] = repo.worker(cfg, "build", repo.user_facing(cfg, rows[name]))[0].title()
        lines += [f"{len(ready)} part{'s' if len(ready) != 1 else ''} of {title} can start now"
                  f"{'; start them together.' if len(ready) > 1 else '.'}",
                  *(f"Next: forge task start {key}/{task}  # {builds[task]} builds it"
                    for task in ready)]
    if waiting:
        lines += waiting + ([] if ready else ["Next: git fetch origin, then forge next"])
    return lines or [f"{title} is approved; its other parts wait for earlier parts to merge.",
                     "Next: git fetch origin, then forge next"], list(states.values())


def _approval(top: Path, key: str, path: Path, title: str, digest: str,
              refusals: dict[Path, str], text: str, readiness: dict[str, Any] | None = None) -> list[str]:
    """Planning, read or waiting for approval: what's missing, or how to ask for approval."""
    notes = story._text(path / "plans" / f"{key}.read.md")  # pyright: ignore[reportPrivateUsage]
    reread = _next_round(key, notes, repo.git("hash-object", "--", f"plans/{key}.md", cwd=path), title,
                         story.rounds(notes), text)
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
    shown = f"plans/{key}.md" + (" from its title down to ## For the builders"
                                 if story.BUILDERS.search(text) else "")
    if readiness is not None:
        readiness["stage"] = "waiting for approval"
    return [f"{title} is waiting for approval" + (f" (the last answer was not recorded: {why})." if why
                                                  else "."),
            f"Next: in Claude Code, show {shown} in Plan Mode and exit Plan Mode with it as the plan",
            f"Next: in Codex, show {shown}, then ask request_user_input with id approve_plan_{digest}, "
            'question "Approve this plan?", header "Approve plan" and choices "Approve plan", '
            '"Request changes", "Stop"']


def _next_round(key: str, text: str, doc_hash: str, title: str, required: bool, doc: str) -> list[str]:
    """The next round of a read in rounds (`required`) whose latest round had findings or whose doc
    changed above `## For the builders`: `text` is the notes, `doc_hash` and `doc` the doc's git
    hash and text."""
    notes = f"plans/{key}.read.md"
    record, findings = story._record(text)  # pyright: ignore[reportPrivateUsage]
    done, number = int(record.get("round") or 1), story.undisposed(findings)
    if not required:
        return []
    if not record.get("round"):
        return [f"Planning {title}: {notes} has no round of cold read.", f"Next: forge read {key}"]
    if not story.passed(record, findings):
        why = f"round {done} of its cold read had findings"
    elif story.changed_since_read(record.get("read_hash"), doc_hash, doc):
        why = f"plans/{key}.md changed after round {done} of its cold read"
    else:
        return []
    nudge = " It isn't converging: ask the human whether to split the story instead of reading on."
    return [f"Planning {title}: {why}, so round {done + 1} is next.{nudge if done + 1 >= 4 else ''}",
            f"Next: {f'give finding {number} in {notes} a disposition, then ' if number else ''}"
            f"forge read {key}"]


def _task(top: Path, key: str, task: str, trees: dict[str, Path],
          merged_prs: set[str], history: dict[str, Any] | None = None) -> dict[str, Any]:
    """A task's state: merged on the default branch or GitHub, else from its worktree."""
    item = f"{key}/{task}"
    if history is not None:
        landed = history["states"].get(repo.state_path(item))
    else:
        text = story.show(top, story.landed_ref(top), repo.state_path(item))
        landed = story.json_of(text) if text is not None else None
    if landed is not None:
        return {**landed, "status": "merged"}
    branch = f"task/{key}-{task}"
    path = trees.get(branch)
    state = (repo.read_state(item, path) if path else None) or {}
    return {**state, "status": "merged"} if branch in merged_prs else state


def _item_readiness(item: str, state: dict[str, Any], top: Path,
                    checks: str = "unknown", runs: list[dict[str, Any]] | None = None
                    ) -> tuple[str | None, dict[str, Any]]:
    """A matching close receipt grants readiness unless the current checks failed."""
    try:
        receipt = json.loads(repo.ready_path(item, top).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        receipt = {}
    if not isinstance(receipt, dict):
        receipt = {}
    status, branch = state.get("status"), state.get("branch")
    if status not in ("merged", "done", "hotspot"):
        live = [run for run in (runs if runs is not None else board.active_runs(top, item, round_number=state.get("round")))
                if run.get("kind") in ("work", "worker", "review")
                and ("round" not in state or run.get("round") == state["round"])]
        if live:
            status = "reviewing" if live[-1]["kind"] == "review" else "working"
        elif checks == "fail":
            status = "checks failed"
        elif (branch and receipt.get("review") == "clean"
              and repo.run("git", "rev-parse", "--verify", branch, cwd=top).stdout.strip()
              == receipt.get("commit")):
            status = "ready"
        elif status == "ready":
            status = "waiting for checks"
    return status, receipt


def _item(item: str, label: str, state: dict[str, Any], top: Path,
          path: Path | None, prs: dict[str, dict[str, Any]] | None,
          refusals: dict[Path, str], statuses: dict[str, str] | None = None) -> list[str]:
    pr = (prs or {}).get(state.get("branch", "")) or {}
    checks = board._checks(pr, _report_config(path or top, refusals)["checks"],
                           top=top, branch=state.get("branch", ""))[0]
    status, receipt = _item_readiness(item, state, top, checks)
    status = status or "started"
    if statuses is not None:
        statuses[item] = "hotspot" if state.get("stop") and not state["stop"].get("choice") else status
    if state.get("stop") and not state["stop"].get("choice"):
        stop = state["stop"]
        return [f"Close stopped {label}: {stop['file']} keeps breaking. Ask the human to "
                "narrow the part, split it, or accept the remaining findings.",
                "Next: " + close.REFUSALS["hotspot"][1].format(item=item, **stop)]
    if receipt.get("tidied") is True:
        return []
    if status == "merged" and path:
        if repo.merge_setting(top) == "agent" and receipt.get("review") == "clean":
            return [f"{label} is merged; Forge needs to finish tidying up.",
                    f"Next: forge merge {item}"]
        return [f"{label} is merged; clean up its worktree.",
                f"Next: git worktree remove {shlex.quote(str(path))}"]
    sentence, step = STATUS.get(status, ("{label} is {status}.", "forge close {item}"))
    # forge work holds the item's lock, recording its own process, until its round ends.
    lock = codex._item_file(top, item, ".lock", "Build")
    runs = board.active_runs(top, item, round_number=state.get("round"))
    if (status == "working" and (not lock.exists() or codex._alive(codex._json(lock)) is False)
            and not any(run.get("kind") in ("work", "worker") for run in runs)):
        sentence, step = "{label}'s worker has stopped.", "forge close {item}"
    if (status not in ("merged", "done") and any(run.get("kind") == "test" for run in runs)
            and not any(run.get("kind") in ("work", "worker", "review") for run in runs)
            and (not lock.exists() or codex._alive(codex._json(lock)) is False)):
        sentence, step = "Tests are running for {label}.", "wait for them to finish, then forge next"
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
    if status == "ready" and not pr.get("url") and state.get("branch") and shutil.which("gh"):
        # The bulk list missed it (GitHub can time out on it); ask for this branch's link alone.
        view = repo.run("gh", "pr", "view", state["branch"], "--json", "url", "--jq", ".url", cwd=top)
        pr = {"url": view.stdout.strip()} if view.returncode == 0 and view.stdout.strip() else pr
    if status == "ready" and (url := pr.get("url")):
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
