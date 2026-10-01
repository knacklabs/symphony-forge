"""forge land: build a started task or fix, close it, run fix rounds, then merge or hand it off.

Each step is the existing command, run in-process, so a rerun continues from what the records show.
"""
from __future__ import annotations

import argparse
import json
from functools import partial
from pathlib import Path

from forge import checks, close, merge, repo, worker

ROUNDS = 3
REFUSALS: dict[str, tuple[str, str]] = {}
say = partial(print, flush=True)


def land(args: argparse.Namespace) -> int:
    item = args.item
    match = repo.ITEM.fullmatch(item)
    if not match or not (match["task"] or match["fix"]):
        repo.refuse(repo.REFUSALS["bad_item"], item=item)
    if item == merge.ENABLE:
        repo.refuse(merge.REFUSALS["owner_merges"], item=item)
    top = close._worktree(item)
    state, branch = repo.read_state(item, top) or {}, repo.current_branch(top)
    step = argparse.Namespace(item=item, dismiss=None, because=None)  # for close and work alike
    rounds = waits = 0
    try:
        merged = _merged(top, branch)
        status = state.get("status", "started")
        if not merged and state.get("kind") not in ("story-done", "migrate", "adopt") and (
                status == "started" or status == "working" and
                repo.git("log", "-1", "--format=%s", cwd=top) == f"{item} is working"):
            say(f"Building {item}.")
            worker.work(step)
        while True:
            say(f"Closing {item}.")
            try:
                close.close(step)
            except repo.Refused as error:
                if error.entry is checks.REFUSALS["not_green"] and waits < 2:
                    waits += 1
                    say("Checks are still running on the pushed head; waiting again.")
                    continue
                red = error.entry is checks.REFUSALS["red"]
                if red and _rerun(top, item, branch):
                    continue
                what = ("the review's serious findings" if error.entry is close.REFUSALS["blocked"]
                        else "the failing checks" if red and worker._failing(branch) else "")
                if not what:
                    raise
                if rounds == ROUNDS:
                    rounds += 1  # this stop says why itself, so no stop line
                    say(f"Stopped after {ROUNDS} fix rounds: {item} still has {what}.")
                    raise
                rounds, waits = rounds + 1, 0
                say(f"Fix round {rounds} of {ROUNDS}: the worker fixes {what}.")
                worker.work(step)
                continue
            # Merged since close looked: close again, so its merged path reports and tidies.
            if merged or not (merged := _merged(top, branch)):
                break
        if merged:  # Forge's tidy-up, where the agent merges and the item was recorded ready
            ready = repo.ready_path(item, top)
            receipt = json.loads(ready.read_text(encoding="utf-8")) if ready.is_file() else {}
            if receipt.get("review") != "clean" or receipt.get("tidied") or close.merger(top, state) != "agent":
                return 0
        elif close.merger(top, state) != "agent":
            url = json.loads(close._gh(top, "pr", "view", branch, "--json", "url"))["url"]
            say(f"{item} is ready; a human merges its pull request: {url}")
            return 0
        say(f"Merging {item}.")
        return merge.merge(argparse.Namespace(item=item))
    except repo.Refused:
        if rounds <= ROUNDS:
            say(f"Stopped: {item} needs you.")
        raise


def _rerun(top: Path, item: str, branch: str) -> bool:
    """Re-run a failed check whose failure isn't this change's; CHECKS builds it."""
    return False


def _merged(top: Path, branch: str) -> bool:
    return (close._pull_request(top, branch) or {}).get("state") == "MERGED"


COMMANDS = [{
    "words": "land", "run": "land", "changes_state": True,
    "help": "Build, close, fix and merge a task or fix",
    "args": [(('item',), {})], "position": 165,
    "listing": "| `forge land <item>` | Builds, closes, runs fix rounds and merges a task or fix "
               "where the repo allows agent merges; run it in the background |",
}]
