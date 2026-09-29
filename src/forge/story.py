"""Story docs: `story new` (and promotion from a fix), the cold read's rounds, `story done`, the
doc's shape checks and the story-doc part of forge-pr-check.

A story is `plans/<KEY>.md` on its own `story/<KEY>` branch and worktree. Each round of the cold
read of a doc adds to its notes beside it (`plans/<KEY>.read.md`, `docs/specs/<slug>.read.md`), the
same format RECORDS reads for `spec confirm`. The frontmatter is the latest round's:

    ---
    reader: <who read it>
    read_at: <when>
    read_hash: <git hash-object of the doc as read>
    round, passed: <n>, and yes only when that round's whole text, trimmed, is "No findings."
    doc_seen, spec_seen, notes_seen: <what its reader saw, kept by git hash-object -w>
    ---
    ## Round <n>

    <n>. <finding, numbered after the earlier rounds'>
       Disposition: cut | defer | keep <one-line reason>

A task is merged once its state file is on origin/<default>: its pull request carried it there.
"""
from __future__ import annotations

import difflib
import hashlib
import itertools
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from string import Template
from typing import Any

from forge import codex, repo, worker

REFUSALS = {
    "bad_key": ("{key!r} is not a story key; a key is capital letters, digits and hyphens.",
                'forge story new <KEY> "<title>"'),
    "not_on_roadmap": ("{key} is not on the roadmap (plans/roadmap.json).", "forge roadmap add <spec>"),
    "no_title": ("A new story needs a plain-English title.", 'forge story new {key} "<title>"'),
    "no_fix": ("There is no fix named {fix} in a worktree here.", "forge next"),
    "no_story": ("There is no story {key} here.", 'forge story new {key} "<title>"'),
    "no_spec": ("docs/specs/{slug}.md does not exist.", "forge spec save {slug}"),
    "bad_doc": ("{doc} is malformed: {problem}.", "edit {doc}, then run forge next"),
    "discarded": ("A file changed during the cold read of {doc}, so the read was discarded.",
                  "git status, then forge read {target}"),
    "reader_failed": ("The cold read of {doc} failed: {problem}", "forge read {target}"),
    "coordinator": ("Forge can't tell which app is coordinating, so it can't pick the other one "
                    "to read.", "run forge read {target} from Claude Code or Codex"),
    "wrong_app": ("{reader} is the cold reader of {doc}, so its next round can't start from {reader}.",
                  "run forge read {target} from {app}"),
    "no_read": ("{doc} has no cold read.", "forge read {target}"),
    "changed": ("{doc} changed after its last round of cold read.", "forge read {target}"),
    "not_passed": ("Round {round} of the cold read of {doc} hasn't passed, so it needs another round.",
                   "forge read {target}"),
    "no_disposition": ("Finding {number} in {notes} has no disposition: cut, defer, or keep with a "
                       "reason.", "edit {notes}, then forge next"),
    "not_finished": ("{key} isn't finished: {problem}.", "git fetch origin, then forge next"),
}

TEMPLATES = Path(__file__).parent / "templates"
KEY = re.compile(r"[A-Z][A-Z0-9-]*")
COLUMNS = ("ID", "Name", "What it delivers", "Covers", "Scope", "Tests", "After", "User-facing")
APPROVED = ("What changes for you", "Done when")  # the sections an approval binds
RECORD = ("reader", "read_at", "read_hash", "round", "passed", "doc_seen", "spec_seen", "notes_seen")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
FINDING = re.compile(r"^(\d+)\.[ \t]", re.M)
DISPOSITION = re.compile(r"^[ \t]*(?:[-*][ \t]+)?\**disposition:\**[ \t]*(cut|defer|keep)\b"
                         r"[ \t:\u2014\u2013-]*(\S?)", re.I | re.M)
# The variable each coordinating app sets in the commands it runs; Codex's is its conversation's id.
COORDINATORS = {"CLAUDECODE": "claude", "CODEX_THREAD_ID": "codex"}
NAMES = {"claude": "Claude Code", "codex": "Codex"}


