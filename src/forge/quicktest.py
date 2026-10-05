"""Advice for repos without fast_test; never edits their settings."""
from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any


def test_parts(top: Path, command: str) -> list[tuple[str, str, str]]:
    """Classify the same runner and setup parts for advice and Python-only execution."""
    package = top / "package.json"
    scripts = json.loads(package.read_text("utf-8")).get("scripts", {}) if package.is_file() else {}
    parts = []
    # ponytail: recognize straight && pipelines; let the agent adapt other shell flows.
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
        runner_names = [word.replace("\\", "/").rsplit("/", 1)[-1] for word in runner_words]
        kind = next((name for name in ("vitest", "jest") if name in runner_names), "")
        if "pytest" in names:
            kind = "python"
        elif words and words[0] in ("npm", "pnpm", "yarn", "bun") and len(words) > 1 and words[1] in ("ci", "install"):
            kind = "node-install"
        parts.append((kind, part, passthrough))
    return parts


def suggest(top: Path, cfg: dict[str, Any]) -> None:
    if cfg["fast_test"]:
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
                    end = part.index("exec") + len("exec")
                    part = part[:end] + " --" + part[end:]
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
    print("Suggested quick tests in forge.toml (keep the full test command for CI):", flush=True)
    print(f"fast_test = {json.dumps(command)}", flush=True)
