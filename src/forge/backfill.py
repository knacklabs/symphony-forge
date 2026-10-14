"""Rebuild missing pull-request time stories from the item's own surviving evidence."""
import json
import re
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any

from forge import board_facts, repo, story, time_records

UNREACHABLE = ("Couldn't reach GitHub, so older items' time stories weren't rebuilt; "
               "the next forge close on this machine tries again.")


def _json(top: Path, ref: str, path: str) -> dict[str, Any]:
    return story.json_of(story.show(top, ref, path))


def _identity(top: Path, head: str, branch: str) -> tuple[str, dict[str, Any]]:
    for path in repo.git("ls-tree", "-r", "--name-only", head, "--", ".factory", cwd=top).splitlines():
        if not path.endswith(".json"):
            continue
        state = _json(top, head, path)
        if state.get("branch") == branch:
            if path.startswith(".factory/fixes/"):
                return path.removeprefix(".factory/fixes/").removesuffix(".json"), state
            match = re.fullmatch(r".factory/stories/([^/]+)/tasks/([^/]+).json", path)
            if match:
                return f"{match[1]}/{match[2]}", state
            match = re.fullmatch(r".factory/stories/([^/]+)/story.json", path)
            if match:
                return match[1], state
    raise ValueError("The pull request's item state could not be read")


def _checks(top: Path, head: str) -> list[dict[str, Any]]:
    # ponytail: one check-runs request per pushed head in the six-week window; batch through GraphQL if a repo has hundreds.
    done = repo.run("gh", "api", "--paginate", "--jq", ".check_runs[]",
                    f"repos/{{owner}}/{{repo}}/commits/{head}/check-runs?per_page=100", cwd=top)
    done.check_returncode()
    text = done.stdout.strip()
    runs = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines()]
    if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
        raise ValueError("The check runs could not be read")
    return runs


def rebuild(top: Path, pr: dict[str, Any], *, pushed_head: str = "") -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Fetch the original branch into FETCH_HEAD, even after a squash and branch deletion."""
    if pushed_head:
        head = pushed_head  # First publication just pushed this original history from this checkout.
    else:
        fetched = repo.run("git", "fetch", "-q", "origin", f"refs/pull/{pr['number']}/head", cwd=top)
        fetched.check_returncode()
        head = repo.git("rev-parse", "FETCH_HEAD", cwd=top)
    key, state = _identity(top, head, pr["headRefName"])
    path = repo.state_path(key)
    starts = repo.git("log", "--reverse", "--diff-filter=A", "--format=%H", head, "--", path,
                      cwd=top).splitlines()
    if not starts:
        raise ValueError("The item's start commit could not be read")
    start = starts[0]
    commits = [start, *repo.git("rev-list", "--reverse", "--ancestry-path", f"{start}..{head}", cwd=top).splitlines()]
    events, timings, clean = [], [], []
    number, last_green = 0, None
    required = repo.config(top)["checks"]
    for commit in commits:
        at, subject, author, email = repo.git("show", "-s", "--format=%cI%x00%s%x00%aN%x00%aE", commit,
                                               cwd=top).split("\0")
        if commit == start:
            events.append({"id": f"rebuilt-start-{commit}", "item": key, "event": "item started",
                           "at": at, "by": author, "email": email})
        one = _json(top, commit, path)
        reviewed = re.match(rf"^Review of {re.escape(key)}: (blocked|clean)\b", subject)
        if reviewed:
            last_green = None
            number += 1
            result = one.get("review") or {}
            events.append({"id": f"rebuilt-review-{commit}", "item": key, "event": "review result",
                           "at": at, "round": number, "review_round": number,
                           "commit": result.get("commit"), "rebuilt_commit": commit,
                           "outcome": reviewed[1], "findings": result.get("findings")})
            # A review commit gives an outcome, never the time spent on the review.
            timings.append({"item": key, "step": "review", "round": number,
                            "start": at, "outcome": reviewed[1], "rebuilt_commit": commit})
        eligible = (one.get("review", {}).get("status") == "clean"
                    and one.get("status") in ("waiting for checks", "ready"))
        if eligible:
            clean.append({"commit": commit, "at": at, "outcome": "clean"})
        if not reviewed and not (commit == head and eligible):
            continue
        runs = _checks(top, commit)
        named = [run for run in runs if run.get("name") in required]
        began = [time_records.when(run.get("started_at")) for run in named]
        ended = [time_records.when(run.get("completed_at")) for run in named]
        complete = (set(required) <= {run.get("name") for run in named} and named
                    and all(began) and all(ended))
        if complete:
            a, b = min(began), max(ended)
            if b >= a:
                green = all(run.get("conclusion") == "success" for run in named)
                timings.append({"item": key, "step": "CI wait", "round": number,
                                "start": a.isoformat(), "seconds": (b - a).total_seconds(),
                                "outcome": "passed" if green else "unknown"})
                if eligible and green:
                    last_green = max(b, time_records.when(at))
    if "/" in key:
        approval_path = repo.state_path(key.split("/")[0])
        approved = repo.git("log", "-1", "--format=%H%x00%cI%x00%aN%x00%aE", "-F",
                            "--grep=Approve the plan: ", head, "--", approval_path, cwd=top)
        if approved:
            commit, at, author, email = approved.split("\0")
            events.append({"id": f"rebuilt-approval-{commit}", "item": key, "event": "plan approved",
                           "approved_at": at, "by": author, "email": email})
    merged_at = pr.get("mergedAt")
    if merged_at:
        state = {**state, "status": "merged"}
        if last_green and time_records.when(merged_at) >= last_green:
            events.append({"id": f"rebuilt-merge-wait-{head}", "item": key, "event": "owner wait start",
                           "reason": "merge", "at": last_green.isoformat(), "round": number})
        events.append({"id": f"rebuilt-finished-{head}", "item": key, "event": "item finished", "at": merged_at})
    # Approval happened before the item started: do not extend the item's unknown span to it.
    began = next(event["at"] for event in events if event["event"] == "item started")
    state = {**state, "steps": [{"step": "start", "at": began}]}
    record = {"events": events, "timings": timings, "state": state,
              "clean_reviews": clean, "rebuilt": True}
    return key, state, record


def seed(body: str, record: dict[str, Any]) -> str:
    """Add evidence inside Forge's section; the usual history writer renders and bounds it."""
    marker = "<!-- forge:time-record " + json.dumps(record, separators=(",", ":")) + " -->\n"
    if "<!-- forge:begin -->" not in body:
        body = body.rstrip() + "\n\n<!-- forge:begin -->\n<!-- forge:end -->\n"
    def replace(block: re.Match[str]) -> str:
        text = re.sub(r"<!-- forge:time-record \{.*?\} -->\n?", "", block[0], flags=re.S)
        return text.replace("<!-- forge:end -->", marker + "<!-- forge:end -->", 1)
    return re.sub(r"<!-- forge:begin -->.*?<!-- forge:end -->", replace, body, count=1, flags=re.S)


