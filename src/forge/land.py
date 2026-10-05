"""forge land: build a started task or fix, close it, run fix rounds, then merge or hand it off.

Each step is the existing command, run in-process, so a rerun continues from what the records show.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from functools import partial
from pathlib import Path

from forge import checks, close, merge, repo, review, worker

ROUNDS = 3
REFUSALS = {
    "rerun": ("GitHub has not started the re-run of {check}.", "forge land {item}"),
}
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
        start = repo.git("log", "-1", "--diff-filter=A", "--format=%H", "--",
                         repo.state_path(item), cwd=top)
        if not merged and state.get("kind") not in ("story-done", "migrate", "adopt") and (
                status == "started" and repo.git("rev-parse", "HEAD", cwd=top) == start or
                status == "working" and
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
                        else "the failing tests" if error.entry is close.REFUSALS["tests_failed"]
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
    """Re-run the pull request's failed checks once per pushed head, when every failure is a job
    whose first attempt's log names none of the change's files and this machine's tests passed on
    these committed files. Any gh call that fails means no re-run."""
    command = repo.config(top)["test"]
    passed = review.passed_record(top, command) if command else None
    marker = repo.forge_dir(top) / "reruns" / repo.git("rev-parse", "HEAD", cwd=top)
    if not (passed and passed.exists()) or marker.exists():
        return False
    try:  # gh exits non-zero when a check fails, so read what it printed either way
        listed = json.loads(repo.run("gh", "pr", "checks", branch, "--json", "name,bucket,link",
                                     cwd=top).stdout)
    except ValueError:
        return False
    failing = [check for check in listed if check.get("bucket") not in ("pass", "skipping")]
    default = repo.default_branch(top)
    changed = [path for path in repo.git("diff", "--name-only", "-z", "--no-renames",
                                         f"origin/{default}...HEAD", cwd=top).split("\0") if path]
    runs: dict[str, list[str]] = {}
    for check in failing:
        job = re.search(r"/runs/(\d+)/job/(\d+)", check.get("link") or "")
        if check.get("bucket") != "fail" or not job:
            return False
        if job[1] not in runs and _attempt(top, job[1]) != 1:
            return False
        log = repo.run("gh", "run", "view", "--job", job[2], "--log-failed", cwd=top)
        if log.returncode or any(path in log.stdout or path.replace("/", "\\") in log.stdout
                                 for path in changed):
            return False
        runs.setdefault(job[1], []).append(check.get("name", "a check"))
    if not runs:
        return False
    marker.parent.mkdir(exist_ok=True)
    marker.touch()
    for names in runs.values():
        for name in names:
            say(f"Re-running {name} once: its failure names none of this change's files and the "
                "tests passed here.")
    for run in runs:
        if repo.run("gh", "run", "rerun", run, "--failed", cwd=top).returncode:
            return False
    # ponytail: FORGE_CHECKS_WAIT is the wait seam, as in checks.wait (tests set 0 to look once).
    deadline = time.monotonic() + float(os.environ.get("FORGE_CHECKS_WAIT", "600"))
    for run, names in runs.items():
        while (_attempt(top, run) or 0) <= 1:
            left = deadline - time.monotonic()
            if left <= 0:
                repo.refuse(REFUSALS["rerun"], check=", ".join(names), item=item)
            time.sleep(min(15, left))
    return True


def _attempt(top: Path, run: str) -> int | None:
    """The run's latest attempt number, or None when gh can't say."""
    done = repo.run("gh", "run", "view", run, "--json", "attempt", cwd=top)
    try:
        attempt = json.loads(done.stdout).get("attempt") if not done.returncode else None
    except (ValueError, AttributeError):
        return None
    return attempt if isinstance(attempt, int) else None


def _merged(top: Path, branch: str) -> bool:
    return (close._pull_request(top, branch) or {}).get("state") == "MERGED"


COMMANDS = [{
    "words": "land", "run": "land", "changes_state": True,
    "help": "Build, close, fix and merge a task or fix",
    "args": [(('item',), {})], "position": 165,
    "listing": "| `forge land <item>` | Builds, closes, runs fix rounds and merges a task or fix "
               "where the repo allows agent merges; run it in the background |",
}]
