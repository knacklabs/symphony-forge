"""forge migrate: move a client that copied Forge in (the factory/ layout) to v1 in one pull request.

Everything is worked out from the default branch as last fetched, which the checkout must be at,
before anything changes, and `--dry-run` prints that plan and stops. The run works in its own
worktree on forge/migrate-v1:
- it deletes the copied-in Forge's listed paths, except files that differ from the copied-in
  version (the Forge source at the commit constitution/VENDORED_FROM names), which move to
  .forge-migrate/kept/. .envrc is set aside only when it has lines besides the old Forge's, and
  its old verify commands become forge.toml's test;
- it deletes every old record under .factory/ and the old ledgers under plans/; git history
  keeps them;
- it moves gstack's office-hours design docs to docs/context/, deletes the rest of .gstack/, and
  takes the old Forge's gstack lines out of .gitignore and .gitattributes;
- each active plan approved on the default branch becomes a story doc whose approval carries
  over; a task whose old marker is on the default branch is merged, and a story whose every task
  is merged is finished. An unapproved plan, or an unfinished one whose story doc is malformed,
  becomes a draft in .forge-migrate/replan/;
- AGENTS.md becomes just the Forge block only when it is the old Forge's word for word, and
  CLAUDE.md loses its import of the deleted .claude/CLAUDE.md;
- it pins forge.toml to this Forge, runs forge sync, and makes one commit.
Its fix state (kind migrate) holds an allow-large reason naming who ran it, and the plan as notes
for the pull request. `forge close` turns on branch protection once that pull request merged.
With repo = "forge-source" it only converts plans and writes the adapters.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from forge import __version__, init, repo, story, sync

REFUSALS = {
    "dirty": ("The working tree has changes that aren't committed: {paths}.",
              "commit or drop them, then forge migrate --dry-run"),
    "not_current": ("This checkout isn't at {ref}, which forge migrate moves, so it can't check "
                    "that tree here.", "git switch {default} && git pull, then forge migrate"),
    "taken": ("{path} is already there, so forge migrate won't write over it.",
              "move {aside} aside, then forge migrate"),
    "no_layout": ("{ref} has no copied-in factory/ layout to move; a client from before it (the "
                  '.agents/ layout) moves with the "move vendored clients" story.', "forge next"),
    "in_flight": ("Work is still in flight in the copied-in Forge: {items}.",
                  "finish or drop each one with the copied-in ./forge, then forge migrate --dry-run"),
    "no_source": ("Forge can't read the copied-in version ({problem}), so it can't tell your "
                  "changes from its own.",
                  "check the network and constitution/VENDORED_FROM, then forge migrate --dry-run"),
    "link": ("{path} is a link, and forge migrate never follows one.",
             "remove that link, then forge migrate --dry-run"),
    "not_ours": ("forge/migrate-v1 holds work that forge migrate didn't make, so it won't start the "
                 "branch again.", "git branch -m forge/migrate-v1 <another name>, then forge migrate"),
    "unsaved": ("{path}, the folder of forge/migrate-v1, has changes that aren't committed, so "
                "forge migrate won't start that branch again.",
                "look at them in {path}; if none are yours, git worktree remove --force {path}, "
                "then forge migrate"),
}

BRANCH, ITEM, MESSAGE = "forge/migrate-v1", "migrate-v1", "Move to Forge v1"
MADE = "migrate-made"  # in .git/forge/: the one commit migrate made, so a rerun may replace it
SOURCE = "https://github.com/knacklabs/symphony-forge"
# The copied-in Forge: a file here that differs from the copied-in version is set aside.
VENDORED = ("factory", "forge", "forge.cmd", "harness.yaml", "harness", "install", "constitution",
            "WORKFLOW.md", "setup", "docs/FACTORY.md", "docs/QUALITY.md", "docs/ROLES.md",
            "docs/harness-philosophy.md", "docs/degraded-mode.md", "docs/windows.md",
            "docs/codex-factory.md", "docs/memory/factory-entry-contract.md", ".codex/agents",
            ".codex/explore.config.toml", ".codex/skills/forge", ".claude/skills/forge",
            ".claude/CLAUDE.md", ".envrc",
            *(f".github/workflows/{name}.yml" for name in (
                "factory-scaffold", "gardener", "harness-health", "roadmap-gate", "board-invariant",
                "pr-link", "pr-ticket-check")))
# Old Forge records: deleted, never set aside.
LEDGERS = ("plans/quickfixes", "plans/quickfixes.jsonl", "plans/lessons", "plans/lessons.jsonl",
           "plans/deferrals.md", "plans/review-briefs", "plans/codex-briefs")
# Written by the old vendoring itself, so they always differ from the source; not client work.
FORGE_MADE = ("constitution/VENDORED_FROM", "constitution/VENDOR_MANIFEST.json")
KEPT, REPLAN = ".forge-migrate/kept", ".forge-migrate/replan"
# A story doc section, and the old plan sections it comes from (the first one there wins).
SECTIONS = {"What changes for you": ("What changes for you", "Scope / Non-goals", "Scope"),
            "Why": ("What and why", "Why", "Problem"),
            "Done when": ("Done when", "Acceptance Criteria", "Acceptance criteria"),
            "Risks": ("Risks",)}
MISSING = "<Not in the old plan; write it.>"
FINISHED = "Finished before the move to the new Forge."
IMPORT = re.compile(r"^@\.claude/CLAUDE\.md[ \t]*(?:\r?\n|\Z)", re.M)  # the old Claude adapter
# The old Forge's .envrc lines: its comments word for word, its harness-only block and its
# exports. Any other line, a comment too, is the client's, so the file is set aside. Its verify
# commands, in this order, become test.
VERIFY = ("FACTORY_STRUCTURAL_CMD", "FACTORY_TYPECHECK_CMD", "FACTORY_TEST_CMD")
OLD_ENVRC = re.compile(r"[ \t]*(?:if \[ ! -f constitution/VENDORED_FROM \]; then|fi|"
                       rf"export (?:GSTACK_HOME|{'|'.join(VERIFY)})=.*)?")
OLD_COMMENTS = frozenset("""\
# Project-local gstack (loaded by direnv; run `direnv allow` once per machine).
# Design docs, decision store, and learnings land in <repo>/.gstack — committed
# and shared — instead of a personal ~/.gstack. Machine-local noise under
# .gstack/ is gitignored; JSONL stores union-merge via .gitattributes.
# The three phases verify.py runs. It REFUSES when these are unset rather than
# guessing a toolchain, so each repo must name its own commands.
#
# ONLY in the harness itself. This file is vendored verbatim into client repos,
# and factory/tests goes with it — so an unconditional export would make a
# client's verify run the HARNESS's gate tests and record green having tested
# none of their product. That is the exact failure the refusal exists to
# prevent. VENDORED_FROM is written into every scaffolded/upgraded target and
# never exists here, so it is the discriminator. Client repos: set your own
# three commands below this block.""".splitlines())
HARNESS_ONLY = re.compile(r"^[ \t]*if \[ ! -f constitution/VENDORED_FROM \].*?^[ \t]*fi[ \t]*$",
                          re.M | re.S)
