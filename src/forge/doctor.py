"""forge doctor: tools, the pins (Forge's and the Autoreview helper's), the git hooks, the host
hooks, adapter drift, CI and, for Codex workers, the Codex SDK and the project's trust; a row per
problem. With Codex workers, or under Claude Code with Codex installed, whose cold read runs on
Codex, it checks the SDK. Whatever the workers, it stops the Codex processes a crashed forge work
or read left, never a running one's. It also finds the folders of finished work.

--fix repairs what it safely can, in this order: it installs a newer pinned Forge and runs doctor
again with it, then installs the Codex SDK, puts back the git hooks, removes the folders of
finished work and brings the files forge sync writes up to date: in doctor's own fix on the
default branch, in place elsewhere, never over a change made by hand. Each repair prints a
"- Fixed:" line."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Any

from forge import __version__, codex, init, repo, review, story, sync, task

COMMANDS = [{
    "words": "doctor", "run": "doctor", "changes_state": False,
    "help": "Check tools, versions, hooks, adapter drift and the named CI checks",
    "args": [(('--fix',), {"action": "store_true", "help":
              "repair what doctor safely can: the pinned Forge, the Codex SDK, the git hooks, "
              "the folders of finished work and the files forge sync writes"})],
    "position": 30,
    "listing": "| `forge doctor` | Checks tools, versions, hooks, generated-file drift and CI; one row per problem, each with a fix; `--fix` repairs what it safely can |",
}]

REFUSALS = {
    "problems": ("forge doctor found {count} problem(s); each row above gives its fix.",
                 "forge doctor"),
}

# How to install each tool doctor looks for: git, gh, uv and, for Claude workers, Claude Code.
INSTALL = {
    "git": "install git from https://git-scm.com/downloads",
    "gh": "install gh from https://cli.github.com",
    "uv": "curl -LsSf https://astral.sh/uv/install.sh | sh",
    "claude": "npm install -g @anthropic-ai/claude-code",
    "impeccable": "npx skills add pbakaus/impeccable -g",
    "emil-design-eng": "install emil-design-eng where the worker reads skills",
    "autoreview": (f"install skills/autoreview from https://github.com/openclaw/agent-skills at "
                   f"{review.AUTOREVIEW_PIN} into {review.HELPERS[0].parents[1]} or "
                   f"{review.HELPERS[1].parents[1]}"),
}

# Folders the tools make again, which a finished worktree may hold besides uv.lock.
CACHES = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
REPAIR = "forge doctor --fix"
# Doctor's own fix, which brings the files forge sync writes up to date on the default branch.
WHY = "Bring the files Forge writes for Claude Code and Codex up to date"
DONE = "The files match what forge sync writes for the pinned Forge"
HAND = "move your change out of this file, since forge sync rewrites it, then forge doctor --fix"

# A harmless payload per hook event, so each host hook runs without changing anything.
SAMPLES = {
    "SessionStart": {"source": "startup"},
    "PreToolUse": {"tool_name": "Bash", "tool_input": {"command": "git status"}},
    "PostToolUse": {"tool_name": "forge-doctor", "tool_input": {}, "tool_response": {}},
}

BARE_PATH = "/usr/bin:/bin"


def _forge_hooks(text: str) -> list[tuple[str, str]]:
    """(event, command) for each Forge hook in a host's hook file. A broken file shows as drift."""
    try:
        hooks = json.loads(text or "{}").get("hooks", {})
        return [(event, hook["command"]) for event, groups in hooks.items() for group in groups
                for hook in group.get("hooks", []) if sync.FORGE_COMMAND.search(hook.get("command", ""))]
    except (ValueError, AttributeError, TypeError, KeyError):
        return []


def _codex_trusts(top: Path, config: Path) -> bool:
    """Whether the user's Codex config trusts this checkout or its main repo."""
    common = Path(repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=top))
    roots = {top.resolve(), common.resolve().parent}
    try:
        projects = tomllib.loads(sync.read(config)).get("projects", {})
        return any(Path(path).resolve() in roots and project.get("trust_level") == "trusted"
                   for path, project in projects.items())
    except (tomllib.TOMLDecodeError, AttributeError):
        return False


