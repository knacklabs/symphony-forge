"""Machines that run a repo's work besides this laptop: the record of the one this clone uses."""
import json
from pathlib import Path
from types import ModuleType
from typing import Any

from forge import box_ssh, repo


class ProviderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


PROVIDERS = {"ssh": box_ssh}


def provider(name: str) -> ModuleType:
    return PROVIDERS[name]


def _file(top: Path) -> Path:
    return repo.forge_dir(top) / "box.json"  # shared by every worktree of one clone, never committed


def record(top: Path) -> dict[str, Any] | None:
    try:
        return json.loads(_file(top).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(top: Path, saved: dict[str, Any] | None) -> None:
    if saved is None:
        _file(top).unlink(missing_ok=True)
    else:
        _file(top).write_text(json.dumps(saved), encoding="utf-8")


def command(top: Path, args: Any) -> int:
    """`forge lanes --box setup|off`."""
    if args.box == "setup":
        repo.check_pin(top, words="lanes")
        cfg = repo.config(top)
        if cfg["boxes"] == "off":
            raise repo.Refused("This repo's forge.toml has boxes = \"off\", so Forge runs no work on another machine.",
                               "ask the owner, then turn it on in a settings fix: boxes = \"ssh\" for a machine you own")
        return provider(cfg["boxes"]).setup(top, args)
    saved = record(top)
    if saved is None:
        print("This clone has nothing set up on another machine, so there is nothing to delete.")
        return 0
    return provider(saved["provider"]).off(top, saved, args.yes)
