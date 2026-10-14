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

from forge import (__version__, approval, board, board_facts, close, codex, machine, records, repo, review, spotted, story,
                   score, task, time_records, upgrade)
from forge.task import _started, developer, github_login, start_base, waits_for

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
    lines = _report(top, history, schedules=True)[0]
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
                         "Nothing in progress."),
            "step": line.removeprefix("Next: ") if line else None}


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


def _report(top: Path, history: dict[str, Any] | None = None,
            schedules: bool = False) -> tuple[list[str], list[str]]:
    """The lines `forge next` prints, and one state line per story and fix with its human touches."""
    lines: list[str] = []
    states: list[str] = []
    refusals: dict[Path, str] = {}
    # Only forge next asks GitHub for scheduled runs; hooks stay offline. An open fix for a
    # failed run shows its own lines under it.
    alerts = _failed_schedules(top) if schedules else {}
    pinned: list[str] = []

    def claim(state: dict[str, Any]) -> list[str] | None:  # by the workflow file the fix's why names
        key = next((key for key in alerts if key in str(state.get("why") or "")), None)
        return alerts.pop(key) if key else None
    trees = story.worktrees(top)
    # A machine view (history given) reads the board's lists, kept a minute; forge next asks GitHub.
    github = board_facts.prs(top) if history is not None else None
    if github is None and history is not None:  # the board's one try failed: unknown, no live call per item
        merged_prs, opened = set(), []
    elif github is None:
        merged_prs = {pr["headRefName"] for pr in _prs(top, "merged", "headRefName")} if trees else set()
        opened = _prs(top, "open", "headRefName,headRefOid,body,url,isDraft")
    else:
        merged_prs = {pr["headRefName"] for pr in board_facts.merged_prs(github)} if trees else set()
        opened = [pr for pr in github["open"] if isinstance(pr.get("headRefName"), str)]
    prs = {pr["headRefName"]: pr for pr in opened if isinstance(pr.get("url"), str)}
    if trees:
        prs.update({pr["headRefName"]: {**pr, **prs.get(pr["headRefName"], {})}
                    for pr in board._machine_prs(top)
                    if isinstance(pr.get("headRefName"), str)})
    stories = _stories(top, history)
    if history is not None and any(
            rel in history["expired"] and (match := board.STATE.fullmatch(rel))["task"]
            and match["key"] in stories and stories[match["key"]][1].get("status") != "done"
            and (branch := state.get("branch") or f"task/{match['key']}-{match['task']}") not in merged_prs
            and branch not in prs
            for rel, state in history["states"].items()):
        merged_prs.update(board_facts.merged_before_weeks(top))
    for key, (path, state, text) in sorted(stories.items()):
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
            found = _item(name, f"The fix {name}", state, top, path, prs, refusals)
            if alert := branch not in merged_prs and claim(state):
                pinned += alert[:-1] + found
            else:
                lines += found
            states.append(f"The fix {name} ({state.get('status', 'started')}): "
                          f"{_touches(state.get('touches', 0))} so far.")
    pushed = repo.git("for-each-ref", "--format=%(refname:strip=3)", "refs/remotes/origin/fix/",
                      "refs/remotes/origin/forge/", cwd=top).splitlines()
    landed = story.landed_ref(top)
    for branch in sorted(set(prs) | set(pushed)):  # a fix started elsewhere, with no worktree here
        kind, _, name = branch.partition("/")
        if (branch in trees or branch in merged_prs or kind not in ("fix", "forge")
                or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name)
                or history is not None and repo.state_path(name) in history["expired"]
                or (repo.state_path(name) in history["states"] if history is not None  # merged
                    else story.show(top, landed, repo.state_path(name)) is not None)):
            continue
        if state := remote_state(top, name, branch, prs.get(branch), history):
            found = _item(name, f"The fix {name}", state, top, None, prs, refusals)
            if alert := claim(state):
                pinned += alert[:-1] + found
            else:
                lines += found
    for path in sorted(trees.values()):  # a spec read stopped on any work branch
        for notes in sorted((path / "docs" / "specs").glob("*.read.md")):
            text = notes.read_text(encoding="utf-8")
            spec = notes.with_name(notes.name.removesuffix(".read.md") + ".md")
            if spec.is_file() and story._blocked_reads(  # pyright: ignore[reportPrivateUsage]
                    path, *story._record(text)) >= 3:  # pyright: ignore[reportPrivateUsage]
                lines += _read_loop(spec.stem, spec.read_text(encoding="utf-8"), text, path)
    lines = _refresh(top, trees) + (lines or ([] if pinned else _idle(top)))
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
    return (_due(top, history) + pinned + [line for alert in alerts.values() for line in alert]
            + _hotspots(top, trees) + lines), states


