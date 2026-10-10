"""forge init: set up a new repo in one first commit, or adopt a repo with history on a fix branch."""
from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, NoReturn

from forge import __version__, githooks, repo, story, sync

COMMANDS = [{
    # False: init checks the pin itself, after adoption lists a forge.toml Forge didn't write.
    "words": "init", "run": "init", "changes_state": False,
    "help": "Set up a new repo: forge.toml, the docs skeleton, the first commit, then sync",
    "args": [(("--test",), {"help": "a repo with history: the test command CI runs"}),
             (("--runner",), {"default": "ubuntu-latest",
                              "help": "GitHub Actions runner label (default: ubuntu-latest)"}),
             (("--checks",), {"action": "append", "metavar": "CHECK",
                              "help": "a repo with history: a check branch protection requires"}),
             (("--interfaces",), {"action": "append", "metavar": "GLOB",
                                  "help": "a repo with history: its route or migration folders"}),
             (("--approver",), {"help": "a repo with history: who approves stories"}),
             (("--merger",), {"help": "a repo with history: who merges pull requests"}),
             (("--never-touch",), {"action": "append", "metavar": "PATH",
                                   "help": "a repo with history: a path agents never change"})],
    "position": 10,
    "listing": "| `forge init` | Sets up a new repo: `forge.toml`, the docs skeleton, the first commit, then `forge sync` |",
}]

REFUSALS = {
    "answers": ("This repo already has commits, so forge init adopts it on a fix branch, and it "
                "needs the answers you confirmed: {missing}.",
                'forge init --test "<command>" --checks <check> --interfaces "<glob>" '
                '--approver "<who>" --merger "<who>" --never-touch "<path>"'),
    "not_current": ("This checkout isn't clean at {ref}, which forge init adopts, so it can't check "
                    "that tree here.", "commit or set aside your changes, git switch {default} && "
                    "git pull, then forge init again"),
    "adopting": ("fix/adopt-forge is already there, so Forge has started adopting this repo.",
                 "forge close adopt-forge"),
    "taken": ("forge init won't write over files that Forge didn't write: {paths}.",
              "move or rename those files, then forge init again"),
    "no_origin": ("This repo has no origin remote, so Forge can't push the first commit or protect "
                  "the default branch.", "gh repo create <name> --private --source . --remote origin"),
    "origin_repo": ("Forge cannot identify a GitHub repository from origin.", "git remote set-url origin <GitHub repository URL>"),
    "protect": ("Branch protection on {branch} was not set: {problem}.", "{command}"),
}

# Interface paths for the fix lane: API routes, the database schema and migrations, a CLI
# command table and the config schema.
INTERFACES = ["**/routes/**", "**/*.controller.*", "**/migrations/**", "**/schema.*",
              "**/*.schema.*", "**/cli.*"]
# ponytail: the stack is read from one marker file; add a row when a client brings another stack.
# Go needs -v to print a skipped test and its reason, which forge close shows the reviewer.
STACKS = [("pyproject.toml", "uv run pytest"), ("go.mod", "go test -v ./...")]
# Otherwise the smallest client stack (Node). Before the first story adds the app there is
# nothing to test, and the tests check passes; after that it runs the app's tests.
NODE_TEST = "[ ! -f package.json ] || (npm ci && npm test)"
# Implementation and cold-read models for each host; Autoreview owns its review defaults.
MODELS = """
[models.build.codex]
model = "gpt-6.1-sol"
effort = "medium"

[models.build.claude]
model = "claude-sonnet-5-5"
effort = "xhigh"

[models.fix.codex]
model = "gpt-6.1-sol"
effort = "medium"

[models.fix.claude]
model = "claude-sonnet-5-5"
effort = "xhigh"

[models.lite.codex]
model = "gpt-6.1-sol"
effort = "medium"
subagents = "gpt-6-luna"
subagent_effort = "max"

[models.lite.claude]
model = "claude-sonnet-5-5"
effort = "xhigh"

[models.explore.codex]
model = "gpt-6.1-sol"
effort = "medium"
subagents = "gpt-6-luna"
subagent_effort = "max"

[models.explore.claude]
model = "claude-haiku-5-5"
effort = "high"

[models.grill.codex]
model = "gpt-6.1-sol"
effort = "high"

[models.grill.claude]
model = "claude-opus-5-5"
effort = "high"

[models.design.claude]
model = "claude-sonnet-5-5"
effort = "xhigh"

[models.design.codex]
model = "gpt-6.1-sol"
effort = "high"

"""


