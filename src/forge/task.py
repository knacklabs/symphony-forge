"""Starting work: a task of an approved story, a fix with its why and done-when, and the human's
permission for a fix to go over the fix limit. Also the story-doc reading that work needs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
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
    "started": ("{item} is already started on {branch}{person}.", "forge work {item}"),
    "waiting": ("{item} waits for {deps} to merge first.", "forge next"),
    "overlap": ("{item} would change {paths}, which {other} is changing and hasn't merged yet.",
                "forge close {other}"),
    "fix_lines": ("A fix needs a one-line why and a one-line done-when.",
                  'forge fix start "<why>" --done "<done when>"'),
    "not_fix": ("{branch} is not a fix, and allow-large works only inside a fix's folder.",
                'cd <the fix folder> && forge fix allow-large "<reason>"'),
    "no_reason": ("The permission needs a one-line reason.", 'forge fix allow-large "<reason>"'),
    "bad_slug": ("{slug!r} is not a fix name; a fix name is lowercase words joined by hyphens.",
                 'forge fix start "<why>" --done "<done when>" --slug <name>'),
    "amend_lines": ("A new done-when needs one line of text and a one-line reason.",
                    'forge fix amend {fix} --done "<done when>" --because "<why>"'),
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
    return {row.get("ID", "").strip("` "): row for row in table}


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
        if (repo.ITEM.fullmatch(item) and (state := repo.read_state(item, top)) is not None
                and (kind != "task" or state.get("branch") == branch)):
            return item, state
    return None


def settings_allowed(item: str, top: Path, state: dict[str, Any]) -> bool:
    """Only this item's own Done-when can permit forge.toml edits."""
    done = state.get("done_when", "")
    if (match := repo.ITEM.fullmatch(item))["task"]:
        from forge import story

        text = (top / "plans" / f"{match['key']}.md").read_text(encoding="utf-8")
        row = rows(sections(text)).get(match["task"], {})
        covers = {int(n) for n in re.findall(r"\d+", row.get("Covers", ""))}
        parsed = story.parse(text)
        done = "\n".join(story.item(parsed, n, True) for n in parsed["done"] if n in covers)
    return "forge.toml" in done


def main_ref() -> str:
    """The default branch as the remote has it, freshly fetched: merged work lives there."""
    git("fetch", "-q", "--prune", "--tags", "origin")
    return f"origin/{repo.default_branch()}"


def show(ref: str, rel: str, top: Path | None = None) -> str | None:
    """A file's text at a commit, or None when it isn't there."""
    done = run("git", "show", f"{ref}:{rel}", cwd=top)
    return done.stdout if done.returncode == 0 else None


def _folder(name: str) -> Path:
    """A new worktree folder next to the main checkout, named <repo>-<name>."""
    main = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir")).parent
    return main.parent / f"{main.name}-{name}"


def _new_checkout(item: str, branch: str, folder: str, base: str, state: dict[str, Any],
                  message: str, carry: tuple[str, list[str]] | None = None) -> Path:
    """Make the branch in its own worktree and commit the item's state there, after a first
    commit of the files `carry` names from its branch."""
    path = _folder(folder)
    git("worktree", "add", "-q", "--no-track", "-b", branch, str(path), base)
    rel = repo.write_state(item, repo.add_step({**state, "status": "started", "branch": branch},
                                               "start"), path)
    if carry:  # after the state, so the git hooks know the branch
        # Copying files alone would lose the story's starter and approval after cleanup.
        git("update-ref", f"refs/tags/forge-plan/{branch}", carry[0], "", cwd=path)
        git("checkout", carry[0], "--", *carry[1], cwd=path)
        key = item.split("/")[0]
        entries = json.loads(show(carry[0], "plans/roadmap.json") or "{}").get("items", [])
        entry = next((entry for entry in entries if entry["key"] == key), None)
        if entry and key not in {entry["key"] for entry in repo.roadmap(path)}:
            from forge import story
            carry[1].extend(story.add_to_roadmap(path, [entry]))
        repo.commit_state(f"Bring in the approved plan from {carry[0]}", *carry[1], top=path)
    repo.commit_state(message, rel, top=path)
    publish_start(path, branch)
    return path


