"""forge doctor: tools, the pins (Forge's and the Autoreview helper's), the git hooks, the host
hooks, adapter drift, CI and, for Codex workers, the Codex SDK and the project's trust; a row per
problem. With Codex workers, --fix installs the SDK."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tomllib
from pathlib import Path

from forge import __version__, codex, repo, review, sync

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
    "autoreview": (f"install skills/autoreview from https://github.com/openclaw/agent-skills at "
                   f"{review.AUTOREVIEW_PIN} into {review.HELPER.parents[1]}"),
}

# A harmless payload per hook event, so each host hook runs without changing anything.
SAMPLES = {
    "SessionStart": {"source": "startup"},
    "PreToolUse": {"tool_name": "Bash", "tool_input": {"command": "git status"}},
    "PostToolUse": {"tool_name": "forge-doctor", "tool_input": {}, "tool_response": {}},
}


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


def doctor(args: argparse.Namespace) -> None:
    top = repo.root()
    cfg = repo.config(top)
    install = sync.install_line(cfg["version"])
    rows: list[tuple[str, str]] = []
    on_codex = cfg["workers"] == "codex"
    # Without uv there is nothing to install with; the uv row below says how to get it.
    if args.fix and on_codex and shutil.which("uv") and codex.sdk_problem():
        codex.install()

    # Codex workers run the Codex program bundled with the SDK, checked below, not one on PATH.
    for tool in ("git", "gh", "uv") if on_codex else ("git", "gh", "uv", "claude"):
        if not shutil.which(tool):
            rows.append((f"{tool} is not installed or not on PATH.", INSTALL[tool]))
    if shutil.which("gh") and repo.run("gh", "auth", "status", cwd=top).returncode:
        rows.append(("gh is not signed in to GitHub.", "gh auth login"))
    pinned = "v" + cfg["version"].removeprefix("v")
    if pinned != f"v{__version__}":
        rows.append((repo.REFUSALS["pin"][0].format(installed=f"v{__version__}", pinned=pinned),
                     install))
    if on_codex and (problem := codex.sdk_problem()):
        rows.append((problem, "forge doctor --fix"))
    try:  # the reviewer close runs, at the version Forge pins
        review.helper()
    except repo.Refused as refused:
        rows.append((str(refused).partition("\nNext: ")[0], INSTALL["autoreview"]))

    try:
        wanted = sync.files(top, cfg)
    except repo.Refused as refused:
        problem, _, fix = str(refused).partition("\nNext: ")
        rows.append((problem, fix))
        wanted = {}
    rows += [(f"{rel} differs from what forge sync writes for Forge {cfg['version']}.", "forge sync")
             for rel, text in wanted.items() if sync.read(top / rel) != text]
    if any(sync.read(path) != text for path, text in sync.shims(top, cfg).items()):
        rows.append(("The git hooks that check each commit and push aren't installed.", "forge sync"))

    if not shutil.which("sh"):
        rows.append(("sh isn't on PATH, so no host hook can run.",
                     "install Git, which brings sh, and put it on PATH"))
    else:
        for rel in sync.HOSTS:
            # Only a command exactly as forge sync writes it ever runs. Any other one makes the
            # file differ from sync's, so it is already a drift row above, and it never runs.
            generated = set(_forge_hooks(wanted.get(rel, "")))
            for event, command in _forge_hooks(sync.read(top / rel)):
                if (event, command) not in generated:
                    continue
                payload = {"session_id": "forge-doctor", "cwd": str(top), "hook_event_name": event,
                           **SAMPLES.get(event, {})}
                done = repo.run("sh", "-c", command, cwd=top, input=json.dumps(payload))
                if done.returncode:
                    said = (done.stderr.strip() or "it printed nothing").splitlines()
                    # Forge's own Next line when forge ran and refused; else it couldn't launch.
                    fix = next((line[6:] for line in said if line.startswith("Next: ")), install)
                    rows.append((f"The {event} hook in {rel} fails with exit code "
                                 f"{done.returncode}: {said[0]}", fix))

    if not cfg["checks"]:
        rows.append(("forge.toml names no checks, so close has nothing to wait for.",
                     'set checks = ["tests", "forge-pr-check"] in forge.toml'))
    if not cfg["test"]:
        rows.append(("forge.toml has no test command.",
                     'set test = "<the full test command>" in forge.toml, then run forge sync'))
    elif f"run: {json.dumps(cfg['test'])}" not in sync.read(top / sync.WORKFLOW_PATH):
        rows.append((f"The tests check in {sync.WORKFLOW_PATH} doesn't run forge.toml's test "
                     "command.", "forge sync"))

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

    # impeccable is the one required UI skill, so it must be where the configured worker reads
    # skills: its own config folder (Claude's is $CLAUDE_CONFIG_DIR when set), or the repo's.
    skills = {"claude": [Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude"),
                         top / ".claude"],
              "codex": [codex_config.parent, Path.home() / ".agents", top / ".codex",
                        top / ".agents"]}
    if not any((folder / "skills" / "impeccable" / "SKILL.md").is_file()
               for folder in skills[cfg["workers"]]):
        rows.append((f"impeccable, the one UI skill Forge requires, isn't installed where the "
                     f"{cfg['workers']} worker reads skills.", INSTALL["impeccable"]))

    for problem, fix in rows:
        print(f"- {problem}\n  Fix: {fix}")
    if on_codex:
        # Codex also asks the user to approve each project hook, and no outside program sees that.
        print("- Note: when Codex asks you to approve Forge's hooks, approve them; Forge can't see "
              "whether you did.")
    elif not trusted:
        print("- Note: Codex runs this repo's hooks only in a project it trusts, and it doesn't "
              f"trust this one yet.\n  Fix: {trust}")
    if rows:
        repo.refuse(REFUSALS["problems"], count=len(rows))
    print(f"Everything {'checks' if trusted else 'else checks'} out for Forge {cfg['version']}.")
