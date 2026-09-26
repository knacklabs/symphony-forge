"""Shared seams: git, forge.toml, the roadmap, the version pin, refusals and `.factory` state.

Refusal convention: every module declares one REFUSALS table of (problem, next command)
templates and raises its entries with refuse(). The CLI prints the problem, then a
`Next:` line, and exits non-zero.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from forge import __version__

REFUSALS = {
    "no_repo": ("This folder is not inside a git repository.", "cd <your repo>"),
    "missing_tool": ("{tool} is not installed or not on PATH.", "forge doctor"),
    "no_config": ("This repo has no forge.toml.", "forge init"),
    "bad_config": ("forge.toml is not usable: {problem}.", "forge doctor"),
    "models": ("forge.toml's [models] table is not usable: {problem}.",
               "ask your agent to fix forge.toml's [models] table"),
    "old_model": ("forge.toml's model setting is now the [models] table.",
                  "ask your agent to move it into forge.toml's [models] table"),
    "pin": (
        "Forge {installed} is installed, but this repo pins {pinned}.",
        "uv tool install git+https://github.com/knacklabs/symphony-forge@{pinned}",
    ),
    "bad_roadmap": ("plans/roadmap.json is not usable: {problem}.", "git checkout -- plans/roadmap.json"),
    "bad_item": ("{item!r} is not a story key, a KEY/TASK task or a fix name.", "forge next"),
    "bad_state": ("{path} is not usable: {problem}.", "git checkout -- {path}"),
    "default_branch": (
        "Forge changes nothing on {branch}; work happens on a story, task or fix branch.",
        'forge fix start "<why>" --done "<done when>"',
    ),
}


class Refused(Exception):
    """A refusal: the problem in one sentence, then the next command."""

    def __init__(self, problem: str, next_step: str, code: int = 1):
        super().__init__(f"{problem}\nNext: {next_step}")
        self.code = code


def refuse(entry: tuple[str, str], code: int = 1, **values: Any) -> NoReturn:
    """Raise one entry of a module's REFUSALS table, filled in with values."""
    problem, next_step = entry
    raise Refused(problem.format(**values), next_step.format(**values), code)


# --- git -------------------------------------------------------------------------------


