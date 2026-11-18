"""Read CI times from GitHub without keeping history or changing the check gate."""
from __future__ import annotations

import json
import re
from datetime import datetime
from math import ceil
from pathlib import Path
from statistics import median
from typing import Any

from forge import checks, repo

CHECKS = """checkSuites(first:20) { nodes { workflowRun { databaseId }
    checkRuns(first:100, filterBy: { checkType: ALL }) { nodes {
      name status conclusion startedAt completedAt
    } pageInfo { hasNextPage } }
  } pageInfo { hasNextPage } }"""
COMMIT_CHECKS = "commits(last:100) { nodes { commit { oid " + CHECKS + " } } pageInfo { hasPreviousPage } }"
PUSH_HEADS = """commits(last:100) { nodes { commit {
  id statusCheckRollup { contexts { totalCount } }
} } pageInfo { hasPreviousPage } }"""


def _read(top: Path, *args: str) -> Any:
    done = repo.run("gh", "api", *args, cwd=top, timeout=60)
    try:
        value = json.loads(done.stdout) if done.returncode == 0 else None
    except ValueError:
        return None
    return None if isinstance(value, dict) and value.get("errors") else value


def _pulls(top: Path, options: str, commits: str = COMMIT_CHECKS) -> dict[str, Any]:
    query = ("query($owner:String!,$name:String!) { repository(owner:$owner,name:$name) { "
             f"pullRequests({options}) {{ nodes {{ mergedAt updatedAt {commits} }} "
             "pageInfo { hasNextPage endCursor } } } }")
    value = _read(top, "graphql", "-F", "owner={owner}", "-F", "name={repo}", "-f", "query=" + query)
    try:
        pulls = value["data"]["repository"]["pullRequests"]
        return pulls if isinstance(pulls, dict) and isinstance(pulls.get("nodes"), list) else {}
    except (KeyError, TypeError):
        return {}


def _at(value: Any) -> float:
    return datetime.fromisoformat(value).timestamp()


def _seconds(start: Any, end: Any) -> float:
    return max(0, _at(end) - _at(start))


def _eligible(run: dict[str, Any], limit: int | None = None) -> bool:
    if str(run.get("conclusion")).lower() == "cancelled":
        return checks.cancelled_at_limit({
            **run, "status": str(run.get("status")).lower(), "conclusion": "cancelled",
            "started_at": run.get("started_at", run.get("startedAt")),
            "completed_at": run.get("completed_at", run.get("completedAt")),
        }, limit)
    return (bool(run.get("name")) and run["name"] != "Review pull request"
            and str(run.get("conclusion")).lower() not in ("skipped", "neutral"))


def _measure(top: Path, pr: dict[str, Any], current: bool = False) -> dict[str, Any] | None:
    pushes = []
    heads = 0
    for node in reversed(pr.get("commits", {}).get("nodes", [])):
        suites = node.get("commit", {}).get("checkSuites") or {}
        if suites.get("pageInfo", {}).get("hasNextPage"):
            return None  # A partial list cannot give an honest wall time or runner total.
        runs = []
        has_checks = False
        for suite in suites.get("nodes", []):
            suite_checks = suite.get("checkRuns") or {}
            if suite_checks.get("pageInfo", {}).get("hasNextPage"):
                return None
            has_checks = has_checks or bool(suite_checks.get("nodes"))
            runs.extend({**run, "checkSuite": {"workflowRun": suite.get("workflowRun")}}
                        for run in suite_checks.get("nodes", []))
        if not has_checks:
            continue  # A multi-commit push starts checks only on its head commit.
        limit = (checks.timeout_limit(top, node["commit"].get("oid", ""))
                 if any(str(run.get("conclusion")).lower() == "cancelled" for run in runs) else None)
        runs = [dict(run, conclusion="TIMED_OUT") if str(run.get("conclusion")).lower() == "cancelled" else run
                for run in runs if _eligible(run, limit)]
        heads += 1
        ended = [run for run in runs if str(run.get("status")).lower() == "completed"]
        try:
            if ended:
                seconds = max(_at(run["completedAt"]) for run in ended) - min(
                    _at(run["startedAt"]) for run in ended)
                slowest = max(ended, key=lambda run: _seconds(run["startedAt"], run["completedAt"]))
                pushes.append({"seconds": seconds, "runs": runs, "slowest": slowest,
                               "runner": sum(ceil(_seconds(run["startedAt"], run["completedAt"]) / 60) for run in ended),
                               "pending": len(runs) - len(ended), "limit": limit})
        except (KeyError, TypeError, ValueError):
            return None
        if heads == 5:
            break
    if heads < 5 and pr.get("commits", {}).get("pageInfo", {}).get("hasPreviousPage"):
        return None
    return (pushes[0] if pushes else None) if current else max(pushes, key=lambda push: push["seconds"], default=None)


