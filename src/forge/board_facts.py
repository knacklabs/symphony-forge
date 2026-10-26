"""The board's team facts: each item's one state, the counts, and GitHub's pull request lists.

`board.machine_board` calls `team` once; every surface reads its output and computes nothing of
its own. Keys a later part fills stay null until then.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from forge import board_trends, repo, story, time_records

Item = dict[str, Any]
STORY_STATES = ("done", "building", "approved, not started", "waiting for approval", "planning", "no plan yet")
IN_PROGRESS_STATES = ("building", "in progress", "ready to merge")  # the board page's In progress group
WORK_STATES = ("done", "ready to merge", "in progress", "to do")
FIELDS = "headRefName,headRefOid,state,title,body,mergedAt,mergedBy,author,number,url,isDraft,updatedAt,files"


# The explicit query retains GitHub's own occurrence ids; gh pr list's default rollup does not.
CHECKS_QUERY = """query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 25, states: OPEN, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes { number headRefName headRefOid title url isDraft body
        commits(last: 1) { nodes { commit { oid statusCheckRollup {
          contexts(first: 100) { pageInfo { hasNextPage } nodes {
            __typename
            ... on CheckRun { databaseId name status conclusion startedAt completedAt
              checkSuite { status conclusion workflowRun { workflow { id name } } } }
            ... on StatusContext { id context state createdAt }
          } }
        } } } }
      }
    }
  }
}"""


def machine_prs(top: Path) -> list[Item]:
    """One request for the newest 25 open PRs, cached across command invocations for 60s."""
    from forge.board import _rollup, _when

    cache = repo.forge_dir(top) / "checks-cache.json"
    fetched_at = repo.now()
    now = _when(fetched_at)
    try:
        saved = json.loads(cache.read_text(encoding="utf-8"))
        at = _when(saved.get("fetched_at"))
        if now and at and 0 <= (now - at).total_seconds() < 60 and isinstance(saved.get("prs"), list):
            return [{**pr, "checks_fetched_at": saved["fetched_at"]} for pr in saved["prs"]]
    except (OSError, ValueError, AttributeError):
        pass
    done = repo.run("gh", "api", "graphql", "-F", "owner={owner}", "-F", "name={repo}",
                    "-f", f"query={' '.join(CHECKS_QUERY.split())}", cwd=top) if shutil.which("gh") else None
    try:
        response = json.loads(done.stdout) if done and done.returncode == 0 else {}
        prs = response["data"]["repository"]["pullRequests"]["nodes"]
        if response.get("errors") or not isinstance(prs, list) or not all(isinstance(p, dict) for p in prs):
            return []
    except (ValueError, KeyError, TypeError):
        return []  # An expired answer must not hide a failed check while GitHub is unreachable.
    for pr in prs:
        for check in _rollup(pr):
            if check.get("conclusion") != "CANCELLED" or not isinstance(check.get("databaseId"), int):
                continue
            annotations = repo.run("gh", "api", "--paginate", "--slurp",
                f"repos/{{owner}}/{{repo}}/check-runs/{check['databaseId']}/annotations?per_page=100", cwd=top)
            try:
                pages = json.loads(annotations.stdout) if annotations.returncode == 0 else []
                check["timeout"] = any("has exceeded the maximum execution time of" in str(a.get("message", ""))
                                       for page in pages if isinstance(page, list)
                                       for a in page if isinstance(a, dict))
            except (ValueError, TypeError):
                pass  # Without GitHub's annotation, a cancellation is a failure, not a guessed timeout.
    temp = cache.with_name(f"checks-cache-{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps({"fetched_at": fetched_at, "prs": prs}), encoding="utf-8")
        os.replace(temp, cache)
    except OSError:
        pass  # A read-only/full Git directory must not prevent a view.
    finally:
        temp.unlink(missing_ok=True)
    return [{**pr, "checks_fetched_at": fetched_at} for pr in prs]


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
    if time_records.view_body(pr.get("body") or "") or not isinstance(files, list) or len(files) >= 100:
        return True  # Missing or capped file evidence cannot establish that the state is absent.
    return item_key(branch, [file["path"] for file in files if isinstance(file, dict)
                             and isinstance(file.get("path"), str)]) is not None


def full_weeks(now: datetime, count: int) -> list[datetime]:
    """The Mondays (00:00 UTC) that start the last `count` full weeks, oldest first."""
    now = now.astimezone(timezone.utc)
    monday = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=now.weekday())
    return [monday - timedelta(weeks=n) for n in range(count, 0, -1)]


def _cached(top: Path, name: str, fetch: Any, *, stale: bool = False, seconds: float = 60) -> Any:
    """Serialize readers through the fetch and write, then let waiters reuse the answer."""
    from forge import codex
    with ExitStack() as guard:
        try:
            guard.enter_context(codex._one_at_a_time(repo.forge_dir(top) / f"{name}.lock"))
        except OSError:
            pass  # A read-only Git directory must not prevent a view.
        return _read_cached(top, name, fetch, stale=stale, seconds=seconds)


def _read_cached(top: Path, name: str, fetch: Any, *, stale: bool, seconds: float) -> Any:
    cache = repo.forge_dir(top) / f"{name}.json"
    now = time_records.when(repo.now()) or datetime.now(timezone.utc)
    previous = None
    try:
        saved = json.loads(cache.read_text(encoding="utf-8"))
        previous = saved.get("data")
        at = time_records.when(saved.get("fetched_at"))
        if at and 0 <= (now - at).total_seconds() < seconds and "data" in saved:
            return saved["data"]
    except (OSError, ValueError, AttributeError):
        pass
    if not shutil.which("gh"):
        return previous if stale else None
    data = fetch(now)
    if data is None:
        return previous if stale else None
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


def prs(top: Path, *, fresh: bool = False, people: bool = False,
        merged_fields: str = FIELDS, open_fields: str = FIELDS,
        open_read: Future[list[Item] | None] | None = None) -> Item | None:
    """Open pull requests, and the merged ones searched one week at a time for six full weeks and
    this one. Past weeks live a day; open and current-week lists live a minute.
    Only people may use expired records during an outage. Fresh reads can select only the fields
    their caller uses; cached reads always keep the complete board records.
    A caller may share its pending open-list read with its checks query."""
    # ponytail: a week over 1,000 merges shows unknown, search by day if a team needs it.
    def fetch(now: datetime) -> Item | None:
        # Validate each body's revision against GitHub; file lists also require
        # the same immutable PR head. People and other metadata always refresh.
        previous_rows = {}
        if not fresh:
            try:
                previous = json.loads((repo.forge_dir(top) / "prs-cache.json").read_text("utf-8"))["data"]
                previous_rows = {(pr["number"], pr["headRefOid"]): pr
                         for week in previous["weeks"] for pr in week["prs"]
                         if isinstance(pr.get("number"), int) and pr.get("headRefOid")
                         and isinstance(pr.get("files"), list)}
            except (OSError, ValueError, KeyError, TypeError):
                pass
        day_counts = Counter(str(pr.get("mergedAt") or "")[:10] for pr in previous_rows.values())
        # Board restoration and backfill share these windows. The first Monday
        # is at least 42 days ago, including the cutoff on a Sunday (48 days).
        starts = [*full_weeks(now, 6), full_weeks(now + timedelta(weeks=1), 1)[0]]
        def week(start: datetime) -> list[Item] | None:
            def listing(_now: datetime) -> list[Item] | None:
                query = f"merged:{start:%Y-%m-%d}..{start + timedelta(days=6):%Y-%m-%d}"
                if previous_rows:
                    # The last read tells us where pagination would serialize a
                    # busy week. Cover the same seven days in parallel ranges
                    # sized for GitHub's 100-row pages; never truncate a range.
                    ranges, low, count = [], start, 0
                    for offset in range(7):
                        day = start + timedelta(days=offset)
                        size = day_counts.get(f"{day:%Y-%m-%d}", 0)
                        if count and count + size > 100:
                            ranges.append((low, day - timedelta(days=1)))
                            low, count = day, 0
                        count += size
                    ranges.append((low, start + timedelta(days=6)))
                    def metadata(bounds: tuple[datetime, datetime]) -> list[Item] | None:
                        return _listing(top, "merged", "--search",
                                        f"merged:{bounds[0]:%Y-%m-%d}..{bounds[1]:%Y-%m-%d}",
                                        fields=FIELDS.replace(",body", "").removesuffix(",files"))
                    with ThreadPoolExecutor(len(ranges)) as pages:
                        found = list(pages.map(metadata, ranges))
                    if None in found:
                        return None
                    rows = [pr for page in found if page is not None for pr in page]
                    if len(rows) >= 1000:  # Preserve the weekly ceiling and its unknown counts.
                        rows = metadata((start, start + timedelta(days=6)))
                    elif len(ranges) > 1:
                        rows.sort(key=lambda pr: pr.get("number", 0), reverse=True)
                    if rows is None:
                        return None
                    restored, missing = [], []
                    for pr in rows:
                        old = previous_rows.get((pr.get("number"), pr.get("headRefOid")), {})
                        if (pr.get("updatedAt") and pr["updatedAt"] == old.get("updatedAt")
                                and isinstance(old.get("body"), str)):
                            restored.append({**pr, "body": old["body"], "files": old["files"]})
                        else:
                            missing.append(pr)
                    if not missing:
                        return restored
                    if len(missing) == 1 and isinstance(missing[0].get("number"), int):
                        done = repo.run("gh", "pr", "view", str(missing[0]["number"]), "--json", FIELDS, cwd=top)
                        try:
                            record = json.loads(done.stdout) if done.returncode == 0 else None
                        except ValueError:
                            return None
                        if not (isinstance(record, dict) and isinstance(record.get("body"), str)
                                and isinstance(record.get("files"), list)
                                and record.get("number") == missing[0]["number"]
                                and record.get("headRefName") == missing[0].get("headRefName")):
                            return None
                        by_number = {pr["number"]: pr for pr in [*restored, record]}
                        return [by_number[pr["number"]] for pr in rows]
                return _listing(top, "merged", "--search", query, fields=merged_fields if fresh else FIELDS)
            return (listing(now) if fresh or start == starts[-1] else
                    _cached(top, f"prs-week-{start:%Y-%m-%d}", listing, seconds=86400))
        with ThreadPoolExecutor(len(starts) + 2) as pool:
            # Repositories that needed older parts before will usually need them
            # again. Refresh that small inventory beside the weekly requests.
            older_read = (pool.submit(merged_before_weeks, top)
                          if any(repo.forge_dir(top).glob("prs-older-*-cache.json")) else None)
            opened_read = open_read or pool.submit(_listing, top, "open",
                                                   fields=open_fields if fresh else FIELDS.removesuffix(",files"))
            lists = list(pool.map(week, starts))
            opened = opened_read.result()
            if older_read is not None:
                older_read.result()
        if not fresh and (opened is None or None in lists):
            return None
        weeks = []
        for start, found in zip(starts, lists):
            # A capped week need not hold all of its rows, so its counts are unknown.
            weeks.append({"start": start.isoformat(), "prs": found or [],
                          "complete": found is not None and len(found) < 1000})
        return {"open": opened or [], "open_complete": opened is not None and len(opened) < 1000,
                "weeks": weeks}
    if fresh:
        return fetch(time_records.when(repo.now()) or datetime.now(timezone.utc))
    current = repo.command_fact("github prs", top, lambda: _cached(top, "prs-cache", fetch))  # one try a command
    return (_cached(top, "prs-cache", lambda _: None, stale=True)
            if current is None and people else current)


def person(record: Item | str | None = None, name: str | None = None, *, field: str | None = None,
           names: dict | None = None) -> Item:
    """Use a loaded login and keep its name; a login alone is also a visible name."""
    if field:
        actors = record if isinstance(record, dict) else {}
        summary = actors.get("summary") or {}
        event = next((entry for entry in actors.get("events", [])
                      if entry.get("event") == {"started_by": "item started", "approved_by": "plan approved"}[field]), {})
        record = ({"name": summary.get(field), "login": summary.get(field + "_login")}
                  if summary.get(field) or summary.get(field + "_login")
                  else {"name": event.get("by"), "login": event.get("by_login"), "email": event.get("email")})
    record = {"login": record} if isinstance(record, str) else record or {}
    login = record.get("login")
    display = record.get("name") or name or login
    identity = ("login", login.casefold()) if login else (
        ("email", record["email"].casefold()) if record.get("email") else None)
    if names is not None and identity and display:
        display = names.setdefault(identity, display)
    return {"name": display, "login": login}


def merged_before_weeks(top: Path, branches: set[str] | None = None) -> dict[str, Item]:
    """Older merged names, with bodies only for the parts the board still needs.
    The list keeps its original 1,000-PR ceiling and daily lifetime."""
    now = time_records.when(repo.now()) or datetime.now(timezone.utc)
    cutoff = full_weeks(now, 6)[0] - timedelta(days=1)
    def names(_now: datetime) -> list[Item] | None:
        return _listing(top, "merged", "--search", f"merged:*..{cutoff:%Y-%m-%d}",
                        fields="headRefName,number,mergedAt")
    found = {pr["headRefName"]: pr for pr in _cached(
        top, f"prs-older-{cutoff:%Y-%m-%d}-cache", names, seconds=86400) or []
        if isinstance(pr.get("headRefName"), str)}
    if branches is None:
        return found
    needed = {branch: pr for branch, pr in found.items() if branch in branches}
    def read(branch: str) -> tuple[str, Item]:
        if "body" in needed[branch]:
            return branch, needed[branch]  # An unexpired full record from an earlier release.
        def fetch(_now: datetime) -> list[Item] | None:
            # "*..day" rather than "<day": cmd.exe reads "<" in a gh.cmd argument as a redirect.
            return _listing(top, "merged", "--head", branch, "--search", f"merged:*..{cutoff:%Y-%m-%d}")
        rows = _cached(top, f"prs-older-{cutoff:%Y-%m-%d}-{branch.replace('/', '-')}-cache",
                       fetch, seconds=86400) or []
        return branch, next((pr for pr in reversed(rows) if pr.get("headRefName") == branch), needed[branch])
    with ThreadPoolExecutor(4) as pool:
        return dict(pool.map(read, sorted(needed)))


def details(top: Path) -> list[Item]:
    """The last 25 merged pull requests with their files and checks, for the success numbers,
    cached for a minute like the lists."""
    return _cached(top, "prs-details-cache", lambda now: _listing(
        top, "merged", fields="headRefName,headRefOid,state,title,body,mergedAt,mergedBy,url,files,statusCheckRollup",
        limit="25")) or []


def failed_schedules(top: Path) -> list[Item]:
    """Failed scheduled workflows and manual Forge full runs on the default branch.
    Read each run list once and one log per failed workflow, kept ten minutes."""
    branch = repo.default_branch(top)

    def fetch(now: datetime) -> list[Item] | None:
        # ponytail: the newest 100 scheduled runs; a frequent schedule can crowd out a daily one.
        # Separate query fields avoid cmd.exe interpreting an ampersand in a gh.cmd argument.
        with ThreadPoolExecutor(2) as pool:
            manual_read = pool.submit(repo.run, "gh", "api", "repos/{owner}/{repo}/actions/workflows/forge.yml/runs",
                                      "--method", "GET", "--raw-field", "event=workflow_dispatch",
                                      "--raw-field", f"branch={branch}", "--raw-field", "per_page=100", cwd=top)
            done = repo.run("gh", "api", "repos/{owner}/{repo}/actions/runs", "--method", "GET",
                            "--raw-field", "event=schedule", "--raw-field", f"branch={branch}",
                            "--raw-field", "per_page=100", cwd=top)
            manual = manual_read.result()
        try:
            runs = json.loads(done.stdout).get("workflow_runs") if done.returncode == 0 else None
        except (ValueError, AttributeError):
            return None
        if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
            return None
        try:
            manual_runs = json.loads(manual.stdout).get("workflow_runs", []) if not manual.returncode else []
        except (ValueError, AttributeError):
            manual_runs = []
        if isinstance(manual_runs, list) and all(isinstance(run, dict) for run in manual_runs):
            runs += manual_runs
        runs.sort(key=lambda run: run.get("created_at", ""), reverse=True)
        latest: dict[Any, Item] = {}
        for run in runs:  # newest first
            latest.setdefault(run.get("workflow_id"), run)
        def failure(run: Item) -> Item | None:
            def read(_now: datetime) -> Item | None:
                log = repo.run("gh", "run", "view", str(run.get("id")), "--log-failed", cwd=top)
                if log.returncode != 0:
                    return None
                lines = log.stdout.splitlines()
                return {"workflow": str(run.get("name") or "workflow"), "branch": branch,
                        "event": run.get("event", "schedule"),
                        "file": str(run.get("path") or run.get("workflow_id")).rsplit("/", 1)[-1],
                        "jobs": sorted({line.split("\t", 1)[0] for line in lines if "\t" in line}),
                        "tests": sorted({found[1] for line in lines if (found := re.search(
                            r"(?:FAILED|ERROR|-) (\S+?::[^\s\[]+(?:\[.*?\])?|\S+\.py)(?= - |$)", line))})}
            # A completed attempt's log is immutable; reruns reuse the id with a new attempt.
            if type(run.get("id")) is int and type(run.get("run_attempt")) is int and run["run_attempt"] > 0:
                return _cached(top, f"run-{run['id']}-{run['run_attempt']}-failure-cache", read, seconds=math.inf)
            return read(now)  # Missing attempt information cannot establish an immutable answer.
        with ThreadPoolExecutor(4) as pool:
            failed = list(pool.map(failure, [run for run in latest.values() if run.get("conclusion") == "failure"]))
        if None in failed:
            return None
        return sorted((run for run in failed if run is not None), key=lambda run: (run["workflow"], run["file"]))
    return _cached(top, "schedule-cache", fetch, seconds=600) or []


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
    """Started work idle a day or more, and the
    unfinished part the most unfinished parts wait on, longest-standing first."""
    found = []
    for row in rows:
        if row["kind"] == "story" or row.get("state") not in ("in progress", "ready to merge"):
            continue
        if row["idle_seconds"] is not None and row["idle_seconds"] >= 86400:
            found.append({**_entry(row, "stalled", f"No activity for {time_records.plain(row['idle_seconds'])}",
                                   None, now), "seconds": row["idle_seconds"]})
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
         person_waits: dict[str, list[Item]], names: dict | None = None) -> Item:
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
    later, clause = board_trends.facts(top, history, counts, list(items.values()), github, names)
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
