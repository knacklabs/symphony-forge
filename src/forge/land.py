"""forge land: build a started task or fix, close it, run fix rounds, then merge or hand it off.

Each step is the existing command, run in-process, so a rerun continues from what the records show.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from forge import checks, close, merge, repo, worker

ROUNDS = 3
# Close runs in a row while the checks are still running, before land stops with close's refusal.
WAITS = 3
FINDINGS, FAILING = "the review's serious findings", "the failing checks"
REFUSALS: dict[str, tuple[str, str]] = {}


def land(args: argparse.Namespace) -> int:
    item = args.item
    match = repo.ITEM.fullmatch(item)
    if not match or not (match["task"] or match["fix"]):
        repo.refuse(repo.REFUSALS["bad_item"], item=item)
    if item == merge.ENABLE:
        repo.refuse(merge.REFUSALS["owner_merges"], item=item)
    top = close._worktree(item)
    state = repo.read_state(item, top) or {}
    branch = repo.current_branch(top)
    limited = False
    try:
        if _is_merged(top, branch):
            _step(f"Closing {item}.")
            close.close(_close_args(item))
            return _after_merged(top, item, state)
        status = state.get("status", "started")
        if state.get("kind") not in ("story-done", "migrate", "adopt") and (
                status == "started" or status == "working" and
                repo.git("log", "-1", "--format=%s", cwd=top) == f"{item} is working"):
            _step(f"Building {item}.")
            worker.work(_work_args(item))
        rounds = waits = 0
        while True:
            _step(f"Closing {item}.")
            try:
                close.close(_close_args(item))
                break
            except repo.Refused as error:
                if error.entry is checks.REFUSALS["not_green"] and waits < WAITS - 1:
                    waits += 1
                    _step("Checks are still running on the pushed head; waiting again.")
                    continue
                if error.entry is checks.REFUSALS["red"] and _rerun(top, item, branch):
                    waits = 0
                    continue
                what = (FINDINGS if error.entry is close.REFUSALS["blocked"] else
                        FAILING if error.entry is checks.REFUSALS["red"] and worker._failing(branch)
                        else "")
                if not what:
                    raise
                if rounds == ROUNDS:
                    _step(f"Stopped after {ROUNDS} fix rounds: {item} still has {what}.")
                    limited = True
                    raise
                rounds, waits = rounds + 1, 0
                _step(f"Fix round {rounds} of {ROUNDS}: the worker fixes {what}.")
                worker.work(_work_args(item))
        if _is_merged(top, branch):  # merged on GitHub while close ran: close said so already
            return _after_merged(top, item, state)
        if close.merger(top, state) == "agent":
            _step(f"Merging {item}.")
            return merge.merge(argparse.Namespace(item=item))
        url = json.loads(close._gh(top, "pr", "view", branch, "--json", "url"))["url"]
        _step(f"{item} is ready; a human merges its pull request: {url}")
        return 0
    except repo.Refused as error:
        if not limited:
            _step(f"Stopped: {item} needs you.")
        raise


def _rerun(top: Path, item: str, branch: str) -> bool:
    """Re-run a failed check whose failure isn't this change's; CHECKS builds it."""
    return False


def _after_merged(top: Path, item: str, state: dict[str, Any]) -> int:
    """Finish Forge's tidy-up when the agent merges here and the item was recorded ready."""
    try:
        receipt = json.loads(repo.ready_path(item, top).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        receipt = {}
    if (isinstance(receipt, dict) and receipt.get("review") == "clean"
            and receipt.get("tidied") is not True and close.merger(top, state) == "agent"):
        _step(f"Merging {item}.")
        return merge.merge(argparse.Namespace(item=item))
    return 0


def _is_merged(top: Path, branch: str) -> bool:
    return (close._pull_request(top, branch) or {}).get("state") == "MERGED"


def _close_args(item: str) -> argparse.Namespace:
    return argparse.Namespace(item=item, dismiss=None, because=None)


def _work_args(item: str) -> argparse.Namespace:
    return argparse.Namespace(item=item, note=None)


def _step(line: str) -> None:
    print(line, flush=True)


COMMANDS = [{
    "words": "land", "run": "land", "changes_state": True,
    "help": "Build, close, fix and merge a task or fix",
    "args": [(('item',), {})], "position": 165,
    "listing": "| `forge land <item>` | Builds, closes, runs fix rounds and merges a task or fix "
               "where the repo allows agent merges; run it in the background |",
}]