# gstack's store, which the old Forge kept in the repo: only office-hours design docs stay.
DESIGN = re.compile(r"\.gstack/projects/[^/]+/[^/]*-design-[^/]*\.md")
GSTACK_LINES = {  # the old Forge's own gstack lines; the client's other gstack lines stay
    ".gitignore": re.compile(r"^# forge gstack: project-local store.*\n\.gstack/\*\r?\n"
                             r"!\.gstack/projects/\r?\n\.gstack/\*\*/brain-cache/\r?\n"
                             r"\.gstack/\*\*/timeline\.jsonl[ \t]*(?:\r?\n|\Z)", re.M),
    ".gitattributes": re.compile(r"^\.gstack/\*\*/\*\.jsonl merge=union[ \t]*(?:\r?\n|\Z)", re.M)}
HEADER = ["| " + " | ".join(story.COLUMNS) + " |", "|" + "---|" * len(story.COLUMNS)]
DOC = """# {title}

## What changes for you

{what}

## Why

{why}

## Done when

{done}

## Tasks

{table}

{moving}

## Risks

{risks}

## Notes

Converted from {old} by forge migrate.

{notes}
"""
WHY = "Move this repo from its copied-in Forge to the installed Forge v1."
DONE = ("Forge v1 runs this repo: forge doctor passes, every active plan is a story doc or a "
        "draft, and every Forge file you changed is set aside for you.")


