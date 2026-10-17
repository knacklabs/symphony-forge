"""Starting work: a task of an approved story, a fix with its why and done-when, and the human's
permission for a fix to go over the fix limit. Also the story-doc reading that work needs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
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
    "base_not_started": ("{item} builds on {base}, which hasn't started yet.", "forge task start {base}"),
    "base_local": ("{item} waits for {base} to publish reviewed changes.", "forge close {base}"),
    "base_not_built": ("{item} builds on {base}, whose latest changes haven't passed review.", "forge close {base}"),
    "base_stacked": ("{item} waits for {base}, which builds on {below}, so it starts once {below} merges.", "forge next"),
    "base_older": ("{item} waits for {base}, which runs an older Forge release, so it starts once {base} merges.", "forge next"),
    "two_bases": ("{item} waits for {deps}, so it starts once all but one of them merge.", "forge next"),
    "overlap": ("{item} would change {paths}, which {other} is changing and hasn't merged yet.",
                "forge close {other}"),
    "fix_lines": ("A fix needs a one-line why and a one-line done-when.",
                  'forge fix start "<why>" --done "<done when>"'),
    "fix_kind": ("A prototype fix needs --kind ui, backend or mechanical.",
                 'forge fix start "<why>" --done "<done when>" --kind <kind>'),
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


def owner(text: str) -> str | None:
    found = re.search(r"^Owner:[ \t]*`?([^`\s]+)", text, re.M)
    return found[1] if found else None


def assign(args: argparse.Namespace) -> None:
    from forge import story

    top, login = repo.root(), args.login
    match = repo.ITEM.fullmatch(args.item)
    if not match or not story.KEY.fullmatch(match["key"]):
        raise repo.Refused("Use a story key or a story key and part to assign work.",
                           "forge assign <KEY or KEY/TASK> <login>")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", login) or "--" in login:
        raise repo.Refused("Use a GitHub username with letters, digits and single hyphens, without @.",
                           "forge assign <KEY or KEY/TASK> <login>")
    key, part = match["key"], match["task"]
    main_ref()
    branch, rel = f"story/{key}", f"plans/{key}.md"
    source = story.plan_ref(top, key)
    text = story.show(top, source, rel) or ""
    tasks = rows(sections(text))
    if not tasks:
        raise repo.Refused("This story has no plan. Plan it first, then assign it.", "forge next")
    if part and part not in tasks:
        refuse(REFUSALS["no_task"], key=key, task=part)
    path = story.stories_here(top).get(key)
    if path and git("status", "--porcelain", cwd=path):
        raise repo.Refused("The story has local changes. Commit or set them aside before you assign it.",
                           "forge next")
    if path is None:
        if git("branch", "--list", branch, cwd=top):
            path = _folder(branch.replace("/", "-"))
            git("worktree", "add", "-q", str(path), branch, cwd=top)
        else:
            path = story.add_worktree(top, branch, source)
    if git("rev-parse", "HEAD", cwd=path) != git("rev-parse", source, cwd=top):
        updated = run("git", "merge", "--ff-only", source, cwd=path)
        if updated.returncode:
            raise repo.Refused("The local and published story differ. Reconcile them before you assign it.",
                               "forge next")
    text = (path / rel).read_text(encoding="utf-8")
    if part:
        assignments = {tid: developer(row) for tid, row in rows(sections(text)).items()}
        assignments[part] = login
        text = story._with_developers(text, assignments, True)
    elif re.search(r"^Owner:", text, re.M):
        text = re.sub(r"^Owner:[^\n]*", f"Owner: {login}", text, count=1, flags=re.M)
    else:
        # Keep assignment metadata out of the approval's What changes and Done when sections.
        heading = re.search(r"^## For the builders[ \t]*$", text, re.M)
        at = heading.end() if heading else text.index("\n")
        text = text[:at] + f"\nOwner: {login}" + text[at:]
    (path / rel).write_bytes(text.encode("utf-8"))
    repo.commit_state(f"Assign the {'part' if part else 'story'} to {login}", rel, top=path)
    pushed = run("git", "push", "-q", "--set-upstream", "origin", branch, cwd=path)
    if pushed.returncode:
        raise repo.Refused("The assignment is local. The push failed: " + pushed.stderr.strip(),
                           f"git -C {str(path)!r} push origin {branch}")
    print(f"Assigned the {'part' if part else 'story'} to {login} and published it.")


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
    old_pin = published != main and repo._older(repo._pin(show(published, "forge.toml") or ""),
                                                 repo._pin(show(main, "forge.toml") or ""))
    update_plan = published != main and (old_pin or (show(published, doc_rel) is not None and
            run("git", "diff", "--name-only", "-z", published, main).stdout == doc_rel + "\0"))
    # Preview the automatic update without creating a branch, checkout or commit.
    preview = None
    folder = story.stories_here(top).get(key)
    if update_plan and (folder is None or not git("status", "--porcelain", cwd=folder)):
        merged = run("git", "merge-tree", "--write-tree", published, main)
        if merged.returncode == 0:
            preview = merged.stdout.splitlines()[0]
    notes_rel = f"plans/{key}.read.md"
    # Published builder assignments stay current even after the first part lands.
    state_rel = repo.state_path(key)
    source = preview or story.plan_ref(top, key)
    text = show(source, doc_rel)
    if text is None:
        refuse(REFUSALS["no_doc"], key=key, default=repo.default_branch())
    if preview is None:
        text = story._plan(top, key)
    try:
        story.parse(text, repo.root(), key=key)
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
    approval = json.loads(show(source, repo.state_path(key)) or "{}").get("approval") or {}
    approved = approval.get("hash")
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
    scope = cell_list(tasks[task].get("Scope", ""))
    blockers = waits_for(item, waiting, scope, started)
    stacked = stack_base(item, blockers, main, top)
    if waiting and not stacked:
        refuse(REFUSALS["waiting"], item=item, deps=", ".join(waiting))
    for other, theirs in started.items():
        if stacked and other == blockers[0]:
            continue
        shared = [path for path in scope if any(_overlap(path, their) for their in theirs)]
        if shared:
            refuse(REFUSALS["overlap"], item=item, paths=", ".join(shared), other=other)

    if (published != main and not git("branch", "--list", story_branch)
            and show(f"origin/{story_branch}", doc_rel) is not None):
        git("branch", "--track", story_branch, f"origin/{story_branch}")
    behind = story.plan_behind(top, key, main) if published != main else ""
    if update_plan:
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
            if published != story_branch:
                git("merge", "-q", "--ff-only", published, cwd=folder)
            merged = run("git", "merge", "-q", "--no-edit", main, cwd=folder)
            if not merged.returncode:
                reason = "updated its Forge release" if old_pin else "only the story doc differs"
                print(f"Merged {main} into {story_branch}; {reason}.")
                behind = ""
            elif old_pin:
                if git("diff", "--name-only", "--diff-filter=U", cwd=folder):
                    raise repo.Refused(f"Resolve the merge conflicts, if any, in {folder}, then commit the merge.", retry)
                raise repo.Refused(f"Could not update {story_branch}'s Forge release: {merged.stderr.strip()}",
                                   f"git -C {repo.quote(str(folder))} status; fix the reported problem "
                                   f"and finish the merge, then {retry}")
            elif not run("git", "rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=folder).returncode:
                git("merge", "--abort", cwd=folder)
    if behind:
        sys.exit(behind)  # the same one line forge next prints
    source = story.plan_ref(top, key)

    assigned = developer(tasks[task]) or owner(text)
    if assigned and (login := github_login(top)) and assigned.casefold() != login.casefold():
        print(f"This part was assigned to {assigned}; starting it anyway.", file=sys.stderr)
    base = stacked or start_base(main, key, tasks[task])
    carry = (source, [rel for rel in (doc_rel, notes_rel, state_rel) if show(source, rel) is not None]
             ) if source != base else None
    # Earlier approvals keep their agreed parts, including ones not started yet.
    state = {"part_line_limit": approval["part_line_limit"]} if approval.get("part_line_limit") else {}
    if stacked:
        state.update(stacked_on=blockers[0], base=git("rev-parse", stacked))
    path = _new_checkout(item, branch, f"{key}-{task}", base, state, f"Start {item}", carry)
    on = f" on top of {blockers[0]}" if stacked else ""
    print(f"Started {item}{on} on {branch} in {path}")
    print(f"Next: forge work {item}")


def forge_merged(main: str, item: str, top: Path | None = None) -> str:
    """The default branch commit where Forge merged this item, or an empty string."""
    commit = git("log", "--first-parent", "--diff-filter=A", "-1", "--format=%H", main,
                 "--", repo.state_path(item), cwd=top)
    if commit and f"Forge-merged: {item}" in git("show", "-s", "--format=%B", commit, cwd=top).splitlines():
        return commit
    return ""


def stack_base(item: str, blockers: list[str], main: str, top: Path | None = None) -> str | None:
    """The single reviewed remote base for a new part; refuse before any start mutation."""
    top = top or repo.root()
    if not blockers or repo.config(top)["stack"] == "off":
        return None
    if len(blockers) != 1:
        refuse(REFUSALS["two_bases"], item=item, deps=", ".join(blockers))
    base = blockers[0]
    ref = "origin/task/" + base.replace("/", "-")
    state = json.loads(show(ref, repo.state_path(base), top) or "{}")
    if not state or state.get("branch") != ref.removeprefix("origin/"):
        local = ref.removeprefix("origin/")
        local_state = json.loads(show(local, repo.state_path(base), top) or "{}")
        if local_state.get("branch") == local:
            refuse(REFUSALS["base_local"], item=item, base=base)
        refuse(REFUSALS["base_not_started"], item=item, base=base)
    if below := state.get("stacked_on"):
        merged = forge_merged(main, below, top)
        if not merged or run("git", "merge-base", "--is-ancestor", merged, ref, cwd=top).returncode:
            refuse(REFUSALS["base_stacked"], item=item, base=base, below=below)
    if repo._pin(show(ref, "forge.toml", top) or "") != repo._pin(show(main, "forge.toml", top) or ""):
        refuse(REFUSALS["base_older"], item=item, base=base)
    from forge import review
    from forge.prcheck import _on_branch
    result = state.get("review") or {}
    if (result.get("status") != "clean" or not _on_branch(top, str(result.get("commit", "")), ref)
            or review.blocking(result)
            or result.get("changed") != review.fingerprint(ref, base, top, state, main)):
        refuse(REFUSALS["base_not_built"], item=item, base=base)
    return ref


def start_base(main: str, key: str, row: dict[str, str], history: dict[str, Any] | None = None,
               top: Path | None = None) -> str:
    """Where forge task start branches a task, so the task takes that branch's forge.toml: the
    default branch once the story doc is there, or when the task comes after another story's
    task, whose merged code is only there; else the story branch."""
    if (any("/" in dep for dep in cell_list(row.get("After", "")))
            or (history["docs"].get(f"{main}:plans/{key}.md") is not None if history is not None
                else show(main, f"plans/{key}.md") is not None)):
        return main
    from forge import story
    return story.plan_ref(top or repo.root(), key, history)


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


def waits_for(part: str, after: list[str], scope: list[str] | None = None,
              busy: dict[str, list[str]] | None = None) -> list[str]:
    """Published prerequisites and started parts whose scopes block the part KEY/TASK; a part
    never waits for itself."""
    key = part.split("/", 1)[0]
    waits = [item if "/" in item else f"{key}/{item}" for item in after]
    blockers = [item for item, owned in (busy or {}).items()
                if any(_overlap(a, b) for a in (scope or []) for b in owned)]
    return [item for item in dict.fromkeys(waits + blockers) if item != part]


# --- forge fix start / forge fix allow-large -------------------------------------------


def _one_line(text: str) -> bool:
    return bool(text.strip()) and "\n" not in text.strip()


def require_prototype_design(top: Path) -> None:
    """Unsigned-prototype UI gate: DESIGN fills this hook with the approved-design check."""


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
    prototype = (top / "forge.toml").is_file() and repo.is_prototype(top)
    fix_kind = args.kind
    if prototype and fix_kind is None:
        refuse(REFUSALS["fix_kind"])
    if prototype and fix_kind == "ui":
        require_prototype_design(top)
    parent = branch_item(repo.current_branch(top), top)
    base = "HEAD" if parent and not _merged(main, parent[0]) else main
    state = {"kind": "fix", "why": why, "done_when": done, "base": git("rev-parse", base),
             "fix_kind": fix_kind or "mechanical"}
    if base == "HEAD":
        state["stacked_on"] = parent[0]
    if prototype:
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
    found = branch_item(branch, top) if branch.startswith(("fix/", "forge/", "task/")) else None
    if found is None:
        refuse(REFUSALS["not_fix"], branch=branch or "A detached HEAD")
    name, state = found
    state["allow_large"] = args.reason.strip()
    kind, limit = ("story part", "line limit") if "/" in name else ("fix", "fix limit")
    repo.commit_state(f"Allow the {kind} past the {limit}: {state['allow_large']}",
                      repo.write_state(name, state, top), top=top)
    print(f"{kind.capitalize()} {name} may now go over the {limit}.")


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


def require_active(item: str, top: Path | None = None) -> None:
    """A retained checkout cannot resume a dropped fix without an explicit restore."""
    from forge import nextstep

    if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item):
        top = top or repo.root()
        for branch in (f"fix/{item}", f"forge/{item}"):
            if nextstep.remote_state(top, item, branch).get("status") == "dropped":
                raise repo.Refused(f"Fix {item} is dropped.", f"forge fix drop {item} --undo")


def fix_drop(args: argparse.Namespace) -> None:
    from forge import close, codex, machine, story

    item = args.item
    command = f'forge fix drop {item} --undo' if args.undo else f'forge fix drop {item} --because "<reason>"'
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", item):
        raise repo.Refused("Give the name of a fix to drop or restore.", "forge next")
    if bool(args.undo) == bool(args.because) or (args.because is not None and not _one_line(args.because)):
        raise repo.Refused("Give one reason with --because, or use --undo to restore the fix.", command)
    top = repo.root()
    main = main_ref()
    branch, rel = f"fix/{item}", repo.state_path(item)
    remote = f"origin/{branch}"
    trees = story.worktrees(top)
    path = trees.get(branch)
    local = show(branch, rel, top)
    published = show(remote, rel, top)
    state = json.loads((local if local else published) or "{}")
    if not state or state.get("branch") != branch or state.get("kind") != "fix":
        raise repo.Refused(f"Fix {item} has not started.", "forge next")
    if path and git("status", "--porcelain", "--untracked-files=all", cwd=path):
        raise repo.Refused(f"Fix {item} has uncommitted changes. Commit or set them aside first.", command)
    root = machine.main_checkout(top)
    held = any(entry.get("item") == item and entry.get("repo_root") == root.as_posix()
               for entry in machine.entries())
    lock = codex._item_file(top, item, ".lock", "Build")
    if held or lock.exists() and codex._alive(codex._json(lock)) is not False:
        raise repo.Refused(f"A Forge run on this machine holds fix {item}. Wait for it to finish.", command)
    prs = json.loads(close._gh(top, "pr", "list", "--head", branch, "--state", "all",
                             "--json", "number,state"))
    if _merged(main, item, top) or any(pr.get("state") == "MERGED" for pr in prs):
        raise repo.Refused(f"Fix {item} is already merged. Start a new fix instead.",
                           'forge fix start "<why>" --done "<done when>"')
    if not args.undo:
        dependents = set()
        refs = git("for-each-ref", "--format=%(refname)", "refs/heads/fix/",
                   "refs/remotes/origin/fix/", cwd=top).splitlines()
        for ref in refs:
            name = ref.split("/fix/", 1)[1]
            # The published record wins over a stale local checkout after another machine drops it.
            text = show(f"origin/fix/{name}", repo.state_path(name), top) or show(ref, repo.state_path(name), top)
            other = json.loads(text or "{}")
            if (other.get("stacked_on") == item and other.get("status") != "dropped"
                    and not _merged(main, name, top)):
                dependents.add(name)
        if dependents:
            raise repo.Refused(f"Open fixes stacked on {item}: {', '.join(sorted(dependents))}. "
                               "Drop or finish them first.", "forge next")
    # Reconcile before writing the record; fast-forward only, so local work is never overwritten.
    if published and local and run("git", "merge-base", "--is-ancestor", remote, branch, cwd=top).returncode:
        if run("git", "merge-base", "--is-ancestor", branch, remote, cwd=top).returncode:
            raise repo.Refused(f"Local and remote work for {item} differ. Reconcile the branch first.", command)
    if args.undo and (json.loads(published or local or "{}").get("status") != "dropped"):
        raise repo.Refused(f"Fix {item} is not dropped.", "forge next")
    if path is None:
        path = _folder(f"fix-{item}")
        if local:
            git("worktree", "add", "-q", str(path), branch, cwd=top)
        else:
            git("worktree", "add", "-q", "-b", branch, str(path), remote, cwd=top)
    if published:
        git("merge", "--ff-only", "--no-overwrite-ignore", remote, cwd=path)
    state = repo.read_state(item, path) or {}
    if args.undo:
        dropped = state["drop"]
        if number := dropped.get("pull_request"):
            if any(pr.get("number") == number and pr.get("state") == "CLOSED" for pr in prs):
                close._gh(path, "pr", "reopen", str(number))
        previous = dropped["status"]
        state["status"] = "waiting for checks" if previous == "ready" else previous
        dropped["restored_at"] = repo.now()
        repo.add_step(state, "restore")
        repo.commit_state(f"Restore the fix: {state['why']}", repo.write_state(item, state, path), top=path)
        git("push", "-q", "--set-upstream", "origin", branch, cwd=path)
        print(f"Restored fix {item} in {path}.")
        next_command = "close" if previous in ("ready", "waiting for checks", "reviewing") else "work"
        print(f"Next: forge {next_command} {item}")
    else:
        git("push", "-q", "--set-upstream", "origin", branch, cwd=path)
        pr = next((pr for pr in prs if pr.get("state") == "OPEN"), None)
        if state.get("status") != "dropped":
            state["drop"] = {"because": args.because.strip(), "by": git("var", "GIT_AUTHOR_IDENT", cwd=path),
                             "at": repo.now(), "status": state.get("status", "started")}
            if pr:
                state["drop"]["pull_request"] = pr["number"]
            state["status"] = "dropped"
            repo.add_step(state, "drop")
            repo.commit_state(f"Drop the fix: {state['why']}", repo.write_state(item, state, path), top=path)
            git("push", "-q", "origin", branch, cwd=path)
        if pr:
            close._gh(path, "pr", "close", str(pr["number"]), "--comment", state["drop"]["because"])
        ignored = git("ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z", cwd=path)
        rebuildable = {".venv", "node_modules", ".pytest_cache", "__pycache__", "dist", "build"}
        kept = [name for name in ignored.split("\0") if name and not any(
            part in rebuildable and path.joinpath(*Path(name).parts[:index + 1]).is_dir()
            and not path.joinpath(*Path(name).parts[:index + 1]).is_symlink()
            for index, part in enumerate(Path(name).parts))]
        print(f"Dropped fix {item}. Its remote branch keeps the work.")
        if kept:
            print(f"Kept the worktree for ignored paths: {', '.join(kept)}")
        elif path.resolve() == root:
            print("Kept the main checkout. Its fix is still dropped.")
        else:
            git("worktree", "remove", "--force", str(path), cwd=root)
            git("branch", "-d", branch, cwd=root)
    (repo.forge_dir(top if top.exists() else root) / "prs-cache.json").unlink(missing_ok=True)


COMMANDS = [
    {"words": "assign", "run": "assign", "changes_state": True,
     "help": "Give a story or part to a developer by GitHub username",
     "args": [(('item',), {}), (('login',), {})], "position": 95,
     "listing": '| `forge assign <KEY or KEY/TASK> <login>` | Gives a story or part to a developer and publishes the plan |'},
    {"words": "task start", "run": "start", "changes_state": True,
     "help": "Start a task in its own branch and worktree",
     "args": [(('item',), {"metavar": "KEY/TASK"})], "position": 100,
     "listing": "| `forge task start <KEY>/<TASK>` | Starts a task in its own branch and worktree |"},
    {"words": "fix start", "run": "fix_start", "changes_state": True,
     "help": "Start a fix in its own branch and worktree, with a one-line why and done-when",
     "args": [(('why',), {}), (('--done',), {"required": True, "metavar": "DONE_WHEN"}),
              (('--kind',), {"choices": ["ui", "backend", "mechanical"],
                             "help": "the worker kind; required for prototype fixes"}),
              (('--slug',), {"metavar": "NAME", "help": "the fix's name, instead of one cut from the why"})],
     "position": 110,
     "listing": '| `forge fix start "<why>" --done "<done when>"` | Starts a small fix in its own branch and worktree (`--slug <name>` names it) |'},
    {"words": "fix drop", "run": "fix_drop", "changes_state": True,
     "help": "Drop a fix with a reason, or restore it with --undo",
     "args": [(("item",), {"metavar": "FIX"}), (("--because",), {"metavar": "REASON"}),
              (("--undo",), {"action": "store_true"})], "position": 115,
     "listing": '| `forge fix drop <fix> --because "<reason>"` / `--undo` | Drops a fix with your reason, or brings it back, keeping its remote branch |'},
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
