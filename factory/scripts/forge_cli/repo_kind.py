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
    if _is_locked_path(rel, source_repo):
        return rel

    # Preserve callers' protection for a docs-side symlink into product code,
    # while judging both names lexically instead of resolving through links.
    root_path = Path(os.path.abspath(root))
    candidate = root_path / rel
    if candidate.is_symlink():
        target = Path(os.readlink(candidate))
        if not target.is_absolute():
            target = candidate.parent / target
        target_rel = _lexical_repo_path(str(target), root_path)
        if target_rel is not None and _is_locked_path(target_rel, source_repo):
            return target_rel
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