def ships(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    from forge import sync

    skill = (TEMPLATES / "skill.md").read_text(encoding="utf-8")
    return {
        ".claude/skills/forge/SKILL.md": skill,
        ".codex/skills/forge/SKILL.md": skill,
        **{f"{host}/skills/forge/standards.md":
           (TEMPLATES.parent / "standards.md").read_text(encoding="utf-8")
           for host in (".claude", ".codex")},
        **{f"{host}/skills/forge/fde.md":
           sync._synced_text(".codex/skills/forge/fde.md", "fde.md")
           for host in (".claude", ".codex")},
    }


# --- commands ------------------------------------------------------------------------------


def new(args: Any) -> int:
    top, key, fix = repo.root(), args.key, args.from_fix
    if not KEY.fullmatch(key):
        repo.refuse(REFUSALS["bad_key"], key=key)
    if (top / "forge.toml").is_file() and repo.is_prototype(top):
        repo.refuse(("Stories wait for the customer's sign-off. Build and demo the prototype first.",
                     "forge next"))
    why, row, fix_top, fix_state = "<Why this matters now, in plain English.>", "", None, None
    done = "Something anyone can observe once this is done."
    if fix:
        fix_top = worktrees(top).get(f"fix/{fix}")
        fix_state = repo.read_state(fix, fix_top) if fix_top else None
        if not fix_state:
            repo.refuse(REFUSALS["no_fix"], fix=fix)
        why = fix_state.get("why") or why
        done = fix_state.get("done_when") or done  # the promoted task covers Done-when item 1
        # The task's Scope is what the fix changed since it left the default branch.
        base = repo.git("merge-base", repo.default_branch(top), "HEAD", cwd=fix_top)
        scope = [f"`{path}`" for path in repo.git("diff", "--name-only", base, cwd=fix_top).splitlines()
                 if not path.startswith(".factory/")]
        row = f"| SPEC | {why} | {why} | 1 | {', '.join(scope)} | | none | no |\n"
    elif key not in {item["key"] for item in repo.roadmap(top)}:
        repo.refuse(REFUSALS["not_on_roadmap"], key=key)
    title = args.title or (why if fix else "")
    if not title:
        repo.refuse(REFUSALS["no_title"], key=key)
    path = add_worktree(top, f"story/{key}", repo.default_branch(top))
    doc = f"plans/{key}.md"
    text = Template((TEMPLATES / "story.md").read_text(encoding="utf-8"))
    _write(path / doc, text.safe_substitute(title=title, why=why, done=done, tasks=row))
    changed = [doc, *(_add_to_roadmap(path, key, title) if fix else [])]
    state = repo.add_step({"title": title, "doc": doc, "status": "planning", "touches": 0}, "start")
    changed.append(repo.write_state(key, state, path))
    repo.commit_state(f"Start the story: {title}", *changed, top=path)
    print(f"Started the story {key} in {path}.")
    if fix_top:
        print(_promote(fix_top, fix, key, fix_state))
    print(f"Next: write {doc} there, then forge read {key}")
    return 0


def read(args: Any) -> int:
    target = args.target
    top, doc, notes, is_story = _paths(target)
    # ponytail: CORE's branch rule, so a read never writes on the default branch.
    repo._work_branch(top)  # pyright: ignore[reportPrivateUsage]
    rel, old = _rel(top, doc), _text(notes)
    record, findings = _record(old)
    later = bool(record.get("read_hash"))
    number = undisposed(findings) if later else ""
    if number:
        repo.refuse(REFUSALS["no_disposition"], number=number, notes=_rel(top, notes))
    if is_story:
        _parsed(doc, rel)
    apps = [app for variable, app in COORDINATORS.items() if os.environ.get(variable)]
    if len(apps) != 1:  # neither app, or one running inside the other
        repo.refuse(REFUSALS["coordinator"], target=target)
    here, installed = apps[0], {"claude": shutil.which("claude") is not None, "codex": codex.installed()}
    other = "claude" if here == "codex" else "codex"
    # The other app reads when it is installed, else a separate conversation of this one. A later
    # round stays with the recorded reader while its app is installed.
    recorded = record.get("reader", "").split(" ")[0]
    gone = recorded in NAMES and not installed[recorded]
    if recorded == here and installed[other] and not gone:
        repo.refuse(REFUSALS["wrong_app"], doc=rel, reader=NAMES[here], app=NAMES[other],
                    target=target)
    reader = recorded if recorded in NAMES and not gone else other if installed[other] else here
    why = f"its reader, {NAMES[recorded]}, is no longer installed" if gone else ""
    left = codex.record(top, target, "Grill") if gone else {}
    left = left.get("conversation") if recorded == "codex" else (left.get("claude") or {}).get("id")
    config = repo.config(top)
    models = worker.ready(top, config, "Grill", reader == "codex")  # forge work's checks
    first, again, head = re.split(r"<!-- forge:(?:round|notes) -->\n",
                                  (TEMPLATES / "cold-read.md").read_text(encoding="utf-8"))
    before = _snapshot(top)  # first, so any change from here on discards the read
    text = doc.read_bytes()  # one read: the reader gets exactly the bytes that are hashed
    read_hash = _store(top, text, rel)
    spec = _find_spec(top, target) if is_story else None
    spec_text, blocks = spec[2] if spec else "", _findings(findings)
    fill: dict[str, Any] = {
        "path": rel, "doc": text.decode("utf-8"), "target": target, "traps": _known_traps(top),
        "spec": (f"\nConfirmed spec at `{spec[0]}` on `{spec[1]}`:\n\n{spec[2]}\n" if spec else
                 "\nNo linked confirmed spec was found in the local branches.\n") if is_story else ""}
    prompt = fresh_prompt = Template(first).safe_substitute(fill)
    round_number = int(record.get("round") or 1) + 1 if later else 1
    if later:
        # What the last round's reader saw, to send only what changed since. Old notes have none.
        seen = {name: repo.run("git", "cat-file", "blob", record.get(name) or "-", cwd=top)
                for name in ("doc_seen", "spec_seen", "notes_seen")}
        diff = _diff(seen["doc_seen"].stdout, text.decode("utf-8"), rel)
        spec_diff = _diff(seen["spec_seen"].stdout, spec_text, spec[0] if spec else "spec")
        if any(done.returncode for done in seen.values()):
            why = why or "Forge has no copy of what its last round read"
            diff = spec_diff = "(not available)"
        saw = _findings(_record(seen["notes_seen"].stdout)[1])
        fill.update(round=round_number, diff=diff, spec_diff=spec_diff, next=max(blocks, default=0) + 1)
        fresh_prompt += "\n" + Template(again).safe_substitute(fill, dispositions="\n".join(blocks.values()))
        # The last round's findings are the ones its reader hadn't seen; older ones only if changed.
        prompt = Template(again).safe_substitute(fill, dispositions="\n".join(
            block for n, block in blocks.items() if saw.get(n, "").split() != block.split()) or "None.")
    session = codex.record(top, target, "Grill").get("claude") if later and not why else None
    if reader == "claude":
        if later and not why and not session:
            why = "Forge has no record of its Claude session on this machine"
        elif session and session.get("checkout") != str(top):
            why, session = f"its session was started in another checkout, {session['checkout']}", None
        done = _claude_read(top, target, models, prompt, fresh_prompt, session and session["id"], why)
        said, failed = done.stdout.strip(), done.returncode
        problem = (done.stderr.strip().splitlines() or [f"it wrote nothing (exit code {done.returncode})"])[-1]
    else:
        thread, why = codex.conversation(top, target, None, "Grill") if later and not why else (None, why)
        with codex.hold(top, target, "Grill"):  # one read per item, and nothing left running
            name = f"Read · {target}"
            if len(name) > 60:
                prefix = name[:59]
                name = (prefix.rstrip(" -") if name[59] in " -" else
                        prefix.rsplit("-", 1)[0] if "-" in prefix else
                        prefix.rsplit(" ", 1)[0]) + "…"
            ran = codex.run(top, target, "Grill", name, prompt, "read-only", thread,
                            fresh=why or "first turn", fresh_prompt=fresh_prompt)
        said, failed = (ran["text"] or "").strip(), ran["status"] != "completed"
        problem = (f"Codex reported the turn {ran['status']}." if failed and ran["status"] else
                   "Codex never reported the turn's end." if failed else "it wrote nothing.")
    said = _repo_root_paths(said, {str(top), str(top.resolve())})
    if _snapshot(top) != before or failed or not said:
        # Nothing is recorded, and the retry starts a fresh conversation.
        codex._record(codex._item_file(top, target, ".json", "Grill"),  # pyright: ignore[reportPrivateUsage]
                      conversation=None, start=None, claude=None)
        if _snapshot(top) != before:
            repo.refuse(REFUSALS["discarded"], doc=rel, target=target)
        repo.refuse(REFUSALS["reader_failed"], doc=rel, target=target, problem=problem)
    passed = said == "No findings."
    if not passed:
        # ponytail: unstructured output is one finding, so it still needs a disposition. Findings
        # number on from earlier rounds', whatever numbers the reader used.
        numbers = itertools.count(max(blocks, default=0) + 1)
        said = FINDING.sub(lambda match: f"{next(numbers)}.{match[0][-1]}",
                           said if FINDING.search(said) else f"1. {said}")
    model = repo.models(config, "grill", reader)["model"]
    record = {"reader": f"{reader} ({model})" + (
                  f", a separate {NAMES[reader]} conversation because {NAMES[other]} isn't installed"
                  if reader == here else ""),
              "read_at": repo.now(), "read_hash": read_hash,
              "round": str(round_number), "passed": "yes" if passed else "no",
              "doc_seen": read_hash, "spec_seen": _store(top, spec_text.encode("utf-8")),
              "notes_seen": _store(top, old.encode("utf-8"))}
    kept = findings.rstrip("\n") if later else head.strip()
    _write(notes, _notes(record, f"{kept}\n\n## Round {round_number}\n\n{said}\n"))
    if reader == "codex" and passed and ran.get("conversation"):
        try:
            archived = codex.archive(top, target, "Grill", ran["conversation"])
        except Exception:
            archived = False
        if not archived:
            print(f"Forge could not archive the cold read's Codex conversation for {target}; "
                  "archive it in Codex when it is available.")
    if passed and left:
        print(f"The cold read's earlier {NAMES[recorded]} conversation for {target}, {left}, is left "
              f"as it is, because {NAMES[recorded]} is no longer installed.")
    changed = [rel, _rel(top, notes)]
    if is_story:
        state = repo.read_state(target, top) or {}
        if (state.get("approval") or {}).get("hash") != approval_hash(text.decode("utf-8")):
            state["status"] = "read"
        changed.append(repo.write_state(target, repo.add_step(state, "read"), top))
    if passed:  # a passing round is committed, so tasks and pull requests carry what passed
        repo.commit_state(f"Round {round_number} of the cold read of {rel} found nothing", *changed,
                          top=top)
    print(f"Round {round_number} of the cold read of {rel} found nothing.\nNext: forge next" if passed else
          f"Wrote round {round_number} of the cold read to {_rel(top, notes)}.\n"
          f"Next: give every finding a disposition, amend the doc, then forge read {target}")
    return 0


def done(args: Any) -> int:
    top, key = repo.root(), args.key
    doc, ref = f"plans/{key}.md", landed_ref(top)
    text = show(top, ref, doc)
    if text is None:
        repo.refuse(REFUSALS["not_finished"], key=key, problem="its story doc isn't on the default branch yet")
    try:
        tasks = parse(text)["tasks"]
    except ValueError as exc:
        repo.refuse(REFUSALS["bad_doc"], doc=doc, problem=exc)
    dates = {task["id"]: merged_at(top, ref, repo.state_path(f"{key}/{task['id']}")) for task in tasks}
    waiting = [task for task, date in dates.items() if not date]
    if not tasks or waiting:
        repo.refuse(REFUSALS["not_finished"], key=key,
                    problem=f"{', '.join(waiting)} not merged yet" if waiting else "it has no tasks")
    state = json_of(show(top, ref, repo.state_path(key)))
    title, slug = state.get("title") or key, f"{key.lower()}-done"
    path = add_worktree(top, f"fix/{slug}", ref)
    state.update(status="done", outcome=args.outcome, merged=dates, finished=max(dates.values()))
    fix = {"kind": "story-done", "why": f"Record that {title} is finished, and what it achieved.",
           "done_when": "The board shows the story as finished, with its outcome.", "outcome": args.outcome,
           "branch": f"fix/{slug}", "base": repo.git("rev-parse", ref, cwd=top), "status": "started",
           "touches": 0}
    changed = [repo.write_state(key, repo.add_step(state, "done"), path),
               repo.write_state(slug, repo.add_step(fix, "start"), path)]
    repo.commit_state(f"Record the outcome of {title}", *changed, top=path)
    print(f"Opened the fix that records the outcome of {title} in {path}.\nNext: forge close {slug}")
    return 0


# --- the story doc -------------------------------------------------------------------------


def sections(text: str) -> dict[str, str]:
    """The doc's `## ` sections, heading to body, in order."""
    found: dict[str, str] = {}
    for block in re.split(r"^## ", text.replace("\r\n", "\n"), flags=re.M)[1:]:
        heading, _, body = block.partition("\n")
        found.setdefault(heading.strip(), body)
    return found


def parse(text: str) -> dict[str, Any]:
    """A story doc's title, sections, Done-when items, task rows and `New moving parts:` line.

    Raises ValueError naming what is malformed, and the task row when a row is wrong.
    """
    found = sections(text)
    if next(iter(found), None) != "What changes for you":
        raise ValueError('it must start with "What changes for you"')
    for name in ("Done when", "Tasks", "Risks"):
        if name not in found:
            raise ValueError(f'it has no "{name}" section')
    moving = re.search(r"^New moving parts:.*$", found["Tasks"], re.M)
    if not moving:
        raise ValueError('its Tasks section has no "New moving parts:" line')
    done = {int(n): item for n, item in re.findall(r"^(\d+)\.\s+(.*)$", found["Done when"], re.M)}
    table = [[cell.strip() for cell in line.strip().strip("|").split("|")]
             for line in found["Tasks"].splitlines() if line.strip().startswith("|")]
    header = table[0] if table else []
    missing = [name for name in COLUMNS if name not in header]
    if missing:
        raise ValueError(f'its Tasks table has no "{missing[0]}" column')
    tasks: dict[str, dict[str, Any]] = {}
    for cells in table[1:]:
        if all(set(cell) <= set(":- ") for cell in cells):
            continue  # the |---| line
        row = dict(zip(header, cells + [""] * len(header)))
        task = row["ID"].strip("` ")
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]*", task):
            raise ValueError(f"Tasks row {task or '?'}: an ID is capital letters, digits and hyphens")
        if task in tasks:
            raise ValueError(f"Tasks row {task}: the ID is used twice")
        covers = [int(n) for n in re.findall(r"\d+", row["Covers"])]
        wrong = [n for n in covers if n not in done]
        if wrong:
            raise ValueError(f"Tasks row {task}: Covers {wrong[0]} is not a Done-when item")
        scope = _cell_paths(row["Scope"])
        if not scope:
            raise ValueError(f"Tasks row {task}: Scope is empty")
        tasks[task] = {**row, "id": task, "covers": covers, "scope": scope,
                       "tests": _cell_paths(row["Tests"]),
                       "after": re.findall(r"[A-Z0-9][A-Z0-9-]*", row["After"]),
                       "user_facing": row["User-facing"].lower() in ("yes", "true")}
    for task in tasks.values():
        unknown = [after for after in task["after"] if after not in tasks]
        if unknown:
            raise ValueError(f"Tasks row {task['id']}: After {unknown[0]} is not a task in this table")
    _no_cycle(tasks)
    title = re.search(r"^# (.+)$", text, re.M)
    return {"title": title[1].strip() if title else "", "sections": found, "done": done,
            "tasks": list(tasks.values()), "moving_parts": moving[0]}