def _failed_schedules(top: Path) -> dict[str, list[str]]:
    """By "(<workflow file>)", which its fix's why names: each workflow whose latest scheduled run on
    the default branch failed, with its failed jobs and tests and, last, the command that starts its fix."""
    def clean(text: str) -> str:  # safe inside double quotes in POSIX, PowerShell and cmd
        return " ".join(re.sub(r"[^A-Za-z0-9 .,:;/_=()-]", " ", text).split())
    alerts = {}
    for run in board_facts.failed_schedules(top):
        key = f"({clean(run['file'])})"
        run = {**run, "workflow": f"{run['workflow']} {key}"}
        workflow, branch = clean(run["workflow"]), clean(run["branch"])
        why = f"The scheduled {workflow} run fails on {branch}"
        jobs = "; ".join(clean(job) for job in run["jobs"]) or "its failed jobs"
        done = f"{jobs} of the scheduled {workflow} workflow pass again on the next scheduled run on {branch}"
        alerts[key] = [f"The latest scheduled {run['workflow']} run on {run['branch']} failed in: "
                       f"{'; '.join(run['jobs']) or 'unknown jobs'}.",
                       *([f"Failing tests: {', '.join(run['tests'])}."] if run["tests"] else []),
                       f'Next: forge fix start "{why}" --done "{done}"']
    return alerts


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
    """Nothing in progress: discover a problem, then plan its story; specs are optional."""
    ref = story.landed_ref(top)
    items = story.json_of(story.show(top, ref, records.ROADMAP)).get("items")
    if isinstance(items, list) and any(
            not isinstance(item, dict) or item.get("status") != "superseded" for item in items):
        return ["No story or fix is in progress.",
                'Next: forge story new <KEY> "<title>"',
                'Next: forge fix start "<why>" --done "<done when>"']
    fields = CARD_FIELD.findall(story.show(top, ref, DISCOVERY) or "")
    if any(value.strip().lower() not in ("", "unknown") for value in fields):
        return ["No story or fix is in progress and the roadmap is empty; the discovery notes hold "
                "a problem card, so plan its story with the problem in Why.",
                'Next: forge story new <KEY> "<title>"']
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
        found[key] = (None, state, (history["docs"].get(f"{ref}:plans/{key}.md", "") if history is not None
                                    else story.show(top, ref, f"plans/{key}.md") or ""))
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
        if history is None:
            state = story.json_of(story.show(top, ref, repo.state_path(key)))
        else:  # the board's one read of every ref
            full = f"refs/heads/{ref}" if ref.startswith("story/") else f"refs/remotes/{ref}" if ref.startswith("origin/story/") else ref
            state = history["ref_states"].get(full, {}).get(repo.state_path(key), {})
        if state:
            found[key] = (story.stories_here(top).get(key), state, story._plan(top, key, history=history))
    return found


def _blocker(top: Path, key: str, ref: str, problem: str, readiness: dict[str, Any] | None) -> None:
    """A problem forge next reports that blocks the story's plan, for the board's Needs you, with
    the date of the plan's last change on the ref read."""
    if readiness is not None:
        since = repo.run("git", "log", "-1", "--format=%cI", ref, "--", f"plans/{key}.md", cwd=top).stdout.strip()
        readiness["blocker"] = {"problem": problem, "since": since or None}


