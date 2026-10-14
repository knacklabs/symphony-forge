"""`forge board`: one static page that tells each story's history and current state in plain English,
how long each step took, which steps were slow, and the three success numbers. `forge next` shows
those numbers in one line once the check date is here.

It reads every copy of the state: in local worktrees, on Forge's branches on the remote, and on the
default branch. Steps are only ever added, so the copy with the most dated steps is the newest. gh
adds each pull request's title, summary line, merge date and when its checks passed; close stores
none of those. Without gh the page shows the state and its dates only.
"""
from __future__ import annotations

import functools
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from textwrap import shorten
from typing import Any

from forge import __version__, approval, board_facts, board_graph, board_visuals, codex, machine, repo, story, task

COMMANDS = [{
    "words": "board", "run": "board", "changes_state": False,
    "help": "Write and open the plain-English board page",
    "args": [(('--json',), {"action": "store_true", "help": "Print the machine view"}),
             (('--out',), {"metavar": "PATH", "help":
              "write the page here instead of .git/forge/board.html"})],
    "position": 60,
    "listing": "| `forge board` | Writes the plain-English board page and opens it (`--out <path>` to write it elsewhere) |",
}]

CHECK_DATE = "2026-11-15"  # ponytail: the rebuild's check date, from the spec's success measure
PREFIXES = ("story/", "task/", "fix/", "forge/")  # the branches Forge starts; forge/ is migrate's
STATE = re.compile(r"\.factory/(?:stories/(?P<key>[A-Z][A-Z0-9-]*)/(?:story|tasks/(?P<task>[A-Z0-9][A-Z0-9-]*))"
                   r"|fixes/(?P<fix>[a-z0-9][a-z0-9-]*))\.json")
# ponytail: a merged fix "fixed Forge" when it changed Forge's own files; widen once a miss shows up.
FORGE_FILES = ("forge.toml", ".claude/", ".codex/", ".github/workflows/forge.yml", "src/forge/")
STATUS = {"started": "Waiting to start", "working": "In progress", "reviewing": "Under review",
          "fixing": "Needs fixes", "waiting for checks": "Checks running",
          "ready": "Ready to merge", "hotspot": "Needs your decision"}

Item = dict[str, Any]


def board(args: Any) -> int:
    top = repo.root()
    if repo.run("git", "fetch", "-q", "--prune", "--tags", "origin", cwd=top).returncode:
        print("Could not refresh work from GitHub; showing the local git records.", file=sys.stderr)
    if args.json:
        print(json.dumps(machine_board(top)))
        return 0
    view = machine_board(top, trim=False)
    stories, prs = _gather(top)
    page = board_visuals.page(view, "How the factory is doing: " + "; ".join(_numbers(stories, prs)) + ".",
                              prs is not None, _when(repo.now()) or datetime.now(timezone.utc))
    out = Path(args.out) if args.out else repo.forge_dir(top) / "board.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(page.encode("utf-8"))  # same bytes on Windows
    print(f"Wrote the board to {out}")
    if sys.stdout.isatty():  # ponytail: open it for a person at a terminal; never in a pipe or a test
        webbrowser.open(out.resolve().as_uri())
    return 0


def repo_root(top: Path) -> str:
    """The main worktree identifies a repo across all of its worktrees."""
    listing = repo.git("worktree", "list", "--porcelain", cwd=top)
    return str(Path(listing.splitlines()[0].removeprefix("worktree ")).resolve())


# The explicit query retains GitHub's own occurrence ids; gh pr list's default rollup does not.
CHECKS_QUERY = """query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 25, states: OPEN, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes { number headRefName headRefOid title url isDraft body
        commits(last: 1) { nodes { commit { oid statusCheckRollup {
          contexts(first: 100) { pageInfo { hasNextPage } nodes {
            __typename
            ... on CheckRun { databaseId name status conclusion startedAt completedAt }
            ... on StatusContext { id context state createdAt }
          } }
        } } } }
      }
    }
  }
}"""


def _machine_prs(top: Path) -> list[Item]:
    """One request for the newest 25 open PRs, cached across command invocations for 60s."""
    cache = repo.forge_dir(top) / "checks-cache.json"
    now = _when(repo.now())
    try:
        saved = json.loads(cache.read_text(encoding="utf-8"))
        at = _when(saved.get("fetched_at"))
        if now and at and 0 <= (now - at).total_seconds() < 60 and isinstance(saved.get("prs"), list):
            return saved["prs"]
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
        temp.write_text(json.dumps({"fetched_at": repo.now(), "prs": prs}), encoding="utf-8")
        os.replace(temp, cache)
    except OSError:
        pass  # A read-only/full Git directory must not prevent a view.
    finally:
        temp.unlink(missing_ok=True)
    return prs


def _checks(pr: Item | None, required: list[str]) -> tuple[str, list[Item], list[Item]]:
    if not pr:
        return "unknown", [], []
    try:
        commit = pr["commits"]["nodes"][-1]["commit"]
        if not pr.get("headRefOid") or commit.get("oid") != pr["headRefOid"]:
            return "unknown", [], []
        contexts = commit["statusCheckRollup"]["contexts"]
        nodes = contexts["nodes"]
        if not isinstance(nodes, list):
            return "unknown", [], []
    except (KeyError, TypeError, IndexError):
        return "unknown", [], []
    statuses, events, names, failures = [], [], [], []
    for check in nodes:
        if not isinstance(check, dict):
            continue
        name = check.get("name") or check.get("context") or "Check"
        names.append(name)
        value = (check.get("conclusion") if check.get("status") == "COMPLETED" else None) or check.get("state")
        failed = (value in ("FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE", "STALE")
                  or value in ("NEUTRAL", "SKIPPED") and
                  any(name == want or name.startswith(want + " (") for want in required))
        statuses.append("fail" if failed else "pass" if value in ("SUCCESS", "NEUTRAL", "SKIPPED")
                        else "running" if value in ("PENDING", "EXPECTED") or check.get("status") in
                        ("QUEUED", "IN_PROGRESS", "WAITING", "PENDING", "REQUESTED") else "unknown")
        if failed:
            failures.append({"job": name, "cause": "timeout" if value == "TIMED_OUT" or
                             value == "CANCELLED" and check.get("timeout") is True else "failed"})
            identity = (f"check-run:{check['databaseId']}:{check['completedAt']}"
                        if check.get("databaseId") is not None and check.get("completedAt")
                        else f"status:{check['id']}" if check.get("__typename") == "StatusContext" and check.get("id") else None)
            if identity:
                events.append({"id": identity, "kind": "checks_failed", "title": f"{name} failed"})
    missing = any(not any(n == want or n.startswith(want + " (") for n in names) for want in required)
    status = ("fail" if "fail" in statuses else "running" if "running" in statuses else
              "unknown" if not statuses or "unknown" in statuses or missing or
              contexts.get("pageInfo", {}).get("hasNextPage") else "pass")
    return status, events, failures