def approval_hash(text: str) -> str | None:
    """What an approval binds: sha256 of the stripped "What changes for you" body, a newline, and the
    stripped "Done when" body. None when the text lacks either section.

    ponytail: WORK's task.approval_hash is the same function; collapse the two once both land.
    """
    found = sections(text)
    if not all(name in found for name in APPROVED):
        return None
    return hashlib.sha256("\n".join(found[name].strip() for name in APPROVED).encode("utf-8")).hexdigest()


def overlaps(scope: list[str], other: list[str]) -> bool:
    """Whether two Scope lists share a path: the same path, one inside the other, or a glob match."""
    def one(a: str, b: str) -> bool:
        a, b = a.rstrip("/"), b.rstrip("/")
        return a == b or a.startswith(b + "/") or b.startswith(a + "/") or fnmatch(a, b) or fnmatch(b, a)
    return any(one(a, b) for a in scope for b in other)


# --- the cold read gate and forge-pr-check -------------------------------------------------


def check_read(target: str, top: Path | None = None) -> None:
    """Refuse unless a story doc or spec has a cold read whose latest round passed, is unchanged
    since that round, and every finding has a disposition. Approval and `forge next` call this.
    Notes written before rounds count as round 1, which never passed."""
    top, doc, notes, is_story = _paths(target, top)
    rel = _rel(top, doc)
    gate(target, rel, _text(notes), _hash(top, doc))
    if is_story:
        _parsed(doc, rel)


