"""The board's team facts: each item's one state, the counts, and GitHub's pull request lists.

`board.machine_board` calls `team` once; every surface reads its output and computes nothing of
its own. Keys a later part fills stay null until then.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from forge import board_trends, repo, story, time_records

Item = dict[str, Any]
STORY_STATES = ("done", "building", "approved, not started", "waiting for approval", "planning", "no plan yet")
IN_PROGRESS_STATES = ("building", "in progress", "ready to merge")  # the board page's In progress group
WORK_STATES = ("done", "ready to merge", "in progress", "to do")
FIELDS = "headRefName,headRefOid,state,title,body,mergedAt,mergedBy,author,number,url,isDraft,files"


def item_key(branch: str, paths: list[str]) -> str | None:
    """An item's own state identifies a Forge branch; its prefix alone does not."""
    for path in paths:
        fix = re.fullmatch(r"\.factory/fixes/([^/]+)\.json", path)
        plan = re.fullmatch(r"\.factory/stories/([^/]+)/story\.json", path)
        part = re.fullmatch(r"\.factory/stories/([^/]+)/tasks/([^/]+)\.json", path)
        if fix and branch == f"fix/{fix[1]}":
            return fix[1]
        if plan and branch == f"story/{plan[1]}":
            return plan[1]
        if part and branch == f"task/{part[1]}-{part[2]}":
            return f"{part[1]}/{part[2]}"
    return None


def through_forge(pr: Item) -> bool:
    branch = str(pr.get("headRefName") or "")
    if not branch.startswith(("story/", "task/", "fix/")):
        return False
    files = pr.get("files")
    if time_records.from_body(pr.get("body") or "") or not isinstance(files, list) or len(files) >= 100:
        return True  # Missing or capped file evidence cannot establish that the state is absent.
    return item_key(branch, [file["path"] for file in files if isinstance(file, dict)
                             and isinstance(file.get("path"), str)]) is not None


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


def prs(top: Path, *, fresh: bool = False) -> Item | None:
    """Open pull requests, and the merged ones searched one week at a time for six full weeks and
    this one, cached together for a minute. None when gh is missing or any list fails."""
    # ponytail: eight list calls a minute at most; a week over 1,000 merges shows unknown, search by day if a team needs it.
    def fetch(now: datetime) -> Item | None:
        opened = _listing(top, "open")
        if opened is None:
            return None  # GitHub is unreachable: one call, not eight
        # Board restoration and backfill share these windows. The first Monday
        # is at least 42 days ago, including the cutoff on a Sunday (48 days).
        starts = [*full_weeks(now, 6), full_weeks(now + timedelta(weeks=1), 1)[0]]
        with ThreadPoolExecutor(len(starts)) as pool:  # the weeks at once; one at a time took ~7x as long
            lists = list(pool.map(lambda start: _listing(
                top, "merged", "--search", f"merged:{start:%Y-%m-%d}..{start + timedelta(days=6):%Y-%m-%d}"), starts))
        if None in lists:
            return None
        weeks = []
        for start, found in zip(starts, lists):
            # A capped week need not hold all of its rows, so its counts are unknown.
            weeks.append({"start": start.isoformat(), "prs": found, "complete": len(found) < 1000})
        return {"open": opened, "open_complete": len(opened) < 1000, "weeks": weeks}
    if fresh:
        return fetch(time_records.when(repo.now()) or datetime.now(timezone.utc))
    return repo.command_fact("github prs", top, lambda: _cached(top, "prs-cache", fetch))  # one try a command


def people(body: str) -> Item:
    """Original actors survive a deleted squash branch in the item's shared evidence."""
    record = time_records.from_body(body)
    events, summary = record.get("events", []), record.get("summary") or {}
    return {field: summary.get(field) or next((event.get("by") for event in events if event.get("event") == name), None)
            for field, name in (("started_by", "item started"), ("approved_by", "plan approved"))}


def merged_before_weeks(top: Path) -> dict[str, Item]:
    """Pull requests merged before the weekly searches, by branch: one request of at most 1,000,
    kept for a minute. Only asked when an unfinished story has parts merged that long ago."""
    # ponytail: one capped request; a part beyond its newest 1,000 shows its time as unknown.
    def fetch(now: datetime) -> list[Item] | None:
        # "*..day" rather than "<day": cmd.exe reads "<" in a gh.cmd argument as a redirect.
        return _listing(top, "merged", "--search", f"merged:*..{full_weeks(now, 6)[0] - timedelta(days=1):%Y-%m-%d}")
    return {pr["headRefName"]: pr for pr in _cached(top, "prs-older-cache", fetch) or []
            if isinstance(pr.get("headRefName"), str)}