def _newer(version: str) -> bool:
    """The version is a release newer than the installed Forge, by its three numbers."""
    release, installed = (re.match(r"v?(\d+)\.(\d+)\.(\d+)", v) for v in (version, __version__))
    return bool(release and installed and
                tuple(map(int, release.groups())) > tuple(map(int, installed.groups())))


def _last(done: subprocess.CompletedProcess[str]) -> str:
    said = (done.stderr.strip() or done.stdout.strip() or f"exit code {done.returncode}")
    return said.splitlines()[-1]


def _kept(line: str) -> bool:
    """A git status line a finished worktree may hold: the root uv.lock, or an ignored cache."""
    code, entry = line[:2], line[3:]
    return entry == "uv.lock" or (code == "!!" and entry.endswith("/")
                                  and Path(entry).name in CACHES)


def _finished(top: Path, main: Path) -> list[tuple[Path, str, str]]:
    """(folder, branch, "merged" or "closed") for each worktree whose work is finished: GitHub
    has a merged or closed pull request at its branch's head and none open, and the folder holds
    nothing else."""
    if not shutil.which("gh"):
        return []
    found = []
    for branch, path in story.worktrees(top).items():
        if (not branch.startswith(("story/", "task/", "fix/", "forge/"))
                or path.resolve() in (main, top.resolve()) or (path / ".gitmodules").exists()):
            continue
        done = repo.run("gh", "pr", "list", "--head", branch, "--state", "all", "--limit", "100",
                        "--json", "headRefOid,state", cwd=top)
        try:
            prs = json.loads(done.stdout) if done.returncode == 0 else None
        except ValueError:
            prs = None
        # 100 entries may be a cut-off list, which could hide an open one.
        if not isinstance(prs, list) or len(prs) >= 100 or not all(isinstance(pr, dict)
                                                                   for pr in prs):
            continue
        head = repo.git("rev-parse", f"refs/heads/{branch}", cwd=top)
        states = {pr.get("state") for pr in prs if pr.get("headRefOid") == head}
        state = "merged" if "MERGED" in states else "closed" if "CLOSED" in states else ""
        if not state or any(pr.get("state") == "OPEN" for pr in prs):
            continue
        status = repo.run("git", "status", "--porcelain", "--ignored", "--untracked-files=normal",
                          cwd=path)
        if status.returncode == 0 and all(map(_kept, status.stdout.splitlines())):
            found.append((path, branch, state))
    return found


def _said(failed: Exception) -> str:
    """A failure in one line: a refusal's problem, git's last line, or the system's error."""
    if isinstance(failed, subprocess.CalledProcessError):
        return ((failed.stderr or "").strip() or (failed.stdout or "").strip()
                or f"exit code {failed.returncode}").splitlines()[-1]
    return str(failed).partition("\nNext: ")[0]


def _held(top: Path, cfg: dict[str, Any], rel: str, ref: str) -> str:
    """Why doctor won't overwrite a file, or "": changes not committed yet in the checkout doctor
    runs in, or a last commit on ref that isn't Forge's. Forge's is on the default branch and
    changes the pin or is doctor's own fix; neither can carry a hand edit to these files."""
    if repo.git("status", "--porcelain", "--untracked-files=all", "--ignored", "--", rel, cwd=top):
        return "has changes not committed yet, so doctor won't overwrite it"
    last = repo.git("log", "-1", "--format=%H %s", ref, "--", rel, cwd=top)
    if not last or cfg["repo"] == "forge-source":  # Forge's own repo keeps its templates here
        return ""
    commit, _, subject = last.partition(" ")
    pin = lambda at: repo._pin(story.show(top, at, "forge.toml") or "")  # noqa: E731  # pyright: ignore[reportPrivateUsage]
    landed = repo.run("git", "merge-base", "--is-ancestor", commit, story.landed_ref(top),
                      cwd=top).returncode == 0
    if landed and (subject.startswith(WHY) or pin(commit) != pin(f"{commit}^")):
        return ""
    return f"was changed by hand ({subject}), so doctor won't overwrite it"