def gate(target: str, rel: str, notes: str, doc_hash: str) -> None:
    """check_read on a doc's notes text and the doc's git hash (a worktree file or a commit's)."""
    record, findings = _record(notes)
    if not record.get("read_hash"):
        repo.refuse(REFUSALS["no_read"], doc=rel, target=target)
    number = undisposed(findings)
    if number:
        repo.refuse(REFUSALS["no_disposition"], number=number, notes=rel.removesuffix(".md") + ".read.md")
    if not passed(findings):
        repo.refuse(REFUSALS["not_passed"], doc=rel, target=target, round=record.get("round") or 1)
    if doc_hash != record["read_hash"]:
        repo.refuse(REFUSALS["changed"], doc=rel, target=target)


def passed(findings: str) -> bool:
    """The latest round's whole text, trimmed, is exactly "No findings."; never the passed flag."""
    parts = re.split(r"^## Round \d+[ \t]*$", findings, flags=re.M)
    return len(parts) > 1 and parts[-1].strip() == "No findings."


def rounds(notes: str | None, state: str | None = None) -> bool:
    """A story read in rounds: its notes have rounds, or its approval names the round it passed,
    so notes deleted later still need a round. A story approved on older notes keeps its rules."""
    return bool(_record(notes or "")[0].get("round")
                or (json_of(state).get("approval") or {}).get("round"))


