"""Advice for repos without fast_test; never edits their settings."""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

from forge import init


def _npm_runner_index(words: list[str]) -> int:
    index = 2
    while index < len(words) and words[index].startswith("-"):
        if words[index] == "--":
            return index + 1
        index += 2 if words[index] in ("--package", "-p", "--workspace", "-w", "--cache",
                                      "--prefix", "--registry", "--userconfig", "--globalconfig") else 1
    return index


def shell_steps(command: str) -> list[str]:
    """Return raw && steps, or no steps when shell control flow cannot be selected safely."""
    steps = []
    start = 0
    operators = re.compile(r'''\\.|"(?:\\.|[^"\\])*"|'[^']*'|&&|[;&|<>()]''')
    for match in operators.finditer(command):
        token = match.group()
        if token == "&&":
            step = command[start:match.start()].strip()
            if not step:
                return []
            steps.append(step)
            start = match.end()
        elif token[0] in ";&|<>()":
            return []
    step = command[start:].strip()
    return steps + [step] if step else []


def runner_words(top: Path, words: list[str]) -> tuple[list[str], str]:
    """Resolve a known launcher or one package-script body, keeping its arguments."""
    passthrough = ""
    if words[:1] and words[0] in {"npm", "pnpm", "yarn", "bun"} and words[1:2] != ["exec"]:
        if words[1:2] and words[1] in {"ci", "install", "add", "remove", "uninstall", "update", "init"}:
            return [], ""
        index = 2 if words[1:2] in (["run"], ["run-script"]) else 1
        package = top / "package.json"
        scripts = json.loads(package.read_text("utf-8")).get("scripts", {}) if package.is_file() else {}
        script = scripts.get(words[index], "") if index < len(words) else ""
        steps = shell_steps(script)
        if len(steps) != 1:
            return [], ""
        passthrough = " --" if words[0] == "npm" and "--" not in words else ""
        words = shlex.split(steps[0]) + [word for word in words[index + 1:] if word != "--"]
    if len(words) > 1 and words[0] in {"npm", "pnpm", "yarn", "bun"} and words[1] == "exec":
        words = words[_npm_runner_index(words) if words[0] == "npm" else 2:]
    if words[:2] == ["uv", "run"]:
        words = words[2:]
        while words:
            if words[0] == "--python" and len(words) > 1:
                words = words[2:]
            elif words[0] in {"--frozen", "--locked", "--no-sync", "--offline"} or words[0].startswith("--python="):
                words = words[1:]
            else:
                break
    if len(words) > 2 and re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?",
                                      Path(words[0]).name) and words[1:3] == ["-m", "pytest"]:
        words = words[2:]
    elif words[:1] == ["npx"]:
        words = words[2:] if words[1:2] == ["--no-install"] else words[1:]
    return words, passthrough


def test_parts(top: Path, command: str, *, plain: bool = True) -> list[tuple[str, str, str]]:
    """Plain calls own chain steps; broad recognition preserves the legacy pytest picker."""
    parts = []
    if command == init.NODE_TEST:
        command = command.partition("(")[2][:-1]
    directory_changed = False
    for part in shell_steps(command):
        try:
            words = shlex.split(part)
            directory_changed |= words[:1] == ["cd"]
            runner, passthrough = runner_words(top, words) if not (plain and directory_changed) else ([], "")
        except ValueError:
            return []
        name = runner[0].replace("\\", "/").rsplit("/", 1)[-1] if runner else ""
        name = name.removesuffix(".cmd").removesuffix(".exe")
        kind = "python" if name == "pytest" else name if name in {"vitest", "jest", "playwright"} else ""
        if not plain and any(word.replace("\\", "/").rsplit("/", 1)[-1] in {"pytest", "pytest.exe"}
                             for word in words):
            kind = "python"
        if plain and any(arg.startswith(("-k", "-m", "--keyword", "--markexpr")) for arg in runner[1:]):
            kind = ""
        if name == "playwright" and runner[1:2] != ["test"]:
            kind = ""
        if name == "nx" and runner[1:2] == ["run-many"] and "run-many" in words:
            kind = "nx"
        parts.append((kind, part, passthrough))
    return parts


def suggest(top: Path, cfg: dict[str, Any]) -> None:
    if cfg["fast_test"]:
        return
    if not cfg["test"].strip():
        return
    python_repo = any((top / marker).is_file() for marker in
                      ("pyproject.toml", "pytest.ini", "setup.py", "requirements.txt"))
    test_parts_found = test_parts(top, cfg["test"])
    javascript_repo = (top / "package.json").is_file()
    python_only = len(test_parts_found) == 1 and test_parts_found[0][0] == "python"
    parts = []
    has_selection = False
    for kind, part, passthrough in test_parts_found:
        if kind in ("vitest", "jest", "playwright"):
            has_selection = True
            words = shlex.split(part)
            if words[:2] == ["npm", "exec"] and "--" not in words:
                index = _npm_runner_index(words)
                if index < len(words):
                    tokens = list(re.finditer(r'''(?:[^\s"']+|"[^"]*"|'[^']*')+''', part))
                    start = tokens[index].start()
                    part = part[:start] + "-- " + part[start:]
            if kind == "playwright":
                part += f"{passthrough} --only-changed={{base}}"
            else:
                changed = "--changed" if kind == "vitest" else "--changedSince"
                part += f"{passthrough} {changed} {{base}} --passWithNoTests"
        parts.append(part)
    if not python_only and not has_selection:
        if not python_repo and not javascript_repo:
            return
        command = cfg["test"]
    elif python_only:
        command = "forge test --pytest {base}"
    else:
        command = " && ".join(parts)
        if cfg["test"] == init.NODE_TEST:
            command = cfg["test"].partition("(")[0] + "(" + command + ")"
    print("Suggested quick tests in forge.toml (keep the full test command for CI):", flush=True)
    print(f"fast_test = {json.dumps(command)}", flush=True)