def details(top: Path) -> list[Item]:
    """The last 25 merged pull requests with their files and checks, for the success numbers,
    cached for a minute like the lists."""
    return _cached(top, "prs-details-cache", lambda now: _listing(
        top, "merged", fields="headRefName,headRefOid,state,title,body,mergedAt,mergedBy,url,files,statusCheckRollup",
        limit="25")) or []


def failed_schedules(top: Path) -> list[Item]:
    """Each workflow whose latest scheduled run on the default branch failed: its name and file,
    failed jobs and failing pytest tests as printed; [] when none failed or GitHub can't be read.
    One request for the runs and one log per failed workflow, kept a minute."""
    branch = repo.default_branch(top)

    def fetch(now: datetime) -> list[Item] | None:
        # ponytail: the newest 100 scheduled runs; a frequent schedule can crowd out a daily one.
        # Separate query fields avoid cmd.exe interpreting an ampersand in a gh.cmd argument.
        done = repo.run("gh", "api", "repos/{owner}/{repo}/actions/runs", "--method", "GET",
                        "--raw-field", "event=schedule", "--raw-field", f"branch={branch}",
                        "--raw-field", "per_page=100", cwd=top)
        try:
            runs = json.loads(done.stdout).get("workflow_runs") if done.returncode == 0 else None
        except (ValueError, AttributeError):
            return None
        if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
            return None
        latest: dict[Any, Item] = {}
        for run in runs:  # newest first
            latest.setdefault(run.get("workflow_id"), run)
        failed = []
        for run in latest.values():
            if run.get("conclusion") != "failure":
                continue
            log = repo.run("gh", "run", "view", str(run.get("id")), "--log-failed", cwd=top)
            if log.returncode != 0:
                return None
            lines = log.stdout.splitlines()
            failed.append({"workflow": str(run.get("name") or "workflow"), "branch": branch,
                           "file": str(run.get("path") or run.get("workflow_id")).rsplit("/", 1)[-1],
                           "jobs": sorted({line.split("\t", 1)[0] for line in lines if "\t" in line}),
                           "tests": sorted({found[1] for line in lines if (found := re.search(
                               r"(?:FAILED|ERROR) (\S+?::[^\s\[]+(?:\[.*?\])?)(?= - |$)", line))})})
        return sorted(failed, key=lambda run: (run["workflow"], run["file"]))
    return _cached(top, "schedule-cache", fetch) or []


def merged_prs(github: Item | None) -> list[Item]:
    return [pr for week in (github or {}).get("weeks", []) for pr in week["prs"]
            if pr.get("state", "MERGED") == "MERGED" and isinstance(pr.get("headRefName"), str)]


def work_state(row: Item) -> str:
    return ("done" if row["stage"] in ("merged", "done") else "ready to merge" if row["stage"] == "ready"
            else "to do" if row["stage"] == "unstarted" else "in progress")


def _branch(row: Item, state: Item) -> str:
    return state.get("branch") or (f"task/{row['id'].replace('/', '-')}" if row["kind"] == "task" else f"fix/{row['id']}")


def _entry(row: Item, reason: str, detail: str | None, since: Any, now: datetime) -> Item:
    at = time_records.when(since)
    return {"id": row["id"], "kind": row["kind"], "title": row["title"], "reason": reason, "detail": detail,
            "since": since if at else None, "seconds": max(0, (now - at).total_seconds()) if at else None}


def needs_you(top: Path, rows: list[Item], readiness: dict[str, Item], person_waits: dict[str, list[Item]],
              now: datetime) -> list[Item]:
    """Every item waiting on a person, oldest first, as `nextstep.person_waits` decides it: the
    waits each part's and fix's row worked out, and each story's plan approval or blocking problem."""
    from forge import nextstep  # nextstep imports this module

    found = []
    for row in rows:
        waits = []
        if row["kind"] == "story":
            blocker = readiness.get(row["id"], {}).get("blocker")
            if blocker or row.get("state") == "waiting for approval":
                waits = nextstep.person_waits(top, row["id"], {}, row["state"], blocker=blocker)
        elif row.get("state") in ("in progress", "ready to merge"):
            waits = person_waits.get(row["id"], [])
        found += [_entry(row, wait["reason"], wait["detail"], wait["since"], now) for wait in waits]
    for entry in found:
        entry["waited_seconds"] = entry.pop("seconds")
    return sorted(found, key=lambda entry: (entry["since"] is None, time_records.when(entry["since"]) or now))


