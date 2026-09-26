"""forge init: set up a new repo in one first commit, push it, then protect its default branch."""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, NoReturn

from forge import __version__, repo, sync

REFUSALS = {
    "has_commits": ("forge init sets up a new repo, and this one already has commits; a repo with "
                    "the copied-in Forge moves over with forge migrate.", "forge migrate"),
    "no_origin": ("This repo has no origin remote, so Forge can't push the first commit or protect "
                  "the default branch.", "gh repo create <name> --private --source . --remote origin"),
    "protect": ("Branch protection on {branch} was not set: {problem}.", "{command}"),
}

# Interface paths for the fix lane: API routes, the database schema and migrations, a CLI
# command table and the config schema.
INTERFACES = ["**/routes/**", "**/*.controller.*", "**/migrations/**", "**/schema.*",
              "**/*.schema.*", "**/cli.*"]
# ponytail: the stack is read from one marker file; add a row when a client brings another stack.
STACKS = [("pyproject.toml", "uv run pytest"), ("go.mod", "go test ./...")]
# Otherwise the smallest client stack (Node). Before the first story adds the app there is
# nothing to test, and the tests check passes; after that it runs the app's tests.
NODE_TEST = "[ ! -f package.json ] || (npm ci && npm test)"
# The model and effort each kind of work runs on; the review kind's model goes to Autoreview. The
# cold read (grill) runs on the family that isn't coordinating, so it has an entry for each.
MODELS = """
[models.build]
model = "opus"
effort = "high"

[models.fix]
model = "opus"
effort = "high"

[models.lite]
model = "sonnet"
effort = "medium"

[models.grill.codex]
model = "gpt-6-sol"
effort = "high"

[models.grill.claude]
model = "opus"
effort = "high"

[models.review]
model = "gpt-6-astra"
"""


def _scaffold(top: Path) -> dict[str, str]:
    """forge.toml, the docs skeleton and an empty roadmap: repo-relative path -> text."""
    skeleton = sync.TEMPLATES / "skeleton"
    test = next((command for marker, command in STACKS if (top / marker).is_file()), NODE_TEST)
    return {
        "forge.toml": (
            "# Forge's settings. Your coding agent keeps this file: ask it to change a setting or "
            "upgrade Forge.\n"
            f'version = "v{__version__}"\nrepo = "client"\nworkers = "claude"\n'
            f"test = {json.dumps(test)}\n"
            f"checks = {json.dumps(['tests', 'forge-pr-check'])}\n"
            f"interfaces = {json.dumps(INTERFACES)}\n{MODELS}"),
        **{path.relative_to(skeleton).as_posix(): path.read_text(encoding="utf-8")
           for path in sorted(skeleton.rglob("*")) if path.is_file()},
        "plans/roadmap.json": '{\n  "items": []\n}\n',
    }


def protect(top: Path, branch: str, checks: list[str]) -> None:
    """Allow changes to branch only through a pull request with these checks green, and say so.

    It never weakens a rule already there: it reads the branch's protection, adds the pull request
    requirement, these checks and admins included, and keeps everything else as it was.
    """
    endpoint = f"repos/{{owner}}/{{repo}}/branches/{branch}/protection"
    read = ["gh", "api", endpoint]
    done = repo.run(*read, cwd=top)
    try:
        current = json.loads(done.stdout) if done.returncode == 0 else {}
    except ValueError:
        current = None
    # GitHub answers 404 "Branch not protected" when there is no rule yet; anything else unread
    # would be overwritten blind, so it stops.
    if not isinstance(current, dict) or (
            done.returncode and "Branch not protected" not in done.stdout + done.stderr):
        _protect_failed(done, branch, read)
    body = _stronger(current, checks)
    path = repo.forge_dir(top) / "branch-protection.json"
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    args = ["gh", "api", "--method", "PUT", endpoint, "--input", str(path)]
    done = repo.run(*args, cwd=top)
    if done.returncode:
        _protect_failed(done, branch, args)
    print(f"Branch protection is on for {branch}: changes arrive only through a pull request whose "
          f"{' and '.join(checks)} checks pass, and nobody can push to it directly."
          + (" Its other rules stay as they were." if current else ""))


