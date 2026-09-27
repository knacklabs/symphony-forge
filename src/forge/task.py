"""Starting work: a task of an approved story, a fix with its why and done-when, and the human's
permission for a fix to go over the fix limit. Also the story-doc reading that work needs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from forge import repo
from forge.repo import git, refuse, run

REFUSALS = {
    "bad_task": ("{item!r} is not a task; a task is named KEY/TASK.", "forge next"),
    "no_doc": ("Story {key} has no story doc on {default} or on story/{key}.",
               'forge story new {key} "<title>"'),
    "no_task": ("The story doc of {key} has no task {task}.", "forge next"),
    "not_approved": ("Story {key} is not approved yet.", "forge next"),
    "changed": ('"What changes for you" or "Done when" of story {key} changed after its approval, '
                "so it needs a new approval.", "forge next"),
    "started": ("{item} is already started on {branch}.", "forge work {item}"),
    "waiting": ("{item} waits for {deps} to merge first.", "forge next"),
    "overlap": ("{item} would change {paths}, which {other} is changing and hasn't merged yet.",
                "forge close {other}"),
    "fix_lines": ("A fix needs a one-line why and a one-line done-when.",
                  'forge fix start "<why>" --done "<done when>"'),
    "not_fix": ("{branch} is not a fix, and allow-large works only inside a fix's folder.",
                'cd <the fix folder> && forge fix allow-large "<reason>"'),
    "no_reason": ("The permission needs a one-line reason.", 'forge fix allow-large "<reason>"'),
}


# --- the story doc ---------------------------------------------------------------------


def sections(text: str) -> dict[str, str]:
    """A story doc's `## ` sections by heading; "#" holds the title."""
    parts = re.split(r"^## +(.+?) *$", text, flags=re.M)
    found = {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}
    title = re.search(r"^# +(.+?) *$", parts[0], re.M)
    found["#"] = title[1] if title else ""
    return found


def rows(doc: dict[str, str]) -> dict[str, dict[str, str]]:
    """The Tasks table's rows by ID, each cell under its column name."""
    # ponytail: a `|` inside a cell splits it; story docs keep cells to plain words and paths.
    lines = [line.strip().strip("|") for line in doc.get("Tasks", "").splitlines()
             if line.lstrip().startswith("|")]
    if len(lines) < 2:
        return {}
    header = [cell.strip() for cell in lines[0].split("|")]
    table = (dict(zip(header, (cell.strip() for cell in line.split("|")))) for line in lines[2:])
    return {row.get("ID", ""): row for row in table}


def cell_list(cell: str) -> list[str]:
    """A comma-separated cell (Scope, Tests, After) as a list; "none" and "—" are empty."""
    items = (part.strip().strip("`").strip() for part in cell.split(","))
    return [item for item in items if item.lower() not in ("", "none", "—", "-")]


def approval_hash(text: str) -> str:
    """The hash an approval binds: "What changes for you" and "Done when", nothing else."""
    doc = sections(text)
    both = f"{doc.get('What changes for you', '')}\n{doc.get('Done when', '')}"
    return hashlib.sha256(both.encode("utf-8")).hexdigest()


# --- branches, checkouts and the default branch ----------------------------------------


def branch_item(branch: str, top: Path) -> tuple[str, dict[str, Any]] | None:
    """The story, task or fix whose state in this checkout marks the branch as Forge's."""
    kind, _, name = branch.partition("/")
    if kind == "task":  # task/<KEY>-<TASK>: both may hold hyphens, so try every split
        items = [f"{name[:i]}/{name[i + 1:]}" for i, char in enumerate(name) if char == "-"]
    else:  # forge/<name> is migrate's fix branch
        items = [name] if kind in ("story", "fix", "forge") else []
    for item in items:
        if repo.ITEM.fullmatch(item) and (state := repo.read_state(item, top)) is not None:
            return item, state
    return None


def main_ref() -> str:
    """The default branch as the remote has it, freshly fetched: merged work lives there."""
    git("fetch", "-q", "--prune", "origin")
    return f"origin/{repo.default_branch()}"


def show(ref: str, rel: str) -> str | None:
    """A file's text at a commit, or None when it isn't there."""
    done = run("git", "show", f"{ref}:{rel}")
    return done.stdout if done.returncode == 0 else None


def _folder(name: str) -> Path:
    """A new worktree folder next to the main checkout, named <repo>-<name>."""
    main = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    return main.parent / f"{main.name}-{name}"


def _new_checkout(item: str, branch: str, folder: str, base: str, state: dict[str, Any],
                  message: str) -> Path:
    """Make the branch in its own worktree and commit the item's state there."""
    path = _folder(folder)
    git("worktree", "add", "-q", "--no-track", "-b", branch, str(path), base)
    rel = repo.write_state(item, repo.add_step({**state, "status": "started", "branch": branch},
                                               "start"), path)
    repo.commit_state(message, rel, top=path)
    return path


# --- forge task start ------------------------------------------------------------------