def blocked(top: Path, rows: list[Item], best: dict[str, Any], maps: list[Item], now: datetime) -> list[Item]:
    """Started work idle a day or more, reviews blocked three or more rounds in a row, and the
    unfinished part the most unfinished parts wait on, longest-standing first."""
    from forge import nextstep, review  # both import this module

    found = []
    for row in rows:
        if row["kind"] == "story" or row.get("state") not in ("in progress", "ready to merge"):
            continue
        if row["idle_seconds"] is not None and row["idle_seconds"] >= 86400:
            found.append({**_entry(row, "stalled", f"No activity for {time_records.plain(row['idle_seconds'])}",
                                   None, now), "seconds": row["idle_seconds"]})
        if row["gates"]["review"]["status"] == "blocked":
            ref = nextstep.review_ref(top, _branch(row, best.get(repo.state_path(row["id"]), ({}, None))[0]))
            count, since = review.blocked_rounds(top, row["id"], ref) if ref else (0, None)
            if count >= 3:
                found.append(_entry(row, "looping", f"Review blocked {count} rounds in a row", since, now))
    states = {row["id"]: row.get("state") for row in rows}
    parts = [part for entry in maps if states.get(entry["id"]) in ("building", "approved, not started")
             for part in entry["parts"] if part["status"] != "Merged"]
    waiting: dict[str, list[str]] = {}
    for part in parts:
        for other in part["waits_for"]:
            waiting.setdefault(other, []).append(part["id"])
    most, top_part = 0, None
    for part in parts:  # in plan order, so a tie goes to the earlier part
        seen, stack = set(), [part["id"]]
        while stack:
            for dependant in waiting.get(stack.pop(), []):
                if dependant not in seen:
                    seen.add(dependant)
                    stack.append(dependant)
        if len(seen - {part["id"]}) > most:
            most, top_part = len(seen - {part["id"]}), part
    if top_part:
        state = best.get(repo.state_path(top_part["id"]), ({}, None))[0]
        story_state = best.get(repo.state_path(top_part["id"].split("/")[0]), ({}, None))[0]
        since = next((step.get("at") for step in state.get("steps", []) if step.get("step") == "start"),
                     (story_state.get("approval") or {}).get("at"))
        found.append(_entry({**top_part, "kind": "task"}, "blocks the most",
                            f"{most} unfinished part{'s wait' if most != 1 else ' waits'} on it", since, now))
    for entry in found:
        entry.pop("since")
    return sorted(found, key=lambda entry: (entry["seconds"] is None, -(entry["seconds"] or 0)))


def team(top: Path, history: Item, items: dict[str, Item], maps: list[Item], best: dict[str, Any],
         completed: dict[str, Item], github: Item | None, readiness: dict[str, Item],
         person_waits: dict[str, list[Item]]) -> Item:
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
    now = time_records.when(repo.now()) or datetime.now(timezone.utc)
    rows = [row for parent in items.values() for row in (parent, *parent["children"])]
    waiting, slow = needs_you(top, rows, readiness, person_waits, now), blocked(top, rows, best, maps, now)
    work = [counts[kind][state] for state in ("in progress", "ready to merge") for kind in ("parts", "fixes")]
    building = counts["stories"]["building"]
    sentence = (f"{building} {'story' if building == 1 else 'stories'} building, {sum(work[:2])} parts and fixes "
                f"in progress, {sum(work[2:])} ready to merge, {len(waiting)} need{'s' if len(waiting) == 1 else ''} "
                f"you, {len(slow)} blocked or slow; {clause[0].lower()}{clause[1:]}")
    return {"sentence": sentence, "counts": counts, "needs_you": waiting,
            # The page's In progress group: an item that needs you or is blocked sits in that group instead.
            "in_progress": [{key: row[key] for key in ("id", "title", "kind", "state")}
                            for row in items.values() if row.get("state") in IN_PROGRESS_STATES
                            and row["id"] not in {entry["id"] for entry in [*waiting, *slow]}], "blocked": slow,
            **later}
