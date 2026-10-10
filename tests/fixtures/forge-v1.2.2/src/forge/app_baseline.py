"""Ship the default client app skill to both agent hosts."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def ships(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    from forge import sync

    skill = sync._synced_text(".codex/skills/app-baseline/SKILL.md",
                              "skills/app-baseline/SKILL.md")
    return {f"{host}/skills/app-baseline/SKILL.md": skill
            for host in (".claude", ".codex")}
