"""forge upgrade: move a repo to a newer Forge release in one fix, from the install to the close.

It skips the pin check (the command changes the pin), and runs the new release's own sync and
close through uv, so neither an old cached build nor an older forge on PATH writes the files.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from forge import close, repo, story, task

COMMANDS = [{
    "words": "upgrade", "run": "upgrade", "changes_state": False,
    "help": "Upgrade Forge in this repo to a release, or the newest, through one fix",
    "args": [(('release',), {"nargs": "?", "help": "such as v1.3.0; the newest when left out"})],
    "position": 45,
    "listing": "| `forge upgrade [release]` | Upgrades Forge to the release, or the newest: installs it, has it refresh Forge's files in a fix, and closes that fix |",
}]

SOURCE = "knacklabs/symphony-forge"
INSTALL = ("uv tool install --force --reinstall --no-cache --python 3.11 "
           f"git+https://github.com/{SOURCE}@{{release}}")
PREFIX = "upgrade-forge-to-"
RELEASE = re.compile(r"v(\d+)\.(\d+)\.(\d+)")

REFUSALS = {
    "own_repo": ("This is Forge's own repo, which moves its version by releasing a new Forge.",
                 "forge next"),
    "not_default": ("forge upgrade runs on {default}, and this checkout is on {branch}.",
                    "git switch {default}, then {again}"),
    "dirty": ("This checkout has changes you haven't committed: {files}.",
              "commit or undo them, then {again}"),
    "bad_release": ("{release!r} is not a Forge release; a release is v and three numbers, such "
                    "as v1.3.0.", "forge upgrade <release>"),
    "not_newer": ("{default} already pins Forge {pinned}, so {release} would not be an upgrade.",
                  "forge upgrade <a release newer than {pinned}>"),
    "no_newest": ("Forge could not find its newest release: {reason}.",
                  "forge upgrade <release>, naming the release"),
    "other_open": ("The upgrade to Forge {other} is still open in fix {fix}.",
                   "forge upgrade {other} to finish it, or remove it: git worktree remove --force "
                   "{path} && git branch -D fix/{fix}"),
    "leftover": ("Fix {fix} was interrupted as it started, and its folder {path} holds work, so "
                 "Forge left it alone.", "check that folder, then git worktree remove --force "
                 "{path} && git branch -D fix/{fix}, then forge upgrade {release}"),
    "taken": ("Fix {fix} already exists {how}, so Forge left it alone.",
              "finish or remove that fix, then forge upgrade {release}"),
    "install": ("Installing Forge {release} failed: {reason}",
                "run {install} in your own terminal, then forge upgrade {release}"),
    "stale": ("After the install, your PATH finds {found} instead of Forge {release}.",
              "remove that forge or put uv's tool folder ahead of it on PATH, then "
              "forge upgrade {release}"),
}


def upgrade(args: argparse.Namespace) -> int:
    top = repo.root()
    again = " ".join(["forge upgrade", *([args.release] if args.release else [])])
    if repo.config(top)["repo"] == "forge-source":
        repo.refuse(REFUSALS["own_repo"])
    default, branch = repo.default_branch(top), repo.current_branch(top)
    if branch != default:
        repo.refuse(REFUSALS["not_default"], default=default, branch=branch or "a detached HEAD",
                    again=again)
    # The index and the working tree both, so a staged change undone in the folder still counts;
    # untracked files don't.
    dirty = repo.run("git", "status", "--porcelain", "-z", "--no-renames", "--untracked-files=no",
                     cwd=top).stdout
    if dirty:
        repo.refuse(REFUSALS["dirty"], files=", ".join(entry[3:] for entry in dirty.split("\0") if entry),
                    again=again)
    release = args.release or _newest(top)
    if not RELEASE.fullmatch(release):
        repo.refuse(REFUSALS["bad_release"], release=release)
    pinned = repo.default_config(top)["version"]  # fetches the default branch first
    if _numbers(release) <= _numbers(pinned):
        repo.refuse(REFUSALS["not_newer"], default=default, pinned=pinned, release=release)
    name, ref = PREFIX + release.replace(".", "-"), f"origin/{default}"
    trees = story.worktrees(top)
    for other, path in trees.items():
        if other.startswith(f"fix/{PREFIX}") and other != f"fix/{name}":
            repo.refuse(REFUSALS["other_open"], fix=other[4:], path=path,
                        other=other[4 + len(PREFIX):].replace("-", "."))
    repo.set_version(story.show(top, ref, "forge.toml") or "", release)  # refuses before anything
    why, done = f"Upgrade Forge to {release}.", f"This repo pins and runs Forge {release}."

    # 1. The fix, started like forge fix start's, or the one an earlier run left.
    path = trees.get(f"fix/{name}")
    state = {"kind": "fix", "why": why, "done_when": done}
    if path is None:
        if repo.run("git", "rev-parse", "-q", "--verify", f"refs/heads/fix/{name}", cwd=top
                    ).returncode == 0 or repo.git("ls-remote", "--heads", "origin", f"fix/{name}", cwd=top):
            repo.refuse(REFUSALS["taken"], fix=name, how="as a branch without its folder",
                        release=release)
        path = task._new_checkout(name, f"fix/{name}", f"fix-{name}", ref,
                                  {**state, "base": repo.git("rev-parse", ref, cwd=top)},
                                  f"Start the fix: {why}")
        print(f"Started fix {name} in {path}.", flush=True)
    else:
        found = repo.read_state(name, path) if path.is_dir() else {}
        if found is None:  # interrupted right after the folder was made: take it up only when clean
            if repo.git("rev-list", "HEAD", "--not", ref, cwd=path) or repo.git(
                    "status", "--porcelain", "--untracked-files=all", cwd=path):
                repo.refuse(REFUSALS["leftover"], fix=name, path=path, release=release)
            rel = repo.write_state(name, repo.add_step(
                {**state, "base": repo.git("rev-parse", "HEAD", cwd=path), "status": "started",
                 "branch": f"fix/{name}"}, "start"), path)
            repo.commit_state(f"Start the fix: {why}", rel, top=path)
        elif found.get("why") != why:
            repo.refuse(REFUSALS["taken"], fix=name, release=release,
                        how="for other work" if path.is_dir() else "as a branch without its folder")
        print(f"Continuing fix {name} in {path}.", flush=True)

    # 2. The version, and nothing else, in the fix's forge.toml.
    toml = path / "forge.toml"
    text = toml.read_bytes().decode("utf-8")  # bytes keep its line endings
    edited = repo.set_version(text, release)
    if edited != text:
        toml.write_bytes(edited.encode("utf-8"))
    print(f'Set version = "{release}" in the fix\'s forge.toml.', flush=True)

    # 3 and 4. The release installed, and the forge on PATH is it.
    if _on_path()[0] == release:
        print(f"Forge {release} is already installed, so the install was skipped.", flush=True)
    else:
        install = INSTALL.format(release=release)
        installed = repo.run(*install.split())
        if installed.returncode:
            reason = (installed.stderr or installed.stdout).strip().splitlines() or ["uv gave no reason"]
            repo.refuse(REFUSALS["install"], release=release, reason=reason[-1], install=install)
        print(f"Installed Forge {release}.", flush=True)
    found, where = _on_path()
    if found != release:
        repo.refuse(REFUSALS["stale"], release=release,
                    found=(f"Forge {found} at {where}" if found else f"a forge of unknown version at {where}")
                    if where else "no forge")
    print(f"The forge on your PATH is Forge {release}.", flush=True)

    # 5. The release's own sync refreshes Forge's files in the fix's folder.
    print(f"Running Forge {release}'s forge sync in the fix's folder.", flush=True)
    synced = repo.run_release(release, ["sync"], path)
    if synced:
        return synced

    # 6. One commit: forge.toml and everything sync changed, deletions included, never hook shims.
    changed = close.synced_changes(path)
    # A deletion already staged, such as a rename's old name, is in neither the folder nor the
    # index, so git add can't name it; the commit by path still takes it.
    listed = repo.git("ls-files", "-z", "--", *changed, cwd=path).split("\0") if changed else []
    adding = [rel for rel in changed if rel in listed or (path / rel).exists()]
    if adding:
        repo.git("add", "--", *adding, cwd=path)
    if changed and repo.run("git", "diff", "--cached", "--quiet", "--", *changed, cwd=path).returncode:
        repo.git("commit", "-q", "-m", f"Upgrade Forge to {release}", "--", *changed, cwd=path)
        print(f"Committed the upgrade to Forge {release}.", flush=True)
    else:
        print("Nothing new to commit.", flush=True)

    # 7 and 8. The release's own close; its last line says who merges, and its exit code is ours.
    print(f"Running Forge {release}'s forge close {name}.", flush=True)
    return repo.run_release(release, ["close", name], path)


def release_notice(top: Path) -> list[str]:
    """Best-effort daily release check, shared by all of this repo's worktrees."""
    try:
        pinned = repo.config(top)["version"]
        cache = repo.forge_dir(top) / f"release-{repo.now()[:10]}.json"
        try:
            # Exclusive creation claims today's check before contacting GitHub. A failed or
            # interrupted check stays claimed, so other worktrees never retry it today.
            claimed = cache.open("x", encoding="utf-8")
        except FileExistsError:
            tag = json.loads(cache.read_text(encoding="utf-8"))
        else:
            with claimed:
                try:
                    tag = _newest(top, timeout=3)
                except (repo.Refused, OSError, subprocess.TimeoutExpired):
                    tag = None
                json.dump(tag, claimed)
        if isinstance(tag, str) and RELEASE.fullmatch(tag) and _numbers(tag) > _numbers(pinned):
            return [f"Forge {tag} is out (you pin {pinned}): forge upgrade {tag}"]
    except (repo.Refused, OSError, ValueError):
        # No cache access or an in-flight writer: this optional notice must not block next.
        pass
    return []