def publish_start(top: Path, branch: str) -> None:
    """Create the remote claim only if nobody else has made it."""
    # Keep the original commit reachable after squash merges and branch cleanup.
    tag = f"refs/tags/forge-start/{branch}"
    git("update-ref", tag, "HEAD", "", cwd=top)
    pushed = run("git", "push", "-q", "--atomic", "--set-upstream",
                 f"--force-with-lease=refs/heads/{branch}:", f"--force-with-lease={tag}:",
                 "origin", branch, tag, cwd=top)
    if pushed.returncode:
        print(f"Could not push {branch} to GitHub; the work stays local.\n{pushed.stderr.strip()}",
              file=sys.stderr)


def starters(top: Path, ref: str = "--all") -> dict[str, str]:
    """Names from the commits that started items, never from their later contributors."""
    log = git("log", ref, "--reverse", "--diff-filter=A", "--no-renames", "--grep=^Start ",
              "--format=%x00%an%x00", "--name-only", "--", ".factory/stories", ".factory/fixes",
              cwd=top).split("\0")[1:]
    found: dict[str, str] = {}
    for name, paths in zip(log[::2], log[1::2]):
        for rel in paths.splitlines():
            if rel.endswith(".json"):
                found.setdefault(rel, name)
    return found


def github_login(top: Path) -> str | None:
    def read() -> str | None:
        result = run("gh", "api", "user", "--jq", ".login", cwd=top)
        if not result.returncode and result.stdout.strip():
            return result.stdout.strip()
        print("Could not read your GitHub login; assignment matching is unavailable.", file=sys.stderr)
        return None
    return repo.command_fact("GitHub login", top, read)


def developer(row: dict[str, Any]) -> str | None:
    return (row.get("Developer") or "").strip("` ") or None


# --- forge task start ------------------------------------------------------------------


