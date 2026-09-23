"""Repository-kind discriminator shared by Forge gate machinery."""
from __future__ import annotations

import os
from pathlib import Path


ORCHESTRATION_PREFIXES = (
    "plans/", "docs/", ".gstack/", "prototype/",
)
CLIENT_MACHINERY_PREFIXES = (
    "factory/", "constitution/", "harness/", ".claude/", ".codex/",
)
ORCHESTRATION_FILES = {
    "README.md", ".gitignore", ".gitattributes", ".envrc",
    ".factory/scratchpad.md",
}


def is_harness_source_repo(root: Path) -> bool:
    """Return whether root is the Symphony Forge source repository."""
    return (root / ".factory" / "harness-source.json").exists()


def locked_repo_path(
    raw: str, root: Path, *, harness_source: bool | None = None,
) -> str | None:
    """Return a canonical locked repo path, or None for an exempt surface."""
    rel = _lexical_repo_path(raw, root)
    if rel is None:
        return None
    source_repo = (
        is_harness_source_repo(root) if harness_source is None else harness_source
    )
    root_path = Path(os.path.abspath(root))
    candidate = root_path / rel
    lexical_locked = _is_locked_path(rel, source_repo)

    current = root_path
    has_symlink = False
    for part in Path(rel).parts:
        current /= part
        if current.is_symlink():
            has_symlink = True
            break
    if not has_symlink:
        return rel if lexical_locked else None

    # A symlink at any point can make the lexical prefix misleading. Resolve
    # only linked paths; missing leaves and other failures lock the lexical path.
    try:
        resolved_root = root_path.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        resolved_rel = resolved.relative_to(resolved_root).as_posix()
    except (OSError, RuntimeError, ValueError):
        # Outside targets, loops, and other resolution failures fail closed.
        return rel

    if lexical_locked:
        return rel
    if _is_locked_path(resolved_rel, source_repo):
        return resolved_rel
    return None


def _lexical_repo_path(raw: str, root: Path) -> str | None:
    """Normalize a repo path without following symlinks or shell expansions."""
    if not raw or raw == "-":
        return None
    root_path = Path(os.path.abspath(root))
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root_path / candidate
    candidate = Path(os.path.abspath(candidate))
    try:
        rel = candidate.relative_to(root_path).as_posix()
    except ValueError:
        return None
    return rel or None


def _is_locked_path(rel: str, source_repo: bool) -> bool:
    if rel in ORCHESTRATION_FILES:
        return False
    exempt_prefixes = ORCHESTRATION_PREFIXES
    if not source_repo:
        exempt_prefixes += CLIENT_MACHINERY_PREFIXES
    return not any(rel == prefix.rstrip("/") or rel.startswith(prefix)
                   for prefix in exempt_prefixes)