def _split(top: Path, folder: Path, cfg: dict[str, Any], wanted: dict[str, str],
           ref: str) -> tuple[list[str], list[tuple[str, str]], frozenset[str]]:
    """The files forge sync would change in folder, split into those doctor may let it write and a
    row for each one held back, with the held-back set. A change staged in the checkout doctor
    runs in counts even when the file already matches sync."""
    staged = set(repo.run("git", "diff", "--cached", "--name-only", "-z", "--", *wanted,
                          cwd=top).stdout.split("\0"))
    differing = set(sync.differing(folder, wanted))
    free, rows, keep = [], [], set()
    for rel in (rel for rel in wanted if rel in differing or rel in staged):
        if reason := _held(top, cfg, rel, ref):
            rows.append((f"{rel} {reason}.", HAND))
            keep.add(rel)
        else:
            free.append(rel)
    if "AGENTS.md" in keep and "CLAUDE.md" in free:  # sync moves CLAUDE.md's lines into AGENTS.md
        free.remove("CLAUDE.md")
        keep.add("CLAUDE.md")
        rows.append(("CLAUDE.md stays until doctor can write AGENTS.md, since sync moves its lines "
                     "there.", HAND))
    return free, rows, frozenset(keep)


def _linked(folder: Path, wanted: dict[str, str]) -> list[tuple[str, str]]:
    """One row when a file sync would write or read, or a folder above it, is a link: doctor then
    repairs none of Forge's files, since a write or a read could reach whatever the link leads to."""
    for rel in [*wanted, "AGENTS.md", "CLAUDE.md"]:
        path = folder / rel
        if any(part.is_symlink() for part in [path, *path.parents] if part.is_relative_to(folder)
               and part != folder):
            return [(f"{rel} is a link, so doctor repaired none of Forge's files.",
                     f"replace the link with a regular file, then {REPAIR}")]
    return []


def _unfinished(name: str, branch: str, path: Path | None) -> tuple[str, str]:
    remove = (f'git worktree remove --force --force "{path}" and ' if path else "")
    return (f"Doctor's fix {name} isn't merged yet, so doctor started no new one.",
            f"finish it with forge close {name}, or remove it with {remove}git branch "
            f"-D {branch}, then {REPAIR}")


