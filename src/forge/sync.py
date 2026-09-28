"""forge sync: the adapter files for Claude Code and Codex, the CI workflow and the git hook shims.

The Markdown lives in templates/; the rest is inline here. AGENTS.md, both host hook
files and .codex/config.toml are merged: everything in them that isn't Forge's stays as it is.
A git hook that was there before Forge is kept as <hook>.pre-forge and runs first.
"""
from __future__ import annotations

import argparse
import ast
import importlib
import json
import pkgutil
import re
import tomllib
from pathlib import Path
from typing import Any

import forge
from forge import githooks, prcheck, repo

COMMANDS = [{
    "words": "sync", "run": "sync", "changes_state": True,
    "help": "Write the generated adapter files and git hooks for the pinned version",
    "args": [], "position": 20,
    "listing": "| `forge sync` | Writes the generated files for both hosts, the CI workflow and the git hooks |",
}]

REFUSALS = {
    "outside": ("{path} leads outside this repo, so Forge won't write through it; remove that link.",
                "forge sync"),
    "cant_merge": ("{path} can't be merged ({problem}); fix it by hand.", "forge sync"),
    "bad_block": ("{path} has a broken Forge block; keep one <!-- forge:begin --> line and, after "
                  "it, one <!-- forge:end --> line.", "forge sync"),
    "hook_link": ("{path} links to a file outside this repo's .git folder, so Forge won't write "
                  "through it; put the hook itself there instead of the link.", "forge sync"),
    "hook_kept": ("{path} and {kept} both hold a hook that isn't Forge's; combine them into {kept} "
                  "by hand and delete {path}.", "forge sync"),
}

TEMPLATES = Path(__file__).with_name("templates")
SOURCE = Path(__file__).resolve().parents[2]
BEGIN, END = "<!-- forge:begin -->", "<!-- forge:end -->"
WORKFLOW_PATH = prcheck.WORKFLOW_PATH
# A Forge host hook command: v1's, or the copied-in Forge's ("$(git rev-parse ...)/forge" hook x).
FORGE_COMMAND = re.compile(r'forge"? hook ')


def command(hook: str) -> str:
    """A host hook command that fails closed (decision 0038, ported).

    If forge can't launch, the inner guard turns that into exit 2; if sh itself can't, the outer
    one does. Exit 2 is the code both hosts treat as blocking.
    """
    return f"sh -c 'forge hook {hook} || exit 2' || exit 2"


HOSTS = githooks.HOSTS

CODEX_CONFIG = """\
# Codex runs the project hooks in .codex/hooks.json only with this on; forge sync keeps it on.
[features]
hooks = true
"""
FEATURES = re.compile(r"^[ \t]*\[[ \t]*features[ \t]*\][ \t]*(#.*)?$", re.M)
TABLE = re.compile(r"^[ \t]*\[", re.M)

shims = githooks.shims