def _rollup(pr: Item) -> list[Item]:
    try:
        commit = pr["commits"]["nodes"][-1]["commit"]
        if not pr.get("headRefOid") or commit.get("oid") != pr["headRefOid"]:
            return []
        nodes = commit["statusCheckRollup"]["contexts"]["nodes"]
        return [{**n, "startedAt": n.get("createdAt")} if n.get("__typename") == "StatusContext" else n
                for n in nodes if isinstance(n, dict)] if isinstance(nodes, list) else []
    except (KeyError, TypeError, IndexError):
        return []


def _event_history(top: Path) -> tuple[list[Item], dict[str, list[Item]]]:
    def read():
        path = repo.forge_dir(top) / "events.jsonl"
        recorded, by_item = [], {}
        for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    recorded.append(event)
                    by_item.setdefault(event.get("item"), []).append(event)
            except ValueError:
                continue
        return recorded, by_item
    return repo.command_fact("board events", top, read)


def active_runs(top: Path, item: str, activity: list[Item] | None = None,
                round_number: int | None = None) -> list[Item]:
    if activity is None:
        activity = _event_history(top)[1].get(item, [])
    ended = {e.get("run_id") for e in activity if e.get("event") == "run end"}
    runs = []
    for event in activity:
        if (event.get("event") != "run start" or event.get("id") in ended
                or round_number is not None and event.get("round") is not None
                and event["round"] != round_number):
            continue
        kind = event.get("kind")
        if kind in ("work", "worker") or kind == "read" and event.get("family") == "codex":
            lock = codex._item_file(top, item, ".lock", "Grill" if kind == "read" else "Build")
            if lock.is_file() and codex._alive(codex._json(lock)) is False:
                continue
        runs.append(event)
    return runs


