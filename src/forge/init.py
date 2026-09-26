"""forge init: set up a new repo in one first commit, push it, then protect its default branch."""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
from pathlib import Path

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


def _scaffold(top: Path) -> dict[str, str]:
    """forge.toml, the docs skeleton and an empty roadmap: repo-relative path -> text."""
    skeleton = sync.TEMPLATES / "skeleton"
    test = next((command for marker, command in STACKS if (top / marker).is_file()), NODE_TEST)
    return {
        "forge.toml": (
            "# Forge's settings. Your coding agent keeps this file: ask it to change a setting or "
            "upgrade Forge.\n"
            f'version = "v{__version__}"\nrepo = "client"\nworkers = "claude"\nmodel = "opus"\n'
            f"test = {json.dumps(test)}\n"
            f"checks = {json.dumps(['tests', 'forge-pr-check'])}\n"
            f"interfaces = {json.dumps(INTERFACES)}\n"),
        **{path.relative_to(skeleton).as_posix(): path.read_text(encoding="utf-8")
           for path in sorted(skeleton.rglob("*")) if path.is_file()},
        "plans/roadmap.json": '{\n  "items": []\n}\n',
    }


def protect(top: Path, branch: str, checks: list[str]) -> None:
    """Allow changes to branch only through a pull request with these checks green, and say so."""
    body = {"required_status_checks": {"strict": False, "contexts": checks},
            "enforce_admins": True,  # nobody pushes directly, admins included
            "required_pull_request_reviews": {"required_approving_review_count": 0},
            "restrictions": None}
    path = repo.forge_dir(top) / "branch-protection.json"
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    args = ["gh", "api", "--method", "PUT", f"repos/{{owner}}/{{repo}}/branches/{branch}/protection",
            "--input", str(path)]
    done = repo.run(*args, cwd=top)
    if done.returncode:
        said = (done.stderr.strip() or f"gh exited with code {done.returncode}").splitlines()[0]
        repo.refuse(REFUSALS["protect"], branch=branch, problem=said.rstrip("."),
                    command=shlex.join(args))
    print(f"Branch protection is on for {branch}: changes arrive only through a pull request whose "
          f"{' and '.join(checks)} checks pass, and nobody can push to it directly.")


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
