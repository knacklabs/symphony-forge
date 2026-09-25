"""forge-pr-check: the required pull request check, run from a checkout of the base branch.

Policy and config come from the base checkout. The pull request head is data only: its files are
read through git and never run, imported or checked out.
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from forge import repo, review

REFUSALS = {
    "usage": ("forge hook pr-check needs the pull request's --base, --head and --branch.",
              "forge hook pr-check --base <base commit> --head <head commit> --branch <branch>"),
    "not_started": ("Forge did not start {branch}: no task or fix at its head is on that branch.",
                    'forge fix start "<why>" --done "<done when>"'),
    "fix_line": ("The fix on {branch} has no {line} line.",
                 'forge fix start "<why>" --done "<done when>"'),
    "promote": ("The fix on {branch} {problem}, and has no allow-large reason.",
                'forge story new <KEY> --from-fix {fix} (or, with the human\'s permission, '
                'forge fix allow-large "<reason>")'),
    "not_reviewed": ("The committed review at the head of {branch} is {problem}.",
                     "forge close {item}"),
}
CODE_LIMIT = 5


def pr_check(args: argparse.Namespace) -> int:
    # The workflow runs: forge hook pr-check --base <sha> --head <sha> --branch <head branch>
    given = dict(zip(args.args[::2], args.args[1::2]))
    if len(args.args) != 6 or set(given) != {"--base", "--head", "--branch"}:
        repo.refuse(REFUSALS["usage"])
    base, head, branch = given["--base"], given["--head"], given["--branch"]
    top = repo.root()
    cfg = repo.config(top)  # the base checkout's forge.toml, never the head's
    item, state = _started(top, head, branch)
    changed = repo.git("diff", "--name-only", f"{base}...{head}", cwd=top).splitlines()
    if "/" not in item:
        missing = [line for line, key in (("Why:", "why"), ("Done when:", "done_when"))
                   if not str(state.get(key) or "").strip()]
        if missing:
            repo.refuse(REFUSALS["fix_line"], branch=branch, line=" or ".join(missing))
        problem = "" if state.get("allow_large") else promote_problem(changed, cfg["interfaces"])
        if problem:
            repo.refuse(REFUSALS["promote"], branch=branch, problem=problem, fix=item)
    try:
        story = importlib.import_module("forge.story")
    except ModuleNotFoundError as exc:
        if exc.name != "forge.story":
            raise
        # ponytail: STORY builds story.py in parallel; its story-doc checks run once it lands.
        story = None
    if story:
        story.check_pr_docs(top, head, changed)
    result = state.get("review")
    if not (isinstance(result, dict) and isinstance(result.get("findings"), list)
            and isinstance(result.get("dismissals"), list)):
        problem = "missing"
    elif not _on_branch(top, str(result.get("commit", "")), head):
        problem = "for a commit that isn't part of this branch"
    elif result.get("tree") != review.fingerprint(head, item, top, state):
        problem = "out of date: the product files or what the change must do changed after it"
    elif review.blocking(result):
        problem = "blocked by serious findings no one fixed or dismissed"
    else:
        print(f"forge-pr-check passed for {branch}.")
        return 0
    repo.refuse(REFUSALS["not_reviewed"], branch=branch, problem=problem, item=item)


def promote_problem(changed: list[str], interfaces: list[str]) -> str:
    """Why a fix must become a story, or "": it touches an interfaces path, or more than five code
    files. Markdown, .factory/ and plans/ never count."""
    code = [path for path in changed
            if not path.lower().endswith(".md") and not path.startswith(review.BOOKKEEPING)]
    for path in code:
        # "/" + path lets "**/routes/**" match a top-level routes/ folder too.
        if any(fnmatch(path, pattern) or fnmatch("/" + path, pattern) for pattern in interfaces):
            return f"changes the interface path {path}"
    if len(code) > CODE_LIMIT:
        return f"changes {len(code)} code files, over the limit of {CODE_LIMIT}"
    return ""


def _on_branch(top: Path, commit: str, head: str) -> bool:
    """The reviewed commit is the head or one of its ancestors. It is read from the head, so it
    must look like a commit id before it goes near git."""
    return bool(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit)) and repo.run(
        "git", "merge-base", "--is-ancestor", commit, head, cwd=top).returncode == 0


def _started(top: Path, head: str, branch: str) -> tuple[str, dict[str, Any]]:
    """The task or fix whose state at head names this branch."""
    # ponytail: reads every task and fix state at the head, one git call each; batch them
    # (git cat-file --batch) when a repo holds thousands.
    listing = repo.git("ls-tree", "-r", "-z", "--name-only", head, "--", ".factory/stories",
                       ".factory/fixes", cwd=top)
    for path in listing.split("\0"):
        match = re.fullmatch(r"\.factory/(?:stories/([^/]+)/tasks/([^/]+)|fixes/([^/]+))\.json",
                             path)
        if not match:
            continue
        try:
            state = json.loads(repo.git("show", f"{head}:{path}", cwd=top))
        except ValueError:
            continue
        if isinstance(state, dict) and state.get("branch") == branch:
            return (f"{match[1]}/{match[2]}" if match[1] else match[3]), state
    repo.refuse(REFUSALS["not_started"], branch=branch)