def machine_board(top: Path, history: Item | None = None, trim: bool = True) -> Item:
    """Stories and fixes, with tasks one level down. No invented run times or occurrence ids.
    `trim` leaves out work finished more than seven days ago; the page keeps it."""
    from forge import nextstep, time_records

    trees = story.worktrees(top)
    history = history if history is not None else _machine_history(top)
    if not trim:
        history = {**history, "expired": set()}
    landed = history["landed"]
    starters = _starters(top)
    best: dict[str, tuple[Item, Path | str]] = {}
    merged = set()
    for rel, state, where in history["copies"]:
        if where == landed:
            merged.add(rel)
        if rel not in best or len(_steps(state)) > len(_steps(best[rel][0])):
            best[rel] = state, where
    prs = _machine_prs(top)
    by_branch = {p.get("headRefName"): p for p in prs}
    # Older open PRs keep their number, but deliberately have unknown checks.
    github = board_facts.prs(top)
    for pr in (github or {}).get("open", []):
        if isinstance(pr.get("headRefName"), str):
            by_branch[pr["headRefName"]] = {**by_branch.get(pr["headRefName"], {}), **pr}
    finished_prs = board_facts.merged_prs(github)
    by_branch.update({p["headRefName"]: p for p in finished_prs})
    merged_details = {p["headRefName"]: p for p in finished_prs}
    merged_prs = set(merged_details)
    merged_dates = {branch: pr.get("mergedAt") for branch, pr in merged_details.items()}
    readiness: dict[str, Item] = {}
    person_waits: dict[str, list[Item]] = {}  # each part's and fix's waits on a person, for Needs you
    roadmap = {s["key"]: s for s in repo.roadmap(top) if s.get("status") != "superseded"}
    completed = {key: state for key, state in history["stories"].items() if state.get("status") == "done"}
    completed.update({key: state for key, state in roadmap.items() if state.get("status") == "done"})
    completed.update({STATE.fullmatch(rel)["key"]: state for rel, (state, _) in best.items()
                      if rel.endswith("/story.json") and state.get("status") == "done"})
    recorded, by_item = _event_history(top)
    timings = time_records.read(top, "timings")

    branch_dates = dict(line.split("\0", 1) for line in repo.git(
        "for-each-ref", "--format=%(refname:short)%00%(committerdate:iso-strict)",
        "refs/heads", "refs/remotes/origin", cwd=top).splitlines())
    timing_dates: dict[str, list[str]] = {}
    timings_by_item: dict[Any, list[Item]] = {}
    for timing in timings:
        timings_by_item.setdefault(timing.get("item"), []).append(timing)
        start = _when(timing.get("start"))
        if start:
            end = start + timedelta(seconds=timing.get("seconds") or 0)
            timing_dates.setdefault(timing.get("item"), []).append(end.isoformat())

    @functools.cache
    def story_read(key: str) -> tuple[str, Item]:
        """A story's plan read and task rows: the same for the story and each of its parts."""
        where = landed if key in completed else story.plan_ref(top, key, history)  # finished: the landed plan
        if where == f"story/{key}":
            where = trees.get(where) or where
        notes = _read(top, where, f"plans/{key}.read.md", history)
        assignments = task.rows(task.sections(story._plan(top, key, landed if key in completed else None, history)))
        if not story._record(notes)[0]:
            return "none", assignments
        text = _read(top, where, f"plans/{key}.md", history)
        digest = repo.blob_hash(text)
        try:
            story.gate(key, f"plans/{key}.md", notes, digest, text, top)
            return "passed", assignments
        except repo.Refused:
            return "blocked", assignments

    def row(item: str, kind: str, title: str, state: Item, where: Path | str) -> Item:
        if kind == "story" and item in completed:
            state = {**state, **completed[item], "status": "done"}
        elif kind == "task" and item.split("/")[0] in completed:
            state = {**state, "status": "merged"}
        if kind == "fix":
            title = shorten(title, width=70, placeholder="…")
        if kind != "story" and repo.state_path(item) in merged:
            state = {**state, "status": "merged"}
        branch = state.get("branch") or (f"task/{item.replace('/', '-')}" if kind == "task"
                                         else f"{kind}/{item}")
        if kind != "story" and branch in merged_prs:
            state = {**state, "status": "merged"}
        tree = trees.get(branch)
        cfg = nextstep._report_config(tree or top, {})
        pr = by_branch.get(branch)
        state = nextstep.at_ref(top, item, state, pr) if kind != "story" else state
        checks, events, failures = _checks(pr, cfg["checks"])
        plan_text = ""
        if state.get("status") == "done" or (state.get("status") == "merged" and not tree):
            lines = [f"{title} is finished."]
        elif not state and kind == "story":
            lines = [f"{title} needs a story doc.", f'Next: forge story new {item} {json.dumps(title)}']
        else:
            try:
                if kind == "story":
                    plan_text = _read(top, tree or where, f"plans/{item}.md", history)
                lines = (nextstep._item(item, title, state, top, tree, by_branch, {}) if kind != "story"
                         else nextstep._story(top, item, tree, plan_text,
                                              title, trees, merged_prs, by_branch, {}, history,
                                              readiness.setdefault(item, {}))[0])
            except (repo.Refused, subprocess.CalledProcessError):
                lines = [f"Couldn't check the next step for {title}; check the connection, then run forge next."]
        review = state.get("review") or {}
        dismissed = {d.get("finding") for d in review.get("dismissals", [])
                     if isinstance(d, dict)}
        findings = [{"title": f.get("title") or "Untitled finding", "priority": f.get("priority")} for n, f in
                    enumerate(review.get("findings", []), 1)
                    if isinstance(f, dict) and n not in dismissed]
        worker = None
        lock = codex._item_file(top, item, ".lock", "Grill" if kind == "story" else "Build")
        if lock.is_file() and codex._alive(codex._json(lock)) is not False:
            family = state.get("worker")
            role = "grill" if kind == "story" else "build" if kind == "task" else "lite"
            if family == "codex" and kind != "story":
                turns = codex._item_file(top, item, ".log", "Build")
                for line in turns.read_text(encoding="utf-8").splitlines() if turns.is_file() else []:
                    try:
                        turn = json.loads(line)
                        if isinstance(turn, dict) and turn.get("kind") in ("Build", "Fix", "Lite"):
                            role = turn["kind"].lower()
                    except ValueError:
                        continue
            try:
                models = ({} if family not in ("codex", "claude") else
                          repo.models(cfg, role, family) if kind == "story" else
                          repo.worker_models(cfg, role, family))
                if kind == "task":
                    key, tid = item.split("/")
                    spec = task.rows(task.sections(_read(top, where, f"plans/{key}.md"))).get(tid) or {}
                    if family in ("codex", "claude") and repo.user_facing(cfg, spec):
                        models = repo.design_models(cfg, family)
                elif (family in ("codex", "claude") and kind == "fix"
                      and state.get("allow_large") == "Prototype before sign-off"
                      and repo.is_prototype(tree or top, cfg)):
                    models = repo.design_models(cfg, family)
                model = models.get("model")
            except repo.Refused:
                model = None
            worker = {"kind": "read" if kind == "story" else "build", "model": model,
                      "started_at": None}
        activity = by_item.get(item, [])
        active = active_runs(top, item, activity, state.get("round") if kind != "story" else None)
        finished = state.get("status") in ("done", "merged")
        if finished:
            active, worker = [], None
        agents = [e for e in active if e.get("kind") in ("work", "worker", "read", "review")
                  and (kind == "story" or "round" not in state or e.get("round") == state["round"])]
        if agents:
            agent = agents[-1]
            worker = {"kind": {"work": "build", "worker": "build"}.get(agent["kind"], agent["kind"]),
                      "tool": agent.get("family"), "model": agent.get("model"),
                      "effort": agent.get("effort"), "round": agent.get("round"),
                      "started_at": agent.get("at"),
                      "step": next((e.get("step") for e in reversed(activity)
                                    if e.get("run_id") == agent["id"] and e.get("step")), None)}
            for key in ("model", "effort"):
                worker[key] = next((e[key] for e in reversed(activity)
                                    if e.get("run_id") == agent["id"] and key in e), worker[key])
        now = _when(repo.now())
        elapsed = lambda at: max(0, (now - _when(at)).total_seconds()) if now and _when(at) else None
        if worker:
            worker["elapsed"] = elapsed(worker.get("started_at"))
        dates = ([e.get("at") for e in activity] + [s.get("at") for s in _steps(state)]
                 + timing_dates.get(item, [])
                 + [branch_dates.get(branch), branch_dates.get("origin/" + branch)])
        if kind == "story":
            dates.extend(e.get("at") for e in recorded if str(e.get("item", "")).startswith(item + "/"))
            prefix = f".factory/stories/{item}/tasks/"
            dates.extend(s.get("at") for rel, (part, _) in best.items() if rel.startswith(prefix)
                         for s in _steps(part))
            dates.extend(at for rel, at in history["dates"].items() if rel.startswith(prefix))
            part_branches = {f"task/{item}-{tid.strip('` ')}" for tid in task.rows(task.sections(plan_text))}
            part_branches.update(part.get("branch") or f"task/{item}-{STATE.fullmatch(rel)['task']}"
                                 for rel, (part, _) in best.items() if rel.startswith(prefix))
            dates.extend(merged_details.get(branch, {}).get("mergedAt") for branch in part_branches)
            dates.extend(at for part, times in timing_dates.items() if str(part).startswith(item + "/")
                         for at in times)
            dates.extend(branch_dates.get(ref) for branch in part_branches
                         for ref in (branch, "origin/" + branch))
        idle_since = (max((at for at in dates if _when(at)), key=_when, default=None)
                      or history["dates"].get(repo.state_path(item))) if not active and not worker and not finished else None
        test_runs = [e for e in active if e.get("kind") == "test"]
        tests = None
        if test_runs:
            current = test_runs[-1]
            tests = {"started_at": current.get("at"), "elapsed": elapsed(current.get("at"))}
            tests.update(next(({k: e[k] for k in ("done", "total") if e.get(k) is not None}
                               for e in reversed(activity) if e.get("run_id") == current["id"]
                               and e.get("event") == "progress"), {}))
        item_timings = timings_by_item.get(item, [])
        round_number = (worker.get("round") if worker and worker.get("round") is not None else
                        state.get("round", (activity or item_timings or [{}])[-1].get("round")))
        stages = []
        for name, step, kinds in (("Build", "worker round", ("work", "worker")),
                                  ("Tests", "test run", ("test",)), ("Review", "review", ("review",)),
                                  ("CI", "CI wait", ("ci",)), ("Merge", "merge", ())):
            records = [r for r in item_timings if round_number is not None
                       and r.get("round") == round_number and r.get("step") == step]
            live = [e for e in active if e.get("round") == round_number and e.get("kind") in kinds]
            outcome = records[-1].get("outcome") if records else None
            status = {"completed": "pass", "clean": "pass", "passed": "pass",
                      "failed": "fail", "blocked": "fail"}.get(outcome, outcome)
            end = (_when(records[-1].get("start")) if records else None)
            if end is not None and records[-1].get("seconds") is not None:
                end += timedelta(seconds=records[-1]["seconds"])
            else:
                end = None
            stages.append({"name": name, "status": status,
                           "started_at": records[0].get("start") if records else None,
                           "ended_at": end.isoformat() if end else None,
                           "seconds": sum(r.get("seconds") or 0 for r in records)
                           if any(r.get("seconds") is not None for r in records) else None})
            if live:
                stages[-1].update(status="running", started_at=live[0].get("at"), ended_at=None)
                stages[-1]["elapsed"] = elapsed(live[0].get("at"))
        stage, receipt = (nextstep._item_readiness(item, state, top, checks, runs=active, pr=pr)
                          if kind != "story" else (state.get("status"), {}))
        if kind == "story" and not finished:
            stage = readiness.get(item, {}).get("stage", "planning")
        if worker and not finished:
            stage = ("planning" if kind == "story" else
                     "reviewing" if worker["kind"] == "review" else "working")
            if kind != "story":
                lines = nextstep._item(item, title, {**state, "status": stage}, top, tree, by_branch, {})
            else:
                lines = [f"A reader is reading {title}.", "Next: wait for the reader to finish"]
        stage = stage or "unknown"
        pending = codex.record(top, item).get("question_id")
        latest_review = next((e for e in reversed(activity) if e.get("event") == "review result"), {})
        for event in activity:
            event_kind = event.get("event")
            if event_kind == "run end":
                occurrence_kind, message = "run_finished", f"{event.get('kind', 'Run').capitalize()} finished"
            elif event_kind == "worker question" and event.get("id") == pending:
                occurrence_kind, message = "worker_question", event.get("question")
            elif (event_kind == "review result" and event == latest_review
                  and (event.get("outcome") == "failed" or findings)):
                occurrence_kind, message = "review_findings", "Review found problems" if findings else "Review failed"
            else:
                continue
            events.append({"id": event["id"], "kind": occurrence_kind, "title": message})
        if kind != "story" and stage == "ready" and (identity := review.get("id")):
            events.append({"id": identity + ":" + receipt["commit"], "kind": "ready_to_merge",
                           "title": "Ready to merge"})
        doc = (tree / "plans" / f"{item}.md" if kind == "story" and stage != "done" and tree
               and approval.waiting_digest(item, tree) else None)
        read_key = item.split("/")[0] if kind != "fix" else None
        plan_read, assignments = story_read(read_key) if read_key else ("none", {})
        ci = {"status": {"pass": "green", "fail": "red", "running": "running"}.get(checks, "none")}
        if checks == "running":
            starts = [c.get("startedAt") for c in _rollup(pr or {}) if _when(c.get("startedAt"))
                      and (c.get("status") in ("QUEUED", "IN_PROGRESS", "WAITING", "PENDING", "REQUESTED")
                           or c.get("state") in ("PENDING", "EXPECTED"))]
            ci["elapsed"] = elapsed(min(starts, key=_when)) if starts else None
        elif checks == "unknown" and any(e.get("kind") == "ci" for e in active):
            ci = {"status": "running", "elapsed": elapsed(next(e["at"] for e in active if e.get("kind") == "ci"))}
        status = ({"done": "Finished", "merged": "Finished", "planning": "Planning",
                   "waiting for approval": "Waiting for approval", "approved": "Approved",
                   "checks failed": "Checks failed"}.get(stage) or STATUS.get(stage, "Not started yet"))
        finished_at = (merged_details.get(branch, {}).get("mergedAt") or state.get("finished")
                       or (history["dates"].get(repo.state_path(item)) if finished and kind != "story" else None))
        if finished and _when(finished_at):
            status += " on " + _day(_when(finished_at))
        if worker:
            status = {"build": "Worker", "read": "Plan read", "review": "Review"}.get(worker["kind"], "Worker") + " running"
            if worker.get("elapsed") is not None:
                status += " for " + board_visuals.duration(worker["elapsed"])
        elif tests:
            status = "Tests running"
            if tests.get("elapsed") is not None:
                status += " for " + board_visuals.duration(tests["elapsed"])
        idle_seconds = elapsed(idle_since)
        return {"id": item, "kind": kind, "title": title, "stage": stage, "status": status,
                "started_by": starters.get(repo.state_path(item)),
                "approved_by": _approver(top, read_key) if read_key else None,
                "developer": task.developer(assignments.get(item.split("/")[-1], {})) if kind == "task" else None,
                "outcome": " ".join(str(state.get("outcome") or "").split()) or None if kind == "story" else None,
                "took": [("Checks" if s["name"] == "CI" else s["name"]) + ": "
                         + board_visuals.stage_duration(s) for s in stages
                         if board_visuals.stage_seconds(s) is not None],
                "activity": {"status": "running", "action": active[-1].get("kind")} if active else
                            {"status": "running", "action": worker["kind"]} if worker else {"status": "idle"},
                "idle_since": idle_since, "idle_seconds": idle_seconds,
                "waits_on": lines[0] if not finished and not active and not worker and lines else None,
                "needs_person": not finished and bool(person_waits.setdefault(item, nextstep.person_waits(
                    top, item, state, stage, pr, readiness.get(item, {}).get("blocker")))),
                "stalled": bool(idle_seconds is not None and idle_seconds > 86400),
                "gates": {"plan_read": {"status": plan_read},
                          "review": {"status": "blocked", "count": len(findings)} if nextstep.review.blocking(review) else
                              {"status": "clean" if review else "none"}, "ci": ci},
                "tests": tests,
                "approval": {"doc": doc.resolve().as_posix()} if doc else None,
                "worker": worker, "pr": {"number": (pr or {}).get("number"), "url": (pr or {}).get("url"),
                       "checks": checks, "failures": failures},
                "findings": {"count": len(findings), "titles": [f["title"] for f in findings], "items": findings,
                             "dismissed": len(dismissed & set(range(1, len(review.get("findings", [])) + 1)))}, "round": round_number,
                "merged_by": (pr or {}).get("mergedBy"), "merged_at": finished_at if finished else None,
                **({k: v for k, v in time_records.combined(
                    top, item, state, (pr or {}).get("body") or "", events=activity, timings=item_timings,
                    ended_at=merged_dates.get(branch)).items()
                    if k not in ("events", "timings", "state", "ended_at", "seen", "known", "summary")} if kind != "story" else {}),
                "stages": stages, "occurrences": events, "next": nextstep.machine_next(lines),
                "children": []}

    items, children = {}, {}
    for rel, (state, where) in best.items():
        if rel in history["expired"]:
            continue
        match = STATE.fullmatch(rel)
        if match["fix"]:
            if state.get("kind") != "story-done":
                name = match["fix"]
                items[name] = row(name, "fix", state.get("why") or "A small fix", state, where)
        elif match["task"]:
            key, tid = match["key"], match["task"]
            plan_where = trees.get(f"story/{key}") or best.get(repo.state_path(key), ({}, where))[1]
            text = (_read(top, plan_where, f"plans/{key}.md", history)
                    if key in completed or story.plan_ref(top, key, history) == landed
                    else story._plan(top, key, history=history))
            names = task.rows(task.sections(text))
            names = {cell.strip("` "): spec for cell, spec in names.items()}
            title = (names.get(tid) or {}).get("Name") or "A part with no name yet"
            children.setdefault(key, []).append(row(f"{key}/{tid}", "task", title, state, where))
        else:
            key = match["key"]
            completion = history["stories"].get(key, {})
            if state.get("status") != "done" and completion.get("status") == "done":
                state = completion
            text = _read(top, trees.get(f"story/{key}", where), f"plans/{key}.md", history)
            title = state.get("title") or next((s.removeprefix("# ") for s in text.splitlines()
                                                if s.startswith("# ")), "A story with no title yet")
            items[key] = row(key, "story", title, state, where)
    for key, parts in children.items():
        if key not in items:
            items[key] = row(key, "story", "A story with missing state", {}, landed)
        items[key]["children"] = parts
        running = next((part for part in parts if part["activity"]["status"] == "running"
                        or part["gates"]["ci"]["status"] == "running"), None)
        if running and items[key]["stage"] != "done":
            items[key].update(activity={"status": "running", "action": running["activity"].get("action", "ci")},
                              idle_since=None, idle_seconds=None, waits_on=None, stalled=False)
    for key, state in roadmap.items():
        if key not in items and repo.state_path(key) not in history["expired"]:
            items[key] = row(key, "story", state.get("title") or "A story with no title yet",
                             completed.get(key, {}), landed)
    for key, item in items.items():
        if item["kind"] != "story" or item["stage"] == "done":
            continue
        for tid, spec in task.rows(task.sections(story._plan(top, key, history=history))).items():
            if (task.developer(spec) and repo.state_path(f"{key}/{tid}") not in history["expired"]
                    and not any(child["id"] == f"{key}/{tid}" for child in item["children"])):
                child = row(f"{key}/{tid}", "task", spec.get("Name") or tid, {}, landed)
                child.update(stage="unstarted", next=nextstep.machine_next(["Next: forge next"]))
                item["children"].append(child)
    older_parts: dict[str, list[Item]] = {}
    older = [(rel, state, match["key"], match["task"], state.get("branch") or f"task/{match['key']}-{match['task']}")
             for rel, (state, _) in best.items() if rel in history["expired"]
             and (match := STATE.fullmatch(rel))["task"] and match["key"] in items]
    # An unfinished story's parts merged before the weekly searches still bring their records.
    if any(branch not in by_branch and key not in completed for _, _, key, _, branch in older):
        by_branch.update({branch: pr for branch, pr in board_facts.merged_before_weeks(top).items()
                          if branch not in by_branch})
    for rel, state, key, tid, branch in older:
        if rel in merged or branch in merged_prs or key in completed:
            state = {**state, "status": "merged"}
        older_parts.setdefault(key, []).append(time_records.combined(
            top, f"{key}/{tid}", state, by_branch.get(branch, {}).get("body") or "",
            events=by_item.get(f"{key}/{tid}", []), timings=timings_by_item.get(f"{key}/{tid}", []),
            ended_at=by_branch.get(branch, {}).get("mergedAt")))
    notes_by_story = {key: _read(top, landed if key in completed else story.plan_ref(top, key, history),
                                 f"plans/{key}.read.md", history)
                      for key, current in items.items() if current["kind"] == "story"}
    past_notes = history["past notes"]  # read with every plan read, in the same one git process
    for key, notes in notes_by_story.items():
        current = items[key]
        current["read_rounds"] = _read_rounds(notes)
        read_rounds, seen = [], set()
        while notes:
            record, _ = story._record(notes)
            try:
                seconds = float(record["seconds"])
            except (KeyError, ValueError):
                seconds = None
            read_rounds.append({"read_at": record.get("read_at"), "seconds": seconds})
            previous = record.get("notes_seen")
            if not previous or previous in seen:
                break
            seen.add(previous)
            notes = past_notes.get(previous, "")
        started = _step(best.get(repo.state_path(key), ({}, landed))[0], "start")
        current.update(time_records.story([*current["children"], *older_parts.get(key, [])], read_rounds,
                                          unfinished=current["stage"] != "done",
                                          started_at=started.isoformat() if started else None,
                                          finished_at=completed.get(key, {}).get("finished")))
    # Maps keep the whole plan, including dependencies too old for the active rows.
    maps = []
    active_parts = {p["id"]: p for parts in children.values() for p in parts if p["stage"] != "unstarted"}
    for rel, (state, where) in best.items():
        match = STATE.fullmatch(rel)
        if not match["key"] or match["task"]:
            continue
        key = match["key"]
        text = (_read(top, trees.get(f"story/{key}", where), f"plans/{key}.md", history)
                if key in completed or story.plan_ref(top, key, history) == landed
                else story._plan(top, key, history=history))
        specs = task.rows(task.sections(text))
        parts = []
        for tid, spec in specs.items():
            tid = tid.strip("` ")
            item = f"{key}/{tid}"
            waits = task.waits_for(item, task.cell_list(spec.get("After", "")))
            current = active_parts.get(item, {})
            task_state = nextstep._task(top, key, tid, trees, merged_prs, history)
            waits = list(dict.fromkeys(waits + readiness.get(key, {}).get("waits", {}).get(tid, [])))
            status = ("Merged" if key in completed or task_state.get("status") == "merged" else
                      "Running" if current.get("activity", {}).get("status") == "running"
                      or current.get("worker") or current.get("tests")
                      or current.get("gates", {}).get("ci", {}).get("status") == "running" else
                      "Waiting" if current else readiness.get(key, {}).get("parts", {}).get(tid, "Not started"))
            parts.append({"id": item, "title": spec.get("Name") or "A part with no name yet",
                          "status": status, "waits_for": waits})
        phase = ("done" if key in completed else
                 readiness.get(key, {}).get("stage", "planning"))
        if items.get(key, {}).get("worker"):
            phase = "planning"
        if key in items and not items[key].get("worker") and phase in ("building", "ready to merge"):
            finished_parts = sum(p["status"] == "Merged" for p in parts)
            ready_parts = sum(active_parts.get(p["id"], {}).get("stage") == "ready" for p in parts)
            items[key]["status"] = ("Ready to merge" if phase == "ready to merge" else
                "Approved; no part has started yet" if not children.get(key) and not finished_parts else
                f"In progress: {finished_parts} of {len(parts)} parts finished"
                + (f", {ready_parts} ready to merge" if ready_parts else ""))
            items[key]["stage"] = phase
        maps.append({"id": key, "title": items.get(key, {}).get("title") or state.get("title")
                     or "A story with no title yet", "parts": parts, "stage": phase, "planned": bool(parts)})
    mapped = {m["id"] for m in maps}
    maps.extend({"id": s["key"], "title": s.get("title") or "A story with no title yet",
                 "parts": [], "stage": "done" if s["key"] in completed else "needs a spec", "planned": False}
                for s in roadmap.values() if s["key"] not in mapped)
    order = list(roadmap)  # roadmap order; stories off the roadmap keep theirs, after it
    maps.sort(key=lambda entry: order.index(entry["id"]) if entry["id"] in roadmap else len(order))
    part_titles = {part["id"]: part["title"] for entry in maps for part in entry["parts"]}
    for parent in items.values():
        for item in [parent, *parent["children"]]:
            if item["waits_on"]:
                item["waits_on"] = re.sub(r"(?<![\w/-])[A-Z][A-Z0-9-]*/[A-Z0-9][A-Z0-9-]*(?![\w/-])",
                    lambda match: part_titles.get(match[0], "A part with no name yet"), item["waits_on"])
    for entry in maps:
        if entry["stage"] == "needs a spec" and not items[entry["id"]].get("worker"):
            items[entry["id"]].update(stage="needs a spec", status="Not started yet")
    team = board_facts.team(top, history, items, maps, best, completed, github, readiness, person_waits)
    fixes = [{"id": row["id"], "title": row["title"], "waits_for": [], "running": row["activity"]["status"] == "running"
              or bool(row.get("worker")) or row["gates"]["ci"]["status"] == "running",
              "started_on": next((on for on in [best.get(repo.state_path(row["id"]), ({}, None))[0].get("stacked_on")]
                                  if "/" in str(on)), None)}  # stacked on a story part, not on a fix
             for row in items.values() if row["kind"] == "fix" and row["stage"] not in ("merged", "done")]
    if fixes:
        maps.insert(0, {"id": "fixes", "kind": "fixes", "title": "Fixes", "parts": fixes, "planned": True})
    board_graph.place(maps)
    event_lines = {"run start": "started", "run end": "finished", "review result": "Review "}
    recent = [{"time": e.get("at"), "item": e.get("item"), "line":
               " ".join((e.get("question") or "Worker asked a question").split()) if e.get("event") == "worker question" else
               "Review " + e.get("outcome", "finished") if e.get("event") == "review result" else
               {"work": "Worker", "worker": "Worker", "ci": "Checks", "read": "Plan read",
                "test": "Tests", "review": "Review"}.get(e.get("kind"), "Run") + " " + event_lines[e["event"]]}
              for e in recorded if e.get("event") in (*event_lines, "worker question")][-20:]
    return {"version": __version__, "repo_root": repo_root(top), "items": list(items.values()),
            "dependency_maps": maps, "team": team, "events": recent,
            "lanes": machine.view(), "machine": machine.load()}