def migrate(args: argparse.Namespace) -> int:
    top = repo.root()
    own = (top / "forge.toml").is_file() and repo.config(top)["repo"] == "forge-source"
    dirty = repo.run("git", "status", "--porcelain", cwd=top).stdout.splitlines()
    if dirty:
        repo.refuse(REFUSALS["dirty"], paths=", ".join(line[3:] for line in dirty[:5]))
    ref, default = story.landed_ref(top), repo.default_branch(top)
    # The checks below read this checkout; clean and at ref, it is the tree migrate moves.
    heads = repo.run("git", "rev-parse", "HEAD", f"{ref}^{{commit}}", cwd=top).stdout.split()
    if len(heads) != 2 or heads[0] != heads[1]:
        repo.refuse(REFUSALS["not_current"], ref=ref, default=default)
    if not own and repo.run("git", "cat-file", "-e", f"{ref}:factory", cwd=top).returncode:
        repo.refuse(REFUSALS["no_layout"], ref=ref)
    busy = _in_flight(top)
    if busy:
        repo.refuse(REFUSALS["in_flight"], items="; ".join(busy))
    plan = _plan(top, ref, own)
    # sync's own list of the adapters it will write (their text is not needed here).
    adapters = sync.files(top, {"version": f"v{__version__}", "test": plan["test"]})
    # Never through a link, even one inside the repo: the run works in another folder.
    for rel in [*_touched(plan), *adapters]:
        parts = Path(rel).parts
        link = next((Path(*parts[:n]).as_posix() for n in range(1, len(parts) + 1)
                     if (top / Path(*parts[:n])).is_symlink()), "")
        if link:
            repo.refuse(REFUSALS["link"], path=link)
    # A moved or written file never lands on anything there, or on another moved file, even by a
    # name that differs only in capitals: a disk may not tell those apart.
    there = {path.casefold() for rel in repo.git("ls-files", "-z", cwd=top).split("\0") if rel
             for path in (rel, *map(str, Path(rel).parents))}
    landed: dict[str, str] = {}
    for rel, dest in [*plan["moves"], *((entry["old"], entry["dest"])
                                        for entry in plan["stories"] if "dest" in entry)]:
        if dest.casefold() in landed or dest.casefold() in there or os.path.lexists(top / dest):
            first = landed.get(dest.casefold(), "")
            repo.refuse(REFUSALS["taken"], path=f"{dest} (from {first})" if first else dest,
                        aside=rel if first else ".forge-migrate/" if dest.startswith(KEPT) else dest)
        landed[dest.casefold()] = rel
    report = _report(plan, default)
    if args.dry_run:
        print(f"Nothing was changed. forge migrate would do this, on its own branch {BRANCH}:\n\n"
              f"{report}")
        return 0
    path = _fresh_branch(top, ref)
    _apply(top, path, plan, report)
    print(f"{report}\n\nMade {BRANCH} in {path} with one commit, not pushed yet. The git hooks "
          f"that check each commit and push are installed.\nNext: forge doctor and your tests in "
          f"{path}, then forge close {ITEM}")
    return 0


# --- the plan: computed from the default branch, before anything changes -------------------


def _plan(top: Path, ref: str, own: bool) -> dict[str, Any]:
    vendored = {} if own else _tree(top, ref, *VENDORED)
    records = {} if own else _tree(top, ref, ".factory", *LEDGERS)
    source = _source(top, ref) if vendored else {}
    envrc = (story.show(top, ref, ".envrc") or "") if vendored else ""
    ours = any(line.strip() not in OLD_COMMENTS and not OLD_ENVRC.fullmatch(line)
               for line in envrc.splitlines())
    kept = sorted(path for path, blob in vendored.items() if path not in FORGE_MADE
                  and (ours if path == ".envrc" else source.get(path) != blob))
    # Outside the harness-only block; the last export of each wins, as in the shell.
    said = dict(word.partition("=")[::2]
                for word in shlex.split(HARNESS_ONLY.sub("", envrc), comments=True))
    store = {} if own else _tree(top, ref, ".gstack")
    designs = [(path, f"docs/context/{Path(path).name}") for path in store if DESIGN.fullmatch(path)]
    texts = {} if own else {name: story.show(top, ref, name) or "" for name in GSTACK_LINES}
    edits = {name: GSTACK_LINES[name].sub("", text) for name, text in texts.items()
             if GSTACK_LINES[name].search(text)}
    left = {name: lines for name, text in texts.items()
            if (lines := [line for line in edits.get(name, text).splitlines() if "gstack" in line])}
    phases = [said[name] for name in VERIFY if said.get(name)]
    # ponytail: no shell parsing; a # or a line break could hide the phases after it, so none go.
    unsafe = any(re.search(r"[#\r\n]", phase) for phase in phases)
    # AGENTS.md is replaced only when it is the old Forge's word for word; else it is the client's.
    agents = _tree(top, ref, "AGENTS.md").get("AGENTS.md") if vendored else None
    return {"ref": ref, "own": own, "kept": kept, "stories": _stories(top, ref, own),
            "delete": sorted((set(vendored) - set(kept)) | set(records)
                             | (set(store) - {path for path, _ in designs})),
            "moves": [*((path, f"{KEPT}/{path}") for path in kept), *designs],  # (from, to)
            "gstack": len(store), "designs": len(designs), "gstack_edits": edits,
            "gstack_left": left,
            # A phase with its own && or || is grouped, so it fails as one step.
            "test": "" if unsafe else " && ".join(f"({phase})" if re.search(r"[;&|]", phase)
                                                  else phase for phase in phases),
            "unseeded": ", ".join(json.dumps(phase, ensure_ascii=False) for phase in phases)
                        if unsafe else "",
            "agents": "" if not agents else "replace" if agents == source.get("AGENTS.md") else "keep",
            "claude_import": ".claude/CLAUDE.md" in vendored
                             and bool(IMPORT.search(story.show(top, ref, "CLAUDE.md") or ""))}


