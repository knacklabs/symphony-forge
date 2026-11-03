"""Ship the pinned, licensed design skills to both client agent hosts."""
from pathlib import Path
from typing import Any


def ships(top: Path, cfg: dict[str, Any]) -> dict[str, str]:
    from forge import sync

    if cfg.get("repo") != "client":
        return {}
    source = sync.TEMPLATES / "skills"
    return {f"{host}/skills/{path.relative_to(source).as_posix()}":
            path.read_bytes().decode("utf-8")
            for name in ("impeccable", "emil-design-eng")
            for path in sorted((source / name).rglob("*")) if path.is_file()
            for host in (".claude", ".codex")}