def numbers_line(top: Path, checks: list[str]) -> str:
    """The three success numbers in one line, for `forge next`."""
    stories, prs = _gather(top, checks)
    return "How the factory is doing: " + "; ".join(_numbers(stories, prs)) + "."


# --- reading the state and GitHub ------------------------------------------------------------


def _gather(top: Path, checks: list[str] | None = None) -> tuple[list[Item], list[Item] | None]:
    """Each story with its parts' start, green and touches, for the success numbers, and gh's pull
    requests (None without a working gh)."""
    landed = story.landed_ref(top)
    best: dict[str, Item] = {}
    for rel, state, _ in _copies(top, landed):
        if rel not in best or len(_steps(state)) > len(_steps(best[rel])):
            best[rel] = state
    prs = _prs(top)
    by_branch: dict[str, Item] = {}
    for pr in prs or []:  # newest first; a merged one wins
        if pr.get("headRefName") not in by_branch or pr.get("state") == "MERGED":
            by_branch[str(pr.get("headRefName"))] = pr
    if checks is None:
        checks = repo.config(top)["checks"] if (top / "forge.toml").is_file() else []
    found: dict[str, Item] = {}
    parts: dict[str, list[Item]] = {}
    for rel, state in best.items():
        match = STATE.fullmatch(rel)
        if match["task"]:
            pr = by_branch.get(state.get("branch") or f"task/{match['key']}-{match['task']}")
            parts.setdefault(match["key"], []).append({"start": _step(state, "start"), "touches": state.get("touches", 0),
                                                       "green": _green_at(pr, checks)})
        elif match["key"]:
            found[match["key"]] = state
    roadmap = {item["key"]: item for item in repo.roadmap(top) if item.get("status") != "superseded"}
    stories = []
    for key in [*roadmap, *sorted((set(found) | set(parts)) - set(roadmap))]:
        state = found.get(key, {})
        completed = story.completed(top, key, landed)
        if state.get("status") != "done" and completed.get("status") == "done":
            state = completed
        if roadmap.get(key, {}).get("status") == "done":
            state = {**state, **roadmap[key]}
        mine = parts.get(key, [])
        stories.append({"parts": mine, "approved": bool(_when((state.get("approval") or {}).get("at"))),
                        "touches": state.get("touches", 0) + sum(part["touches"] for part in mine)})
    return stories, prs