def _in_fix(top: Path, cfg: dict[str, Any], wanted: dict[str, str]) -> list[tuple[str, str]]:
    """On the default branch, freshly fetched: Forge's files go into doctor's own fix, never onto
    the branch."""
    ref, default = story.landed_ref(top), repo.default_branch(top)
    # Doctor keeps at most one fix of its own: a branch of it stops a new one.
    trees = story.worktrees(top)
    for branch in repo.git("for-each-ref", "--format=%(refname:short)", "refs/heads/fix/",
                           cwd=top).splitlines():
        name = branch.removeprefix("fix/")
        if not repo.ITEM.fullmatch(name):
            continue
        state = story.json_of(story.show(top, branch, repo.state_path(name)))
        if state.get("why") != WHY or story.show(top, ref, repo.state_path(name)) is not None:
            continue
        # Doctor never looks inside it: one step, whether it is current, stale or locked.
        return [_unfinished(name, branch, trees.get(branch))]
    # A clean checkout at the default branch's latest commit would make the same fix: none.
    heads = repo.run("git", "rev-parse", "HEAD", ref, cwd=top).stdout.split()
    free, held, _ = _split(top, top, cfg, wanted, ref)
    if len(set(heads)) == 1 and not free:
        return held
    # The fix inherits the default branch's pin; only that Forge may write its files.
    newer = repo._pin(story.show(top, ref, "forge.toml") or "")  # pyright: ignore[reportPrivateUsage]
    if newer != __version__:
        return [(f"{default} now pins Forge v{newer}, not the installed v{__version__}, so "
                        "doctor started no fix for Forge's files.",
                        f"git pull --ff-only, then {REPAIR}"), *_rows(free), *held]
    # When this checkout is behind, inspect the fetched default branch before starting a fix.
    # This detached preview has no fix branch or record, and runs no checkout hook.
    if len(set(heads)) != 1:
        try:
            with tempfile.TemporaryDirectory() as temporary:
                preview = Path(temporary) / "default"
                repo.git("-c", f"core.hooksPath={os.devnull}", "worktree", "add", "-q", "--detach",
                         str(preview), ref, cwd=top)
                try:
                    if linked := _linked(preview, wanted):
                        return linked
                    fixed = repo.config(preview)
                    free, held, _ = _split(top, preview, fixed, sync.files(preview, fixed), ref)
                finally:
                    repo.git("worktree", "remove", "--force", str(preview), cwd=top)
        except (repo.Refused, OSError, subprocess.CalledProcessError) as failed:
            return [(f"doctor couldn't check Forge's files on {default}: {_said(failed)}", REPAIR),
                    *held]
        if not free:
            return held
    # forge fix start's naming rule, with doctor's slug.
    taken = {ref_name.split("/fix/", 1)[1] for ref_name in repo.git(
        "for-each-ref", "--format=%(refname)", "refs/heads/fix/", "refs/remotes/origin/fix/",
        cwd=top).splitlines()}
    name, n = "forge-files", 1
    while name in taken or story.show(top, ref, repo.state_path(name)) is not None:
        n += 1
        name = f"forge-files-{n}"
    who = repo.git("var", "GIT_AUTHOR_IDENT", cwd=top).split("<")[0].strip()
    state = {"kind": "fix", "why": WHY, "done_when": DONE, "base": repo.git("rev-parse", ref, cwd=top),
             "allow_large": "Doctor brings every file forge sync writes up to date in one change; "
                            f"{who} allowed it by running forge doctor --fix."}
    branch, path = f"fix/{name}", task._folder(f"fix-{name}")  # pyright: ignore[reportPrivateUsage]
    try:
        task._new_checkout(name, branch, f"fix-{name}", ref, state, f"Start the fix: {WHY}")  # pyright: ignore[reportPrivateUsage]
        fixed = repo.config(path)
        fixed_wanted = sync.files(path, fixed)
        if linked := _linked(path, fixed_wanted):
            return [(problem, _unfinished(name, branch, path)[1]) for problem, _ in linked]
        free, held, keep = _split(top, path, cfg, fixed_wanted, ref)
        if free:  # forge sync's own write, so deletions and links behave exactly as there
            free = sync.write(path, fixed, keep)
            repo.git("add", "-A", "-f", "--", *free, cwd=path)
            repo.git("commit", "-q", "-m", WHY, "--", *free, cwd=path)
    except (repo.Refused, OSError, subprocess.CalledProcessError) as failed:
        return [(f"Doctor couldn't bring Forge's files up to date in fix {name}: "
                        f"{_said(failed)}", _unfinished(name, branch, path)[1]), *held]
    if not free:
        return [_unfinished(name, branch, path), *held]
    print(f"- Fixed: wrote {len(free)} of Forge's files in fix {name}.")
    return [(f"Doctor's fix {name} holds Forge's files and isn't merged yet.",
                    f"forge close {name}"), *held]


def _rows(free: list[str]) -> list[tuple[str, str]]:
    return [(f"{rel} differs from what forge sync writes for the installed Forge v{__version__}.",
             REPAIR) for rel in free]


def _files(top: Path, cfg: dict[str, Any], wanted: dict[str, str],
           fix: bool) -> list[tuple[str, str]]:
    """A row per file that differs from what sync writes. With fix, they are written in doctor's
    own fix on the default branch, or in place, not committed, as forge sync does, elsewhere."""
    if linked := _linked(top, wanted):
        return linked
    default = repo.default_branch(top)
    on_default, failed = repo.current_branch(top) == default, []
    if fix and on_default:
        # The fix starts from the default branch's latest commit, so doctor needs it first.
        fetched = repo.run("git", "fetch", "-q", "origin", cwd=top)
        if not fetched.returncode:
            return _in_fix(top, cfg, wanted)
        failed = [(f"doctor couldn't fetch {default} from origin, so it started no fix for "
                   f"Forge's files: {_last(fetched)}",
                   f"check your network and GitHub access, then {REPAIR}")]
    free, rows, keep = _split(top, top, cfg, wanted,
                              story.landed_ref(top) if on_default else "HEAD")
    if not fix or not free or failed:
        return failed + _rows(free) + rows
    try:  # forge sync's own write, so deletions and links behave exactly as there
        written = sync.write(top, cfg, keep)
    except (repo.Refused, OSError) as error:  # what is written stays, as forge sync leaves it
        still = [rel for rel in sync.differing(top, sync.files(top, cfg)) if rel not in keep]
        written = [rel for rel in free if rel not in still]
        if isinstance(error, repo.Refused) and error.entry is repo.REFUSALS["default_branch"]:
            problem, _, next_step = str(error).partition("\nNext: ")
            failure = (problem, next_step)  # a detached HEAD: sync's own refusal
        else:
            failure = (f"doctor couldn't write Forge's files: {_said(error)}", REPAIR)
        rows = [failure, *_rows(still), *rows]
    for rel in written:
        print(f"- Fixed: {'wrote' if (top / rel).exists() else 'removed'} {rel}.")
    return rows