def _touched(plan: dict[str, Any]) -> list[str]:
    """Every path the run removes, moves or writes, but the adapters sync.files lists."""
    written = [path for entry in plan["stories"] if "dest" in entry
               for path in (entry["old"], entry["dest"], *map(repo.state_path, entry["states"]))]
    return [*plan["delete"], *(path for move in plan["moves"] for path in move),
            *plan["gstack_edits"], *written, "forge.toml", repo.state_path(ITEM)]


def _tree(top: Path, ref: str, *paths: str) -> dict[str, str]:
    """Each file under these paths at ref, with its blob id."""
    listing = repo.git("ls-tree", "-r", "-z", ref, "--", *paths, cwd=top)
    return {entry.partition("\t")[2]: entry.split()[2] for entry in listing.split("\0")
            if entry and entry.split()[1] == "blob"}


def _names(top: Path, ref: str, folder: str) -> list[str]:
    return repo.git("ls-tree", "--name-only", ref, "--", folder, cwd=top).splitlines()


def _source(top: Path, ref: str) -> dict[str, str]:
    """The copied-in version of the listed paths: the Forge source at VENDORED_FROM's commit."""
    commit = re.search(r"\b[0-9a-f]{40}\b", story.show(top, ref, FORGE_MADE[0]) or "")
    if not commit:
        repo.refuse(REFUSALS["no_source"], problem=f"{FORGE_MADE[0]} names no copied-in commit")
    url = os.environ.get("FORGE_SOURCE_URL", SOURCE)  # ponytail: the tests' seam, like FORGE_NOW
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        repo.git("init", "-q", "--bare", tmp)
        # Only the commit and its trees: blob ids are enough to compare files.
        done = repo.run("git", "fetch", "-q", "--depth", "1", "--filter=blob:none", url,
                        commit[0], cwd=tmp)
        if done.returncode:
            said = (done.stderr.strip().splitlines() or [f"exit code {done.returncode}"])[-1]
            repo.refuse(REFUSALS["no_source"], problem=f"fetching it from {url} failed: {said}")
        return _tree(Path(tmp), "FETCH_HEAD", *VENDORED, "AGENTS.md")


def _in_flight(top: Path) -> list[str]:
    """Old Forge work not finished in any checkout of this repo: an open window, an active stage."""
    found = set()
    for path in {top, *story.worktrees(top).values()}:
        factory = path / ".factory"
        window = story.json_of(sync.read(factory / "quickfix.json"))
        if window:
            found.add(f"the {window.get('profile', 'quickfix')} window {window.get('id', '')} "
                      f"in {path}")
        for file in (factory / "stages.json", *factory.glob("stories/*/stages.json"),
                     *factory.glob("stories/*/stages/*.json")):
            data = story.json_of(sync.read(file))
            found.update(f"the stage {stage.get('id')} in {path}"
                         for stage in data.get("stages", [data])
                         if isinstance(stage, dict) and stage.get("status") == "active")
    return sorted(found)