def _story(top: Path, key: str, path: Path | None, text: str,
           title: str, trees: dict[str, Path], merged_prs: set[str], prs: dict[str, dict[str, Any]],
           refusals: dict[Path, str], history: dict[str, Any] | None = None,
           readiness: dict[str, Any] | None = None
           ) -> tuple[list[str], list[dict[str, Any]]]:
    """A story's lines, and its tasks' states."""
    if readiness is not None:
        readiness.update(stage="planning", parts={}, waits={})
    if held := _native_round(top, key, title, "Grill"):
        return held, []
    if any(run.get("kind") == "read" for run in board.active_runs(top, key)):
        return [f"A reader is reading {title}.", "Next: wait for the reader to finish"], []
    ref = story.plan_ref(top, key, history)
    if ref != story.landed_ref(top):
        text = story._plan(top, key, history=history)
    if history is None:
        notes, saved = story.show(top, ref, f"plans/{key}.read.md") or "", story.show(top, ref, repo.state_path(key))
    else:  # the board's one read of every ref
        notes = history["docs"].get(f"{ref}:plans/{key}.read.md", "")
        full = f"refs/heads/{ref}" if ref.startswith("story/") else f"refs/remotes/{ref}" if ref.startswith("origin/story/") else ref
        saved = json.dumps(history["ref_states"].get(full, {}).get(repo.state_path(key), {}))
    required = story.rounds(notes, saved)
    if path and ref == f"story/{key}" and (path / "plans" / f"{key}.md").is_file():
        notes = story._text(path / "plans" / f"{key}.read.md")  # pyright: ignore[reportPrivateUsage]
        required = story.rounds(notes, story._text(path / repo.state_path(key)))  # pyright: ignore[reportPrivateUsage]
    doc_hash = repo.blob_hash(text)
    try:
        doc = story.parse(text, top, history=history, key=key)
    except ValueError as exc:
        lines = [f"The story doc of {title} is malformed: {exc}.", f"Next: edit plans/{key}.md, then run forge next"]
        _blocker(top, key, ref, lines[0], readiness)
        return lines, []
    digest = approval.waiting_digest(key, path) if path else None
    if readiness is not None:
        readiness["parts"] = {task["id"]: "Not started" for task in doc["tasks"]}
    if digest:
        return _approval(top, key, path, title, digest, refusals, text, readiness), []
    if readiness is not None:
        readiness["stage"] = "building"
    states = {task["id"]: _task(top, key, task["id"], trees, merged_prs, history, prs)
              for task in doc["tasks"]}
    merged = {task for task, state in states.items() if state.get("status") == "merged"}
    cleanup = [line for task in doc["tasks"]
               if (tree := trees.get(f"task/{key}-{task['id']}")) and task["id"] in merged
               and (history is None or repo.state_path(f"{key}/{task['id']}") not in history["expired"])
               for line in _item(f"{key}/{task['id']}", f"{key}/{task['id']}",
                                 states[task["id"]], top, tree, prs, refusals)]
    behind = story.plan_behind(top, key, story.landed_ref(top), history) if ref != story.landed_ref(top) else ""
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
        _blocker(top, key, ref, behind, readiness)
        if readiness is not None:
            readiness["stage"] = "planning"
        return lines + [behind], list(states.values())
    merged |= {after for task in doc["tasks"] for after in task["after"] if "/" in after
               and _task(top, *after.split("/"), trees, merged_prs, history).get("status") == "merged"}
    waits = {task["id"]: waits_for(f"{key}/{task['id']}", [after for after in task["after"] if after not in merged])
             for task in doc["tasks"] if not states[task["id"]]}
    busy = _started(story.landed_ref(top), top, history)
    overlapping: set[str] = set()
    for task in doc["tasks"]:
        if task["id"] in waits:
            blockers = waits_for(f"{key}/{task['id']}", [], task["scope"], busy)
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
    reread = _next_round(top, key, notes, doc_hash, title, required, text)
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
            base = start_base(landed, key, rows[name], history, top)
            settings = (story.show(top, base, "forge.toml") if history is None
                        else history["docs"].get(f"{base}:forge.toml"))
            try:
                cfg = (repo._config_text(settings, top) if settings  # pyright: ignore[reportPrivateUsage]
                       else _report_config(top, refusals))
            except repo.Refused:  # unreadable there: what forge next reads here
                cfg = _report_config(top, refusals)
            # The worker beside each task, as a shell comment so the line still pastes as a command.
            design = repo.user_facing(cfg, rows[name])
            sources = repo.setting_sources(cfg, "build", design)
            builds[name] = repo.worker(cfg, "build", design)[0].title() + " builds it" + (
                f" ({sources})" if sources else "")
        lines += [f"{len(ready)} part{'s' if len(ready) != 1 else ''} of {title} can start now"
                  f"{'; start them together.' if len(ready) > 1 else '.'}",
                  *(f"Next: forge task start {key}/{task}  # {builds[task]}"
                    for task in ready)]
    if waiting:
        lines += waiting + ([] if ready else ["Next: git fetch origin, then forge next"])
    return lines or [f"{title} is approved; its other parts wait for earlier parts to merge.",
                     "Next: git fetch origin, then forge next"], list(states.values())