def failed(top: Path) -> None:
    (repo.forge_dir(top) / "backfill-pending").touch()
    print(UNREACHABLE)


def run(top: Path) -> None:
    """A best-effort whole rebuild. Keep the retry until all reads and writes succeeded."""
    from forge import close

    pending = repo.forge_dir(top) / "backfill-pending"
    pending.touch()
    try:
        github = board_facts.prs(top, fresh=True)
        if github is None or not github["open_complete"] or not all(week["complete"] for week in github["weeks"]):
            raise ValueError("The pull requests could not all be read")
        cutoff = time_records.when(repo.now()) - timedelta(days=42)
        prs = [*github["open"], *[pr for pr in board_facts.merged_prs(github)
                                if time_records.when(pr.get("mergedAt")) and time_records.when(pr["mergedAt"]) >= cutoff]]
        for pr in {pr["number"]: pr for pr in prs}.values():
            if not pr.get("headRefName", "").startswith(("fix/", "task/", "story/")) or time_records.from_body(pr.get("body") or ""):
                continue
            key, state, record = rebuild(top, pr)
            close._refresh_record(top, key, state, {**pr, "body": seed(pr.get("body") or "", record)})
    except (repo.Refused, subprocess.CalledProcessError, OSError, ValueError, KeyError, TypeError):
        failed(top)
        return
    pending.unlink(missing_ok=True)


def upgrade_fix(top: Path, item: str, state: dict[str, Any]) -> bool:
    if state.get("kind") != "fix":
        return False
    starts = repo.git("log", "--reverse", "--diff-filter=A", "--format=%H", "HEAD", "--",
                      repo.state_path(item), cwd=top).splitlines()
    return bool(starts and repo._pin(story.show(top, f"{starts[0]}^", "forge.toml") or "")
                != repo._pin(story.show(top, "HEAD", "forge.toml") or ""))