def run(*args: str, cwd: str | os.PathLike[str] | None = None,
        input: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a program without a shell. It is looked up on PATH, so .cmd shims work on Windows."""
    exe = shutil.which(args[0])
    if exe is None:
        refuse(REFUSALS["missing_tool"], tool=args[0])
    # An empty stdin, never the terminal: a prompt would hang instead of failing.
    return subprocess.run([exe, *args[1:]], cwd=cwd, input=input or "", capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def git(*args: str, cwd: str | os.PathLike[str] | None = None) -> str:
    """Run git and return its trimmed output. A failure raises CalledProcessError."""
    done = run("git", *args, cwd=cwd)
    if done.returncode:
        raise subprocess.CalledProcessError(done.returncode, ["git", *args], done.stdout, done.stderr)
    return done.stdout.strip()


def root(cwd: str | os.PathLike[str] | None = None) -> Path:
    """The top of the current checkout (a worktree's own folder inside a worktree)."""
    done = run("git", "rev-parse", "--show-toplevel", cwd=cwd)
    if done.returncode:
        refuse(REFUSALS["no_repo"])
    return Path(done.stdout.strip())


def current_branch(cwd: str | os.PathLike[str] | None = None) -> str:
    """The checked-out branch, or "" on a detached HEAD."""
    return git("branch", "--show-current", cwd=cwd)


def default_branch(cwd: str | os.PathLike[str] | None = None) -> str:
    # ponytail: origin/HEAD, else "main". A remote-less repo on another name needs origin/HEAD set.
    done = run("git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=cwd)
    return done.stdout.strip().removeprefix("origin/") if done.returncode == 0 else "main"


def forge_dir(cwd: str | os.PathLike[str] | None = None) -> Path:
    """`.git/forge/`, shared by every worktree, for logs and the board. Never committed."""
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
    path = Path(common) / "forge"
    path.mkdir(exist_ok=True)
    return path


def work_log(top: Path, item: str) -> Path:
    """The item's work log in `.git/forge/`, where its worker's progress goes."""
    return forge_dir(top) / f"work-{item.replace('/', '-')}.log"


# --- forge.toml, the pin and the roadmap -----------------------------------------------

KEYS = {"version": str, "repo": str, "workers": str, "test": str,
        "checks": list, "interfaces": list, "models": dict}
DEFAULTS = {"repo": "client", "workers": "claude", "test": "",
            "checks": [], "interfaces": [], "models": {}}
CHOICES = {"repo": ("client", "forge-source"), "workers": ("claude", "codex")}
# The kinds of work in forge.toml's [models] table. Each has a model and an effort (a review's
# effort is optional); building and fixing may add their subagents' model and effort, as a pair.
# The cold read runs on either family, so the grill kind has one such entry per family.
KINDS = ("build", "fix", "lite", "grill", "review")
SUBAGENTS = ("subagents", "subagent_effort")
FAMILIES = ("codex", "claude")


def config(top: Path | None = None) -> dict[str, Any]:
    """Read and check forge.toml at the top of the checkout; missing keys get their defaults."""
    path = (top or root()) / "forge.toml"
    if not path.is_file():
        refuse(REFUSALS["no_config"])
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        refuse(REFUSALS["bad_config"], problem=exc)
    if "model" in data:
        refuse(REFUSALS["old_model"])
    problem = _config_problem(data)
    if problem:
        refuse(REFUSALS["bad_config"], problem=problem)
    problem = _models_problem(data.get("models", {}))
    if problem:
        refuse(REFUSALS["models"], problem=problem)
    return {**DEFAULTS, **data}


def models(cfg: dict[str, Any], kind: str, family: str = "") -> dict[str, str]:
    """One kind's models from forge.toml's [models] table, the family's entry for the grill kind;
    refused when the table lacks it."""
    chosen = cfg["models"].get(kind)
    if kind == "grill":
        kind, chosen = f"grill.{family}", (chosen or {}).get(family)
    if chosen is None:
        refuse(REFUSALS["models"], problem=f"it has no [models.{kind}], which this work uses")
    return chosen


def _models_problem(table: Any) -> str:
    if not isinstance(table, dict):
        return "models must be a table"
    for kind, chosen in table.items():
        if kind not in KINDS:
            return f"{kind} is not a kind of work; the kinds are {', '.join(KINDS[:-1])} and {KINDS[-1]}"
        if not isinstance(chosen, dict):
            return f"models.{kind} must be a table"
        wrong = [key for key in chosen if key not in FAMILIES] if kind == "grill" else []
        if wrong:
            return f"models.grill has one entry per family, codex and claude, so it can't set {wrong[0]}"
        entries = ({f"grill.{family}": entry for family, entry in chosen.items()} if kind == "grill"
                   else {kind: chosen})
        for name, entry in entries.items():
            if not isinstance(entry, dict):
                return f"models.{name} must be a table"
            for key, value in entry.items():
                if key not in ("model", "effort", *(SUBAGENTS if kind in ("build", "fix") else ())):
                    return f"models.{name} can't set {key}"
                if not isinstance(value, str):
                    return f"models.{name}.{key} must be a string"
            for key in ("model",) if kind == "review" else ("model", "effort"):
                if key not in entry:
                    return f"models.{name} has no {key}"
            if (SUBAGENTS[0] in entry) != (SUBAGENTS[1] in entry):
                return f"models.{name} sets only one of subagents and subagent_effort; set both or neither"
    return ""


def _config_problem(data: dict[str, Any]) -> str:
    if "version" not in data:
        return "it has no version"
    for key, value in data.items():
        kind = KEYS.get(key)
        if kind is None:
            return f"{key!r} is not a forge.toml key"
        if kind is str and not isinstance(value, str):
            return f"{key} must be a string"
        if kind is list and not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
            return f"{key} must be a list of strings"
        if key in CHOICES and value not in CHOICES[key]:
            return f"{key} must be one of {', '.join(CHOICES[key])}"
    return ""


def check_pin(cwd: str | os.PathLike[str] | None = None) -> None:
    """Refuse when the installed Forge isn't the one forge.toml pins.

    A folder outside git, or a repo with no forge.toml yet (before init or migrate), has no pin.
    """
    done = run("git", "rev-parse", "--show-toplevel", cwd=cwd)
    top = Path(done.stdout.strip())
    if done.returncode or not (top / "forge.toml").is_file():
        return
    pinned = config(top)["version"].removeprefix("v")
    if pinned != __version__:
        refuse(REFUSALS["pin"], installed=f"v{__version__}", pinned=f"v{pinned}")


def roadmap(top: Path | None = None) -> list[dict[str, Any]]:
    """The items of plans/roadmap.json (each has a key), or [] when there is no roadmap yet."""
    path = (top or root()) / "plans" / "roadmap.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        refuse(REFUSALS["bad_roadmap"], problem=exc)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not all(
            isinstance(item, dict) and isinstance(item.get("key"), str) for item in items):
        refuse(REFUSALS["bad_roadmap"], problem="it needs an items list where every item has a key")
    return items


# --- .factory state: one file per story, task or fix -----------------------------------

ITEM = re.compile(r"(?P<key>[A-Z][A-Z0-9-]*)(?:/(?P<task>[A-Z0-9][A-Z0-9-]*))?|(?P<fix>[a-z0-9][a-z0-9-]*)")


def state_path(item: str) -> str:
    """The repo-relative state file of a story (KEY), a task (KEY/TASK) or a fix (its name)."""
    match = ITEM.fullmatch(item)
    if not match:
        refuse(REFUSALS["bad_item"], item=item)
    if match["fix"]:
        return f".factory/fixes/{item}.json"
    if match["task"]:
        # Tasks sit in tasks/ so a task named STORY can't collide with story.json on a
        # case-insensitive disk (macOS, Windows).
        return f".factory/stories/{match['key']}/tasks/{match['task']}.json"
    return f".factory/stories/{item}/story.json"


def read_state(item: str, top: Path | None = None) -> dict[str, Any] | None:
    """An item's state in this checkout, or None when Forge never started it here."""
    rel = state_path(item)
    path = (top or root()) / rel
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        refuse(REFUSALS["bad_state"], path=rel, problem=exc)
    if not isinstance(data, dict):
        refuse(REFUSALS["bad_state"], path=rel, problem="it is not a JSON object")
    return data


def write_state(item: str, data: dict[str, Any], top: Path | None = None) -> str:
    """Write an item's state in a checkout on a work branch. Returns the repo-relative path."""
    top = top or root()
    _work_branch(top)
    rel = state_path(item)
    path = top / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    # Bytes, so Windows writes the same LF file as everyone else.
    tmp.write_bytes((json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    os.replace(tmp, path)
    return rel


def now() -> str:
    """The current UTC time. FORGE_NOW overrides it, so tests can drive dated steps."""
    # ponytail: an env override is the whole clock seam.
    return os.environ.get("FORGE_NOW") or datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_step(data: dict[str, Any], step: str) -> dict[str, Any]:
    """Add a dated step (start, review, ci-green, ready, merged) to an item's state."""
    data.setdefault("steps", []).append({"step": step, "at": now()})
    return data


def commit_state(message: str, *paths: str, top: Path | None = None) -> bool:
    """Commit these repo-relative paths (state and the docs that go with it) on the work branch.

    The git hooks run as usual. Returns False when nothing changed.
    """
    top = top or root()
    _work_branch(top)
    git("add", "--", *paths, cwd=top)
    if run("git", "diff", "--cached", "--quiet", "--", *paths, cwd=top).returncode == 0:
        return False
    git("commit", "-q", "-m", message, "--", *paths, cwd=top)
    return True


def _work_branch(top: Path) -> str:
    """The checkout's branch. Refuses the default branch (once it has a commit) and a detached HEAD."""
    branch = current_branch(top)
    born = run("git", "rev-parse", "--verify", "-q", "HEAD", cwd=top).returncode == 0
    if not branch or (born and branch == default_branch(top)):
        refuse(REFUSALS["default_branch"], branch=branch or "a detached HEAD")
    return branch