ROADMAP = '{\n  "items": []\n}\n'
ADOPT_BRANCH, ADOPT_ITEM = "fix/adopt-forge", "adopt-forge"
ADOPT_WHY = "Adopt Forge in this repo, which already has history."
ADOPT_DONE = ("Forge runs this repo as a live app: forge.toml names its tests, checks and interface "
              "folders, and AGENTS.md keeps the team's lines and its house rules.")


def _settings(stage: str, test: str, checks: list[str], interfaces: list[str],
              merge: str = "", runner: str = "ubuntu-latest") -> str:
    return ("# Forge's settings. Your coding agent keeps this file: ask it to change a setting or "
            "upgrade Forge.\n"
            f'version = "v{__version__}"\nrepo = "client"\nstage = "{stage}"\n'
            + (f'merge = "{merge}"\n' if merge else "") + 'workers = "split"\n'
            f"test = {json.dumps(test)}\n"
            f"checks = {json.dumps(checks)}\n"
            f"runner = {json.dumps(runner)}\n"
            f"interfaces = {json.dumps(interfaces)}\n{MODELS}")


def _scaffold(top: Path, runner: str = "ubuntu-latest") -> dict[str, str]:
    """forge.toml, the docs skeleton and an empty roadmap: repo-relative path -> text."""
    skeleton = sync.TEMPLATES / "skeleton"
    test = next((command for marker, command in STACKS if (top / marker).is_file()), NODE_TEST)
    return {
        "forge.toml": _settings("prototype", test, ["tests", "forge-pr-check"], INTERFACES,
                                runner=runner),
        **{path.relative_to(skeleton).as_posix(): path.read_text(encoding="utf-8")
           for path in sorted(skeleton.rglob("*")) if path.is_file()},
        "plans/roadmap.json": ROADMAP,
    }


def protect(top: Path, branch: str, checks: list[str]) -> None:
    """Require pull requests, live checks and admin enforcement while keeping other rules."""
    origin = repo.git("remote", "get-url", "origin", cwd=top)
    # Local bare remotes are used by Forge's command tests; gh resolves their placeholders.
    match = re.fullmatch(r"(?:https?://github\.com/|ssh://git@(?:ssh\.)?github\.com(?::443)?/|"
                         r"git@github\.com:)([^/]+)/([^/]+?)(?:\.git)?", origin)
    if not match and not Path(origin).is_absolute():
        repo.refuse(REFUSALS["origin_repo"])
    endpoint = f"repos/{match[1]}/{match[2]}/branches/{branch}/protection" if match else (
        f"repos/{{owner}}/{{repo}}/branches/{branch}/protection")
    read = ["gh", "api", endpoint]
    done = repo.run(*read, cwd=top)
    if no_protection_plan(done):
        print(skipped(branch, checks))
        return
    try:
        current = json.loads(done.stdout) if done.returncode == 0 else {}
    except ValueError:
        current = None
    # GitHub answers 404 "Branch not protected" when there is no rule yet; anything else unread
    # would be overwritten blind, so it stops.
    if not isinstance(current, dict) or (
            done.returncode and "Branch not protected" not in done.stdout + done.stderr):
        _protect_failed(done, branch, read)
    body = _stronger(current, checks, _removed_workflow_checks(top))
    path = repo.forge_dir(top) / "branch-protection.json"
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    args = ["gh", "api", "--method", "PUT", endpoint, "--input", str(path)]
    done = repo.run(*args, cwd=top)
    if done.returncode:
        _protect_failed(done, branch, args)
    print(f"Branch protection is on for {branch}: changes arrive only through a pull request whose "
          f"{' and '.join(checks)} checks pass, and nobody can push to it directly."
          + (" Its other rules stay as they were." if current else ""))


