"""The git hooks. pre-commit keeps commits on Forge's own branches and fixes small; pre-push keeps
the default branch pull-request-only and catches fix commits made with --no-verify."""
from __future__ import annotations

import argparse
import json
import sys
from fnmatch import fnmatchcase
from typing import Any

from forge import repo, task
from forge.repo import git, refuse, run

LIMIT = 5  # code files a fix may change before it has to become a story

REFUSALS = {
    "not_forge": ("{branch} was not started by Forge, so it has no story, task or fix.",
                  'forge fix start "<why>" --done "<done when>"'),
    "promote": ("Fix {fix} {problem}, so it has to become a story, unless the human allows it "
                "with forge fix allow-large.", "forge story new <KEY> --from-fix {fix}"),
    "push_default": ("{branch} changes only through a merged pull request, so this push is refused.",
                     "forge close <item>"),
}


def pre_commit(args: argparse.Namespace) -> None:
    top = repo.root()
    branch = repo.current_branch(top)
    if branch == repo.default_branch(top):
        refuse(repo.REFUSALS["default_branch"], branch=branch)
    found = task.branch_item(branch, top) if branch else None
    if found is None:
        refuse(REFUSALS["not_forge"], branch=branch or "A detached HEAD")
    item, state = found
    if branch.startswith(("fix/", "forge/")):
        # Finishing a merge: the default branch's changes coming in don't count against the fix.
        merging = ["MERGE_HEAD"] if run("git", "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0 else []
        _promote(item, state, repo.config(top)["interfaces"], "--cached", _base("HEAD", *merging))


def pre_push(args: argparse.Namespace) -> None:
    default = repo.default_branch()
    for line in sys.stdin.read().splitlines():
        _, sha, remote_ref = (line.split() + ["", "", ""])[:3]
        if remote_ref == f"refs/heads/{default}":
            refuse(REFUSALS["push_default"], branch=default)
        # The destination names the fix, whatever the source: a branch, a tag or a commit ID.
        kind, _, fix = remote_ref.removeprefix("refs/heads/").partition("/")
        if kind not in ("fix", "forge") or set(sha) == {"0"}:  # a deletion pushes no commits
            continue
        match = repo.ITEM.fullmatch(fix)
        state = task.show(sha, repo.state_path(fix)) if match and match["fix"] else None
        # The pushed commit's own state decides; without one there is no allow-large reason.
        _promote(fix, json.loads(state) if state else {}, repo.config()["interfaces"],
                 _base(sha), sha)


def _base(*tips: str) -> str:
    """Where a fix's own changes start: its merge base with the default branch."""
    default = repo.default_branch()
    remote = f"origin/{default}"
    main = remote if run("git", "rev-parse", "-q", "--verify", remote).returncode == 0 else default
    # With several tips, git takes the merge base with a merge of all of them.
    return git("merge-base", main, *tips)


def _promote(fix: str, state: dict[str, Any], interfaces: list[str], *diff: str) -> None:
    """Refuse a fix over the limit or touching an interface, unless the human allowed it."""
    if state.get("allow_large"):
        return
    changed = git("diff", "--name-only", "--no-renames", "-z", *diff).split("\0")
    # Markdown, state and planning documents never count.
    code = [path for path in changed if path and not (
        path.lower().endswith(".md") or path.startswith((".factory/", "plans/")))]
    # ponytail: "**/" also matches zero folders by trying the pattern without it.
    touched = [path for path in code if any(
        fnmatchcase(path, glob) or fnmatchcase(path, glob.replace("**/", "")) for glob in interfaces)]
    if touched:
        refuse(REFUSALS["promote"], fix=fix, problem=f"changes the interface {touched[0]}")
    if len(code) > LIMIT:
        refuse(REFUSALS["promote"], fix=fix,
               problem=f"changes {len(code)} code files, over the limit of {LIMIT}")