def undisposed(findings: str) -> str:
    """The number of the first finding without a disposition (keep needs a reason), or ""."""
    parts = FINDING.split(findings)
    for number, finding in zip(parts[1::2], parts[2::2]):
        found = DISPOSITION.search(finding)
        if not found or (found[1].lower() == "keep" and not found[2]):
            return number
    return ""


def check_pr_docs(top: Path, head: str, changed: list[str]) -> str | None:
    """The story-doc part of forge-pr-check: the problem with the first bad story doc among the
    pull request's changed paths, or None. Everything is read from head, as data."""
    # A change to a story's notes alone checks its doc too.
    docs = [re.sub(r"\.read\.md$", ".md", path) for path in changed]
    for path in dict.fromkeys(docs):
        match = re.fullmatch(r"plans/([A-Z][A-Z0-9-]*)\.md", path)
        text = show(top, head, path) if match else None
        if text is None:
            continue
        try:
            parse(text)
        except ValueError as exc:
            return f"The story doc {path} is malformed: {exc}."
        notes = show(top, head, f"plans/{match[1]}.read.md")
        number = undisposed(_record(notes or "")[1])
        if number:
            return f"Finding {number} in plans/{match[1]}.read.md has no disposition."
        approval = json_of(show(top, head, repo.state_path(match[1]))).get("approval") or {}
        if approval.get("hash") != approval_hash(text):
            return f'The approval of {path} doesn\'t match its "What changes for you" and "Done when".'
        if rounds(notes, show(top, head, repo.state_path(match[1]))):
            try:
                gate(match[1], path, notes or "", repo.git("rev-parse", f"{head}:{path}", cwd=top))
            except repo.Refused as refusal:
                return str(refusal).partition("\nNext: ")[0]
    return None