def _stories(top: Path, ref: str, own: bool) -> list[dict[str, Any]]:
    """Each active plan, converted; one that can't be keeps its place and says why."""
    found: list[dict[str, Any]] = []
    # Lower-cased: a disk that ignores capitals would write plans/CACHE-BUG.md over
    # plans/cache-bug.md. In Forge's own repo the old records stay, so an old
    # .factory/stories/cache-bug/ would clash with the new CACHE-BUG/ the same way.
    taken = {name.lower() for name in [*_names(top, ref, "plans/"),
                                       *(_names(top, ref, ".factory/stories/") if own else [])]}
    for rel in _names(top, ref, "plans/active/"):
        if not rel.endswith(".md"):
            continue
        # ponytail: STORY's frontmatter reader; the plan's decision list isn't carried over.
        fields, body = story._record(story.show(top, ref, rel) or "")  # pyright: ignore[reportPrivateUsage]
        old = fields.get("story") or fields.get("issue") or Path(rel).stem
        key = old.upper()
        clash = next((path for path in (f"plans/{key}.md", f".factory/stories/{key}")
                      if path.lower() in taken and path != f".factory/stories/{old}"), "")
        problem = (f"{old!r} can't be a story key" if not story.KEY.fullmatch(key)
                   else f"another plan already becomes {key}" if any(
                       entry.get("key") == key for entry in found)
                   else f"{clash} is taken by a name that differs only in capitals" if clash
                   else "")
        if problem:
            found.append({"skip": f"{rel} stays as it is: {problem}"})
            continue
        found.append(_convert(top, ref, rel, old, key, fields, story.sections(body)))
    return found


def _convert(top: Path, ref: str, rel: str, old: str, key: str, fields: dict[str, str],
             found: dict[str, str]) -> dict[str, Any]:
    picked = {name: next((heading for heading in olds if heading in found), None)
              for name, olds in SECTIONS.items()}
    text = {name: found[heading].strip() if heading else "" for name, heading in picked.items()}
    done = _numbered(text["Done when"])
    parts = re.split(r"^(\d+)\.[ \t]+", done, flags=re.M)
    items = {int(n): _flat(block) for n, block in zip(parts[1::2], parts[2::2])}
    saved, title = fields.get("saved") or repo.now(), fields.get("title") or key
    rows, states, needs, waiting = _tasks(top, ref, old, key, items, saved)
    moving = re.search(r"^New moving parts:.*(?:\n[ \t]*[-*].*)*", "\n".join(found.values()), re.M)
    notes = [f"### {heading}\n\n{body.strip()}" for heading, body in found.items()
             if heading not in picked.values() and body.strip()]
    doc = DOC.format(title=title, what=text["What changes for you"] or MISSING,
                     why=text["Why"] or MISSING, done=done or MISSING,
                     table="\n".join([*HEADER, *rows]), risks=text["Risks"] or "Risks: none",
                     moving=moving[0] if moving else "New moving parts: none named in the old plan",
                     old=rel, notes="\n\n".join(notes))
    lost = [name for name in ("What changes for you", "Done when") if not text[name]]
    status, where = fields.get("status", ""), ref.removeprefix("origin/")
    why_not = (f'its plan on {where} says "{status or "nothing"}", not "approved"'
               if status != "approved" else
               f'the old plan has no "{lost[0]}" section to approve' if lost else "")
    shipped = bool(states) and len(states) == len(rows)  # every part shipped before the move
    if not why_not:
        try:
            story.parse(doc)
        except ValueError as exc:
            if not needs:
                needs.append(str(exc))
            if not shipped:  # a doc that is malformed isn't approved; a finished story stays done
                why_not = f"the story doc it becomes is malformed: {exc}"
    entry = {"key": key, "title": title, "old": rel, "why_not": why_not, "needs": needs,
             "waiting": waiting, "done": len(states), "total": len(rows), "outcome": ""}
    if why_not:
        return {**entry, "dest": f"{REPLAN}/{key}.md", "text": doc, "states": {}}
    approval = {"by": "carried over from the copied-in Forge", "at": saved,
                "hash": story.approval_hash(doc)}
    state = {"title": title, "doc": f"plans/{key}.md", "status": "approved", "touches": 0,
             "approval": approval, "steps": [{"step": "approved", "at": saved}]}
    if shipped:  # it is finished
        merged = {item.partition("/")[2]: data["steps"][0]["at"] for item, data in states.items()}
        said = story.json_of(story.show(top, ref, f".factory/stories/{old}/outcome.json")).get("outcome")
        entry["outcome"] = _flat(said) if isinstance(said, str) and said.strip() else FINISHED
        state.update(status="done", outcome=entry["outcome"], merged=merged,
                     finished=max(merged.values()))
        state["steps"].append({"step": "done", "at": state["finished"]})
    return {**entry, "dest": f"plans/{key}.md", "text": doc, "states": {key: state, **states}}


