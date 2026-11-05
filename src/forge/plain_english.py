"""Ship bundled writing and security audit skills to both agent hosts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

SKILL = "skills/simplified-technical-english"
# Only the MIT parts of the upstream skill; its word list belongs to the standard's owner.
FILES = ("SKILL.md", "LICENSE", "NOTICE.md", "references/writing-rules.md",
         "references/substitutions.md", "examples/before-after.md", "scripts/ste_check.py")


def ships(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    from forge import sync

    paths = [sync.TEMPLATES / SKILL / name for name in FILES]
    paths.extend(sorted((sync.TEMPLATES / "skills/security-audit").rglob("*")))
    return {f"{host}/{path.relative_to(sync.TEMPLATES).as_posix()}":
            path.read_bytes().decode("utf-8")
            for host in (".claude", ".codex") for path in paths if path.is_file()}