def _blob_texts(top: Path, specs: list[str], *, follow_notes: bool = False) -> dict[str, str]:
    """Read git objects in one process; sizes are bytes, including on Windows."""
    if not specs:
        return {}
    pending, seen, texts = list(dict.fromkeys(specs)), set(specs), {}
    with subprocess.Popen([shutil.which("git") or "git", "cat-file", "--batch"], cwd=top,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env={**os.environ, "FORGE_WORKER": "1"}) as process:
        assert process.stdin is not None and process.stdout is not None
        for spec in pending:
            process.stdin.write((spec + "\n").encode("utf-8"))
            process.stdin.flush()
            header = process.stdout.readline()
            if header.endswith(b" missing\n"):
                continue
            text = process.stdout.read(int(header.split()[-1])).decode("utf-8", errors="replace")
            texts[spec] = text.replace("\r\n", "\n").replace("\r", "\n")
            process.stdout.read(1)
            if follow_notes and (previous := story._record(texts[spec])[0].get("notes_seen")) and previous not in seen:
                seen.add(previous)
                pending.append(previous)
        output, errors = process.communicate()
        if process.returncode:
            raise subprocess.CalledProcessError(process.returncode, process.args, output, errors)
    return texts


def _machine_history(top: Path) -> Item:
    """A fresh bulk read: omit old completions before any per-item command work."""
    landed = story.landed_ref(top)
    history: Item = {"landed": landed}
    copies = _copies(top, landed, history)
    log = repo.git("log", "--first-parent", "--diff-filter=A", "--no-renames",
                   "--format=%x00%cI%x00%B%x00", "--name-only", landed, "--",
                   ".factory/stories", ".factory/fixes", cwd=top).split("\0")[1:]
    dates, messages = {}, {}
    for at, message, paths in zip(log[::3], log[1::3], log[2::3]):
        for rel in paths.splitlines():
            if STATE.fullmatch(rel) and rel not in dates:
                dates[rel], messages[rel] = _when(at).isoformat(), message
    landed_states = {rel: state for rel, state, where in copies if where == landed}
    states = {STATE.fullmatch(rel)["key"]: state for rel, state in landed_states.items()
              if STATE.fullmatch(rel)["key"] and not STATE.fullmatch(rel)["task"]}
    history.update(copies=copies, stories=states, dates=dates, messages=messages, states=landed_states)
    for key in states:
        states[key] = story.completed(top, key, landed, history)
    cutoff = (_when(repo.now()) or datetime.now(timezone.utc)) - timedelta(days=7)
    expired = {rel for rel, at in dates.items() if not rel.endswith("/story.json")
               and _when(at) is not None and _when(at) < cutoff}
    best: dict[str, Item] = {}
    for rel, state, _ in copies:
        if rel not in best or len(_steps(state)) > len(_steps(best[rel])):
            best[rel] = state
    for rel, state in best.items():
        match = STATE.fullmatch(rel)
        if match["key"] and not match["task"] and states.get(match["key"], {}).get("status") == "done":
            state = states[match["key"]]
        if state.get("status") == "done" and (at := _when(state.get("finished"))) and at < cutoff:
            expired.add(rel)
    for rel in best:
        match = STATE.fullmatch(rel)
        if match["task"] and repo.state_path(match["key"]) in expired:
            expired.add(rel)
    return {**history, "expired": expired}


