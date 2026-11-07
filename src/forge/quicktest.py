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


def test_parts(top: Path, command: str) -> list[tuple[str, str, str]]:
    """Classify the same runner and setup parts for advice and Python-only execution."""
    parts = []
    if command == init.NODE_TEST:
        command = command.partition("(")[2][:-1]
    folder = top
    for part in shell_steps(command):
        try:
            words = shlex.split(part)
        except ValueError:
            return []
        names = [word.replace("\\", "/").rsplit("/", 1)[-1] for word in words]
        runner_words = words
        passthrough = ""
        if words[:1] == ["cd"] and len(words) == 2:
            parts.append(("", part, ""))
            folder = (folder / words[1]).resolve()
            continue
        package = folder / "package.json"
        scripts = json.loads(package.read_text("utf-8")).get("scripts", {}) if package.is_file() else {}
        if words and words[0] in ("npm", "pnpm", "yarn", "bun"):
            script = (words[2] if len(words) > 2 and words[1] in ("run", "run-script") else
                      words[1] if len(words) > 1 and words[1] not in
                      ("exec", "ci", "install", "add", "remove", "uninstall", "update", "init") else "")
            if script in scripts:
                script_steps = shell_steps(scripts[script])
                if len(script_steps) != 1:
                    runner_words = []
                else:
                    try:
                        runner_words = shlex.split(script_steps[0])
                    except ValueError:
                        runner_words = []
                passthrough = " --" if words[0] == "npm" and "--" not in words else ""
        if words[:2] == ["npm", "exec"]:
            index = _npm_runner_index(words)
            runner_words = words[index:index + 1]
        runner_names = [word.replace("\\", "/").rsplit("/", 1)[-1] for word in runner_words]
        node = bool(words and words[0] in ("npm", "pnpm", "yarn", "bun", "npx"))
        kind = next((name for name in ("vitest", "jest", "playwright") if name in runner_names),
                    "node-check" if node else "")
        if "nx" in runner_names and "run-many" in words:
            kind = "nx"
        elif "pytest" in names:
            kind = "python"
        elif ("ruff" in names and "check" in words) or "mypy" in names:
            kind = "ruff" if "ruff" in names else "mypy"
        elif words and words[0] in ("npm", "pnpm", "yarn", "bun") and len(words) > 1 and words[1] in ("ci", "install"):
            kind = "node-install"
        if kind == "playwright" and "test" not in runner_words + words:
            kind = "node-check"
        parts.append((kind, part, passthrough))
    return parts


def suggest(top: Path, cfg: dict[str, Any]) -> None:
    if cfg["fast_test"]:
        return
    if not cfg["test"].strip():
        return
    python = any((top / marker).is_file() for marker in
                 ("pyproject.toml", "pytest.ini", "setup.py", "requirements.txt"))
    test_parts_found = test_parts(top, cfg["test"])
    has_cd = any(not kind and shlex.split(part)[:1] == ["cd"]
                 for kind, part, _ in test_parts_found)
    has_python_step = any(kind == "python" for kind, _, _ in test_parts_found)
    if not test_parts_found or (has_cd and has_python_step):
        command = cfg["test"]
        print("Suggested quick tests in forge.toml (keep the full test command for CI):", flush=True)
        print(f"fast_test = {json.dumps(command)}", flush=True)
        return
    parts, kinds = [], set()
    for kind, part, passthrough in test_parts_found:
        if kind == "python":
            python = True
            if "python" in kinds:
                continue
            kinds.add("python")
            part = "forge test --pytest {base}"
        else:
            if kind in ("vitest", "jest", "playwright"):
                kinds.add(kind)
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
    if not kinds and not python:
        return
    if kinds == {"python"}:
        command = "forge test --pytest {base}"
    else:
        if python and "python" not in kinds:
            parts.insert(0, "forge test --pytest {base}")
        command = " && ".join(parts)
        if cfg["test"] == init.NODE_TEST:
            command = cfg["test"].partition("(")[0] + "(" + command + ")"
    print("Suggested quick tests in forge.toml (keep the full test command for CI):", flush=True)
    print(f"fast_test = {json.dumps(command)}", flush=True)
