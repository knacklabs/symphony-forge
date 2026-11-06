"""A person's review skip, bounded to this item's reviewed changes."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from forge import repo, review

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
    # erase the fact that a round held the review bar.
    history = review._history(top, item, "", state.get("review") or {})
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