def _duration(seconds: float) -> str:
    minutes, seconds = divmod(round(seconds), 60)
    return (f"{minutes} min" + (f" {seconds} s" if seconds else "")) if minutes else f"{seconds} s"


def _job_name(run: dict[str, Any]) -> str:
    duration = _duration(_seconds(run["startedAt"], run["completedAt"]))
    result = ", timed out" if str(run.get("conclusion")).lower() == "timed_out" else ""
    return f"{run['name']} ({duration}{result})"


def _stages(jobs: list[dict[str, Any]]) -> str:
    totals: dict[str, float] = {name: 0 for name in ("queue", "setup", "selection", "tests", "retries")}
    reported = set()
    try:
        latest = {}
        for job in jobs:
            latest[job["name"]] = max(latest.get(job["name"], 1), job.get("run_attempt", 1))
        for job in jobs:
            if job.get("created_at") and job.get("started_at"):
                totals["queue"] += _seconds(job["created_at"], job["started_at"])
                reported.add("queue")
            if job.get("run_attempt", 1) < latest[job["name"]] and job.get("completed_at"):
                totals["retries"] += _seconds(job["started_at"], job["completed_at"])
                reported.add("retries")
                continue
            for step in job.get("steps", []):
                if not step.get("started_at") or not step.get("completed_at"):
                    continue
                name = step["name"].lower()
                stage = ("retries" if re.search(r"retr(y|ies)|rerun", name) else
                         "selection" if "review-tests.py" in name or "select" in name or "pick" in name else
                         "tests" if "test" in name else "setup")
                totals[stage] += _seconds(step["started_at"], step["completed_at"])
                reported.add(stage)
    except (KeyError, TypeError, ValueError):
        return "stage times unavailable"
    return "; ".join(f"{name} {_duration(seconds)}" if name in reported
                     else f"{name} not reported separately" for name, seconds in totals.items())


def report(top: Path, branch: str, *, current: bool = False) -> None:
    prs = _pulls(top, f"first:1,states:OPEN,headRefName:{json.dumps(branch)}").get("nodes", [])
    measured = _measure(top, prs[0], current) if prs else None
    if measured is None:
        return  # Timing is optional information; GitHub's check results still decide the gate.
    slowest = measured["slowest"]
    jobs = []
    ids = {run.get("checkSuite", {}).get("workflowRun", {}).get("databaseId")
           for run in measured["runs"] if run.get("checkSuite", {}).get("workflowRun")}
    for run_id in ids - {None}:
        page, read = 1, 0
        while True:
            endpoint = f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs?filter=all&per_page=100"
            value = _read(top, endpoint + (f"&page={page}" if page > 1 else ""))
            if not isinstance(value, dict) or not isinstance(value.get("jobs"), list):
                break
            jobs.extend({**job, "run_id": run_id} for job in value["jobs"] if _eligible(job, measured["limit"]))
            read += len(value["jobs"])
            if not value["jobs"] or read >= value.get("total_count", read):
                break
            page += 1
    slow_run = (slowest.get("checkSuite", {}).get("workflowRun") or {}).get("databaseId")
    slow_jobs = [job for job in jobs if job["run_id"] == slow_run
                 and job.get("name") in (slowest["name"], "docs-check")]
    line = (f"CI: {_duration(measured['seconds'])} (10 min budget); "
            f"{measured['runner']} runner minutes; slowest {_job_name(slowest)}; "
            + _stages(slow_jobs))
    if pending := measured["pending"]:
        line += f"; {pending} job was still running" if pending == 1 else f"; {pending} jobs were still running"
    print(line, flush=True)
    for run_id, name in dict.fromkeys((job["run_id"], job["name"]) for job in jobs
                                      if re.fullmatch(r"test group \d+ of \d+", job["name"])):
        group = [job for job in jobs if job["run_id"] == run_id
                 and job["name"] in (name, "docs-check") and job.get("completed_at")]
        try:
            seconds = max(_at(job["completed_at"]) for job in group) - min(
                _at(job.get("created_at") or job["started_at"]) for job in group)
        except (KeyError, TypeError, ValueError):
            continue
        if seconds > 600:
            print(f"CI over budget: {name} ({_duration(seconds)}); {_stages(group)}", flush=True)