def _copies(top: Path, landed: str, history: Item | None = None) -> list[tuple[str, Item, Path | str]]:
    """Every copy of every state file as (path, state, where): local worktrees first (the freshest,
    so they win a tie), then Forge's branches on the remote, then the default branch."""
    found: list[tuple[str, Item, Path | str]] = []
    trees = story.worktrees(top)
    parsed: dict[str, Item] = {}  # most copies match; a shared state is never changed in place
    for branch, path in trees.items():
        if branch.startswith(PREFIXES):
            for file in sorted(path.glob(".factory/**/*.json")):
                rel = file.relative_to(path).as_posix()
                if STATE.fullmatch(rel):
                    text = file.read_text(encoding="utf-8")
                    if text not in parsed:
                        parsed[text] = story.json_of(text)
                    found.append((rel, parsed[text], path))
    listing = repo.git("for-each-ref", "--format=%(refname) %(tree) %(objectname)",
                       *(f"refs/remotes/origin/{prefix}" for prefix in PREFIXES),
                       *(("refs/heads/story/", "refs/heads/task/") if history is not None else ()), cwd=top)
    refs = {line.split()[0]: line.split()[1] for line in listing.splitlines()}
    if history is not None:
        history["tips"] = {line.split()[0]: line.split()[2] for line in listing.splitlines()}
    refs[landed] = repo.git("show", "-s", "--format=%T", landed, cwd=top)
    empty = repo.run("git", "hash-object", "-t", "tree", "--stdin", cwd=top)
    empty.check_returncode()
    # Comparing each unique tree with Git's empty tree lists all its blobs in one process.
    snapshots: dict[str, dict[str, str]] = {tree: {} for tree in refs.values()}
    # Git requires LF pairs; text-mode stdin adds CR on Windows and Git silently lists nothing.
    done = subprocess.run([shutil.which("git") or "git", "diff-tree", "--stdin", "-r", "--raw",
                           "-z", "--no-abbrev", "--no-renames", "--", ".factory/stories",
                           ".factory/fixes", "plans", "forge.toml"], cwd=top,
                          input="".join(f"{empty.stdout.strip()} {tree}\n" for tree in snapshots).encode("utf-8"),
                          capture_output=True, check=True, env={**os.environ, "FORGE_WORKER": "1"})
    fields = iter(done.stdout.decode("utf-8", errors="replace").split("\0"))
    for field in fields:
        for line in field.splitlines():
            if line.startswith(":"):
                rel = next(fields)
                if (STATE.fullmatch(rel) or rel == "forge.toml"
                        or re.fullmatch(r"plans/[A-Z0-9][A-Z0-9-]*(\.read)?\.md", rel)):
                    snapshots[tree][rel] = line.split()[3]
            elif line:
                tree = line.split()[1]
    texts = _blob_texts(top, list(dict.fromkeys(blob for files in snapshots.values() for blob in files.values())))
    blobs = {blob: story.json_of(text) for blob, text in texts.items()}
    for ref, tree in refs.items():
        if ref == landed or ref.startswith("refs/remotes/"):
            found.extend((rel, blobs[blob], ref) for rel, blob in snapshots[tree].items() if STATE.fullmatch(rel))
    if history is not None:
        history["worktrees"] = trees
        history["ref_states"] = {ref: {rel: blobs[blob] for rel, blob in snapshots[tree].items()
                                       if STATE.fullmatch(rel)} for ref, tree in refs.items()}
        history["docs"] = {f"{alias}:{rel}": texts[blob] for ref, tree in refs.items()
                           for alias in (ref, ref.removeprefix("refs/heads/").removeprefix("refs/remotes/"))
                           for rel, blob in snapshots[tree].items() if not STATE.fullmatch(rel)}
        # The doc each plan read saw, for "changed since the read": one git process for all of them.
        seen = list(dict.fromkeys(h for text in history["docs"].values()
                                  for h in map(story._record(text)[0].get,  # pyright: ignore[reportPrivateUsage]
                                               ("read_hash", "notes_seen")) if h))
        history["past notes"] = _blob_texts(top, seen, follow_notes=True)
        for blob, text in history["past notes"].items():
            repo.command_fact(("read blob", blob), top, lambda text=text: text)
    return found