def _tasks(top: Path, ref: str, old: str, key: str, items: dict[int, str],
           saved: str) -> tuple[list[str], dict[str, Any], list[str], list[str]]:
    """The old decomposition as Tasks rows, the merged tasks' states, what a human must fix in
    the rows, and the rows not done yet."""
    base = f".factory/stories/{old}"
    decomposition = story.json_of(story.show(top, ref, f"{base}/decomposition.json"))
    tasks = [task for task in decomposition.get("tasks") or []
             if isinstance(task, dict) and isinstance(task.get("id"), str)]
    ids = {task["id"]: re.sub(r"[^A-Z0-9]+", "-", task["id"].removeprefix(f"{old}-").upper())
           .strip("-") or "T" for task in tasks}
    # A story shipped whole in one pull request (the older layout) marked the story, not a task.
    shipped = f"{base}/shipped.json"
    shipped = shipped if story.show(top, ref, shipped) is not None else ""
    rows: list[str] = []
    states: dict[str, Any] = {}
    needs = [] if tasks else ["the old plan has no tasks to carry over"]
    waiting: list[str] = []
    for task in tasks:
        tid, marker = ids[task["id"]], f"{base}/tasks/{task['id']}/pr-ready.json"
        done = marker if story.show(top, ref, marker) is not None else shipped
        said = [str(text) for text in task.get("acceptance_criteria") or []] + [
            str(contract.get("statement", "")) for contract in task.get("plan_contracts") or []
            if isinstance(contract, dict)]
        covers = [n for n, item in items.items() if any(_flat(s) and _flat(s) in item for s in said)]
        scope = [str(path) for path in task.get("write_scope") or []]
        tests = list(dict.fromkeys(str(test.get("path") if isinstance(test, dict) else test)
                                   for test in task.get("required_tests") or []
                                   if (test.get("path") if isinstance(test, dict) else test)))
        after = [ids[dep] for dep in task.get("depends_on") or task.get("dependencies") or []
                 if dep in ids]
        row = "| " + " | ".join(_cell(cell) for cell in (
            tid, task.get("title", ""), task.get("objective", ""), ", ".join(map(str, covers)),
            ", ".join(f"`{path}`" for path in scope), ", ".join(f"`{path}`" for path in tests),
            ", ".join(after) or "none", "yes" if task.get("user_facing") else "no")) + " |"
        rows.append(row)
        problems = ["no Scope"] * (not scope) + ["covers no Done-when item"] * (not covers and not done)
        if problems:
            needs.append(f"{tid}: {' and '.join(problems)}")
        if done:
            at = story.merged_at(top, ref, done) or saved
            states[f"{key}/{tid}"] = {"status": "merged", "branch": f"task/{key}-{tid}",
                                      "touches": 0, "steps": [{"step": "merged", "at": at}]}
        else:
            waiting.append(row)
    return rows, states, needs, waiting


def _numbered(text: str) -> str:
    """Done-when items, word for word, as the numbered list a story doc needs."""
    if re.search(r"^\d+\.[ \t]", text, re.M):
        return text
    count = iter(range(1, 10_000))
    return re.sub(r"^[-*][ \t]+", lambda _: f"{next(count)}. ", text, flags=re.M)


def _flat(text: str) -> str:
    return " ".join(text.split())


def _cell(value: object) -> str:
    return _flat(str(value)).replace("|", "/")


def _files(count: int) -> str:
    return f"{count:,} file{'s' * (count != 1)}"


def _story_line(entry: dict[str, Any], default: str) -> str:
    if entry["why_not"]:
        return (f"not carried over, because {entry['why_not']}. Its draft is {entry['dest']}; "
                f"re-plan it with forge story new {entry['key']}.")
    if entry["outcome"]:
        return (f"its approval on {default} carries over, and it is finished: every part was "
                f"done before the move. Outcome: {entry['outcome']}")
    return (f"its approval on {default} carries over; {entry['done']} of {entry['total']} parts "
            "done.")


