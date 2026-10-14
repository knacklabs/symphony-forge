"""Rebuild missing pull-request time stories from the item's own surviving evidence."""
import json
import re
import subprocess
import tomllib
from datetime import timedelta
from pathlib import Path
from typing import Any

from forge import board_facts, repo, story, time_records

UNREACHABLE = ("Couldn't reach GitHub, so older items' time stories weren't rebuilt; "
               "the next forge close on this machine tries again.")


def _json(top: Path, ref: str, path: str) -> dict[str, Any]:
    return story.json_of(story.show(top, ref, path))


def _identity(top: Path, head: str, branch: str) -> tuple[str, dict[str, Any]] | None:
    paths = repo.git("ls-tree", "-r", "--name-only", head, "--", ".factory", cwd=top).splitlines()
    key = board_facts.item_key(branch, paths)
    if key is None:
        return None  # A manually opened PR can use a Forge-looking branch without using Forge.
    state = _json(top, head, repo.state_path(key))
    if not state:
        raise ValueError("The pull request's item state could not be read")
    return key, state


def _checks(top: Path, head: str) -> list[dict[str, Any]]:
    # ponytail: one check-runs request per pushed head in the six-week window; batch through GraphQL if a repo has hundreds.
    # History needs failed attempts too; live readiness reads only the latest attempts.
    done = repo.run("gh", "api", "--paginate", "--method", "GET", "--raw-field", "filter=all",
                    "--raw-field", "per_page=100", "--jq", ".check_runs[]",
                    f"repos/{{owner}}/{{repo}}/commits/{head}/check-runs", cwd=top)
    done.check_returncode()
    text = done.stdout.strip()
    runs = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines()]
    if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
        raise ValueError("The check runs could not be read")
    return runs


def rebuild(top: Path, pr: dict[str, Any], *, pushed_head: str = "") -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    """Fetch the original branch into FETCH_HEAD, even after a squash and branch deletion."""
    if pushed_head:
        head = pushed_head  # First publication just pushed this original history from this checkout.
    else:
        fetched = repo.run("git", "fetch", "-q", "--no-tags", "origin", f"refs/pull/{pr['number']}/head", cwd=top)
        fetched.check_returncode()
        head = repo.git("rev-parse", "FETCH_HEAD", cwd=top)
    identity = _identity(top, head, pr["headRefName"])
    if identity is None:
        return None
    key, state = identity
    path = repo.state_path(key)
    starts = repo.git("log", "--reverse", "--diff-filter=A", "--format=%H", head, "--", path,
                      cwd=top).splitlines()
    if not starts:
        raise ValueError("The item's start commit could not be read")
    start = starts[0]
    commits = [start, *repo.git("rev-list", "--reverse", "--ancestry-path", f"{start}..{head}", cwd=top).splitlines()]
    history = [(commit, repo.git("show", "-s", "--format=%cI%x00%s%x00%aN%x00%aE", commit,
                                cwd=top).split("\0"), _json(top, commit, path)) for commit in commits]
    review_subject = re.compile(rf"^Review of {re.escape(key)}: (blocked|clean)\b")
    reviews = [one for _, (_, subject, _, _), one in history if review_subject.match(subject)]
    # Close pushes each reviewed work head before the review and its result commit afterwards.
    work_heads = {(one.get("review") or {}).get("commit"): number
                  for number, one in enumerate(reviews, 1)}
    events, timings, clean = [], [], []
    number, last_green = 0, None
    for commit, (at, subject, author, email), one in history:
        if commit == start:
            events.append({"id": f"rebuilt-start-{commit}", "item": key, "event": "item started",
                           "at": at, "by": author, "email": email})
        reviewed = review_subject.match(subject)
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
        eligible = ((one.get("review") or {}).get("status") == "clean"
                    and one.get("status") in ("waiting for checks", "ready"))
        if eligible:
            clean.append({"commit": commit, "at": at, "outcome": "clean"})
        if not reviewed and commit not in work_heads and commit != head:
            continue
        required = tomllib.loads(story.show(top, commit, "forge.toml") or "").get("checks", [])
        runs = _checks(top, commit)
        named = [run for run in runs if any(run.get("name") == want
                 or str(run.get("name") or "").startswith(want + " (") for want in required)]
        began = [time_records.when(run.get("started_at")) for run in named]
        ended = [time_records.when(run.get("completed_at")) for run in named]
        complete = (all(any(run.get("name") == want or str(run.get("name") or "").startswith(want + " (")
                            for run in named) for want in required) and named
                    and all(began) and all(ended))
        if complete:
            a, b = min(began), max(ended)
            if b >= a:
                latest = {}
                for run in sorted(named, key=lambda run: run.get("completed_at") or ""):
                    latest[run.get("name")] = run
                green = all(run.get("conclusion") == "success" for run in latest.values())
                timings.append({"item": key, "step": "CI wait", "round": work_heads.get(commit, number),
                                "start": a.isoformat(), "seconds": (b - a).total_seconds(),
                                "outcome": "passed" if green else "unknown"})
                if eligible and green:
                    last_green = max(b, time_records.when(at))
    if "/" in key or pr.get("headRefName", "").startswith("story/"):
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
    managed = re.search(r"<!-- forge:begin -->.*?<!-- forge:end -->", body, re.S)
    previous = time_records.HISTORY_SECTION.search(managed[0]) if managed else None
    if previous and not time_records.from_body(body):
        # Keep rendered prose, not provenance comments inside the new JSON comment.
        legacy = re.sub(r"<!--.*?-->", "", previous[0], flags=re.S)
        record = {**record, "legacy_text": record.get("legacy_text") or
                  legacy.removeprefix("## How it went\n").strip()}
    marker = "<!-- forge:time-record " + json.dumps(record, separators=(",", ":")) + " -->\n"
    if "<!-- forge:begin -->" not in body:
        body = body.rstrip() + "\n\n<!-- forge:begin -->\n<!-- forge:end -->\n"
    def replace(block: re.Match[str]) -> str:
        text = re.sub(r"<!-- forge:time-record \{.*?\} -->\n?", "", block[0], flags=re.S)
        text, count = time_records.HISTORY_SECTION.subn(
            lambda section: section[0].rstrip() + "\n\n" + marker, text, count=1)
        return text if count else text.replace("<!-- forge:end -->", "## How it went\n\n" + marker + "<!-- forge:end -->", 1)
    return re.sub(r"<!-- forge:begin -->.*?<!-- forge:end -->", replace, body, count=1, flags=re.S)