def doctor(args: argparse.Namespace) -> int:
    top = repo.root()
    cfg = repo.config(top)
    install = sync.install_line(cfg["version"])
    rows: list[tuple[str, str]] = []
    pinned = "v" + cfg["version"].removeprefix("v")
    if pinned != f"v{__version__}":
        problem = repo.REFUSALS["pin"][0].format(installed=f"v{__version__}", pinned=pinned)
        # Only a newer pin, once: the second run already names it. An older one runs through uv.
        repairs = _newer(pinned) and os.environ.get("FORGE_PINNED_RUN") != pinned
        if repairs and args.fix and shutil.which("uv"):
            done = repo.run(*install.split())
            forge = shutil.which("forge")
            if done.returncode == 0 and forge:
                print(f"- Fixed: installed Forge {pinned}, the version this repo pins.", flush=True)
                # The rest of the repairs need the pinned Forge's own code and templates.
                return subprocess.run([forge, "doctor", "--fix"],
                                      env={**os.environ, "FORGE_PINNED_RUN": pinned}).returncode
            said = _last(done) if done.returncode else "no forge is on PATH after uv installed it"
            rows.append((f"{problem} Installing it failed: {said}", install))
        else:
            rows.append((problem, REPAIR if repairs and not args.fix else install))
    on_codex = cfg["workers"] != "claude"  # split runs Codex and Claude
    # Under Claude Code the cold read runs on Codex, so the SDK must be ready there too, unless
    # Codex isn't installed: a Claude-only team.
    needs_sdk = on_codex or bool(os.environ.get("CLAUDECODE")
                                 and shutil.which(os.environ.get("CODEX_BIN") or "codex"))
    # Without uv there is nothing to install with; the uv row below says how to get it.
    sdk_failed = ""
    if args.fix and needs_sdk and shutil.which("uv") and codex.sdk_problem():
        try:
            codex.install()
        except repo.Refused as refused:
            sdk_failed = str(refused).partition("\nNext: ")[0]

    # Codex workers run the Codex program bundled with the SDK, checked below, not one on PATH.
    for tool in ("git", "gh", "uv") if cfg["workers"] == "codex" else ("git", "gh", "uv", "claude"):
        if not shutil.which(tool):
            rows.append((f"{tool} is not installed or not on PATH.", INSTALL[tool]))
    if shutil.which("gh") and repo.run("gh", "auth", "status", cwd=top).returncode:
        rows.append(("gh is not signed in to GitHub.", "gh auth login"))
    if needs_sdk and (problem := sdk_failed or codex.sdk_problem()):
        rows.append((problem, REPAIR))
    try:  # the reviewer close runs, at the version Forge pins
        review.helper()
    except repo.Refused as refused:
        rows.append((str(refused).partition("\nNext: ")[0], INSTALL["autoreview"]))

    try:
        wanted = sync.files(top, cfg)
        compared = ("- Note: doctor compared the synced files with the installed Forge "
                    f"v{__version__}")
        compared += "." if pinned == f"v{__version__}" else (
            f", not the pinned {pinned}.\n  To check with {pinned}: {install}, then run forge "
            "doctor again.")
    except repo.Refused as refused:
        problem, _, fix = str(refused).partition("\nNext: ")
        rows.append((f"doctor couldn't compare the synced files with what forge sync writes: "
                     f"{problem}", fix))
        wanted, compared = {}, ""
    # Forge's own repo runs without the default hooks until the switch: every worktree shares
    # that folder. An explicitly configured hooks folder must still be checked.
    checks_hooks = (cfg["repo"] != "forge-source" or
                    repo.run("git", "config", "--get", "core.hooksPath", cwd=top).returncode == 0)
    if checks_hooks and any(sync.read(path) != text for path, text in sync.shims(top, cfg).items()):
        if not args.fix:
            rows.append(("The git hooks that check each commit and push aren't installed.", REPAIR))
        else:
            try:  # never committed, so this repair runs on the default branch too
                sync.install_shims(top, cfg)
                print("- Fixed: installed the git hooks that check each commit and push.")
            except repo.Refused as refused:
                problem, _, fix = str(refused).partition("\nNext: ")
                rows.append((problem, fix))

    main = Path(repo.git("rev-parse", "--path-format=absolute", "--git-common-dir",
                         cwd=top)).resolve().parent
    finished = _finished(top, main)
    if finished and not args.fix:
        rows.append((f"{len(finished)} folders hold finished work: "
                     f"{', '.join(str(path) for path, _, _ in finished)}.", REPAIR))
    for path, branch, state in finished if args.fix else []:
        removed = repo.run("git", "worktree", "remove", "--force", str(path), cwd=main)
        if removed.returncode:
            rows.append((f"Forge couldn't remove {path}: {_last(removed)}",
                         f"unlock it or close programs using it, then {REPAIR}"))
            continue
        deleted = repo.run("git", "branch", "-D", branch, cwd=main)
        if deleted.returncode:
            rows.append((f"Removed {path}, but its branch {branch} is still here: "
                         f"{_last(deleted).rstrip('.')}.", f"git branch -D {branch}"))
        else:
            print(f"- Fixed: removed {path}, whose pull request is {state}.")
    # The installed Forge's templates make these files; doctor writes them only with the pinned one.
    rows += _files(top, cfg, wanted, args.fix and pinned == f"v{__version__}")

    if not shutil.which("sh"):
        rows.append(("sh isn't on PATH, so no host hook can run.",
                     "install Git, which brings sh, and put it on PATH"))
    elif wanted and sync.read(top / sync.LAUNCHER) != wanted.get(sync.LAUNCHER):
        # Every hook sources the launcher, so doctor runs none of them until it is sync's own.
        rows.append((f"doctor didn't run the host hooks, because {sync.LAUNCHER} differs from what "
                     "forge sync writes.", REPAIR))
    else:
        # With a bare PATH, as Codex may run them: each hook must find forge on its own.
        env = {**os.environ, "PATH": BARE_PATH} if os.name != "nt" else None  # Windows has no /usr/bin
        bare = f" when run with PATH={BARE_PATH}" if env else ""
        for rel in sync.HOSTS:
            # Only a command exactly as forge sync writes it ever runs. Any other one makes the
            # file differ from sync's, so it is already a drift row above, and it never runs.
            generated = set(_forge_hooks(wanted.get(rel, "")))
            for event, command in _forge_hooks(sync.read(top / rel)):
                if (event, command) not in generated:
                    continue
                payload = {"session_id": "forge-doctor", "cwd": str(top), "hook_event_name": event,
                           **SAMPLES.get(event, {})}
                done = subprocess.run([shutil.which("sh") or "sh", "-c", command], cwd=top,
                                      input=json.dumps(payload), capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", env=env)
                if done.returncode:
                    said = (done.stderr.strip() or "it printed nothing").splitlines()
                    # Forge's own Next line when forge ran and refused; else it couldn't launch.
                    fix = next((line[6:] for line in said if line.startswith("Next: ")), install)
                    rows.append((f"The {event} hook in {rel} fails with exit code "
                                 f"{done.returncode}{bare}: {said[0]}", fix))

    if not cfg["checks"]:
        rows.append(("forge.toml names no checks, so close has nothing to wait for.",
                     "ask your agent to set checks in forge.toml"))
    protection = (repo.run("gh", "api", f"repos/{{owner}}/{{repo}}/branches/"
                           f"{repo.default_branch(top)}/protection", cwd=top)
                  if shutil.which("gh") else None)
    plan_note = (init.skipped(repo.default_branch(top), cfg["checks"])
                 if protection and init.no_protection_plan(protection) else "")
    if protection and (protection.returncode == 0 or
                       "Branch not protected" in protection.stdout + protection.stderr):
        try:
            required = json.loads(protection.stdout).get("required_status_checks") or {}
            protected = {entry["context"] for entry in required.get("checks") or []
                         if isinstance(entry, dict) and isinstance(entry.get("context"), str)}
            protected.update(name for name in required.get("contexts") or []
                             if isinstance(name, str))
        except (ValueError, AttributeError):
            protected = set()
        if protected != set(cfg["checks"]):
            rows.append(("forge.toml checks differ from branch protection's required checks: "
                         f"Forge names {', '.join(sorted(cfg['checks'])) or 'none'}; protection "
                         f"requires {', '.join(sorted(protected)) or 'none'}.",
                         "ask your agent to reconcile checks in forge.toml with branch protection"))
    if not cfg["test"]:
        rows.append(("forge.toml has no test command.",
                     "ask your agent to set test in forge.toml, then run forge sync"))
    elif "tests" in cfg["checks"] and f"run: {json.dumps(cfg['test'])}" not in sync.read(
            top / sync.WORKFLOW_PATH):
        rows.append((f"The tests check in {sync.WORKFLOW_PATH} doesn't run forge.toml's test "
                     "command.", REPAIR))

    # Codex skips the project hooks (the deny hook included) and the project's Codex settings
    # until the user trusts the project in their own Codex config. That fails Codex workers; with
    # Claude workers it is advice.
    codex_config = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
    trusted = _codex_trusts(top, codex_config)
    trust = ("open Codex here and trust the project, or add "
             f'[projects."{top}"] with trust_level = "trusted" to {codex_config}')
    if on_codex and not trusted:
        rows.append(("Codex doesn't trust this project, so it would skip Forge's hooks and the "
                     "project's Codex settings.", trust))

    # Both UI skills must be where each host reads skills: the configured worker's, and any whose
    # program is installed. A host's own config folder (Claude's is $CLAUDE_CONFIG_DIR when set),
    # or the repo's.
    skills = {"claude": [Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"),
                         top / ".claude"],
              "codex": [codex_config.parent, Path.home() / ".agents", top / ".codex",
                        top / ".agents"]}
    package = top / "package.json"
    packages = json.loads(sync.read(package)) if package.is_file() else {}
    dependencies = {**packages.get("dependencies", {}), **packages.get("devDependencies", {})}
    has_frontend = (any((top / path / "package.json").is_file()
                        for path in ("frontend", "web", "apps/web"))
                    or any(name in dependencies for name in ("react", "react-dom", "vue", "svelte",
                                                             "@angular/core", "next", "vite")))
    if has_frontend:
        # Every configured host, and every host whose program is installed, may build UI work.
        for host in (host for host in skills
                     if cfg["workers"] in (host, "split") or shutil.which(host)):
            for skill in ("impeccable", "emil-design-eng"):
                if not any((folder / "skills" / skill / "SKILL.md").is_file()
                           for folder in skills[host]):
                    rows.append((f"{skill} is required for UI work but isn't installed where the "
                                 f"{host} worker reads skills.", INSTALL[skill]))

    for line in codex.tidy(top):
        print(f"- {line}")
    for problem, fix in rows:
        print(f"- {problem}\n  Fix: {fix}")
    if plan_note:
        print(f"- Note: {plan_note}")
    if cfg["fast_test"]:
        print(f"- Note: close runs fast_test ({cfg['fast_test']}) instead of test, with {{base}} as "
              "the merge base with the default branch; the pull request's tests check still runs "
              "the full test command.")
    if on_codex:
        # Codex also asks the user to approve each project hook, and no outside program sees that.
        print("- Note: when Codex asks you to approve Forge's hooks, approve them; Forge can't see "
              "whether you did.")
    elif not trusted:
        print("- Note: Codex runs this repo's hooks only in a project it trusts, and it doesn't "
              f"trust this one yet.\n  Fix: {trust}")
    # Said whenever the comparison ran, whatever else fails; after the verdict when all is well.
    if rows:
        if compared:
            print(compared)
        repo.refuse(REFUSALS["problems"], count=len(rows))
    print(f"Everything {'checks' if trusted else 'else checks'} out for Forge {cfg['version']}.")
    print(compared)
    return 0