def _report(plan: dict[str, Any], default: str) -> str:
    """The plan in plain English: what --dry-run prints, and the notes of the pull request."""
    lines: list[str] = []
    if plan["own"]:
        lines.append('This is Forge\'s own repo (repo = "forge-source"), so nothing is deleted.')
    else:
        lines.append("Deletes the copied-in Forge, these paths and nothing else (git history "
                     "keeps them):")
        for listed in VENDORED:
            count = sum(1 for path in plan["delete"]
                        if path == listed or path.startswith(listed + "/"))
            if count:
                lines.append(f"- {listed}" if listed in plan["delete"]
                             else f"- {listed}/ ({_files(count)})")
        records = sum(1 for path in plan["delete"] if path.startswith(".factory/"))
        ledgers = sum(1 for path in plan["delete"] if path.startswith("plans/"))
        lines += [f"Deletes {records:,} old Forge records under .factory/; git history keeps them.",
                  f"Deletes {ledgers:,} old ledger records under plans/ (quickfixes, lessons, "
                  "deferrals and briefs); git history keeps them."]
        if plan["gstack"]:
            designs = plan["designs"]
            lines.append(f"Keeps {designs} office-hours design doc{'s' * (designs != 1)} in "
                         "docs/context/; deletes the rest of gstack's store (.gstack/, "
                         f"{_files(plan['gstack'] - designs)}); git history keeps them.")
        lines += [f"Needs you in {name}: these gstack lines are yours, so they stay; take them out "
                  f"once nothing uses them: {', '.join(left)}"
                  for name, left in plan["gstack_left"].items()]
        if plan["kept"]:
            lines.append(f"Sets aside {_files(len(plan['kept']))} that differ from the copied-in "
                         f"Forge, in {KEPT}/, for you to decide on:")
            lines += [f"- {path}" for path in plan["kept"]]
            if ".envrc" in plan["kept"]:
                lines.append(".envrc has lines of your own besides the old Forge's, so it is set "
                             "aside, not deleted.")
        else:
            lines.append("Sets nothing aside: every copied-in Forge file is as it was copied in.")
    count = sum(1 for entry in plan["stories"] if "key" in entry)
    lines.append(f"Converts {count} active plan{'s' * (count != 1)} into story docs:")
    for entry in plan["stories"]:
        if "skip" in entry:
            lines.append(f"- {entry['skip']}")
            continue
        lines.append(f"- {entry['title']} ({entry['key']}): {_story_line(entry, default)}")
        if entry["waiting"]:
            lines += ["  Parts not done yet:", *(f"  {row}" for row in [*HEADER, *entry["waiting"]])]
        if entry["needs"]:
            lines.append(f"  Needs you in {entry['dest']}: {'; '.join(entry['needs'])}.")
    if plan["own"]:
        lines.append("Writes the adapters for Claude Code and Codex with forge sync.")
    else:
        if plan["agents"] == "replace":
            lines.append("Replaces AGENTS.md, which is the old Forge's word for word, with the "
                         "Forge block.")
        elif plan["agents"] == "keep":
            lines.append("Needs you in AGENTS.md: it differs from the old Forge's, so its text "
                         "stays above the Forge block; take the old Forge instructions out of it.")
        if plan["claude_import"]:
            lines.append("Drops CLAUDE.md's import of .claude/CLAUDE.md, the old Claude adapter.")
        if plan["test"]:
            lines.append(f"Moves the old verify commands from .envrc into forge.toml's test: "
                         f"{plan['test']}")
        if plan["unseeded"]:
            lines.append("Couldn't carry your old verify commands into forge.toml's test "
                         f"automatically: {plan['unseeded']}. Ask your agent to set test.")
        lines += [f"Writes forge.toml pinned to Forge v{__version__}, and the adapters for Claude "
                  "Code and Codex with forge sync.",
                  f"After this pull request merges, forge close {ITEM} turns on branch protection "
                  f"for {default}: changes arrive only through a pull request whose tests and "
                  "forge-pr-check checks pass, and nobody can push to it directly."]
    return "\n".join(lines)


# --- the run: its own branch and worktree, one commit ---------------------------------------


