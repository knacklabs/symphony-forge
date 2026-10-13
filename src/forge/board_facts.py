"""The board's team facts: each item's one state, the counts, and GitHub's pull request lists.

`board.machine_board` calls `team` once; every surface reads its output and computes nothing of
its own. Keys a later part fills stay null until then.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from forge import board_trends, repo, story, time_records

Item = dict[str, Any]
STORY_STATES = ("done", "building", "approved, not started", "waiting for approval", "planning", "no plan yet")
WORK_STATES = ("done", "ready to merge", "in progress", "to do")
FIELDS = "headRefName,headRefOid,state,title,body,mergedAt,mergedBy,author,number,url,isDraft"


def full_weeks(now: datetime, count: int) -> list[datetime]:
    """The Mondays (00:00 UTC) that start the last `count` full weeks, oldest first."""
    now = now.astimezone(timezone.utc)
    monday = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=now.weekday())
    return [monday - timedelta(weeks=n) for n in range(count, 0, -1)]


def _cached(top: Path, name: str, fetch: Any) -> Any:
    """`fetch()`'s answer, kept for a minute in .git/forge/<name>.json; None is never kept."""
    cache = repo.forge_dir(top) / f"{name}.json"
    now = time_records.when(repo.now()) or datetime.now(timezone.utc)
    try:
        saved = json.loads(cache.read_text(encoding="utf-8"))
        at = time_records.when(saved.get("fetched_at"))
        if at and 0 <= (now - at).total_seconds() < 60 and "data" in saved:
            return saved["data"]
    except (OSError, ValueError, AttributeError):
        pass
    if not shutil.which("gh"):
        return None
    data = fetch(now)
    if data is None:
        return None  # A failed fetch is never cached.
    temp = cache.with_name(f"{name}-{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps({"fetched_at": repo.now(), "data": data}), encoding="utf-8")
        os.replace(temp, cache)
    except OSError:
        pass  # A read-only Git directory must not prevent a view.
    finally:
        temp.unlink(missing_ok=True)
    return data


def _listing(top: Path, state: str, *args: str, fields: str = FIELDS, limit: str = "1000") -> list[Item] | None:
    done = repo.run("gh", "pr", "list", "--state", state, "--limit", limit, "--json", fields, *args, cwd=top)
    try:
        rows = json.loads(done.stdout) if done.returncode == 0 else None
    except ValueError:
        return None
    return rows if isinstance(rows, list) and all(isinstance(r, dict) for r in rows) else None


def prs(top: Path) -> Item | None:
    """Open pull requests, and the merged ones searched one week at a time for six full weeks and
    this one, cached together for a minute. None when gh is missing or any list fails."""
    # ponytail: eight list calls a minute at most; a week over 1,000 merges shows unknown, search by day if a team needs it.
    def fetch(now: datetime) -> Item | None:
        opened = _listing(top, "open")
        if opened is None:
            return None
        weeks = []
        for start in [*full_weeks(now, 6), full_weeks(now + timedelta(weeks=1), 1)[0]]:
            found = _listing(top, "merged", "--search",
                             f"merged:{start:%Y-%m-%d}..{start + timedelta(days=6):%Y-%m-%d}")
            if found is None:
                return None
            # A capped week need not hold all of its rows, so its counts are unknown.
            weeks.append({"start": start.isoformat(), "prs": found, "complete": len(found) < 1000})
        return {"open": opened, "open_complete": len(opened) < 1000, "weeks": weeks}
    return _cached(top, "prs-cache", fetch)


def merged_before_weeks(top: Path) -> dict[str, Item]:
    """Pull requests merged before the weekly searches, by branch: one request of at most 1,000,
    kept for a minute. Only asked when an unfinished story has parts merged that long ago."""
    # ponytail: one capped request; a part beyond its newest 1,000 shows its time as unknown.
    def fetch(now: datetime) -> list[Item] | None:
        return _listing(top, "merged", "--search", f"merged:<{full_weeks(now, 6)[0]:%Y-%m-%d}")
    return {pr["headRefName"]: pr for pr in _cached(top, "prs-older-cache", fetch) or []
            if isinstance(pr.get("headRefName"), str)}


def details(top: Path) -> list[Item]:
    """The last 25 merged pull requests with their files and checks, for the success numbers,
    cached for a minute like the lists."""
    return _cached(top, "prs-details-cache", lambda now: _listing(
        top, "merged", fields="headRefName,headRefOid,state,title,body,mergedAt,mergedBy,url,files,statusCheckRollup",
        limit="25")) or []


def merged_prs(github: Item | None) -> list[Item]:
    return [pr for week in (github or {}).get("weeks", []) for pr in week["prs"]
            if pr.get("state", "MERGED") == "MERGED" and isinstance(pr.get("headRefName"), str)]


def work_state(row: Item) -> str:
    return ("done" if row["stage"] in ("merged", "done") else "ready to merge" if row["stage"] == "ready"
            else "to do" if row["stage"] == "unstarted" else "in progress")


def team(top: Path, history: Item, items: dict[str, Item], maps: list[Item], best: dict[str, Any],
         completed: dict[str, Item], github: Item | None) -> Item:
    """Give every row its `state` and return the board's `team` facts."""
    stories = "\0".join(rel for rel in best if rel.startswith(".factory/stories/"))
    approvals: dict[str, list[Any]] = {}
    for rel, state, _ in history["copies"]:
        if rel.endswith("/story.json") and (state.get("approval") or state.get("status") == "approved"):
            approvals.setdefault(rel.split("/")[2], []).append((state.get("approval") or {}).get("hash"))

    def approved(key: str) -> bool:
        """Approved for the current plan, as forge next's approval gate checks it: an edit to what
        the approval binds needs a new approval. A state from before approvals had a hash counts."""
        hashes = approvals.get(key, [])
        if not hashes or None in hashes:
            return bool(hashes)
        tree = history.get("worktrees", {}).get(f"story/{key}")
        doc = tree / "plans" / f"{key}.md" if tree else None
        text = doc.read_text(encoding="utf-8") if doc and doc.is_file() else story._plan(top, key, history=history)
        return story.approval_hash(text) in hashes

    def story_state(key: str, row: Item | None) -> str:
        if key in completed or row is None:
            return "done"  # a story left out of the rows finished more than seven days ago
        if approved(key) and row["gates"]["plan_read"]["status"] != "blocked":  # story.gate, as forge next
            return "building" if f".factory/stories/{key}/tasks/" in stories else "approved, not started"
        if row["gates"]["plan_read"]["status"] == "passed":  # story.gate, as forge next checks it
            return "waiting for approval"
        if repo.state_path(key) in best or any(doc.endswith(f":plans/{key}.md") for doc in history["docs"]):
            return "planning"
        return "no plan yet"

    counts: Item = {"stories": dict.fromkeys(STORY_STATES, 0), "parts": dict.fromkeys(WORK_STATES, 0),
                    "fixes": dict.fromkeys(WORK_STATES, 0), "finished_last_7_days": {"parts": 0, "fixes": 0}}
    plans = {entry["id"]: entry["parts"] for entry in maps}
    cutoff = (time_records.when(repo.now()) or datetime.now(timezone.utc)) - timedelta(days=7)

    def recent(row: Item) -> bool:
        return row["state"] == "done" and (at := time_records.when(row["merged_at"])) is not None and at >= cutoff

    for key in dict.fromkeys([*plans, *(k for k, r in items.items() if r["kind"] == "story")]):
        row = items.get(key)
        state = story_state(key, row)
        counts["stories"][state] += 1
        children = {child["id"]: child for child in (row or {}).get("children", [])}
        for child in children.values():
            child["state"] = work_state(child)
        if row:
            row["state"] = state
        if state not in ("done", "building", "approved, not started"):
            continue  # parts of a story not yet approved are not counted
        for part in plans.get(key, []):
            child = children.get(part["id"])
            counts["parts"][child["state"] if child else "done" if part["status"] == "Merged" else "to do"] += 1
        counts["finished_last_7_days"]["parts"] += sum(map(recent, children.values()))
    for rel, (state, _) in best.items():
        name = rel.removeprefix(".factory/fixes/").removesuffix(".json")
        if not rel.startswith(".factory/fixes/") or state.get("kind") == "story-done":
            continue
        row = items.get(name)
        if row:
            row["state"] = work_state(row)
            counts["fixes"][row["state"]] += 1
            counts["finished_last_7_days"]["fixes"] += recent(row)
        else:
            counts["fixes"]["done"] += 1  # a fix left out of the rows finished more than seven days ago
    later, clause = board_trends.facts(top, history, counts, list(items.values()), github)
    work = [counts[kind][state] for state in ("in progress", "ready to merge") for kind in ("parts", "fixes")]
    building = counts["stories"]["building"]
    sentence = (f"{building} {'story' if building == 1 else 'stories'} building, {sum(work[:2])} parts and fixes "
                f"in progress, {sum(work[2:])} ready to merge; {clause[0].lower()}{clause[1:]}")
    return {"sentence": sentence, "counts": counts, "needs_you": None, "in_progress": None, "blocked": None,
            **later}
