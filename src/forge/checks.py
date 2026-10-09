"""Waiting through gh for every check on the pull request's head commit.

Every check on the head must be green, and each check forge.toml names must be there and succeed.
A check forge.toml doesn't name also passes when GitHub skipped it or called it neutral, as
GitHub's own merge box does (a job that runs only on tags is skipped on every pull request). A
named check that hasn't reported, or a GitHub API error, is "not green yet" with the reason.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from forge import repo

REFUSALS = {
    "red": ("Checks failed on the pull request: {names}.", "forge work {item}"),
    "not_green": ("The checks are not green yet: {reason}.", "forge close {item}"),
}
PASS, PENDING, RED, SKIPPED, QUEUED = "pass", "pending", "red", "skipped", "queued"


def wait(top: Path, item: str, sha: str, names: list[str], *, progress: bool = False) -> None:
    """Wait for green checks on sha; land renews its deadline on observed check progress."""
    # ponytail: an env override is the whole wait seam (tests set 0 to look once).
    timeout = float(os.environ.get("FORGE_CHECKS_WAIT", "1800" if progress else "600"))
    deadline = time.monotonic() + timeout
    previous = None
    queued_since = None
    printed_minute = None
    while True:
        queued = False
        try:
            seen, snapshot = _seen(top, item, sha)
            if progress and snapshot != previous:
                previous = snapshot
                deadline = time.monotonic() + timeout
            reason = _pending(item, names, seen)
            queued = any(state == QUEUED for _, state in seen)
        except repo.Refused as error:
            if not progress or error.entry is not REFUSALS["not_green"]:
                raise
            reason = str(error).split("\n", 1)[0].removeprefix("The checks are not green yet: ").rstrip(".")
        else:
            if not reason:
                return
        if queued:
            now = time.monotonic()
            if queued_since is None:
                queued_since = now
            minute = int((now - queued_since) / 60)
            if minute != printed_minute:
                print(f"Waiting: checks queued for {minute} minutes during this wait; "
                      "shared runners may be busy or no runner may match the runner setting "
                      "in forge.toml.", flush=True)
                printed_minute = minute
            # A repo cannot tell a busy shared pool from an absent runner. Zero is
            # the explicit one-look override; ordinary queue time never ends a wait.
            if timeout > 0:
                deadline = now + timeout
        else:
            queued_since = printed_minute = None
        left = deadline - time.monotonic()
        if left <= 0:
            if progress:
                reason = f"GitHub has shown no check progress for {timeout / 60:g} minutes: {reason}"
            repo.refuse(REFUSALS["not_green"], reason=reason, item=item)
        time.sleep(min(15, left))


def _pending(item: str, names: list[str], seen: list[tuple[str, str]]) -> str:
    # A matrix job reports as "tests (ubuntu-latest)", and so on; each counts as its named
    # check, and every one must pass. Checks forge.toml doesn't name go by their own name.
    groups: dict[str, list[str]] = {want: [] for want in names}
    for name, state in seen:
        matches = [want for want in names if name == want or name.startswith(want + " (")]
        if state == SKIPPED:
            state = RED if matches else PASS
        for want in matches or [name]:
            groups.setdefault(want, []).append(state)
    red, missing, pending = [], [], []
    for want, states in groups.items():
        if not states:
            missing.append(want)
        elif RED in states:  # failed, cancelled or timed out (a named one skipped too): red
            red.append(want)
        elif PENDING in states or QUEUED in states:
            pending.append(want)
    if red:
        repo.refuse(REFUSALS["red"], names=", ".join(red), item=item)
    return "; ".join([f"{name} has not reported" for name in missing]
                     + [f"{name} is still {'running' if PENDING in groups[name] else 'queued'}"
                        for name in pending])


def queued_reason(top: Path, sha: str, item: str = "") -> str:
    """Doctor diagnoses old unmet demand, including jobs GitHub already expired."""
    runs = _ask(top, item, ".workflow_runs",
                "repos/{owner}/{repo}/actions/runs?per_page=100")
    now = datetime.fromisoformat(repo.now())
    since = now - timedelta(days=7)
    runner = repo.config(top)["runner"]
    old_demand = current_demand = False
    for run in runs:
        heads = [pr.get("head", {}).get("sha") for pr in run.get("pull_requests") or []]
        jobs = _ask(top, item, ".jobs",
                    f"repos/{{owner}}/{{repo}}/actions/runs/{run['id']}/jobs?filter=all")
        for job in jobs:
            if not any(runner.casefold() == label.casefold() for label in job.get("labels") or []):
                continue
            if job.get("runner_id"):
                if job.get("status") not in ("in_progress", "completed"):
                    continue
                try:
                    started = datetime.fromisoformat(job["started_at"])
                    if started <= now and (since <= started or job["status"] == "in_progress"):
                        return ""
                    finished = datetime.fromisoformat(job["completed_at"])
                    if started <= finished <= now and since <= finished:
                        return ""
                except (KeyError, ValueError, TypeError):
                    pass
                continue
            if job.get("status") == "queued":
                # Fresh retries must not inherit the original run's age.
                observed = job.get("started_at") or run.get(
                    "updated_at" if run.get("run_attempt", 1) > 1 else "created_at")
            elif (job.get("status") == "completed"
                  and job.get("conclusion") in ("failure", "cancelled", "timed_out")):
                observed = job.get("completed_at")
            else:
                continue
            try:
                observed = datetime.fromisoformat(observed)
                if observed > now:
                    continue
                old_demand |= observed <= since
                current_demand |= sha in [run.get("head_sha"), *heads]
            except (ValueError, TypeError):
                continue
    if old_demand and current_demand:
        return ("Runner demand has gone unmet for at least seven days: "
                "likely missing runner; no job in this repo using "
                f"runner = {json.dumps(runner)} in forge.toml has run in the last seven days")
    return ""


def _seen(top: Path, item: str, sha: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Check outcomes on sha and the fields that show a run starting, ending or being replaced."""
    # Every page: a failed matrix job on page two must still count.
    endpoint = f"repos/{{owner}}/{{repo}}/commits/{sha}"
    runs = _ask(top, item, ".check_runs", f"{endpoint}/check-runs?per_page=100")
    statuses = _ask(top, item, ".statuses", f"{endpoint}/status?per_page=100")
    # Ignore earlier pushes for both readiness and progress; GitHub's ordering is not progress.
    runs = [run for run in runs if run.get("head_sha", sha) == sha]
    snapshot = sorted(json.dumps([entry.get(field) for field in fields])
                      for entries, fields in (
                          (runs, ("id", "name", "status", "conclusion", "started_at", "completed_at")),
                          (statuses, ("id", "context", "state", "created_at")))
                      for entry in entries)
    seen = ([(str(run.get("name")), QUEUED if run.get("status") == "queued"
              else PENDING if run.get("status") != "completed"
              else PASS if run.get("conclusion") == "success"
              else SKIPPED if run.get("conclusion") in ("skipped", "neutral") else RED)
             for run in runs]
            + [(str(status.get("context")), {"success": PASS, "pending": PENDING}.get(
                status.get("state"), RED)) for status in statuses])
    return seen, snapshot


def _ask(top: Path, item: str, field: str, endpoint: str) -> list[dict[str, Any]]:
    # --paginate with "<field>[]" prints one JSON object per line across all pages.
    done = repo.run("gh", "api", "--paginate", "--jq", f"{field}[]", endpoint, cwd=top)
    try:
        text = done.stdout.strip()
        found = (json.loads(text) if text.startswith("[")
                 else [json.loads(line) for line in text.splitlines() if line.strip()]
                 ) if done.returncode == 0 else None
    except ValueError:
        found = None
    if not isinstance(found, list) or not all(isinstance(entry, dict) for entry in found):
        said = (done.stderr.strip() or done.stdout.strip() or "no readable answer").splitlines()[-1]
        reason = said if said.startswith("GitHub did not answer.") else f"GitHub did not answer: {said.rstrip('.')}"
        repo.refuse(REFUSALS["not_green"], reason=reason.rstrip("."),
                    item=item)
    return found