# --- worktrees and the default branch ------------------------------------------------------


def worktrees(top: Path) -> dict[str, Path]:
    """Every checked-out branch and its worktree folder."""
    found: dict[str, Path] = {}
    path = top
    for line in repo.git("worktree", "list", "--porcelain", cwd=top).splitlines():
        if line.startswith("worktree "):
            path = Path(line[len("worktree "):])
        elif line.startswith("branch refs/heads/"):
            found[line[len("branch refs/heads/"):]] = path
    return found


def stories_here(top: Path) -> dict[str, Path]:
    """Each story's own worktree, by key."""
    return {branch[6:]: path for branch, path in worktrees(top).items()
            if branch.startswith("story/") and KEY.fullmatch(branch[6:])}


def story_checkout(key: str, top: Path | None = None) -> Path:
    """The checkout holding a story's planning state: its own worktree, else this checkout."""
    top = top or repo.root()
    for path in (stories_here(top).get(key), top):
        if path is not None and repo.read_state(key, path) is not None:
            return path
    repo.refuse(REFUSALS["no_story"], key=key)


def add_worktree(top: Path, branch: str, start: str) -> Path:
    """A new branch in its own worktree, next to the main checkout."""
    main = Path(repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=top)).parent
    path = main.parent / f"{main.name}-{branch.replace('/', '-')}"
    repo.git("worktree", "add", "-q", "-b", branch, str(path), start, cwd=top)
    return path


def landed_ref(top: Path) -> str:
    """Where merged work lands: origin/<default> as last fetched; the local default with no remote."""
    default = repo.default_branch(top)
    fetched = f"origin/{default}"
    found = repo.run("git", "rev-parse", "-q", "--verify", f"{fetched}^{{commit}}", cwd=top).returncode
    return default if found else fetched


def show(top: Path, ref: str, path: str) -> str | None:
    """A file's text at a commit, or None when it isn't there."""
    done = repo.run("git", "show", f"{ref}:{path}", cwd=top)
    return done.stdout if done.returncode == 0 else None


def merged_at(top: Path, ref: str, path: str) -> str:
    """When a file first reached the default branch (a task's merge date) in UTC, or ""."""
    date = repo.git("log", "--first-parent", "--diff-filter=A", "-1", "--format=%cI", ref, "--", path,
                    cwd=top)
    return datetime.fromisoformat(date).astimezone(timezone.utc).isoformat(timespec="seconds") if date else ""


def json_of(text: str | None) -> dict[str, Any]:
    """A JSON object read from git, or {} when it's missing or unreadable."""
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


# --- helpers -------------------------------------------------------------------------------


def _paths(target: str, top: Path | None = None) -> tuple[Path, Path, Path, bool]:
    """The checkout, doc and notes file of a story key or a spec slug, and whether it's a story."""
    if KEY.fullmatch(target):
        top = story_checkout(target, top)
        return top, top / "plans" / f"{target}.md", top / "plans" / f"{target}.read.md", True
    top = top or repo.root()
    doc = top / "docs" / "specs" / f"{target}.md"
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", target) or not doc.is_file():
        repo.refuse(REFUSALS["no_spec"], slug=target)
    return top, doc, doc.with_name(f"{target}.read.md"), False