def failed(top: Path) -> None:
    try:
        (repo.forge_dir(top) / "backfill-pending").touch()
    except OSError:
        pass
    repo.command_fact("backfill warning", top, lambda: print(UNREACHABLE))


def run(top: Path) -> None:
    """A best-effort whole rebuild. Keep the retry until all reads and writes succeeded."""
    from forge import close

    pending = repo.forge_dir(top) / "backfill-pending"
    try:
        pending.touch()
        github = board_facts.prs(top, fresh=True)
        if github is None or not github["open_complete"] or not all(week["complete"] for week in github["weeks"]):
            raise ValueError("The pull requests could not all be read")
        cutoff = time_records.when(repo.now()) - timedelta(days=42)
        prs = [*github["open"], *[pr for pr in board_facts.merged_prs(github)
                                if time_records.when(pr.get("mergedAt")) and time_records.when(pr["mergedAt"]) >= cutoff]]
        for pr in {pr["number"]: pr for pr in prs}.values():
            if not pr.get("headRefName", "").startswith(("fix/", "task/", "story/")) or time_records.from_body(pr.get("body") or ""):
                continue
            rebuilt = rebuild(top, pr)
            if rebuilt is None:
                continue
            key, state, record = rebuilt
            close._refresh_record(top, key, state, {**pr, "body": seed(pr.get("body") or "", record)})
        pending.unlink(missing_ok=True)
    except (repo.Refused, subprocess.CalledProcessError, OSError, ValueError, KeyError, TypeError):
        failed(top)


def upgrade_fix(top: Path, item: str, state: dict[str, Any]) -> bool:
    if state.get("kind") != "fix":
        return False
    starts = repo.git("log", "--reverse", "--diff-filter=A", "--format=%H", "HEAD", "--",
                      repo.state_path(item), cwd=top).splitlines()
    if not starts:
        return False
    commits = repo.git("log", "--first-parent", "--no-merges", "--format=%H",
                       f"{starts[0]}..HEAD", "--", "forge.toml", cwd=top).splitlines()
    return any(repo._pin(story.show(top, f"{commit}^", "forge.toml") or "")
               != repo._pin(story.show(top, commit, "forge.toml") or "") for commit in commits)