def start(args: argparse.Namespace) -> None:
    item = args.item
    match = repo.ITEM.fullmatch(item)
    if not match or not match["task"]:
        refuse(REFUSALS["bad_task"], item=item)
    key, task = match["key"], match["task"]
    main = main_ref()
    doc_rel = f"plans/{key}.md"
    # The story doc lands on the default branch with its first merged task; until then the
    # story branch holds it, and tasks start from there.
    base = main if show(main, doc_rel) is not None else f"story/{key}"
    text = show(base, doc_rel)
    if text is None:
        refuse(REFUSALS["no_doc"], key=key, default=repo.default_branch())
    tasks = rows(sections(text))
    if task not in tasks:
        refuse(REFUSALS["no_task"], key=key, task=task)
    approved = (json.loads(show(base, repo.state_path(key)) or "{}").get("approval") or {}).get("hash")
    if not approved:
        refuse(REFUSALS["not_approved"], key=key)
    if approved != approval_hash(text):
        refuse(REFUSALS["changed"], key=key)

    branch = f"task/{key}-{task}"
    started = _started(main)
    if item in started or _merged(main, item):
        refuse(REFUSALS["started"], item=item, branch=branch)
    waiting = [dep for dep in cell_list(tasks[task].get("After", ""))
               if not _merged(main, f"{key}/{dep}")]
    if waiting:
        refuse(REFUSALS["waiting"], item=item, deps=", ".join(f"{key}/{dep}" for dep in waiting))
    scope = cell_list(tasks[task].get("Scope", ""))
    for other, theirs in started.items():
        shared = [path for path in scope if any(_overlap(path, their) for their in theirs)]
        if shared:
            refuse(REFUSALS["overlap"], item=item, paths=", ".join(shared), other=other)

    path = _new_checkout(item, branch, f"{key}-{task}", base, {}, f"Start {item}")
    print(f"Started {item} on {branch} in {path}")
    print(f"Next: forge work {item}")


def _merged(main: str, item: str) -> bool:
    """An item's state reaches the default branch only with its merged pull request."""
    return show(main, repo.state_path(item)) is not None


def _started(main: str) -> dict[str, list[str]]:
    """Every story's started, unmerged tasks, each with its Scope."""
    # ponytail: a few git calls per task branch; fine for the handful of tasks in flight.
    found: dict[str, list[str]] = {}
    refs = git("for-each-ref", "--format=%(refname)", "refs/heads/task/",
               "refs/remotes/origin/task/").splitlines()
    for ref in refs:
        branch = "task/" + ref.split("/task/", 1)[1]
        for rel in git("ls-tree", "-r", "--name-only", ref, "--", ".factory/stories").splitlines():
            match = re.fullmatch(r"\.factory/stories/([^/]+)/tasks/([^/]+)\.json", rel)
            if match and f"task/{match[1]}-{match[2]}" == branch and not _merged(
                    main, f"{match[1]}/{match[2]}"):
                doc = rows(sections(show(ref, f"plans/{match[1]}.md") or ""))
                found[f"{match[1]}/{match[2]}"] = cell_list(doc.get(match[2], {}).get("Scope", ""))
    return found


def _overlap(a: str, b: str) -> bool:
    """Two Scope entries (files, folders or globs) that may touch the same file: their literal
    prefixes, up to the first wildcard, are disjoint only when neither contains the other."""
    # ponytail: prefix rule, may refuse some disjoint globs; widen only with a real need
    a, b = (re.split(r"[*?[]", entry, maxsplit=1)[0] for entry in (a, b))
    return a.startswith(b) or b.startswith(a)


# --- forge fix start / forge fix allow-large -------------------------------------------


def _one_line(text: str) -> bool:
    return bool(text.strip()) and "\n" not in text.strip()


def fix_start(args: argparse.Namespace) -> None:
    if not (_one_line(args.why) and _one_line(args.done)):
        refuse(REFUSALS["fix_lines"])
    why, done = args.why.strip(), args.done.strip()
    main = main_ref()
    slug = re.sub(r"[^a-z0-9]+", "-", why.lower()).strip("-")[:40].strip("-") or "fix"
    taken = {ref.split("/fix/", 1)[1] for ref in git(
        "for-each-ref", "--format=%(refname)", "refs/heads/fix/", "refs/remotes/origin/fix/").splitlines()}
    name, n = slug, 1
    while name in taken or _merged(main, name):
        n += 1
        name = f"{slug}-{n}"
    state = {"kind": "fix", "why": why, "done_when": done, "base": git("rev-parse", main)}
    path = _new_checkout(name, f"fix/{name}", f"fix-{name}", main, state, f"Start the fix: {why}")
    print(f"Started fix {name} on fix/{name} in {path}")
    print(f"Next: forge work {name}")


def allow_large(args: argparse.Namespace) -> None:
    if not _one_line(args.reason):
        refuse(REFUSALS["no_reason"])
    top = repo.root()
    branch = repo.current_branch(top)
    found = branch_item(branch, top) if branch.startswith(("fix/", "forge/")) else None
    if found is None:
        refuse(REFUSALS["not_fix"], branch=branch or "A detached HEAD")
    name, state = found
    state["allow_large"] = args.reason.strip()
    repo.commit_state(f"Allow the fix past the fix limit: {state['allow_large']}",
                      repo.write_state(name, state, top), top=top)
    print(f"Fix {name} may now go over the fix limit.")
