"""Advice for repos without fast_test; never edits their settings."""
from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any


def suggest(top: Path, cfg: dict[str, Any]) -> None:
    if cfg["fast_test"]:
        return
    python = any((top / marker).is_file() for marker in
                 ("pyproject.toml", "pytest.ini", "setup.py", "requirements.txt"))
    package = top / "package.json"
    scripts = json.loads(package.read_text("utf-8")).get("scripts", {}) if package.is_file() else {}
    parts, kinds = [], set()
    # ponytail: recognize straight && pipelines; let the agent adapt other shell flows.
    for part in cfg["test"].split("&&"):
        part = part.strip()
        try:
            words = shlex.split(part)
        except ValueError:
            return
        names = [word.replace("\\", "/").rsplit("/", 1)[-1] for word in words]
        runner_words = words
        passthrough = ""
        if words and words[0] in ("npm", "pnpm", "yarn", "bun"):
            script = words[2] if len(words) > 2 and words[1] in ("run", "run-script") else (
                words[1] if len(words) > 1 else "")
            if script in scripts:
                runner_words = shlex.split(scripts[script])
                passthrough = " --" if words[0] == "npm" and "--" not in words else ""
        runner_names = [word.replace("\\", "/").rsplit("/", 1)[-1] for word in runner_words]
        if "pytest" in names:
            python = True
            if "python" in kinds:
                continue
            kinds.add("python")
            part = "forge test --pytest {base}"
        else:
            runner = next((name for name in ("vitest", "jest") if name in runner_names), "")
            if runner:
                if runner in kinds:
                    continue
                kinds.add(runner)
                changed = "--changed" if runner == "vitest" else "--changedSince"
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
    print("Suggested quick tests in forge.toml (keep the full test command for CI):", flush=True)
    print(f"fast_test = {json.dumps(command)}", flush=True)
