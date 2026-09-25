"""Waiting through gh for the checks forge.toml names, on the pull request's head commit.

Every named check must succeed. Any check that fails, is cancelled or times out is red. A named
check that hasn't reported, or a GitHub API error, is "not green yet" with the reason.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from forge import repo

REFUSALS = {
    "red": ("Checks failed on the pull request: {names}.", "forge work {item}"),
    "not_green": ("The checks are not green yet: {reason}.", "forge close {item}"),
}
PASS, FINE, PENDING, RED = "pass", "fine", "pending", "red"


def wait(top: Path, item: str, sha: str, names: list[str]) -> None:
    """Return once every named check passed on sha; refuse when one is red or time runs out."""
    # ponytail: an env override is the whole wait seam (tests set 0 to look once).
    deadline = time.monotonic() + float(os.environ.get("FORGE_CHECKS_WAIT", "600"))
    while True:
        seen = _seen(top, item, sha)
        red = [name for name, state in seen if state == RED]
        missing, pending = [], []
        for want in names:
            # A matrix job reports as "tests (ubuntu-latest)", and so on; every one must pass.
            states = [state for name, state in seen if name == want or name.startswith(want + " (")]
            if not states:
                missing.append(want)
            elif PENDING in states:
                pending.append(want)
            elif any(state != PASS for state in states):
                red.append(want)  # a skipped required check never turns green
        if red:
            repo.refuse(REFUSALS["red"], names=", ".join(dict.fromkeys(red)), item=item)
        if not missing and not pending:
            return
        left = deadline - time.monotonic()
        if left <= 0:
            reason = "; ".join(
                [f"{name} has not reported" for name in missing]
                + [f"{name} is still running" for name in pending])
            repo.refuse(REFUSALS["not_green"], reason=reason, item=item)
        time.sleep(min(15, left))


def _seen(top: Path, item: str, sha: str) -> list[tuple[str, str]]:
    """Each check run and commit status on sha, as (name, pass/fine/pending/red)."""
    # ponytail: one page of 100 check runs and 100 statuses per commit; page when a repo has more.
    endpoint = f"repos/{{owner}}/{{repo}}/commits/{sha}"
    runs = _ask(top, item, ".check_runs", f"{endpoint}/check-runs?per_page=100")
    statuses = _ask(top, item, ".statuses", f"{endpoint}/status?per_page=100")
    conclusions = {"success": PASS, "skipped": FINE, "neutral": FINE}
    return ([(str(run.get("name")), PENDING if run.get("status") != "completed"
              else conclusions.get(run.get("conclusion"), RED)) for run in runs]
            + [(str(status.get("context")), {"success": PASS, "pending": PENDING}.get(
                status.get("state"), RED)) for status in statuses])


def _ask(top: Path, item: str, field: str, endpoint: str) -> list[dict[str, Any]]:
    done = repo.run("gh", "api", "--jq", field, endpoint, cwd=top)
    try:
        found = json.loads(done.stdout) if done.returncode == 0 else None
    except ValueError:
        found = None
    if not isinstance(found, list) or not all(isinstance(entry, dict) for entry in found):
        said = (done.stderr.strip() or done.stdout.strip() or "no readable answer").splitlines()[-1]
        repo.refuse(REFUSALS["not_green"], reason=f"GitHub did not answer: {said.rstrip('.')}",
                    item=item)
    return found