def start(args: argparse.Namespace) -> None:
    item = args.item
    match = repo.ITEM.fullmatch(item)
    if not match or not match["task"]:
        refuse(REFUSALS["bad_task"], item=item)
    key, task = match["key"], match["task"]
    from forge import story  # story imports this module's helpers
    main = main_ref()
    top, doc_rel, story_branch = repo.root(), f"plans/{key}.md", f"story/{key}"
    published = story.plan_ref(top, key)
    if (published != main and not git("branch", "--list", story_branch)
            and show(f"origin/{story_branch}", doc_rel) is not None):
        git("branch", "--track", story_branch, f"origin/{story_branch}")
    behind = story.plan_behind(top, key, main) if published != main else ""
    old_pin = published != main and repo._older(repo._pin(show(story_branch, "forge.toml") or ""),
                                                 repo._pin(show(main, "forge.toml") or ""))
    if published != main and (old_pin or (show(story_branch, doc_rel) is not None and
            run("git", "diff", "--name-only", "-z", story_branch, main).stdout == doc_rel + "\0")):
        folder = story.stories_here(top).get(key)
        if folder is None:
            folder = _folder(f"story-{key}")
            git("worktree", "add", "-q", str(folder), story_branch)
        retry = f"forge task start {item}"
        if old_pin:
            if not run("git", "rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=folder).returncode:
                raise repo.Refused(f"Resolve the merge conflicts, if any, in {folder}, then commit the merge.", retry)
            if git("status", "--porcelain", cwd=folder):
                raise repo.Refused(f"Commit or stash the changes in {folder} before updating its Forge release.", retry)
        if (not git("status", "--porcelain", cwd=folder) and
                run("git", "rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=folder).returncode):
            merged = run("git", "merge", "-q", "--no-edit", main, cwd=folder)
            if not merged.returncode:
                reason = "updated its Forge release" if old_pin else "only the story doc differs"
                print(f"Merged {main} into {story_branch}; {reason}.")
                behind = ""
            elif old_pin:
                if git("diff", "--name-only", "--diff-filter=U", cwd=folder):
                    raise repo.Refused(f"Resolve the merge conflicts, if any, in {folder}, then commit the merge.", retry)
                raise repo.Refused(f"Could not update {story_branch}'s Forge release: {merged.stderr.strip()}",
                                   f"git -C {shlex.quote(str(folder))} status; fix the reported problem "
                                   f"and finish the merge, then {retry}")
            elif not run("git", "rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=folder).returncode:
                git("merge", "--abort", cwd=folder)
    if behind:
        sys.exit(behind)  # the same one line forge next prints
    notes_rel = f"plans/{key}.read.md"
    # Published builder assignments stay current even after the first part lands.
    state_rel = repo.state_path(key)
    source = story.plan_ref(top, key)
    text = show(source, doc_rel)
    if text is None:
        refuse(REFUSALS["no_doc"], key=key, default=repo.default_branch())
    text = story._plan(top, key)
    try:
        story.parse(text, repo.root())
    except ValueError as exc:
        refuse(story.REFUSALS["bad_doc"], doc=doc_rel, problem=exc)
    notes = show(source, notes_rel)
    if story.rounds(notes, show(source, state_rel)):
        checkout = story.stories_here(repo.root()).get(key)
        if checkout and source == story_branch:  # edits not committed yet count too
            story.check_read(key, checkout)
        digest = run("git", "hash-object", "--stdin", cwd=top, input=text).stdout.strip()
        story.gate(key, doc_rel, notes or "", digest, text)
    tasks = rows(sections(text))
    if task not in tasks:
        refuse(REFUSALS["no_task"], key=key, task=task)
    approved = (json.loads(show(source, repo.state_path(key)) or "{}").get("approval") or {}).get("hash")
    if not approved:
        refuse(REFUSALS["not_approved"], key=key)
    if approved != approval_hash(text):
        refuse(REFUSALS["changed"], key=key)

    branch = f"task/{key}-{task}"
    started = _started(main)
    if item in started or _merged(main, item):
        ref = f"origin/{branch}" if show(f"origin/{branch}", repo.state_path(item)) else "--all"
        name = starters(top, ref).get(repo.state_path(item))
        refuse(REFUSALS["started"], item=item, branch=branch, person=f" by {name}" if name else "")
    waiting = [dep if "/" in dep else f"{key}/{dep}" for dep in cell_list(tasks[task].get("After", ""))]
    waiting = [dep for dep in waiting if not _merged(main, dep)]
    if waiting:
        refuse(REFUSALS["waiting"], item=item, deps=", ".join(waiting))
    scope = cell_list(tasks[task].get("Scope", ""))
    for other, theirs in started.items():
        shared = [path for path in scope if any(_overlap(path, their) for their in theirs)]
        if shared:
            refuse(REFUSALS["overlap"], item=item, paths=", ".join(shared), other=other)

    assigned = developer(tasks[task])
    if assigned and (login := github_login(top)) and assigned.casefold() != login.casefold():
        print(f"This part was assigned to {assigned}; starting it anyway.", file=sys.stderr)
    base = start_base(main, key, tasks[task])
    carry = (source, [rel for rel in (doc_rel, notes_rel, state_rel) if show(source, rel) is not None]
             ) if source != base else None
    path = _new_checkout(item, branch, f"{key}-{task}", base, {}, f"Start {item}", carry)
    print(f"Started {item} on {branch} in {path}")
    print(f"Next: forge work {item}")


def start_base(main: str, key: str, row: dict[str, str]) -> str:
    """Where forge task start branches a task, so the task takes that branch's forge.toml: the
    default branch once the story doc is there, or when the task comes after another story's
    task, whose merged code is only there; else the story branch."""
    if (any("/" in dep for dep in cell_list(row.get("After", "")))
            or show(main, f"plans/{key}.md") is not None):
        return main
    from forge import story
    return story.plan_ref(repo.root(), key)


def _merged(main: str, item: str, top: Path | None = None) -> bool:
    """An item's state reaches the default branch only with its merged pull request."""
    return show(main, repo.state_path(item), top) is not None


def _started(main: str, top: Path | None = None,
             history: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """Every story's started, unmerged tasks, each with its Scope."""
    # ponytail: a few git calls per task branch; fine for the handful of tasks in flight.
    found: dict[str, list[str]] = {}
    refs = ([ref for ref in history["ref_states"] if ref.startswith(("refs/heads/task/", "refs/remotes/origin/task/"))]
            if history is not None else git("for-each-ref", "--format=%(refname)", "refs/heads/task/",
                                            "refs/remotes/origin/task/", cwd=top).splitlines())
    for ref in refs:
        branch = "task/" + ref.split("/task/", 1)[1]
        paths = (history["ref_states"][ref] if history is not None else
                 git("ls-tree", "-r", "--name-only", ref, "--", ".factory/stories", cwd=top).splitlines())
        for rel in paths:
            match = re.fullmatch(r"\.factory/stories/([^/]+)/tasks/([^/]+)\.json", rel)
            if match and f"task/{match[1]}-{match[2]}" == branch and not (
                    rel in history["states"] if history is not None else _merged(main, f"{match[1]}/{match[2]}", top)):
                text = (history["docs"].get(f"{ref}:plans/{match[1]}.md", "") if history is not None else
                        show(ref, f"plans/{match[1]}.md", top) or "")
                doc = rows(sections(text))
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
    if args.slug is not None and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.slug):
        refuse(REFUSALS["bad_slug"], slug=args.slug)
    main = main_ref()
    slug = args.slug or re.sub(r"[^a-z0-9]+", "-", why.lower()).strip("-")[:40].strip("-") or "fix"
    taken = {ref.split("/fix/", 1)[1] for ref in git(
        "for-each-ref", "--format=%(refname)", "refs/heads/fix/", "refs/remotes/origin/fix/",
        "refs/tags/forge-start/fix/").splitlines()}
    name, n = slug, 1
    while name in taken or _merged(main, name):
        n += 1
        name = f"{slug}-{n}"
    top = repo.root()
    parent = branch_item(repo.current_branch(top), top)
    base = "HEAD" if parent and not _merged(main, parent[0]) else main
    state = {"kind": "fix", "why": why, "done_when": done, "base": git("rev-parse", base)}
    if base == "HEAD":
        state["stacked_on"] = parent[0]
    if (repo.root() / "forge.toml").is_file() and repo.is_prototype(repo.root()):
        state["allow_large"] = "Prototype before sign-off"
    path = _new_checkout(name, f"fix/{name}", f"fix-{name}", base, state, f"Start the fix: {why}")
    print(f"Started fix {name} on fix/{name} in {path}")
    if name != slug:
        print(f"Fix name {slug} is already taken; using {name}.")
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


def amend(args: argparse.Namespace) -> None:
    if not (_one_line(args.done) and _one_line(args.because)):
        refuse(REFUSALS["amend_lines"], fix=args.item)
    from forge import close  # close imports story, which imports this module
    top = close._worktree(args.item)
    state = repo.read_state(args.item, top) or {}
    # The old text and the reason stay in the record; the next review reads only done_when.
    state.setdefault("amendments", []).append(
        {"done_when": state.get("done_when", ""), "because": args.because.strip(), "at": repo.now()})
    state["done_when"] = args.done.strip()
    # The review reads Ruling: lines from the branch's commits, so it drops findings on the old text.
    ruling = (f'Ruling: Done-when changed from "{state["amendments"][-1]["done_when"]}" to '
              f'"{state["done_when"]}" because {args.because.strip()}; judge the new text.')
    repo.commit_state(f"Change the fix's done-when\n\n{ruling}",
                      repo.write_state(args.item, state, top), top=top)
    print(f"Fix {args.item} is now done when: {state['done_when']}")
    print(f"Next: forge close {args.item}")


COMMANDS = [
    {"words": "task start", "run": "start", "changes_state": True,
     "help": "Start a task in its own branch and worktree",
     "args": [(('item',), {"metavar": "KEY/TASK"})], "position": 100,
     "listing": "| `forge task start <KEY>/<TASK>` | Starts a task in its own branch and worktree |"},
    {"words": "fix start", "run": "fix_start", "changes_state": True,
     "help": "Start a fix in its own branch and worktree, with a one-line why and done-when",
     "args": [(('why',), {}), (('--done',), {"required": True, "metavar": "DONE_WHEN"}),
              (('--slug',), {"metavar": "NAME", "help": "the fix's name, instead of one cut from the why"})],
     "position": 110,
     "listing": '| `forge fix start "<why>" --done "<done when>"` | Starts a small fix in its own branch and worktree (`--slug <name>` names it) |'},
    {"words": "fix allow-large", "run": "allow_large", "changes_state": True,
     "help": "Record the human's permission for this fix to go over the fix limit",
     "args": [(('reason',), {})], "position": 120,
     "listing": '| `forge fix allow-large "<reason>"` | Records the human\'s permission for a fix to go over the fix limit |'},
    {"words": "fix amend", "run": "amend", "changes_state": True,
     "help": "Replace a fix's done-when, keeping the old text and the reason in its record",
     "args": [(('item',), {"metavar": "FIX"}), (('--done',), {"required": True, "metavar": "DONE_WHEN"}),
              (('--because',), {"required": True, "metavar": "WHY"})], "position": 125,
     "listing": '| `forge fix amend <fix> --done "<done when>" --because "<why>"` | Replaces a fix\'s done-when; the old text and the reason stay in its record, and the next review judges the new text |'},
]

GROUP_HELP = {
    "task": "Start a task",
    "fix": "Start a fix, let it go over the fix limit, or change its done-when",
}
