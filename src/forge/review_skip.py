"""A person's review skip, bounded to this item's reviewed changes."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from forge import repo, review, sync

REFUSALS = {
    "bad_skip": ("A review skip needs a person's name and reason, without dismissals or a review-loop choice.",
                 'forge close {item} --no-review --by "<name>" --reason "<why>"'),
    "skip_worker": ("Only a person can skip the model review; a worker does not.",
                    'the person runs forge close {item} --no-review --by "<name>" --reason "<why>"'),
    "skip_blocked": ("A review already blocked {item}, so the model review cannot be skipped.",
                     "forge work {item}, then forge close {item} the normal way"),
}


def requested(args: argparse.Namespace, top: Path, item: str,
              state: dict[str, Any]) -> dict[str, str] | None:
    enabled, by = getattr(args, "no_review", False), getattr(args, "by", None)
    if not enabled:
        if by is not None:
            repo.refuse(REFUSALS["bad_skip"], item=item)
        return None
    if os.environ.get("FORGE_WORKER"):
        repo.refuse(REFUSALS["skip_worker"], item=item)
    reason = getattr(args, "reason", None)
    if (not by or not by.strip() or not reason or not reason.strip() or
            args.dismiss or args.because or getattr(args, "resolve", None)):
        repo.refuse(REFUSALS["bad_skip"], item=item)
    # Committed rounds survive another clone. Dismissal and acceptance cannot
    # erase a block, including one merged from another machine's branch history.
    history = review._history(top, item, "", state.get("review") or {}, include_merged=True)
    if any(review.blocking({**result, "dismissals": []}) for result in history):
        repo.refuse(REFUSALS["skip_blocked"], item=item)
    return {"by": " ".join(by.split())[:200], "reason": " ".join(reason.split())[:200]}


def label(result: dict[str, Any], *, reason: bool = False) -> str:
    skipped = result.get("skipped")
    if not skipped:
        return result.get("status", result.get("outcome", "finished"))
    return f"skipped by {skipped['by']}" + (f": {skipped['reason']}" if reason else "")


def readiness(result: dict[str, Any]) -> str:
    return (f"no model review (skipped by {result['skipped']['by']})"
            if result.get("skipped") else "a clean review")


def _modes_kept(top: Path, base: str, head: str) -> bool:
    """Every changed file has the mode forge sync gives it: a launcher is executable (sync's chmod
    sets no executable bit on Windows, where git records 100644), any other file keeps its mode
    or, when new, is 100644."""
    rows = repo.git("diff", "--raw", "-z", "--no-renames", base, head, cwd=top).split("\0")
    for meta, path in zip(rows[::2], rows[1::2]):
        old, new = meta[1:].split()[:2]
        expected = ("100755" if path in sync.EXECUTABLE and os.name != "nt"
                    else old if old != "000000" else "100644")
        if new not in ("000000", expected):
            return False
    return True


def upgrade_only(top: Path, item: str, cfg: dict[str, Any], base: str, head: str, files: list[str],
                 previous: dict[str, Any]) -> bool:
    """True when this is the fix forge upgrade made and its branch changed only the value of
    forge.toml's version line, its own record and files exactly as forge sync writes them (content
    and mode), and no earlier review of it still blocks. Anything else, or any error, gets the
    model review. An item that is not named like an upgrade fix costs no git call."""
    from forge import upgrade  # upgrade imports close, which imports this module

    if not item.startswith(upgrade.PREFIX) or review.blocking(previous):
        return False
    release = item.removeprefix(upgrade.PREFIX).replace("-", ".")

    def blob(ref: str, path: str) -> str:  # bytes, so a changed comment or line ending shows
        return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=top, capture_output=True,
                              check=True).stdout.decode("utf-8")

    try:
        if not upgrade.made(item, json.loads(blob(head, repo.state_path(item))), release):
            return False
        old, new = blob(base, "forge.toml"), blob(head, "forge.toml")
        if (tomllib.loads(new).get("version") != release or tomllib.loads(old).get("version") == release
                or repo.set_version(old, release) != new or not _modes_kept(top, base, head)):
            return False
        rest = set(files) - {"forge.toml", repo.state_path(item)}
        return rest <= sync.synced(top, cfg, base, head, sorted(rest))
    except Exception:  # noqa: BLE001 - a comparison that cannot be made means a normal review
        return False