def _prs(top: Path) -> list[Item] | None:
    """Every pull request gh can see, newest first, or None without a working gh."""
    github = board_facts.prs(top)
    if github is None:
        return None
    prs = list({(pr.get("number"), pr.get("headRefName")): pr
                for pr in [*github["open"], *board_facts.merged_prs(github)]}.values())
    by_branch = {pr["headRefName"]: pr for pr in board_facts.details(top)
                 if isinstance(pr.get("headRefName"), str)}
    opened = {p["headRefName"]: p for p in _machine_prs(top)}
    return [{**pr, **by_branch.get(pr.get("headRefName"), {}),
             **({"statusCheckRollup": _rollup({**opened.get(pr.get("headRefName"), {}), **pr})}
                if pr.get("state") == "OPEN" else {})} for pr in prs]


def _read(top: Path, where: Path | str, rel: str, history: Item | None = None) -> str:
    if isinstance(where, Path):
        return (where / rel).read_text(encoding="utf-8") if (where / rel).is_file() else ""
    if history is not None:
        return history["docs"].get(f"{where}:{rel}", "")
    return story.show(top, where, rel) or ""


# --- a story, a part and the numbers ------------------------------------------------------------


def _numbers(stories: list[Item], prs: list[Item] | None) -> list[str]:
    """The three success numbers, as plain phrases: task cycle time, human touches per story, and
    the share of the last 25 finished changes that fixed Forge itself."""
    cycles = [part["green"] - part["start"] for s in stories for part in s["parts"]
              if part["start"] and part["green"]]
    touches = [s["touches"] for s in stories if s["approved"]]
    merged = sorted((pr for pr in prs or [] if pr.get("mergedAt")), key=lambda pr: str(pr["mergedAt"]),
                    reverse=True)[:25]
    forge = [pr for pr in merged if str(pr.get("headRefName")).startswith(("fix/", "forge/"))
             and any(str(f.get("path")).startswith(FORGE_FILES) for f in pr.get("files") or [])]
    return [
        (f"a part usually takes {_took(statistics.median(cycles))} from its start to ready" if cycles
         else "the usual time from a part's start to ready isn't measured yet") + " (target: under 2 hours)",
        (f"a story usually needs a person {_times(statistics.median(touches))}" if touches
         else "how often a story needs a person isn't measured yet") + " (target: 3 times or fewer)",
        (f"{len(forge)} of the last {len(merged)} finished changes fixed Forge itself" if merged
         else "the share of finished changes that fixed Forge itself isn't measured yet")
        + " (target: under 10%)",
    ]


