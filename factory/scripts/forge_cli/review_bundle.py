"""What the one reviewer is sent: the task diff without lock and generated
noise, sized against the tool's prompt limit (decisions 0078, 0081).

The reviewer tool refuses a prompt over 512 KB. Decision 0078 dealt such a
diff into file groups, each reviewed alone with the whole tree readable. On
WF-BIO-1 T4 (2026-09-18) the review brief grew to 472 KB, the capacity left
for the diff went to nothing, and the same 187 KB diff that had been seven
groups became fifty one-file groups; a reviewer holding one file cannot see
the tests that prove a contract, so it reported eight contracts "partial"
that had passed an hour earlier. Decision 0081 removes grouping: a prompt
that does not fit is refused with its composition, so the operator excludes
generated files, trims what the brief carries, or splits the task.

What stays from 0078: lock and generated files add bytes and nothing to
judge, so they are put back to the task base in the review tip; they still
ship and stay in scope. `FORGE_REVIEW_PROMPT_BYTES` lowers the limit for
probes and tests (the older `FORGE_REVIEW_SPLIT_BYTES` is still read).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .common import fail
from .tasks import _git, _require_git

# The reviewer tool's MAX_REVIEW_PROMPT_BYTES is 512,000; forge stops a
# little under it so the tool never has to chunk what forge sent.
REVIEW_PROMPT_BYTES = 480_000
PROMPT_ENV = "FORGE_REVIEW_PROMPT_BYTES"
LEGACY_PROMPT_ENV = "FORGE_REVIEW_SPLIT_BYTES"
# Prompt bytes the tool adds around the brief, dataset and bundle.
PROMPT_SLACK = 8_000
# Files that add bytes to a bundle and nothing to a review. Put back to the
# task base in every review tip; they still ship in the PR and stay in scope.
REVIEW_NOISE_NAMES = frozenset({
    "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "npm-shrinkwrap.json",
    "Cargo.lock", "poetry.lock", "uv.lock", "Pipfile.lock", "Gemfile.lock",
    "composer.lock", "go.sum", "flake.lock",
})
REVIEW_NOISE_SUFFIXES = (".min.js", ".min.css", ".map", ".snap", ".lock")
REVIEW_NOISE_DIRS = ("__snapshots__/", "generated/", "__generated__/")


def review_prompt_limit() -> int:
    for name in (PROMPT_ENV, LEGACY_PROMPT_ENV):
        raw = os.environ.get(name, "").strip()
        if raw.isdigit() and int(raw) > 0:
            return int(raw)
    return REVIEW_PROMPT_BYTES


def is_review_noise(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (name in REVIEW_NOISE_NAMES
            or name.endswith(REVIEW_NOISE_SUFFIXES)
            or any(f"/{marker}" in f"/{path}" for marker in REVIEW_NOISE_DIRS))


def restore_paths_to_base(worktree: Path, base_sha: str, paths: list[str],
                          message: str) -> str:
    """Put `paths` back to the task base in the detached worktree and commit;
    return the new tip. A path that did not exist at the base is dropped."""
    for rel in paths:
        at_base = _git(worktree, "cat-file", "-e", f"{base_sha}:{rel}").returncode == 0
        if at_base:
            _require_git(worktree, f"restoring {rel} to the task base",
                         "checkout", base_sha, "--", rel)
        else:
            _require_git(worktree, f"dropping {rel} from the review tip",
                         "rm", "-q", "--cached", "--", rel)
            path = worktree / rel
            if path.is_file():
                path.unlink()
    _require_git(worktree, "committing the review tip",
                 "-c", "user.name=forge-review", "-c", "user.email=forge-review@local",
                 "commit", "-q", "--no-verify", "--allow-empty", "-m", message)
    return _require_git(worktree, "resolving the review tip", "rev-parse", "HEAD")


def diff_bytes_by_path(worktree: Path, base_sha: str) -> dict[str, int]:
    """Patch bytes per changed path, base..HEAD, in git's own order."""
    proc = _git(worktree, "-c", "core.pager=cat", "diff", "--no-color",
                "--no-ext-diff", f"{base_sha}..HEAD")
    if proc.returncode != 0:
        fail("listing the review diff failed: " + (proc.stderr.strip() or "git diff"))
    sizes: dict[str, int] = {}
    current = None
    for line in proc.stdout.split("\n"):
        if line.startswith("diff --git "):
            match = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            current = match.group(2) if match else None
            if current is not None:
                sizes.setdefault(current, 0)
        if current is not None:
            sizes[current] += len(line.encode("utf-8", "surrogateescape")) + 1
    return sizes