def _protect_failed(done: subprocess.CompletedProcess[str], branch: str, args: list[str]) -> NoReturn:
    said = (done.stderr.strip() or f"gh exited with code {done.returncode}").splitlines()[0]
    repo.refuse(REFUSALS["protect"], branch=branch, problem=said.rstrip("."), command=shlex.join(args))


def _stronger(current: dict[str, Any], checks: list[str]) -> dict[str, Any]:
    """The protection GitHub reported (its read shape), in the shape it takes, with Forge's rules
    added: a pull request, the named checks and admins included."""
    def on(block: Any) -> bool:
        return isinstance(block, dict) and block.get("enabled") is True

    def who(block: Any) -> dict[str, list[str]]:
        block = block if isinstance(block, dict) else {}
        return {kind: [entry[key] for entry in block.get(kind) or [] if key in entry]
                for kind, key in (("users", "login"), ("teams", "slug"), ("apps", "slug"))}

    status = current.get("required_status_checks") or {}
    # A check keeps the app it must come from; one named only by context (older rules) has none.
    kept = status.get("checks") or [{"context": name} for name in status.get("contexts") or []]
    required = [{"context": entry["context"], **({"app_id": entry["app_id"]}
                                                if isinstance(entry.get("app_id"), int) else {})}
                for entry in kept if isinstance(entry, dict) and "context" in entry]
    required += [{"context": name} for name in checks
                 if name not in {entry["context"] for entry in required}]
    reviews = current.get("required_pull_request_reviews") or {}
    pull = {"required_approving_review_count": reviews.get("required_approving_review_count", 0),
            **{key: reviews[key] for key in ("dismiss_stale_reviews", "require_code_owner_reviews",
                                              "require_last_push_approval") if key in reviews},
            **{key: who(reviews[key]) for key in ("dismissal_restrictions",
                                                   "bypass_pull_request_allowances")
               if key in reviews}}
    return {"required_status_checks": {"strict": status.get("strict") is True, "checks": required},
            "enforce_admins": True,  # nobody pushes directly, admins included
            "required_pull_request_reviews": pull,
            "restrictions": who(current["restrictions"]) if current.get("restrictions") else None,
            **{key: on(current[key]) for key in (
                "required_linear_history", "allow_force_pushes", "allow_deletions", "block_creations",
                "required_conversation_resolution", "lock_branch", "allow_fork_syncing")
               if key in current}}


def init(args: argparse.Namespace) -> None:
    top = repo.root()
    if repo.run("git", "rev-parse", "--verify", "-q", "HEAD", cwd=top).returncode == 0:
        repo.refuse(REFUSALS["has_commits"])
    if repo.run("git", "remote", "get-url", "origin", cwd=top).returncode:
        repo.refuse(REFUSALS["no_origin"])
    if not shutil.which("gh"):
        repo.refuse(repo.REFUSALS["missing_tool"], tool="gh")
    branch = repo.current_branch(top)
    scaffold = _scaffold(top)
    for rel, text in scaffold.items():
        if not (top / rel).exists():  # init never overwrites a file that is already there
            sync.write_file(top, rel, text)
    cfg = repo.config(top)
    sync.write(top, cfg)
    # The one first commit holds the scaffold and the sync output. The git hooks go in after it.
    repo.commit_state("Set up Forge", *scaffold, *sync.files(top, cfg), top=top)
    repo.git("push", "-q", "-u", "origin", branch, cwd=top)
    repo.git("remote", "set-head", "origin", branch, cwd=top)
    sync.install_shims(top, cfg)
    print(f"Set up Forge {cfg['version']} in one first commit on {branch}: forge.toml, the docs "
          "skeleton, and the adapters for Claude Code and Codex.")
    print(f"Pushed {branch} to origin and installed the git hooks that check each commit and push.")
    protect(top, branch, cfg["checks"])
    print("Next: forge next")