def _find_spec(top: Path, key: str) -> tuple[str, str, str] | None:
    """The confirmed spec for a story, including one still on its promoted task branch: its path,
    the branch it was found on and its text."""
    entry = next((item for item in repo.roadmap(top) if item["key"] == key), {})
    linked = entry.get("spec", "")
    refs = repo.git("for-each-ref", "--format=%(refname:short)", "refs/heads",
                    "refs/remotes/origin", cwd=top).splitlines()
    refs.sort(key=lambda ref: (not ref.startswith(f"task/{key}-"), ref))
    for ref in refs:
        # A merge can delete a listed branch before we look inside it: skip it.
        listing = repo.run("git", "ls-tree", "-r", "--name-only", ref, "--", "docs/specs", cwd=top)
        for path in listing.stdout.splitlines() if listing.returncode == 0 else []:
            if not re.fullmatch(r"docs/specs/[a-z0-9]+(?:-[a-z0-9]+)*\.md", path):
                continue
            spec = show(top, ref, path) or ""
            match = FRONTMATTER.match(spec)
            if not match:
                continue
            fields = dict(line.partition(":")[::2] for line in match[1].splitlines() if ":" in line)
            fields = {name.strip(): value.strip().strip('"\'') for name, value in fields.items()}
            body = spec[match.end():]
            if (fields.get("status") == "confirmed"
                    and fields.get("confirmed_hash") == hashlib.sha256(body.encode("utf-8")).hexdigest()
                    and (path == linked or re.search(rf"^- {re.escape(key)}: ", body, re.M))):
                return path, ref, spec
    return None


def _claude_read(top: Path, target: str, models: list[str], prompt: str, fresh_prompt: str,
                 resume: str | None, why: str) -> subprocess.CompletedProcess[str]:
    """Continue session `resume`; else, or when Claude no longer has it, start one with a known id."""
    command = ["claude", "-p", *models, "--permission-mode", "plan"]
    if resume:
        done = repo.run(*command, "--resume", resume, cwd=top, input=prompt)
        if not done.returncode or not done.stderr.startswith("No conversation found"):
            return done
        why = f"Claude couldn't continue session {resume}"
    if why:
        print(f"Starting a new Claude session, because {why}.", flush=True)
    session = str(uuid.uuid4())
    codex._record(codex._item_file(top, target, ".json", "Grill"),  # pyright: ignore[reportPrivateUsage]
                  claude={"id": session, "checkout": str(top)})
    return repo.run(*command, "--session-id", session, cwd=top, input=fresh_prompt)


def _store(top: Path, data: bytes, path: str = "") -> str:
    return subprocess.run(["git", "hash-object", "-w", "--stdin", *([f"--path={path}"] if path else [])],
                          cwd=top, input=data, capture_output=True, check=True).stdout.decode().strip()


def _diff(old: str, new: str, path: str) -> str:
    """A unified diff, line endings aside, so a Windows checkout's CRLF isn't a change."""
    return "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), f"a/{path}", f"b/{path}",
                                          lineterm=""))


def _findings(text: str) -> dict[int, str]:
    parts = FINDING.split(text)
    return {int(n): f"{n}. " + re.split(r"^## ", body, flags=re.M)[0].rstrip()
            for n, body in zip(parts[1::2], parts[2::2])}


def _known_traps(top: Path) -> str:
    """The `## Known traps` section of AGENTS.md on the default branch, outside Forge's block."""
    text = show(top, landed_ref(top), "AGENTS.md") or ""
    text = re.sub(r"<!-- forge:begin -->.*?<!-- forge:end -->", "", text, flags=re.S)
    return sections(text).get("Known traps", "").strip()


def _parsed(doc: Path, rel: str) -> dict[str, Any]:
    try:
        return parse(_text(doc))
    except ValueError as exc:
        repo.refuse(REFUSALS["bad_doc"], doc=rel, problem=exc)


def _record(notes: str) -> tuple[dict[str, str], str]:
    """A notes file's read record (its frontmatter) and the findings after it."""
    match = FRONTMATTER.match(notes)
    if not match:
        return {}, notes
    fields = {key.strip(): value.strip().strip("\"'")
              for key, colon, value in (line.partition(":") for line in match[1].splitlines()) if colon}
    return fields, notes[match.end():]


def _notes(record: dict[str, str], findings: str) -> str:
    head = "".join(f"{key}: {record.get(key) or ''}".rstrip() + "\n" for key in RECORD)
    return f"---\n{head}---\n{findings}"