def no_protection_plan(done: subprocess.CompletedProcess[str]) -> bool:
    """GitHub's answer when the repo's plan has no branch protection, as for a private repo on a
    free plan: 'Upgrade to GitHub Pro (or Team) or make this repository public'."""
    return done.returncode != 0 and "Upgrade to GitHub" in done.stdout + done.stderr


def skipped(branch: str, checks: list[str]) -> str:
    return (f"Branch protection on {branch} was skipped: this repository's GitHub plan doesn't "
            f"offer it. Forge's own close and merge still wait for the {' and '.join(checks)} "
            "checks.")


def _protect_failed(done: subprocess.CompletedProcess[str], branch: str, args: list[str]) -> NoReturn:
    said = (done.stderr.strip() or f"gh exited with code {done.returncode}").splitlines()[0]
    repo.refuse(REFUSALS["protect"], branch=branch, problem=said.rstrip("."), command=shlex.join(args))


def _removed_workflow_checks(top: Path) -> set[str]:
    """Job names removed in history, unless a workflow in this tree still produces them."""
    def jobs(source: str) -> set[str]:
        found: dict[str, str] = {}
        job_id = ""
        in_jobs = False
        for line in source.splitlines():
            if line == "jobs:":
                in_jobs = True
            elif in_jobs and line and not line[0].isspace() and not line.startswith("#"):
                in_jobs = False
            elif in_jobs:
                if job := re.match(r"^  ([\w-]+):\s*(?:#.*)?$", line):
                    job_id = job[1]
                    found[job_id] = job_id
                if job_id and (named := re.match(r"^    name:\s*([^#]+?)\s*(?:#.*)?$", line)):
                    found[job_id] = named[1].strip('"\'')
        return set(found.values())

    removed: set[str] = set()
    for commit in repo.git("log", "--format=%H", "--diff-filter=D", "HEAD", "--",
                           ".github/workflows", cwd=top).splitlines():
        for path in repo.git("diff-tree", "--no-commit-id", "--name-only", "-r", "-z",
                             "--diff-filter=D", commit, "--", ".github/workflows",
                             cwd=top).split("\0"):
            if path.endswith((".yml", ".yaml")):
                if (old := repo.run("git", "show", f"{commit}^:{path}", cwd=top)).returncode == 0:
                    removed.update(jobs(old.stdout))
    remaining = {name for path in (top / ".github/workflows").glob("*.y*ml")
                 for name in jobs(path.read_text(encoding="utf-8"))}
    return removed - remaining


def _stronger(current: dict[str, Any], checks: list[str], removed: set[str]) -> dict[str, Any]:
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
                for entry in kept if isinstance(entry, dict) and "context" in entry
                and (entry["context"] not in removed or entry["context"] in checks)]
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
    if repo.run("git", "remote", "get-url", "origin", cwd=top).returncode:
        repo.refuse(REFUSALS["no_origin"])
    if not shutil.which("gh"):
        repo.refuse(repo.REFUSALS["missing_tool"], tool="gh")
    if repo.run("git", "rev-parse", "--verify", "-q", "HEAD", cwd=top).returncode == 0:
        return _adopt(top, args)
    repo.check_pin(top)
    branch = repo.current_branch(top)
    scaffold = _scaffold(top, args.runner)
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