def _fresh_branch(top: Path, ref: str) -> Path:
    """forge/migrate-v1 in its own worktree, from ref. A branch holding nothing past ref but the
    commit migrate recorded making, in a clean worktree, starts again; anything else stops it."""
    repo.git("worktree", "prune", cwd=top)
    if repo.run("git", "rev-parse", "-q", "--verify", f"refs/heads/{BRANCH}", cwd=top).returncode == 0:
        made = repo.git("rev-list", f"{ref}..{BRANCH}", cwd=top).split()
        path = story.worktrees(top).get(BRANCH)
        if made and made != [sync.read(repo.forge_dir(top) / MADE).strip()]:
            repo.refuse(REFUSALS["not_ours"])
        # ponytail: any uncommitted change stops it, even a stopped run's own; a human looks first.
        if path is not None and repo.git("status", "--porcelain", "--ignored", cwd=path):
            repo.refuse(REFUSALS["unsaved"], path=path)
        if path is not None:
            repo.git("worktree", "remove", "--force", str(path), cwd=top)
        repo.git("branch", "-D", BRANCH, cwd=top)
    return story.add_worktree(top, BRANCH, ref)


def _apply(top: Path, path: Path, plan: dict[str, Any], report: str) -> None:
    touched = [*plan["delete"], *(rel for rel, _ in plan["moves"])]
    for rel, dest in plan["moves"]:
        (path / dest).parent.mkdir(parents=True, exist_ok=True)
        os.replace(path / rel, path / dest)
        touched.append(dest)
    for rel in plan["delete"]:
        (path / rel).unlink(missing_ok=True)
    # Emptied folders go too: on a disk that ignores capitals an old .factory/stories/cache-bug/
    # would swallow the new CACHE-BUG/ state.
    for folder in sorted({(path / rel).parent for rel in touched},
                         key=lambda folder: len(folder.parts), reverse=True):
        with contextlib.suppress(OSError):
            os.removedirs(folder)
    for entry in plan["stories"]:
        if "dest" not in entry:
            continue
        if not plan["own"]:  # Forge's own repo keeps the old plans until the switch
            (path / entry["old"]).unlink()
            touched.append(entry["old"])
        sync.write_file(path, entry["dest"], entry["text"])
        touched += [entry["dest"], *(repo.write_state(item, data, path)
                                     for item, data in entry["states"].items())]
    toml = (sync.read(top / "forge.toml") if plan["own"]
            else init._scaffold(path)["forge.toml"])  # pyright: ignore[reportPrivateUsage]
    if plan["test"]:  # the old verify commands, not the stack's default
        toml = re.sub(r"^test = .*$", lambda _: f"test = {json.dumps(plan['test'])}", toml,
                      count=1, flags=re.M)
    sync.write_file(path, "forge.toml", toml)
    touched.append("forge.toml")
    if plan["agents"] == "replace":  # sync then writes only the Forge block
        sync.write_file(path, "AGENTS.md", "")
        touched.append("AGENTS.md")
    if plan["claude_import"]:
        sync.write_file(path, "CLAUDE.md", IMPORT.sub("", sync.read(path / "CLAUDE.md")))
        touched.append("CLAUDE.md")
    for name, text in plan["gstack_edits"].items():
        sync.write_file(path, name, text)
        touched.append(name)
    cfg = repo.config(path)
    touched += sync.write(path, cfg)
    who = repo.git("var", "GIT_AUTHOR_IDENT", cwd=path).split("<")[0].strip()
    fix = {"kind": "migrate", "why": WHY, "done_when": DONE, "branch": BRANCH, "status": "started",
           "allow_large": f"Moving to Forge v1 replaces the copied-in Forge in one change; {who} "
                          "allowed it by running forge migrate.",
           "base": repo.git("rev-parse", plan["ref"], cwd=path), "touches": 0, "notes": report}
    touched.append(repo.write_state(ITEM, repo.add_step(fix, "start"), path))
    # Exactly these paths, even ones the client's .gitignore matches; nothing else in the folder.
    done = repo.run("git", "--literal-pathspecs", "add", "-A", "-f", "--pathspec-from-file=-",
                    "--pathspec-file-nul", cwd=path, input="\0".join(touched))
    # A name that differs only in capitals can make git skip a file without a word: never commit
    # the move without every file it wrote.
    index = set(repo.git("ls-files", "-z", cwd=path).split("\0"))
    lost = next((rel for rel in touched if (path / rel).exists() and rel not in index), "")
    if done.returncode or lost:
        raise subprocess.CalledProcessError(done.returncode or 1, ["git", "add"], done.stdout,
                                            done.stderr or f"git didn't take in {lost}")
    repo.git("commit", "-q", "-m", MESSAGE, cwd=path)
    (repo.forge_dir(path) / MADE).write_text(repo.git("rev-parse", "HEAD", cwd=path) + "\n",
                                             encoding="utf-8")
    sync.install_shims(path, cfg)