def _green_at(pr: Item | None, names: list[str]) -> datetime | None:
    """When the last named check passed on the pull request's head; None unless every one passed."""
    seen = [(str(c.get("name") or c.get("context")), c.get("conclusion") or c.get("state"),
             _when(c.get("completedAt") or c.get("startedAt")))
            for c in (pr or {}).get("statusCheckRollup") or [] if isinstance(c, dict)]
    times: list[datetime] = []
    for want in names:  # a matrix job reports as "tests (ubuntu-latest)"; every one must pass
        mine = [(ok, at) for name, ok, at in seen if name == want or name.startswith(want + " (")]
        if not mine or any(ok != "SUCCESS" for ok, _ in mine):
            return None
        times += [at for _, at in mine if at]
    return max(times, default=None)


def _display_names(top: Path) -> dict[str, str]:
    def read() -> dict[str, str]:
        names = {}
        for author in repo.git("log", "--all", "--date-order", "--format=%aN%x00%aE", cwd=top).splitlines():
            name, _, email = author.partition("\0")
            names.setdefault(email.casefold(), name)
        return names
    return repo.command_fact("display_names", top, read)


def _starters(top: Path) -> dict[str, str]:
    names = _display_names(top)
    log = repo.command_fact("board starter authors", top, lambda: repo.git(
        "log", "--all", "--reverse", "--diff-filter=A", "--no-renames", "--grep=^Start ",
        "--format=%x00%aN%x00%aE%x00", "--name-only", "--", ".factory/stories", ".factory/fixes",
        cwd=top)).split("\0")[1:]
    found = {}
    for name, email, paths in zip(log[::3], log[1::3], log[2::3]):
        for rel in paths.splitlines():
            if rel.endswith(".json"):
                found.setdefault(rel, names.get(email.casefold(), name))
    return found


def _read_rounds(notes: str) -> list[Item]:
    """Each round of a plan's cold read, from its notes: the round number, each finding's first
    line with its disposition (cut, defer or keep, and keep's reason), and the date of the latest
    round only, which is the one the notes' frontmatter records."""
    record, body = story._record(notes)  # pyright: ignore[reportPrivateUsage]
    rounds = []
    for number, text in re.findall(r"^## Round (\d+)[ \t]*\n(.*?)(?=^## Round \d|\Z)", body, re.M | re.S):
        findings = []
        for finding in story._findings(text).values():  # pyright: ignore[reportPrivateUsage]
            said = re.search(r"^\s*Disposition:\s*(cut|defer|keep)\b[\s:\-]*(?:because\s+)?(.*)$", finding, re.M | re.I)
            findings.append({"title": finding.split("\n", 1)[0].split(". ", 1)[1].strip(),
                             "disposition": said[1].lower() if said else None,
                             "reason": (said[2].strip() or None) if said else None})
        rounds.append({"round": int(number), "findings": findings,
                       "read_at": record.get("read_at") if number == record.get("round") else None})
    return rounds


def _approver(top: Path, key: str, display_names: dict[str, str] | None = None) -> str | None:
    """Who approved the plan, by git name: the author of Forge's approval commit, while a ref has it."""
    if display_names is None:
        display_names = _display_names(top)
    log = repo.command_fact("board approvers", top, lambda: repo.git(
        "log", "--all", "--format=%x00%aN%x00%aE%x00", "-F", "--grep=Approve the plan: ", "--name-only",
        "--", ".factory/stories", cwd=top)).split("\0")[1:]
    newest = {}
    for found, address, paths in zip(log[::3], log[1::3], log[2::3]):
        for rel in paths.splitlines():
            newest.setdefault(rel, (found, address))
    name, email = newest.get(repo.state_path(key), ("", ""))
    name = display_names.get(email.casefold(), name)
    return name or None


# --- plain English ---------------------------------------------------------------------------


def _steps(state: Item) -> list[Item]:
    steps = state.get("steps")
    return [step for step in steps if isinstance(step, dict)] if isinstance(steps, list) else []


def _step(state: Item, name: str) -> datetime | None:
    """When the first step of this name happened."""
    return next((_when(step.get("at")) for step in _steps(state) if step.get("step") == name), None)


def _when(text: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(text)).astimezone(timezone.utc)
    except ValueError:
        return None




def _took(delta: timedelta) -> str:
    from forge.time_records import plain
    return plain(delta.total_seconds())




def _times(n: float) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{n:g} times")


def _day(when: datetime | None) -> str:
    return f"{when.day} {when:%B %Y}" if when else "a date that wasn't recorded"



