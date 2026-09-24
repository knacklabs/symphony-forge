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
    literal: bool = False,
) -> str | None:
    """Return a canonical locked repo path, or None for an exempt surface."""
    if not raw or raw == "-":
        return None
    if not literal and any(char in raw for char in "$`"):
        return None
    source_repo = (
        is_harness_source_repo(root) if harness_source is None else harness_source
    )
    root_path = Path(os.path.abspath(root))
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root_path / candidate
    lexical_rel = _lexical_repo_path(raw, root)

    has_symlink = False
    unresolved_symlink = False
    resolution_failed = False
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        if current.is_symlink():
            has_symlink = True
            try:
                current.resolve(strict=True)
            except (OSError, RuntimeError):
                unresolved_symlink = True

    try:
        resolved_root = root_path.resolve(strict=False)
        resolved = candidate.resolve(strict=False)
        resolved_rel = resolved.relative_to(resolved_root).as_posix()
    except ValueError:
        resolved_rel = None
    except (OSError, RuntimeError):
        resolved_rel = None
        resolution_failed = True

    # A changed lexical symlink and its target are separate write identities.
    # Keep the lexical name when resolving its linked path cannot prove an
    # in-repo target, including links whose ancestors lead outside the repo.
    if has_symlink and (unresolved_symlink or resolution_failed):
        if lexical_rel is not None:
            return lexical_rel
        return candidate.as_posix()
    if has_symlink and resolved_rel is None and lexical_rel is not None:
        return lexical_rel

    lexical_locked = (
        lexical_rel is not None and _is_locked_path(lexical_rel, source_repo)
    )
    resolved_locked = (
        resolved_rel is not None and _is_locked_path(resolved_rel, source_repo)
    )
    if lexical_locked:
        return lexical_rel
    if resolved_locked:
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
