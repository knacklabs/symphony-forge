"""Advice for repos without fast_test; never edits their settings."""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

from forge import init, repo


def group_command(cfg: dict[str, Any]) -> str:
    """The PR command, or the full command that Forge's pytest picker splits."""
    command = cfg.get("fast_test") or cfg["test"]
    return cfg["test"] if re.search(r"\bforge test --pytest(?:\s|$)", command) else command


def group_warning(top: Path, cfg: dict[str, Any]) -> str:
    """Explain why CI uses one group for an unsplittable test command."""
    command = group_command(cfg)
    if (cfg.get("groups", 1) > 1 and "{group}" not in command
            and not repo.pytest_split(top, command)):
        return ("CI uses one group because the test command has no {group} placeholder. "
                "Add the runner's shard options with {group} and {groups} to use more groups.")
    return ""


NPM_VALUE_OPTIONS = ("--package", "-p", "--workspace", "-w", "--cache", "--prefix", "--registry",
                     "--userconfig", "--globalconfig")


def _npm_runner_index(words: list[str]) -> int:
    index = 2
    while index < len(words) and words[index].startswith("-"):
        if words[index] == "--":
            return index + 1
        index += 2 if words[index] in NPM_VALUE_OPTIONS else 1
    return index


def _scripts(top: Path) -> dict[str, str]:
    package = top / "package.json"
    return json.loads(package.read_text("utf-8")).get("scripts", {}) if package.is_file() else {}


# Programs that only start another program, and the one word after Playwright or Cypress that runs tests.
LAUNCHERS = {"npx", "npm", "pnpm", "yarn", "bun", "bunx", "corepack", "exec", "dlx", "cross-env"}
BROWSER_RUNNERS = {"playwright": "test", "cypress": "run"}


def browser_step(top: Path, part: str) -> bool:
    """Is this step one Playwright or Cypress run, direct or as the only command of a package script?

    A step or script that chains commands (&& ; | &), or a script that has a pre or post script
    (npm runs those with it), does more than the browser run, so it is not one."""
    chained = re.compile(r"[;|&]")
    if chained.search(part):
        return False
    try:
        words = shlex.split(part)
        if words[:1] == ["corepack"]:
            words = words[1:]
        if words[:1] in (["npm"], ["pnpm"], ["yarn"], ["bun"]):
            script = words[2] if len(words) > 2 and words[1] in ("run", "run-script") else (
                words[1] if len(words) > 1 else "")
            scripts = _scripts(top)
            body = scripts.get(script)
            if body is not None:
                if chained.search(body) or f"pre{script}" in scripts or f"post{script}" in scripts:
                    return False
                words = shlex.split(body)
    except ValueError:
        return False
    rest = iter(enumerate(words))
    for index, word in rest:
        if word.startswith("-"):  # a launcher option; an option's value is not a program
            if word in NPM_VALUE_OPTIONS:
                next(rest, None)
            continue
        name = word.replace("\\", "/").rsplit("/", 1)[-1]
        if name in BROWSER_RUNNERS and words[index + 1:index + 2] == [BROWSER_RUNNERS[name]]:
            return True
        if name not in LAUNCHERS and "=" not in name:
            return False  # another program, such as a lint step or a script runner
    return False


def test_parts(top: Path, command: str) -> list[tuple[str, str, str]]:
    """Classify the same runner and setup parts for advice and Python-only execution."""
    scripts = _scripts(top)
    parts = []
    if command == init.NODE_TEST:
        command = command.partition("(")[2][:-1]
    # ponytail: recognize straight && pipelines and Forge's Node wrapper; adapt other shell flows in the agent.
    for part in command.split("&&"):
        part = part.strip()
        try:
            words = shlex.split(part)
        except ValueError:
            return []
        names = [word.replace("\\", "/").rsplit("/", 1)[-1] for word in words]
        runner_words = words
        passthrough = ""
        if words and words[0] in ("npm", "pnpm", "yarn", "bun"):
            script = words[2] if len(words) > 2 and words[1] in ("run", "run-script") else (
                words[1] if len(words) > 1 else "")
            if script in scripts:
                runner_words = shlex.split(scripts[script])
                passthrough = " --" if words[0] == "npm" and "--" not in words else ""
        if words[:2] == ["npm", "exec"]:
            index = _npm_runner_index(words)
            runner_words = words[index:index + 1]
        runner_names = [word.replace("\\", "/").rsplit("/", 1)[-1] for word in runner_words]
        node = bool(words and words[0] in ("npm", "pnpm", "yarn", "bun", "npx"))
        kind = next((name for name in ("vitest", "jest") if name in runner_names),
                    "node-check" if node else "")
        if "pytest" in names:
            kind = "python"
        elif words and words[0] in ("npm", "pnpm", "yarn", "bun") and len(words) > 1 and words[1] in ("ci", "install"):
            kind = "node-install"
        parts.append((kind, part, passthrough))
    return parts