def _repo_root_paths(said: str, roots: Any) -> str:
    """Rewrite paths under a checkout, with either separator, to repo-root paths GitHub resolves."""
    for root in roots:
        head = r"[\\/]".join(map(re.escape, re.split(r"[\\/]", root)))
        said = re.sub(head + r"[\\/]([^\s`'\")\]>]*)", lambda m: "/" + m[1].replace("\\", "/"), said)
    return said


def _snapshot(top: Path) -> str:
    """HEAD plus a tree of every file in the checkout, tracked or not, so any change shows."""
    index = Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "index", cwd=top))
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp) / "index"
        if index.is_file():
            shutil.copyfile(index, temp)  # a copy keeps git's stat cache, so this stays fast
        env = {**os.environ, "GIT_INDEX_FILE": str(temp)}
        for args in (["add", "-A"], ["write-tree"]):
            done = subprocess.run(["git", *args], cwd=top, env=env, capture_output=True, text=True,
                                  check=True)
    return done.stdout + repo.run("git", "rev-parse", "-q", "--verify", "HEAD", cwd=top).stdout


def _hash(top: Path, doc: Path) -> str:
    return repo.git("hash-object", "--", str(doc), cwd=top)


def _add_to_roadmap(top: Path, key: str, title: str) -> list[str]:
    items = repo.roadmap(top)  # refuses a roadmap it can't read
    if key in {item["key"] for item in items}:
        return []
    path = top / "plans" / "roadmap.json"
    data = json_of(_text(path)) if path.is_file() else {}
    last = max((item["order"] for item in items if isinstance(item.get("order"), int)), default=0)
    data["items"] = items + [{"key": key, "title": title, "status": "pending", "order": last + 1}]
    _write(path, json.dumps(data, indent=2) + "\n")
    return ["plans/roadmap.json"]


def _promote(fix_top: Path, fix: str, key: str, fix_state: dict[str, Any]) -> str:
    """Turn a fix's branch into the story's first task branch, keeping its commits."""
    task, branch, old = f"{key}/SPEC", f"task/{key}-SPEC", repo.state_path(fix)
    repo.git("branch", "-m", branch, cwd=fix_top)
    tracked = repo.run("git", "ls-files", "--error-unmatch", "--", old, cwd=fix_top).returncode == 0
    (fix_top / old).unlink()
    state = {name: value for name, value in fix_state.items() if name != "kind"}
    new = repo.write_state(task, {**state, "branch": branch}, fix_top)
    repo.commit_state("Turn the fix into the first part of its story", *([old] if tracked else []), new,
                      top=fix_top)
    return f"The fix {fix} is now the story's first task, {task}, in {fix_top}."


def _no_cycle(tasks: dict[str, dict[str, Any]]) -> None:
    checked: set[str] = set()

    def visit(task: str, path: list[str]) -> None:
        if task in path:
            loop = " -> ".join(path[path.index(task):] + [task])
            raise ValueError(f"Tasks row {task}: its After list makes a cycle ({loop})")
        if task not in checked:
            for after in tasks[task]["after"]:
                visit(after, path + [task])
            checked.add(task)

    for task in tasks:
        visit(task, [])


def _cell_paths(cell: str) -> list[str]:
    return [part for part in (piece.strip(" `") for piece in cell.split(","))
            if part not in ("", "-", "\u2014", "none")]


def _rel(top: Path, path: Path) -> str:
    return path.relative_to(top).as_posix()


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))  # bytes, so Windows writes the same LF file


COMMANDS = [
    {"words": "story new", "run": "new", "changes_state": True,
     "help": "Start a story branch, worktree and story doc, or promote a fix",
     "args": [(('key',), {}), (('title',), {"nargs": "?"}),
              (('--from-fix',), {"metavar": "FIX"})], "position": 70,
     "listing": '| `forge story new <KEY> "<title>"` | Starts a story\'s branch, worktree and doc (`--from-fix <fix>` promotes a fix) |'},
    {"words": "story done", "run": "done", "changes_state": True,
     "help": "Record a finished story's outcome sentence and dates",
     "args": [(('key',), {}), (('outcome',), {})], "position": 80,
     "listing": '| `forge story done <KEY> "<outcome>"` | Records a finished story\'s outcome sentence and dates |'},
    {"words": "read", "run": "read", "changes_state": True,
     "help": "Run a round of the cold read of a story doc or spec",
     "args": [(('target',), {"help": "a story key or a spec slug"})],
     "position": 90,
     "listing": '| `forge read <KEY or spec>` | Runs the next round of the cold read of a story doc or spec, until a round finds nothing |'},
]

GROUP_HELP = {"story": "Start a story, or record its outcome"}
