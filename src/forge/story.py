"""Story docs: `story new` (and promotion from a fix), the one cold read, `story done`, the doc's
shape checks and the story-doc part of forge-pr-check.

A story is `plans/<KEY>.md` on its own `story/<KEY>` branch and worktree. The cold read of a doc
writes its notes beside it (`plans/<KEY>.read.md`, `docs/specs/<slug>.read.md`), the same format
RECORDS reads for `spec confirm`:

    ---
    reader: <who read it>
    read_at: <when>
    read_hash: <git hash-object of the doc as read>
    amended_hash: <git hash-object after the amendment, recorded by --amended; empty until then>
    ---
    1. <finding>
       Disposition: cut | defer | keep <one-line reason>

A task is merged once its state file is on origin/<default>: its pull request carried it there.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
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
    "already_read": ("{doc} already has its one cold read.", "forge read {target} --amended"),
    "no_read": ("{doc} has no cold read.", "forge read {target}"),
    "changed": ("{doc} changed after its cold read.", "forge read {target} --amended"),
    # ponytail: --amended may run again, which is how a doc edited after approval gets re-approved.
    "changed_again": ("{doc} changed after its recorded amendment.", "forge read {target} --amended"),
    "no_disposition": ("Finding {number} in {notes} has no disposition: cut, defer, or keep with a "
                       "reason.", "edit {notes}, then forge next"),
    "not_finished": ("{key} isn't finished: {problem}.", "git fetch origin, then forge next"),
}

TEMPLATES = Path(__file__).parent / "templates"
KEY = re.compile(r"[A-Z][A-Z0-9-]*")
COLUMNS = ("ID", "Name", "What it delivers", "Covers", "Scope", "Tests", "After", "User-facing")
APPROVED = ("What changes for you", "Done when")  # the sections an approval binds
RECORD = ("reader", "read_at", "read_hash", "amended_hash")
FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
FINDING = re.compile(r"^(\d+)\.[ \t]", re.M)
DISPOSITION = re.compile(r"^[ \t]*(?:[-*][ \t]+)?\**disposition:\**[ \t]*(cut|defer|keep)\b"
                         r"[ \t:\u2014\u2013-]*(\S?)", re.I | re.M)
# The variable each coordinating app sets in the commands it runs, and the other family, which does
# the cold read, read-only. Codex's is its conversation's id.
READERS = {"CLAUDECODE": "codex", "CODEX_THREAD_ID": "claude"}


# --- commands ------------------------------------------------------------------------------


def new(args: Any) -> int:
    top, key, fix = repo.root(), args.key, args.from_fix
    if not KEY.fullmatch(key):
        repo.refuse(REFUSALS["bad_key"], key=key)
    why, row, fix_top, fix_state = "<Why this matters now, in plain English.>", "", None, None
    done = "<Something anyone can observe once this is done.>"
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
        row = f"| {fix.upper()} | {why} | {why} | 1 | {', '.join(scope)} | | none | no |\n"
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
    rel, text = _rel(top, doc), _text(notes)
    record, findings = _record(text)
    if args.amended:
        if not record.get("read_hash"):
            repo.refuse(REFUSALS["no_read"], doc=rel, target=target)
        _write(notes, _notes({**record, "amended_hash": _hash(top, doc)}, findings))
        print(f"Recorded the amendment of {rel}.\nNext: forge next")
        return 0
    if record.get("read_hash"):
        repo.refuse(REFUSALS["already_read"], doc=rel, target=target)
    if is_story:
        _parsed(doc, rel)
    readers = [reader for variable, reader in READERS.items() if os.environ.get(variable)]
    if len(readers) != 1:  # neither app, or one running inside the other
        repo.refuse(REFUSALS["coordinator"], target=target)
    reader, config = readers[0], repo.config(top)
    models = worker.ready(top, config, "Grill", reader == "codex")  # forge work's checks
    prompt, head = (TEMPLATES / "cold-read.md").read_text(encoding="utf-8").split("<!-- forge:notes -->\n")
    before = _snapshot(top)  # first, so any change from here on discards the read
    text = doc.read_bytes()  # one read: the reader gets exactly the bytes that are hashed
    read_hash = subprocess.run(["git", "hash-object", "--stdin", f"--path={rel}"], cwd=top, input=text,
                               capture_output=True, check=True).stdout.decode().strip()
    prompt = Template(prompt).safe_substitute(path=rel, doc=text.decode("utf-8"))
    if reader == "claude":
        done = repo.run("claude", "-p", *models, "--permission-mode", "plan", cwd=top, input=prompt)
        said, failed = done.stdout.strip(), done.returncode
        problem = (done.stderr.strip().splitlines() or [f"it wrote nothing (exit code {done.returncode})"])[-1]
    else:
        ran = codex.run(top, target, "Grill", f"Grill · {target} · {rel}", prompt, "read-only")
        said, failed = (ran["text"] or "").strip(), ran["status"] != "completed"
        problem = (f"Codex reported the turn {ran['status']}." if failed and ran["status"] else
                   "Codex never reported the turn's end." if failed else "it wrote nothing.")
    if _snapshot(top) != before:
        repo.refuse(REFUSALS["discarded"], doc=rel, target=target)
    if failed or not said:
        repo.refuse(REFUSALS["reader_failed"], doc=rel, target=target, problem=problem)
    if not FINDING.search(said) and not said.lower().startswith("no findings"):
        said = f"1. {said}"  # ponytail: unstructured output is one finding, so it still needs a disposition
    record = {"reader": f"{reader} ({repo.models(config, 'grill', reader)['model']})",
              "read_at": repo.now(), "read_hash": read_hash, "amended_hash": ""}
    _write(notes, _notes(record, f"{head.strip()}\n\n{said}\n"))
    if is_story:
        state = repo.read_state(target, top) or {}
        state["status"] = "read"
        repo.write_state(target, repo.add_step(state, "read"), top)
    print(f"Wrote the cold read to {_rel(top, notes)}.\n"
          f"Next: give every finding a disposition, amend the doc once, then forge read {target} --amended")
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
    """Refuse unless a story doc or spec has its cold read, is unchanged since the read (or its
    amendment), and every finding has a disposition. Approval calls this; so can `spec confirm`."""
    top, doc, notes, is_story = _paths(target, top)
    rel = _rel(top, doc)
    record, findings = _record(_text(notes))
    if not record.get("read_hash"):
        repo.refuse(REFUSALS["no_read"], doc=rel, target=target)
    amended = record.get("amended_hash")
    if _hash(top, doc) != (amended or record["read_hash"]):
        repo.refuse(REFUSALS["changed_again" if amended else "changed"], doc=rel, target=target)
    number = undisposed(findings)
    if number:
        repo.refuse(REFUSALS["no_disposition"], number=number, notes=_rel(top, notes))
    if is_story:
        _parsed(doc, rel)


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
    for path in changed:
        match = re.fullmatch(r"plans/([A-Z][A-Z0-9-]*)\.md", path)
        text = show(top, head, path) if match else None
        if text is None:
            continue
        try:
            parse(text)
        except ValueError as exc:
            return f"The story doc {path} is malformed: {exc}."
        number = undisposed(_record(show(top, head, f"plans/{match[1]}.read.md") or "")[1])
        if number:
            return f"Finding {number} in plans/{match[1]}.read.md has no disposition."
        approval = json_of(show(top, head, repo.state_path(match[1]))).get("approval") or {}
        if approval.get("hash") != approval_hash(text):
            return f'The approval of {path} doesn\'t match its "What changes for you" and "Done when".'
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
    task, branch, old = f"{key}/{fix.upper()}", f"task/{key}-{fix.upper()}", repo.state_path(fix)
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