def _approval(top: Path, key: str, path: Path, title: str, digest: str,
              refusals: dict[Path, str], text: str, readiness: dict[str, Any] | None = None) -> list[str]:
    """Planning, read or waiting for approval: what's missing, or how to ask for approval."""
    notes = story._text(path / "plans" / f"{key}.read.md")  # pyright: ignore[reportPrivateUsage]
    reread = _next_round(top, key, notes, repo.git("hash-object", "--", f"plans/{key}.md", cwd=path), title,
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


def _next_round(top: Path, key: str, text: str, doc_hash: str, title: str, required: bool, doc: str) -> list[str]:
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
    if story._blocked_reads(top, record, findings) >= 3:  # pyright: ignore[reportPrivateUsage]
        return _read_loop(key, doc, text)
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


def _read_loop(target: str, doc: str, notes: str, where: Path | None = None) -> list[str]:
    """A stopped cold-read loop's lines: the stop, its ready-to-ask question and the next step,
    run in `where` for a spec, which forge read finds only in its own checkout."""
    cd = f"cd {repo.quote(str(where))} && " if where else ""
    return [line.format(target=target, question=story.read_question(doc, notes)) for line in
            (story.REFUSALS["read_loop"][0], "Next: " + cd + story.REFUSALS["read_loop"][1])]


def _task(top: Path, key: str, task: str, trees: dict[str, Path], merged_prs: set[str],
          history: dict[str, Any] | None = None, prs: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
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
    state = ((repo.read_state(item, path) if path else remote_state(top, item, branch, (prs or {}).get(branch), history))
             or {})
    return {**state, "status": "merged"} if branch in merged_prs else state


def _item_readiness(item: str, state: dict[str, Any], top: Path,
                    checks: str = "unknown", runs: list[dict[str, Any]] | None = None,
                    pr: dict[str, Any] | None = None
                    ) -> tuple[str | None, dict[str, Any]]:
    """A matching close receipt grants readiness unless the current checks failed."""
    try:
        receipt = json.loads(repo.ready_path(item, top).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        receipt = {}
    if not isinstance(receipt, dict):
        receipt = {}
    status, branch = state.get("status"), state.get("branch")
    # A finished item is never ready, so its review ref would go unread.
    ref = review_ref(top, branch, pr) if branch and status not in ("merged", "done", "hotspot") else ""
    record = time_records.from_body((pr or {}).get("body") or "")
    evidence = {}
    if ref and receipt.get("review") == "clean" and receipt.get("commit") == ref:
        evidence = receipt
    elif ref and (record.get("ready") or {}).get("commit") == ref:
        evidence = {"commit": ref, "review": "clean", "shared": True}
    elif ref and not receipt and not record and checks == "pass":
        # An older release's pull request: its state file at the head says it was closed clean.
        older = story.json_of(story.show(top, ref, repo.state_path(item)))
        if older.get("review") and not review.blocking(older["review"]) and \
                older.get("status") in ("waiting for checks", "ready"):
            evidence = {"commit": ref, "review": "clean", "shared": True}
    if status not in ("merged", "done", "hotspot"):
        live = [run for run in (runs if runs is not None else board.active_runs(top, item, round_number=state.get("round")))
                if run.get("kind") in ("work", "worker", "review")
                and ("round" not in state or run.get("round") == state["round"])]
        if live:
            status = "reviewing" if live[-1]["kind"] == "review" else "working"
        elif checks == "fail":
            status = "checks failed"
        elif evidence:
            status = "ready"
        elif status == "ready":
            status = "waiting for checks"
    return status, evidence if status == "ready" else receipt


def remote_state(top: Path, item: str, branch: str, pr: dict[str, Any] | None = None,
                 history: dict[str, Any] | None = None) -> dict[str, Any]:
    """An item started on another machine (its branch is on the remote, as the board reads it, with
    or without a pull request) and no worktree here: its state at the pull request's head."""
    if not pr and history is not None:  # the board's own bulk read of the branches; a local-only one counts too
        refs = history["ref_states"]
        return (refs.get(f"refs/remotes/origin/{branch}") or refs.get(f"refs/heads/{branch}")
                or {}).get(repo.state_path(item)) or {}
    ref = review_ref(top, branch, pr)
    return story.json_of(story.show(top, ref, repo.state_path(item))) if ref else {}


def _commit(top: Path, ref: str) -> str:
    return repo.run("git", "rev-parse", "-q", "--verify", f"{ref}^{{commit}}", cwd=top).stdout.strip()


def review_ref(top: Path, branch: str, pr: dict[str, Any] | None = None) -> str:
    """The commit an item's review history and readiness are read at: the pull request's head
    (GitHub's head, else origin's branch), unless the local branch contains it. Read once per
    command, like the commit log: a fetch, merge, switch or checkout forgets it."""
    return repo.command_fact(("commits", "review ref", branch, (pr or {}).get("headRefOid")), top,
                             lambda: _review_ref(top, branch, pr))


def _review_ref(top: Path, branch: str, pr: dict[str, Any] | None) -> str:
    local = _commit(top, f"refs/heads/{branch}")
    head = (pr or {}).get("headRefOid") or _commit(top, f"refs/remotes/origin/{branch}")
    if re.fullmatch(r"[0-9a-f]{40}", head) and not _commit(top, head):  # pushed since the last fetch: fetch just it
        repo.run("git", "fetch", "-q", "origin", head, cwd=top)
    if local and (not head or local == head or repo.run(
            "git", "merge-base", "--is-ancestor", head, local, cwd=top).returncode == 0):
        return local
    return head


def at_ref(top: Path, item: str, state: dict[str, Any], pr: dict[str, Any] | None = None) -> dict[str, Any]:
    """The item's state as board and next read it: the copy at `review_ref`, so its status,
    findings and round match readiness; the local copy when that is the local branch."""
    branch = state.get("branch")
    if not branch or state.get("status") in ("merged", "done"):
        return state
    ref = review_ref(top, branch, pr)
    if not ref or ref == _commit(top, f"refs/heads/{branch}"):
        return state
    there = story.json_of(story.show(top, ref, repo.state_path(item)))
    return {**there, "branch": branch} if there else state


def default_due(top: Path, state: dict[str, Any]) -> bool:
    """An unanswered review loop stop older than 30 minutes, in a repo whose stop_default is on."""
    stop = state.get("stop") or {}
    if (not stop or stop.get("choice") or "question" in stop or repo.config(top)["stop_default"] == "off"
            or any(f.get("harm", 1) > 2 for f in score.open_findings(state.get("review") or {}))):
        return False
    # Stops from earlier releases have no time of their own; their owner wait event has one.
    since = time_records.when(stop.get("at") or next(
        (e.get("at") for e in time_records.read(top, "events") if e.get("id") == stop.get("wait_id")), None))
    return bool(since) and time_records.when(repo.now()) - since >= timedelta(minutes=30)


def wait_records(top: Path, item: str, body: str = "") -> list[dict[str, Any]]:
    """The item's waits on a person, oldest first, from this machine's log and its pull request's
    record together, each marked `open` while nothing has ended it. Earlier workers answered
    questions without recording an end: a question with a later worker round, or one this
    machine asked whose record it has since cleared, counts as answered."""
    local = board._event_history(top)[1].get(item, [])  # the log is read once per command
    events = {e.get("id"): e for e in [*time_records.from_body(body).get("events", []), *local]
              if e.get("item") == item}
    ended = {e.get("wait_id") for e in events.values() if e.get("event") == "owner wait end"}
    rounds = [at for e in events.values() if e.get("event") == "run start" and e.get("kind") in ("work", "worker")
              and (at := time_records.when(e.get("at")))]
    cleared = codex.record(top, item).get("question", "") is None
    asked_here = {e.get("id") for e in local}

    def answered(e: dict[str, Any]) -> bool:
        at = time_records.when(e.get("at"))
        return e.get("event") == "worker question" and (
            bool(at and any(start > at for start in rounds)) or cleared and e.get("id") in asked_here)
    return sorted(({**e, "open": e.get("id") not in ended and not answered(e)} for e in events.values()
                   if e.get("event") in ("owner wait start", "worker question")), key=lambda e: str(e.get("at")))


def person_waits(top: Path, item: str, state: dict[str, Any], stage: str, pr: dict[str, Any] | None = None,
                 blocker: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """What the item waits on a person for, each {reason, since, detail}: a plan waiting for
    approval, a stop no one has answered (unless close will record its default), a worker
    question, a merge conflict close stopped on, a ready pull request a human merges, or a story
    plan blocked by a problem forge next reports (`blocker`, from its story readiness). The one
    decision behind the board's Needs you; `bool()` of it is whether the item needs a person."""
    if blocker:
        return [{"reason": "blocked plan", "since": blocker["since"], "detail": blocker["problem"]},
                *person_waits(top, item, state, stage, pr)]
    if stage == "waiting for approval":
        notes = story.show(top, story.plan_ref(top, item), f"plans/{item}.read.md") or ""
        return [{"reason": "approval", "since": story._record(notes)[0].get("read_at"),
                 "detail": None}]
    recorded, waits = wait_records(top, item, (pr or {}).get("body") or ""), []
    opened = [e for e in recorded if e["open"]]

    def since(reason: str) -> str | None:
        return next((e.get("at") for e in reversed(opened) if e.get("reason") == reason), None)
    stop = state.get("stop") or {}
    ended = {e.get("id") for e in recorded if not e["open"]}
    # A choice recorded on another machine ends the stop's wait in the pull request's record. A
    # stop the repo's default will answer still waits until that choice is committed.
    if stop and not stop.get("choice") and stop.get("wait_id") not in ended:
        waits.append({"reason": "review loop",  # a review loop or stuck worker's choice
                      "since": stop.get("at") or since("stuck" if "question" in stop else "review loop"),
                      "detail": stop.get("question")})
    # The newest open question wins over an older one this machine still remembers.
    asked = [e for e in opened if e.get("event") == "worker question"]
    if asked:
        waits.append({"reason": "worker question", "since": asked[-1].get("at"), "detail": asked[-1].get("question")})
    if conflict := since("merge conflict"):
        waits.append({"reason": "conflict", "since": conflict, "detail": None})
    # An older open pull request, ready before merge waits were recorded, still waits on its human
    # merge. This checkout's forge.toml, so the board needs no fetch.
    if stage == "ready" and (since("merge") or pr and pr.get("state", "OPEN") == "OPEN"
                             and repo.config(top)["merge"] == "human"
                             and not any(e.get("reason") == "merge" for e in recorded)):
        waits.append({"reason": "merge", "since": since("merge"), "detail": None})
    return waits


def _native_round(top: Path, item: str, label: str, kind: str) -> list[str]:
    """A handed-out round waits for its session's result, rather than another launch."""
    pending = codex._json(codex._item_file(top, item, ".json", kind)).get("pending") or {}
    entry = pending.get("entry") or {}
    if not entry.get("native") or not any(run["id"] == entry["id"] for run in machine.entries()):
        return []
    return [f"The session holds a round for {label}; wait for its subagent to finish.",
            f"Next: forge handback {item} --round {pending['result']['round']} "
            '--subagent <id> --text "<message>"']


def _item(item: str, label: str, state: dict[str, Any], top: Path,
          path: Path | None, prs: dict[str, dict[str, Any]] | None,
          refusals: dict[Path, str], statuses: dict[str, str] | None = None) -> list[str]:
    if held := _native_round(top, item, label, "Build"):
        return held
    pr = (prs or {}).get(state.get("branch", "")) or {}
    state = at_ref(top, item, state, pr)
    checks = board._checks(pr, _report_config(path or top, refusals)["checks"])[0] if pr else "unknown"
    status, receipt = _item_readiness(item, state, top, checks, pr=pr)
    status = status or "started"
    if statuses is not None:
        statuses[item] = "hotspot" if state.get("stop") and not state["stop"].get("choice") else status
    if not path and status not in ("ready", "merged", "done"):  # its checkout is on another machine
        starter = board._starters(top).get(repo.state_path(item)) or "the person who started it"
        return [f"{label} was started by {starter} and runs on their machine."]
    if state.get("stop") and not state["stop"].get("choice"):
        stop = state["stop"]
        if "question" in stop:
            return [f"Forge stopped {label}. Ask the human:", stop["question"],
                    "Next: " + close.REFUSALS["stuck"][1].format(item=item)]
        if default_due(path or top, state):
            return [f"Nobody answered the review loop stop on {label} in 30 minutes, so close "
                    "records the repo's default choice: narrow.", f"Next: forge close {item}"]
        return [f"Close stopped {label}: {stop['file']} keeps breaking.",
                review.stop_question(path or top, item, state),
                "Next: " + close.REFUSALS["hotspot"][1].format(item=item, **stop)]
    if question := codex.record(top, item).get("question"):  # close and work refuse until it is answered
        return [f"The worker on {label} asked a question. Ask the human:", question,
                "Next: " + close.REFUSALS["question"][1].format(item=item)]
    if receipt.get("tidied") is True:
        return []
    if status == "ready" and not path and repo.merge_setting(top) == "agent":
        starter = board._starters(top).get(repo.state_path(item)) or "the person who started it"
        return [f"{label} is ready to merge; {starter} merges it from their machine."]
    if status == "ready" and path and receipt.get("shared"):
        if repo.git("rev-parse", "HEAD", cwd=path) == receipt["commit"]:  # close here writes the receipt
            return [f"{label} was closed clean on another machine; close it here to check it again.",
                    f"Next: forge close {item}"]
        if repo.merge_setting(top) == "agent":  # forge merge needs this machine's receipt
            return [f"{label} is ready to merge, but this worktree is behind its pull request.",
                    f"Next: git -C {repo.quote(str(path))} pull, then forge close {item}"]
    if status == "merged" and path:
        if repo.merge_setting(top) == "agent" and receipt.get("review") == "clean":
            return [f"{label} is merged; Forge needs to finish tidying up.",
                    f"Next: forge merge {item}"]
        return [f"{label} is merged; clean up its worktree.",
                f"Next: git worktree remove {repo.quote(str(path))}"]
    sentence, step = STATUS.get(status, ("{label} is {status}.", "forge close {item}"))
    # forge work holds the item's lock, recording its own process, until its round ends.
    lock = codex._item_file(top, item, ".lock", "Build")
    runs = board.active_runs(top, item, round_number=state.get("round"))
    if (status == "working" and (not lock.exists() or codex._alive(codex._json(lock)) is False)
            and not any(run.get("kind") in ("work", "worker") for run in runs)):
        native_round = codex._json(lock.with_suffix(".json")).get("native_round")
        sentence, step = "{label}'s worker has stopped.", "forge work {item}" if native_round else "forge close {item}"
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
    stop = state.get("stop") or {}
    answered = ([f"The repo's default answered the review loop stop on {label}: narrow it to its "
                 "Done-when lines; follow-up fixes own the open findings: "
                 f"{', '.join(stop.get('fixes') or []) or 'none'}."] if stop.get("by") == "default" else [])
    if status == "ready" and (url := pr.get("url")):
        next_step = (step.format(**values) if step == "forge merge {item}"
                     else f"merge {url}, then forge next")
        return answered + [f"{label} is ready to merge: {url}", f"Next: {next_step}"]
    built = _builder(item, state, path or top, refusals) if step == "forge work {item}" else ""
    if step == "forge work {item}" and not built and state.get("tool"):
        built = f"  # {state['tool'].title()} builds it"
    return answered + [sentence.format(**values), f"Next: {step.format(**values)}{built}"]


def _builder(item: str, state: dict[str, Any], folder: Path, refusals: dict[Path, str]) -> str:
    """The worker beside a forge work line, chosen as forge work chooses it, with where its
    settings came from, when a forge.local.toml sets any; "" otherwise."""
    cfg = _report_config(folder, refusals)
    if "local" not in cfg:
        return ""
    # Keep in step with forge work's choice of design and kind in worker.work (worker.py lines 89-106).
    key, _, name = item.partition("/")
    design = (repo.user_facing(cfg, task.rows(task.sections((folder / "plans" / f"{key}.md").read_text(
        encoding="utf-8"))).get(name, {})) if name else
        state.get("allow_large") == "Prototype before sign-off" and repo.is_prototype(folder))
    later = (repo.worker(cfg, "build", design, state.get("tool"))[0] == "codex" or design) and bool(
        codex.record(folder, item).get("start") or state.get("status", "started") != "started")
    kind = "fix" if later else "build" if name else "lite"
    sources = repo.setting_sources(cfg, kind, design)
    return f"  # {repo.worker(cfg, kind, design, state.get('tool'))[0].title()} builds it ({sources})"


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