def warning(top: Path) -> str:
    prs: list[dict[str, Any]] = []
    cursor = ""
    while True:
        page = _pulls(top, "first:40,states:MERGED,orderBy:{field:UPDATED_AT,direction:DESC}" + cursor,
                      PUSH_HEADS)
        nodes = page.get("nodes", [])
        if not nodes:
            return ""
        prs.extend(nodes)
        prs.sort(key=lambda pr: pr.get("mergedAt") or "", reverse=True)
        info = page.get("pageInfo", {})
        # updatedAt >= mergedAt: once the page is older than the twentieth merge,
        # later pages cannot contain a more recent merge, even after old PR edits.
        if (not info.get("hasNextPage") or len(prs) >= 20
                and (nodes[-1].get("updatedAt") or "") <= (prs[19].get("mergedAt") or "")):
            break
        cursor = ",after:" + json.dumps(info["endCursor"])
    # Read full check attempts only for the five push heads per PR. Asking for
    # every check on every intermediate commit exceeds GitHub's query limits.
    heads = {}
    for pr in prs[:20]:
        commits = pr.get("commits", {})
        chosen = [node for node in commits.get("nodes", [])
                  if ((node["commit"].get("statusCheckRollup") or {}).get("contexts") or {}).get("totalCount")][-5:]
        if len(chosen) < 5 and commits.get("pageInfo", {}).get("hasPreviousPage"):
            return ""
        pr["commits"] = {"nodes": chosen}
        for node in chosen:
            heads.setdefault(node["commit"]["id"], []).append(node)
    if not heads:
        return ""
    ids = list(heads)
    warning_checks = CHECKS.replace("workflowRun { databaseId }", "")
    fields = [f"checks_{offset}: nodes(ids:" + json.dumps(ids[offset:offset + 50])
              + ") { ... on Commit { id oid " + warning_checks + " } }" for offset in range(0, len(ids), 50)]
    value = _read(top, "graphql", "-f", "query=query { " + " ".join(fields) + " }")
    if not isinstance(value, dict) or not isinstance(value.get("data"), dict):
        return ""
    for offset in range(0, len(ids), 50):
        commits = value["data"].get(f"checks_{offset}")
        if not isinstance(commits, list):
            return ""
        for commit in commits:
            if not commit or commit.get("id") not in heads:
                return ""
            for node in heads.pop(commit["id"]):
                node["commit"] = commit
    if heads:
        return ""
    measured = [_measure(top, pr) for pr in prs[:20]]
    values = sorted((value for value in measured if value is not None and not value["pending"]),
                    key=lambda value: value["seconds"])
    if not values:
        return ""
    usual = median(value["seconds"] for value in values)
    if usual <= 600:
        return ""
    representative = values[len(values) // 2]
    return (f"Usual CI time for the last {len(values)} merged pull requests is {_duration(usual)}, "
            f"over the 10 min budget; slowest {_job_name(representative['slowest'])}. "
            "Forge's guide lists the fixes.")