def _combined_script(top: Path, command: str) -> str:
    """The first package script in the command whose body chains steps, or empty."""
    if command == init.NODE_TEST:  # Forge's generated wrapper: look inside it
        command = command.partition("(")[2][:-1]
    try:
        scripts = json.loads((top / "package.json").read_text("utf-8")).get("scripts", {})
        for part in command.split("&&"):
            words = part.split()
            if words[:1] == ["corepack"]:
                words = words[1:]
            if not words or words[0] not in ("npm", "pnpm", "yarn", "bun"):
                continue
            # `npm ci` and `npm install` are not package scripts, even when a script has that name.
            if len(words) < 2 or words[1] in ("ci", "install"):
                continue
            name = words[2] if words[1] in ("run", "run-script") and len(words) > 2 else words[1]
            # An operator inside quotes, such as a test name "a|b", is part of one step.
            lexer = shlex.shlex(scripts.get(name, ""), posix=True, punctuation_chars=True)
            if any(token in ("&&", "||", ";", "|") for token in lexer):
                return name
    except (OSError, ValueError, AttributeError):
        pass  # no readable package scripts: skip this advice instead of crashing sync or setup
    return ""


def combined_note(top: Path, cfg: dict[str, Any]) -> None:
    """One line for a combined test script with no fast_test; Forge suggests no command for it."""
    if not cfg["fast_test"] and (script := _combined_script(top, cfg["test"])):
        print(f'The test setting runs the combined script "{script}", so Forge cannot limit its tests '
              "to the change. Write a fast_test for this repo as the Forge guide says, then ask the owner.",
              flush=True)


def suggest(top: Path, cfg: dict[str, Any]) -> None:
    if cfg["fast_test"] or _combined_script(top, cfg["test"]):  # combined_note names that case
        return
    python = any((top / marker).is_file() for marker in
                 ("pyproject.toml", "pytest.ini", "setup.py", "requirements.txt"))
    parts, kinds = [], set()
    for kind, part, passthrough in test_parts(top, cfg["test"]):
        if kind == "python":
            python = True
            if "python" in kinds:
                continue
            kinds.add("python")
            part = "forge test --pytest {base}"
        else:
            if kind in ("vitest", "jest"):
                if kind in kinds:
                    continue
                kinds.add(kind)
                words = shlex.split(part)
                if words[:2] == ["npm", "exec"] and "--" not in words:
                    index = _npm_runner_index(words)
                    if index < len(words):
                        tokens = list(re.finditer(r'''(?:[^\s"']+|"[^"]*"|'[^']*')+''', part))
                        start = tokens[index].start()
                        part = part[:start] + "-- " + part[start:]
                changed = "--changed" if kind == "vitest" else "--changedSince"
                part += f"{passthrough} {changed} {{base}} --passWithNoTests"
        parts.append(part)
    if not kinds and not python:
        return
    if kinds <= {"python"}:
        command = "forge test --pytest {base}"
    else:
        if python and "python" not in kinds:
            parts.insert(0, "forge test --pytest {base}")
        command = " && ".join(parts)
        if cfg["test"] == init.NODE_TEST:
            command = cfg["test"].partition("(")[0] + "(" + command + ")"
    print("Suggested quick tests in forge.toml (keep the full test command for CI):", flush=True)
    print(f"fast_test = {json.dumps(command)}", flush=True)