def _adopt(top: Path, args: argparse.Namespace) -> None:
    """Adopt a repo with history: everything is checked against the default branch as last
    fetched, which the checkout must be at, before anything changes; then one commit on
    fix/adopt-forge in its own worktree. The default branch changes only when its pull request
    merges."""
    missing = [f"--{name}" for name in ("test", "checks", "interfaces", "approver", "merger")
               if not getattr(args, name)]
    if missing:
        repo.refuse(REFUSALS["answers"], missing=", ".join(missing))
    ref, default = story.landed_ref(top), repo.default_branch(top)
    heads = repo.run("git", "rev-parse", "HEAD", f"{ref}^{{commit}}", cwd=top).stdout.split()
    if len(heads) != 2 or heads[0] != heads[1] or repo.git("status", "--porcelain", cwd=top):
        repo.refuse(REFUSALS["not_current"], ref=ref, default=default)
    if repo.run("git", "rev-parse", "-q", "--verify", f"refs/heads/{ADOPT_BRANCH}",
                cwd=top).returncode == 0:
        repo.refuse(REFUSALS["adopting"])
    # Forge's own check gates each pull request once Forge is on the default branch.
    checks = [*args.checks, *(["forge-pr-check"] if "forge-pr-check" not in args.checks else [])]
    toml = _settings("live", args.test, checks, args.interfaces, merge="human", runner=args.runner)
    cfg = repo._config_text(toml)  # pyright: ignore[reportPrivateUsage]
    # Files sync merges into keep the team's lines; any other file Forge writes whole, so one
    # already there with other text is the team's, and adoption stops before changing anything.
    merged = {*githooks.ships(top, cfg), *sync.ships(top, cfg)}
    wanted = {"forge.toml": toml, "plans/roadmap.json": ROADMAP, **sync.files(top, cfg),
              repo.state_path(ADOPT_ITEM): None}  # its state file is written later, never kept
    taken = sorted(rel for rel, text in wanted.items() if rel not in merged
                   and (top / rel).exists() and sync.read(top / rel) != text)
    if taken:
        repo.refuse(REFUSALS["taken"], paths=", ".join(taken))
    path = story.add_worktree(top, ADOPT_BRANCH, ref)
    sync.write_file(path, "forge.toml", toml)
    sync.write_file(path, "plans/roadmap.json", ROADMAP)
    never = ", ".join(args.never_touch or []) or "nothing named yet"
    rules = (f"## House rules\n\n- Approves stories: {args.approver}\n"
             f"- Merges pull requests: {args.merger}\n- Never touch: {never}\n")
    team = sync.read(path / "AGENTS.md")
    sync.write_file(path, "AGENTS.md", f"{team.rstrip()}\n\n{rules}" if team.strip() else rules)
    touched = {"forge.toml", "plans/roadmap.json", "AGENTS.md", *sync.write(path, cfg)}
    who = repo.git("var", "GIT_AUTHOR_IDENT", cwd=path).split("<")[0].strip()
    fix = {"kind": "adopt", "why": ADOPT_WHY, "done_when": ADOPT_DONE, "branch": ADOPT_BRANCH,
           "status": "started", "base": repo.git("rev-parse", ref, cwd=path), "touches": 0,
           "allow_large": f"Adopting Forge adds its settings, skills and hooks in one change; "
                          f"{who} allowed it by running forge init."}
    touched.add(repo.write_state(ADOPT_ITEM, repo.add_step(fix, "start"), path))
    # Exactly these paths, even ones the team's .gitignore matches.
    repo.git("add", "-f", "--", *sorted(touched), cwd=path)
    repo.git("commit", "-q", "-m", "Adopt Forge", cwd=path)
    sync.install_shims(path, cfg)
    print(f"Made {ADOPT_BRANCH} in {path} with one commit, not pushed yet: forge.toml marks this "
          "repo live with the tests, checks and interface folders you confirmed, AGENTS.md keeps "
          "your lines and adds the house rules, and the Forge skills and hooks are added. "
          f"{default} is unchanged until its pull request merges.")
    print(f"After that pull request merges, forge close {ADOPT_ITEM} turns on branch protection "
          f"for {default}, keeping its existing rules.")
    print(f"Next: your tests in {path}, then forge close {ADOPT_ITEM}")