def _newest(top: Path, timeout: float | None = None) -> str:
    """The newest release's tag, as GitHub has it."""
    gh = shutil.which("gh")
    if gh is None:
        repo.refuse(REFUSALS["no_newest"], reason="gh is not installed")
    done = subprocess.run([gh, "release", "view", "--repo", SOURCE, "--json", "tagName"],
                          cwd=top, input="", capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)
    try:
        tag = json.loads(done.stdout).get("tagName") if done.returncode == 0 else None
    except (ValueError, AttributeError):
        tag = None
    if not isinstance(tag, str):
        lines = (done.stderr or done.stdout).strip().splitlines() or ["gh gave no release"]
        repo.refuse(REFUSALS["no_newest"], reason=lines[-1].rstrip("."))
    return tag


def _numbers(version: str) -> tuple[int, ...]:
    """A version's three numbers, then 1 for a release or 0 for a prerelease, which comes before it."""
    found = re.match(r"v?(\d+)\.(\d+)\.(\d+)(.*)", version)
    return (*map(int, found.groups()[:3]), 0 if found[4] else 1) if found else ()


def _on_path() -> tuple[str, str]:
    """The release the forge on PATH reports ("" when it can't say), and where it lives."""
    where = shutil.which("forge")
    if where is None:
        return "", ""
    words = repo.run("forge", "--version").stdout.split()
    return (words[-1] if words and RELEASE.fullmatch(words[-1]) else ""), where
