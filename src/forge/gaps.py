"""The "Before production" list: what a signed-off prototype still lacks, read from the default branch."""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from forge import repo, story

HEADING = "Before production: "
ALLOWANCE = "Prototype before sign-off"
LABEL = "Demo only"
NOT_APP = [":(exclude)*.md", *(f":(exclude){name}" for name in (
    "docs", "plans", ".factory", ".claude", ".codex", ".github", "tests", "test", "__tests__")),
    *(f":(exclude,glob)**/{name}/**" for name in ("tests", "test", "__tests__"))]


def listing(top: Path) -> dict[str, Any]:
    """The open gaps as the sign-off block's line and rows; empty unless a prototype is signed off."""
    empty: dict[str, Any] = {"line": "", "open": []}
    ref = story.landed_ref(top)
    text = repo.read_blob(top, f"{ref}:forge.toml")
    try:
        cfg = {**repo.DEFAULTS, **tomllib.loads(text or "")}
    except tomllib.TOMLDecodeError:
        return empty
    if cfg.get("repo") != "client" or cfg.get("stage") != "prototype" or repo.is_prototype(top, cfg, (ref,)):
        return empty
    rows = []
    if cfg.get("sample_data") is True:
        rows.append(("Sample data is on, so the app has no back end, no tests and no CI",
                     "Leave sample data: settle the Personal data answer, set the test command and "
                     "checks, then set sample_data = false in forge.toml"))
    if parts := _light_parts(top, ref):
        names = ", ".join(parts)
        rows.append((f"{_count(len(parts), 'part was', 'parts were')} built with only the light review: {names}",
                     f"Review and test {'this part' if len(parts) == 1 else 'these parts'} in full: {names}"))
    if files := _labelled(top, ref):
        names = ", ".join(files)
        rows.append((f'{_count(len(files), "file carries", "files carry")} the "{LABEL}" label: {names}',
                     f"Build each demo-only feature properly or remove it: {names}"))
    if not rows:
        return empty
    return {"line": f"{HEADING}{_count(len(rows), 'open gap', 'open gaps')}",
            "open": [{"item": item, "say": say} for item, say in rows]}


def _count(number: int, one: str, many: str) -> str:
    return f"{number} {one if number == 1 else many}"


def _labelled(top: Path, ref: str) -> list[str]:
    """App files on the default branch that hold the label."""
    done = repo.run("git", "grep", "-l", "-I", "-F", LABEL, ref, "--", ".", *NOT_APP, cwd=top)
    return sorted(line.removeprefix(f"{ref}:") for line in done.stdout.splitlines())


def _light_parts(top: Path, ref: str) -> list[str]:
    """Fixes that got only the prototype's light review and that no later change names."""
    names = repo.git("ls-tree", "-r", "--name-only", ref, "--", ".factory/fixes/", cwd=top).splitlines()
    texts = repo.blob_texts(top, [f"{ref}:{name}" for name in names if name.endswith(".json")])
    states = {Path(spec.partition(":")[2]).stem: story.json_of(text) for spec, text in texts.items()}
    states = {name: state for name, state in states.items() if state.get("status") != "dropped"}
    level = lambda state: (state.get("review") or {}).get("blocking_level", "P1")  # noqa: E731
    light = sorted(name for name, state in states.items()
                   if state.get("allow_large") == ALLOWANCE and level(state) == "P0")
    if not light:
        return []
    landed = {name: story.merged_at(top, ref, repo.state_path(name)) for name in light}
    # A part leaves the list when a change that landed after it names it: a fully reviewed fix by its
    # text, or a story by its title once its last part is done.
    said = [(f"{state.get('why', '')} {state.get('done_when', '')}", name) for name, state in states.items()
            if level(state) != "P0"]
    said = [(text, story.merged_at(top, ref, repo.state_path(name))) for text, name in said
            if any(_names(part, text) for part in light)]
    paths = repo.git("ls-tree", "-r", "--name-only", ref, "--", ".factory/stories/", cwd=top).splitlines()
    keys = {match[1]: f"{ref}:{match[0]}" for path in paths if (match := re.fullmatch(
        r"\.factory/stories/([A-Z][A-Z0-9-]*)/story\.json", path))}
    titles = {spec: str(story.json_of(text).get("title", ""))
              for spec, text in repo.blob_texts(top, list(keys.values())).items()}
    for key, spec in keys.items():
        if any(_names(part, titles[spec]) for part in light):
            done = story.completed(top, key, ref)
            if done.get("status") == "done":
                said.append((titles[spec], str(done.get("finished", ""))))
    return [name for name in light if not any(_names(name, text) and when > landed[name] for text, when in said)]


def _names(name: str, text: str) -> bool:
    """Whether the text holds the whole name, not the start of a longer one."""
    return bool(re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text))