def install_line(version: str) -> str:
    """The command that installs the pinned Forge (the pin refusal's own Next line)."""
    return repo.REFUSALS["pin"][1].format(pinned="v" + version.removeprefix("v"))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def write_file(top: Path, rel: str, text: str) -> None:
    """Write a repo file with LF line endings, never through a link that leads outside the repo."""
    path = top / rel
    if not path.resolve().is_relative_to(top.resolve()):
        repo.refuse(REFUSALS["outside"], path=rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _span(text: str, rel: str) -> tuple[int, int]:
    """Where the Forge block starts and ends in the text, or (-1, -1) when there is none."""
    start, end = text.find(BEGIN), text.find(END)
    if start == end == -1:
        return -1, -1
    if not 0 <= start < end or text.count(BEGIN) + text.count(END) != 2:
        repo.refuse(REFUSALS["bad_block"], path=rel)
    return start, end + len(END)


def _block(top: Path, rel: str, template: str) -> str:
    """The file with its Forge block replaced, or appended when it has none."""
    text = read(top / rel)
    block = f"{BEGIN}\n{(TEMPLATES / template).read_text(encoding='utf-8').rstrip()}\n{END}"
    start, end = _span(text, rel)
    if start == -1:
        return f"{text.rstrip()}\n\n{block}\n" if text.strip() else f"{block}\n"
    return text[:start] + block + text[end:]


def _claude(top: Path) -> str:
    """CLAUDE.md without the Forge block an older Forge wrote; "" means delete it.

    Claude Code reads AGENTS.md by itself when there is no CLAUDE.md. A CLAUDE.md with content of
    the repo's own stays, and keeps an @AGENTS.md line, since Claude Code reads it instead.
    """
    text = read(top / "CLAUDE.md")
    start, end = _span(text, "CLAUDE.md")
    rest = (text if start == -1 else text[:start] + text[end:]).strip()
    if rest in ("", "@AGENTS.md"):
        return ""
    return rest + "\n" if re.search(r"^@AGENTS\.md[ \t]*$", rest, re.M) else f"{rest}\n\n@AGENTS.md\n"


def _hooks(top: Path, rel: str, events: dict[str, tuple[str | None, str]]) -> str:
    """The host's hook file with Forge's entries replaced (old Forge's too); the rest stays."""
    text = read(top / rel)
    try:
        data = json.loads(text) if text.strip() else {}
        hooks = data.setdefault("hooks", {})
        for event in list(hooks):
            groups = [{**group, "hooks": kept} for group in hooks[event]
                      if (kept := [hook for hook in group.get("hooks", [])
                                   if not FORGE_COMMAND.search(hook.get("command", ""))])]
            if groups:
                hooks[event] = groups
            else:
                del hooks[event]
        for event, (matcher, hook) in events.items():
            group: dict[str, Any] = {"hooks": [{"type": "command", "command": command(hook)}]}
            hooks.setdefault(event, []).append({"matcher": matcher, **group} if matcher else group)
    except (ValueError, AttributeError, TypeError) as exc:
        repo.refuse(REFUSALS["cant_merge"], path=rel, problem=exc)
    return json.dumps(data, indent=2) + "\n"


def _codex_config(top: Path) -> str:
    """.codex/config.toml with Codex's project hooks on; every other setting stays as it is."""
    rel = ".codex/config.toml"
    text = read(top / rel)
    if not text.strip():
        return CODEX_CONFIG
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        repo.refuse(REFUSALS["cant_merge"], path=rel, problem=exc)
    features = data.get("features")
    if isinstance(features, dict) and features.get("hooks") is True:
        return text
    # ponytail: stdlib has no TOML writer, so edit one line as text, then require the result to
    # parse to the same settings plus hooks = true. Anything else (features as dotted keys or an
    # inline table, a quoted or multi-line hooks value) refuses instead of guessing.
    merged, header = "", FEATURES.search(text)
    if features is None:
        merged = f"{text.rstrip()}\n\n{CODEX_CONFIG}"
    elif isinstance(features, dict) and header:
        after = TABLE.search(text, header.end())
        end = after.start() if after else len(text)
        table = text[header.end():end]
        line = re.search(r"^[ \t]*hooks[ \t]*=.*$", table, re.M)
        table = (table[:line.start()] + "hooks = true" + table[line.end():] if line
                 else "\nhooks = true" + table)
        merged = text[:header.end()] + table + text[end:]
    try:
        safe = bool(merged) and tomllib.loads(merged) == {
            **data, "features": {**(features or {}), "hooks": True}}
    except tomllib.TOMLDecodeError:
        safe = False
    if not safe:
        repo.refuse(REFUSALS["cant_merge"], path=rel,
                    problem="Forge can't safely set hooks = true in its [features] table")
    return merged


def _synced_text(source: str, packaged: str) -> str:
    """Read the checkout's copy in editable installs, or the bundled copy in built installs."""
    checked_in = SOURCE / source
    return (checked_in if checked_in.is_file() else TEMPLATES / packaged).read_text(encoding="utf-8")


def files(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    """Every committed file sync writes: repo-relative path -> its text for this checkout."""
    wanted: dict[str, str] = {}
    for info in pkgutil.iter_modules(forge.__path__):
        if info.ispkg:
            continue
        source = Path(info.module_finder.path) / f"{info.name}.py"
        if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "ships"
                   for node in ast.parse(source.read_text(encoding="utf-8")).body):
            continue
        module = importlib.import_module(f"forge.{info.name}")
        for rel, text in module.ships(top, cfg).items():
            if rel in wanted:
                raise ValueError(f"shipped twice: {rel}")
            wanted[rel] = text
    return wanted


def write(top: Path, cfg: dict[str, Any]) -> list[str]:
    """Write the files that differ from what sync makes; returns them. Never on the default branch."""
    wanted = files(top, cfg)
    changed = [rel for rel, text in wanted.items() if read(top / rel) != text]
    if changed:
        repo._work_branch(top)  # the shared rule: a born default branch or a detached HEAD refuses
    for rel in changed:
        if wanted[rel]:
            write_file(top, rel, wanted[rel])
        else:
            (top / rel).unlink()
    return changed


def install_shims(top: Path, cfg: dict[str, Any]) -> bool:
    """Install the git hook shims; returns whether any changed. They are never committed.

    A hook there that isn't Forge's moves to <hook>.pre-forge, and the shim runs it first.
    """
    common = Path(repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=top))
    changed = False
    for path, text in shims(top, cfg).items():
        if path.is_symlink() and not path.resolve().is_relative_to(common.resolve()):
            repo.refuse(REFUSALS["hook_link"], path=path)
        current = read(path)
        if current != text:
            if (path.exists() or path.is_symlink()) and githooks.SHIM_MARK not in current:
                kept = path.with_name(f"{path.name}.pre-forge")
                if kept.exists() or kept.is_symlink():
                    repo.refuse(REFUSALS["hook_kept"], path=path, kept=kept)
                path.rename(kept)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
            changed = True
        path.chmod(0o755)
    return changed


def sync(args: argparse.Namespace) -> None:
    top = repo.root()
    cfg = repo.config(top)
    changed = write(top, cfg)
    for rel in changed:
        print(f"Wrote {rel}")
    if install_shims(top, cfg):
        print("Installed the git hooks that check each commit and push.")
    elif not changed:
        print(f"Nothing to change: the adapters and git hooks already match Forge {cfg['version']}.")
