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
from pathlib import Path
from typing import Any

from forge import repo

REFUSALS = {
    "red": ("Checks failed on the pull request: {names}.", "forge work {item}"),
    "not_green": ("The checks are not green yet: {reason}.", "forge close {item}"),
}
PASS, PENDING, RED, SKIPPED = "pass", "pending", "red", "skipped"


def wait(top: Path, item: str, sha: str, names: list[str]) -> None:
    """Return once every check on sha passed and every named one is there; refuse when one is red
    or time runs out."""
    # ponytail: an env override is the whole wait seam (tests set 0 to look once).
    deadline = time.monotonic() + float(os.environ.get("FORGE_CHECKS_WAIT", "600"))
    while True:
        seen = _seen(top, item, sha)
        # A matrix job reports as "tests (ubuntu-latest)", and so on; each counts as its named
        # check, and every one must pass. Checks forge.toml doesn't name go by their own name.
        groups: dict[str, list[str]] = {want: [] for want in names}
        for name, state in seen:
            want = next((want for want in names if name == want or name.startswith(want + " (")),
                        None)
            if state == SKIPPED:
                state = RED if want else PASS
            groups.setdefault(want or name, []).append(state)
        red, missing, pending = [], [], []
        for want, states in groups.items():
            if not states:
                missing.append(want)
            elif RED in states:  # failed, cancelled or timed out (a named one skipped too): red
                red.append(want)
            elif PENDING in states:
                pending.append(want)
        if red:
            repo.refuse(REFUSALS["red"], names=", ".join(red), item=item)
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
    """Each check run and commit status on sha, as (name, pass/pending/red/skipped)."""
    # Every page: a failed matrix job on page two must still count.
    endpoint = f"repos/{{owner}}/{{repo}}/commits/{sha}"
    runs = _ask(top, item, ".check_runs", f"{endpoint}/check-runs?per_page=100")
    statuses = _ask(top, item, ".statuses", f"{endpoint}/status?per_page=100")
    return ([(str(run.get("name")), PENDING if run.get("status") != "completed"
              else PASS if run.get("conclusion") == "success"
              else SKIPPED if run.get("conclusion") in ("skipped", "neutral") else RED)
             for run in runs]
            + [(str(status.get("context")), {"success": PASS, "pending": PENDING}.get(
                status.get("state"), RED)) for status in statuses])


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
        repo.refuse(REFUSALS["not_green"], reason=f"GitHub did not answer: {said.rstrip('.')}",
                    item=item)
    return found
