"""Ship the bundled Simplified Technical English skill to both agent hosts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

SKILL = "skills/simplified-technical-english"
# Only the MIT parts of the upstream skill; its word list belongs to the standard's owner.
FILES = ("SKILL.md", "LICENSE", "NOTICE.md", "references/writing-rules.md",
         "references/substitutions.md", "examples/before-after.md", "scripts/ste_check.py")


def ships(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    from forge import sync

    return {f"{host}/{SKILL}/{name}": (sync.TEMPLATES / SKILL / name).read_text(encoding="utf-8")
            for host in (".claude", ".codex") for name in FILES}
