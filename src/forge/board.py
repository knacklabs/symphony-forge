"""`forge board`: one static page that tells each story's history and current state in plain English,
how long each step took, which steps were slow, and the three success numbers. `forge next` shows
those numbers in one line once the check date is here.

It reads every copy of the state: in local worktrees, on Forge's branches on the remote, and on the
default branch. Steps are only ever added, so the copy with the most dated steps is the newest. gh
adds each pull request's title, summary line, merge date and when its checks passed; close stores
none of those. Without gh the page shows the state and its dates only.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import statistics
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Template
from typing import Any

from forge import __version__, codex, repo, story, task

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
WAITING = "Ready to merge"
STATUS = {"started": "Waiting to start", "working": "In progress", "reviewing": "Under review",
          "fixing": "Needs fixes", "waiting for checks": "Checks running",
          "ready": "Ready to merge"}

Item = dict[str, Any]


def board(args: Any) -> int:
    top = repo.root()
    if args.json:
        print(json.dumps(machine_board(top)))
        return 0
    stories, fixes, prs = _gather(top)
    out = Path(args.out) if args.out else repo.forge_dir(top) / "board.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(_page(stories, fixes, prs).encode("utf-8"))  # bytes: the same file on Windows
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
      nodes { number headRefName headRefOid title url isDraft
        commits(last: 1) { nodes { commit { statusCheckRollup {
          contexts(first: 100) { pageInfo { hasNextPage } nodes {
            __typename
            ... on CheckRun { databaseId name status conclusion completedAt }
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
                    "-f", f"query={CHECKS_QUERY}", cwd=top) if shutil.which("gh") else None
    try:
        response = json.loads(done.stdout) if done and done.returncode == 0 else {}
        prs = response["data"]["repository"]["pullRequests"]["nodes"]
        if response.get("errors") or not isinstance(prs, list) or not all(isinstance(p, dict) for p in prs):
            return []
    except (ValueError, KeyError, TypeError):
        return []  # An expired answer must not hide a failed check while GitHub is unreachable.
    temp = cache.with_name(f"checks-cache-{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps({"fetched_at": repo.now(), "prs": prs}), encoding="utf-8")
        os.replace(temp, cache)
    except OSError:
        pass  # A read-only/full Git directory must not prevent a view.
    finally:
        temp.unlink(missing_ok=True)
    return prs


def _checks(pr: Item | None, required: list[str]) -> tuple[str, list[Item]]:
    if not pr:
        return "unknown", []
    try:
        contexts = pr["commits"]["nodes"][-1]["commit"]["statusCheckRollup"]["contexts"]
        nodes = contexts["nodes"]
        if not isinstance(nodes, list):
            return "unknown", []
    except (KeyError, TypeError, IndexError):
        return "unknown", []
    statuses, events, names = [], [], []
    for check in nodes:
        if not isinstance(check, dict):
            continue
        name = check.get("name") or check.get("context") or "Check"
        names.append(name)
        value = check.get("conclusion") or check.get("state")
        failed = value in ("FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE")
        statuses.append("fail" if failed else "pass" if value in ("SUCCESS", "NEUTRAL", "SKIPPED")
                        else "running" if value in ("PENDING", "EXPECTED") or check.get("status") in
                        ("QUEUED", "IN_PROGRESS", "WAITING", "PENDING", "REQUESTED") else "unknown")
        if failed:
            identity = (f"check-run:{check['databaseId']}:{check['completedAt']}"
                        if check.get("databaseId") is not None and check.get("completedAt")
                        else f"status:{check['id']}" if check.get("__typename") == "StatusContext" and check.get("id") else None)
            if identity:
                events.append({"id": identity, "kind": "checks_failed", "title": f"{name} failed"})
    missing = any(not any(n == want or n.startswith(want + " (") for n in names) for want in required)
    status = ("fail" if "fail" in statuses else "running" if "running" in statuses else
              "unknown" if not statuses or "unknown" in statuses or missing or
              contexts.get("pageInfo", {}).get("hasNextPage") else "pass")
    return status, events


def _rollup(pr: Item) -> list[Item]:
    try:
        nodes = pr["commits"]["nodes"][-1]["commit"]["statusCheckRollup"]["contexts"]["nodes"]
        return [n for n in nodes if isinstance(n, dict)] if isinstance(nodes, list) else []
    except (KeyError, TypeError, IndexError):
        return []


def machine_board(top: Path) -> Item:
    """Stories and fixes, with tasks one level down. No invented run times or occurrence ids."""
    from forge import nextstep

    trees = story.worktrees(top)
    landed = story.landed_ref(top)
    best: dict[str, tuple[Item, Path | str]] = {}
    merged = set()
    for rel, state, where in _copies(top, landed):
        if where == landed:
            merged.add(rel)
        if rel not in best or len(_steps(state)) > len(_steps(best[rel][0])):
            best[rel] = state, where
    prs = _machine_prs(top)
    by_branch = {p.get("headRefName"): p for p in prs}
    # Older open PRs keep their number, but deliberately have unknown checks.
    older = nextstep._prs(top, "open", "number,headRefName,url,isDraft")
    for pr in older:
        by_branch.setdefault(pr["headRefName"], pr)
    mapped_prs = {branch: {**pr, "statusCheckRollup": _rollup(pr)} for branch, pr in by_branch.items()}
    timings = []
    path = repo.forge_dir(top) / "timings.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                timings.append(value)
        except ValueError:
            continue

    def row(item: str, kind: str, title: str, state: Item, where: Path | str) -> Item:
        if kind != "story" and repo.state_path(item) in merged:
            state = {**state, "status": "merged"}
        branch = state.get("branch") or (f"task/{item.replace('/', '-')}" if kind == "task"
                                         else f"{kind}/{item}")
        tree = trees.get(branch)
        cfg = nextstep._report_config(tree or top, {})
        pr = by_branch.get(branch)
        checks, events = _checks(pr, cfg["checks"])
        lines = (nextstep._item(item, title, state, top, tree, mapped_prs, {}) if kind != "story"
                 else nextstep._story(top, item, tree, _read(top, where, f"plans/{item}.md"),
                                      title, trees, set(), mapped_prs, {})[0])
        if state.get("status") == "done" or (state.get("status") == "merged" and not tree):
            lines = [f"{title} is finished."]
        dismissed = {d.get("finding") for d in (state.get("review") or {}).get("dismissals", [])
                     if isinstance(d, dict)}
        findings = [f.get("title") or "Untitled finding" for n, f in
                    enumerate((state.get("review") or {}).get("findings", []), 1)
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
                      "started_at": state.get("run_started_at")}
        round_number = state.get("round")
        stages = []
        for name, step in (("Build", "worker round"), ("Tests", "test"), ("Review", "review"),
                           ("CI", "CI wait"), ("Merge", "merge")):
            records = [r for r in timings if round_number is not None and r.get("item") == item
                       and r.get("round") == round_number and r.get("step") == step]
            outcome = records[-1].get("outcome") if records else None
            status = {"completed": "pass", "clean": "pass", "failed": "fail", "blocked": "fail"}.get(outcome, outcome)
            stages.append({"name": name, "status": status,
                           "started_at": records[0].get("start") if records else None,
                           "ended_at": records[-1].get("end") if records else None,
                           "seconds": sum(r.get("seconds") or 0 for r in records)
                           if any(r.get("seconds") is not None for r in records) else None})
        return {"id": item, "kind": kind, "title": title, "stage": state.get("status") or "unknown",
                "worker": worker, "pr": {"number": (pr or {}).get("number"), "checks": checks},
                "findings": {"count": len(findings), "titles": findings}, "round": round_number,
                "total_seconds": sum(r.get("seconds") or 0 for r in timings
                                     if r.get("item") == item and r.get("round") is not None)
                                 if round_number is not None else None,
                "stages": stages, "occurrences": events, "next": nextstep.machine_next(lines),
                "children": []}

    items, children = {}, {}
    for rel, (state, where) in best.items():
        match = STATE.fullmatch(rel)
        if match["fix"]:
            if state.get("kind") != "story-done":
                name = match["fix"]
                items[name] = row(name, "fix", state.get("why") or "A small fix", state, where)
        elif match["task"]:
            key, tid = match["key"], match["task"]
            names = task.rows(task.sections(_read(top, where, f"plans/{key}.md")))
            title = (names.get(tid) or {}).get("Name") or "A part with no name yet"
            children.setdefault(key, []).append(row(f"{key}/{tid}", "task", title, state, where))
        else:
            key = match["key"]
            text = _read(top, where, f"plans/{key}.md")
            title = state.get("title") or next((s.removeprefix("# ") for s in text.splitlines()
                                                if s.startswith("# ")), "A story with no title yet")
            items[key] = row(key, "story", title, state, where)
    for key, parts in children.items():
        if key not in items:
            items[key] = row(key, "story", "A story with missing state", {}, landed)
        items[key]["children"] = parts
    return {"version": __version__, "repo_root": repo_root(top), "items": list(items.values())}


def numbers_line(top: Path, checks: list[str]) -> str:
    """The three success numbers in one line, for `forge next`."""
    stories, _, prs = _gather(top, checks)
    return "How the factory is doing: " + "; ".join(_numbers(stories, prs)) + "."


# --- reading the state and GitHub ------------------------------------------------------------


def _gather(top: Path, checks: list[str] | None = None) -> tuple[list[Item], list[Item], list[Item] | None]:
    """Each story (roadmap order first) with its parts and timeline, each fix, and gh's pull
    requests (None without a working gh)."""
    landed, now = story.landed_ref(top), _when(repo.now()) or datetime.now(timezone.utc)
    best: dict[str, tuple[Item, Path | str]] = {}
    merged: set[str] = set()
    for rel, state, where in _copies(top, landed):
        if where == landed:
            merged.add(rel)
        if rel not in best or len(_steps(state)) > len(_steps(best[rel][0])):
            best[rel] = (state, where)
    prs = _prs(top)
    by_branch: dict[str, Item] = {}
    for pr in prs or []:  # newest first; a merged one wins
        if pr.get("headRefName") not in by_branch or pr.get("state") == "MERGED":
            by_branch[str(pr.get("headRefName"))] = pr
    if checks is None:
        checks = repo.config(top)["checks"] if (top / "forge.toml").is_file() else []

    def part(rel: str, state: Item, branch: str, noun: str) -> Item:
        pr = by_branch.get(state.get("branch") or branch)
        return _part(top, landed, rel, state, rel in merged, pr, checks, now, noun)

    found: dict[str, tuple[Item, Path | str]] = {}
    tasks: dict[str, dict[str, Item]] = {}
    fixes: list[Item] = []
    for rel, (state, where) in best.items():
        match = STATE.fullmatch(rel)
        assert match  # _copies keeps only state files
        if match["fix"]:
            if state.get("kind") != "story-done":  # a story's outcome shows in its own timeline
                fix = part(rel, state, f"fix/{match['fix']}", "fix")
                fixes.append({**fix, "name": (fix["pr"] or {}).get("title") or state.get("why")
                              or "A small fix"})
        elif match["task"]:
            tasks.setdefault(match["key"], {})[match["task"]] = part(
                rel, state, f"task/{match['key']}-{match['task']}", "part")
        else:
            found[match["key"]] = (state, where)
    titles = {item["key"]: item.get("title") for item in repo.roadmap(top)
              if item.get("status") != "superseded"}
    stories = []
    for key in [*titles, *sorted((set(found) | set(tasks)) - set(titles))]:
        state, where = found.get(key, ({}, landed))
        rows = task.rows(task.sections(_read(top, where, f"plans/{key}.md")))
        names = {cell.strip("` "): row.get("Name") or "" for cell, row in rows.items()}
        mine = tasks.get(key, {})
        parts = [(names.get(tid) or "A part with no name yet", mine.get(tid))
                 for tid in [*names, *sorted(set(mine) - set(names))]]
        stories.append(_story(top, key, state, state.get("title") or titles.get(key), parts))
    stories.sort(key=lambda item: item["finished"])
    fixes.sort(key=lambda fix: fix["start"] or now, reverse=True)
    return stories, fixes, prs


def _copies(top: Path, landed: str) -> list[tuple[str, Item, Path | str]]:
    """Every copy of every state file as (path, state, where): local worktrees first (the freshest,
    so they win a tie), then Forge's branches on the remote, then the default branch."""
    found: list[tuple[str, Item, Path | str]] = []
    for branch, path in story.worktrees(top).items():
        if branch.startswith(PREFIXES):
            for file in sorted(path.glob(".factory/**/*.json")):
                rel = file.relative_to(path).as_posix()
                if STATE.fullmatch(rel):
                    found.append((rel, story.json_of(file.read_text(encoding="utf-8")), path))
    refs = repo.git("for-each-ref", "--format=%(refname)",
                    *(f"refs/remotes/origin/{prefix}" for prefix in PREFIXES), cwd=top).split()
    blobs: dict[str, Item] = {}  # the same file sits on many branches; read each version once
    for ref in [*refs, landed]:
        listing = repo.git("ls-tree", "-r", ref, "--", ".factory/stories", ".factory/fixes", cwd=top)
        for line in listing.splitlines():
            meta, rel = line.split("\t", 1)
            if STATE.fullmatch(rel):
                blob = meta.split()[2]
                if blob not in blobs:
                    blobs[blob] = story.json_of(repo.git("cat-file", "blob", blob, cwd=top))
                found.append((rel, blobs[blob], ref))
    return found


def _prs(top: Path) -> list[Item] | None:
    """Every pull request gh can see, newest first, or None without a working gh."""
    if not shutil.which("gh"):
        return None
    # GitHub times out on this repo when it resolves files and checks for every pull request.
    done = repo.run("gh", "pr", "list", "--state", "all", "--limit", "1000", "--json",
                    "headRefName,state,title,body,mergedAt,url", cwd=top)
    try:
        prs = json.loads(done.stdout) if done.returncode == 0 else None
    except ValueError:
        prs = None
    if not isinstance(prs, list) or not all(isinstance(pr, dict) for pr in prs):
        return None
    recent = repo.run("gh", "pr", "list", "--state", "merged", "--limit", "25", "--json",
                      "headRefName,state,title,body,mergedAt,url,files,statusCheckRollup", cwd=top)
    try:
        details = json.loads(recent.stdout) if recent.returncode == 0 else []
    except ValueError:
        details = []
    by_branch = {pr["headRefName"]: pr for pr in details if isinstance(pr, dict)
                 and isinstance(pr.get("headRefName"), str)}
    opened = {p["headRefName"]: p for p in _machine_prs(top)}
    return [{**pr, **by_branch.get(pr.get("headRefName"), {}),
             **({"statusCheckRollup": _rollup(opened.get(pr.get("headRefName")) or {})}
                if pr.get("state") == "OPEN" else {})} for pr in prs]


def _read(top: Path, where: Path | str, rel: str) -> str:
    if isinstance(where, Path):
        return (where / rel).read_text(encoding="utf-8") if (where / rel).is_file() else ""
    return story.show(top, where, rel) or ""


# --- a story, a part and the numbers ------------------------------------------------------------


def _story(top: Path, key: str, state: Item, title: str | None,
           parts: list[tuple[str, Item | None]]) -> Item:
    """A story's state sentence, planning time, human touches and dated timeline."""
    started = [part for _, part in parts if part]
    finished = [part for part in started if part["finished"]]
    waiting = [part for part in started if part["status"] == WAITING]
    approved = _when((state.get("approval") or {}).get("at"))
    if not state:
        sentence = "Not started yet."
    elif state.get("status") == "done":
        sentence = f"Finished on {_day(_when(state.get('finished')))}."
    elif not approved:
        sentence = "Planning." if state.get("status") == "planning" else "Waiting for approval."
    elif parts and len(finished) == len(parts):
        sentence = "All parts finished; record the outcome."
    elif not started:
        sentence = "Approved; no part has started yet."
    else:
        sentence = (f"In progress: {len(finished)} of {len(parts)} parts finished"
                    + (f", {len(waiting)} ready to merge" if waiting else "") + ".")
    touches = state.get("touches", 0) + sum(part["touches"] for part in started)
    meta = []
    begun = _step(state, "start")
    if begun and approved:
        meta.append(f"Planning took {_took(approved - begun)}.")
    if state:
        meta.append(f"A person stepped in {_times(touches)}, plus accepting "
                    f"{_n(len(finished), 'finished part')}.")
    timeline = [(approved, _approver(top, key), "")] if approved else []
    timeline += sorted((part["finished"], part["pr"].get("title") or name, _summary(part["pr"]))
                       for name, part in parts if part and part["pr"] and part["pr"].get("mergedAt")
                       and part["finished"])
    ended = _when(state.get("finished"))
    if state.get("status") == "done" and ended:
        timeline.append((ended, "The story was finished.", state.get("outcome") or ""))
    return {"title": title or "A story with no title yet", "sentence": sentence, "meta": meta,
            "parts": parts, "timeline": timeline, "touches": touches, "approved": bool(approved),
            "finished": state.get("status") == "done"}


def _part(top: Path, landed: str, rel: str, state: Item, merged: bool, pr: Item | None,
          checks: list[str], now: datetime, noun: str) -> Item:
    """A task's or fix's status, how long each step took, and its slow lines."""
    start, reviewed, green = _step(state, "start"), _step(state, "review"), _green_at(pr, checks)
    finished = (_when(pr.get("mergedAt")) if pr and pr.get("mergedAt")
                else _when(story.merged_at(top, landed, rel)) if merged else None)
    if finished:
        status = f"Finished on {_day(finished)}"
    elif green and pr and pr.get("state") == "OPEN" and state.get("status") in ("waiting for checks", "ready"):
        status = WAITING
    else:
        status = STATUS.get(state.get("status"), "In progress")
    took = []
    if start and reviewed:
        took.append(f"built in {_took(reviewed - start)}")
    if reviewed and green:
        took.append(f"reviewed and checked in {_took(green - reviewed)}")
    if green and finished:
        took.append(f"waited {_took(finished - green)} to be accepted")
    slow = []
    days = _working_days(start, finished or now) if start else 0
    if days > 2:
        slow.append(f"This {noun} {'was' if finished else 'has been'} open for {days} working days, "
                    "which is slow.")
    if reviewed and green and green - reviewed > timedelta(minutes=30):
        slow.append(f"Reviewing and checking this {noun} took {_took(green - reviewed)}, which is slow.")
    return {"status": status, "took": took, "slow": slow, "start": start, "green": green,
            "finished": finished, "pr": pr, "touches": state.get("touches", 0)}


def _numbers(stories: list[Item], prs: list[Item] | None) -> list[str]:
    """The three success numbers, as plain phrases: task cycle time, human touches per story, and
    the share of the last 25 finished changes that fixed Forge itself."""
    cycles = [part["green"] - part["start"] for s in stories for _, part in s["parts"]
              if part and part["start"] and part["green"]]
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


def _approver(top: Path, key: str) -> str:
    """Who approved the plan, by git name: the author of Forge's approval commit, while a ref has it."""
    name = repo.git("log", "--all", "-1", "--format=%an", "-F", "--grep=Approve the plan: ", "--",
                    repo.state_path(key), cwd=top)
    return f"{name} approved the plan." if name else "The plan was approved."


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


def _working_days(start: datetime, end: datetime) -> int:
    """Weekdays from the start day up to, not including, the end day."""
    # ponytail: weekends only; public holidays count as working days.
    return sum((start + timedelta(days=n)).weekday() < 5 for n in range((end.date() - start.date()).days))


def _took(delta: timedelta) -> str:
    minutes = max(1, round(delta.total_seconds() / 60))
    days, rest = divmod(minutes, 24 * 60)
    hours, minutes = divmod(rest, 60)
    shown = [(days, "day"), (hours, "hour")] if days else [(hours, "hour"), (minutes, "minute")]
    return " ".join(_n(n, word) for n, word in shown if n)


def _n(n: float, word: str) -> str:
    return f"{n:g} {word}{'' if n == 1 else 's'}"


def _times(n: float) -> str:
    return {1: "once", 2: "twice"}.get(n, f"{n:g} times")


def _day(when: datetime | None) -> str:
    return f"{when.day} {when:%B %Y}" if when else "a date that wasn't recorded"


def _summary(pr: Item) -> str:
    """A pull request's done-when line, or the first line of an older body."""
    lines = str(pr.get("body") or "").strip().splitlines()
    line = next((line.removeprefix("Done when: ") for line in lines
                 if line.startswith("Done when: ")), lines[0].strip() if lines else "")
    return "" if line.startswith("<!--") else line


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


# --- the page --------------------------------------------------------------------------------


def _page(stories: list[Item], fixes: list[Item], prs: list[Item] | None) -> str:
    esc = html.escape

    def part(name: str, item: Item | None, summary: str = "") -> str:
        if item is None:
            return f'<li><b>{esc(name)}</b>: <span class="status">Not started yet.</span></li>'
        lines = [f'<span class="detail">{esc(summary)}</span>'] if summary else []
        lines += [f'<p class="took">{esc(_cap("; ".join(item["took"])))}.</p>'] if item["took"] else []
        lines += [f'<p class="slow">{esc(line)}</p>' for line in item["slow"]]
        url = (item.get("pr") or {}).get("url")
        label = (f'<a href="{esc(url, quote=True)}">{esc(name)}</a>' if url else esc(name))
        return f'<li><b>{label}</b>: <span class="status">{esc(item["status"])}.</span>{"".join(lines)}</li>'

    def card(s: Item) -> str:
        body = [f"<h3>{esc(s['title'])}</h3>", f'<p class="sentence">{esc(s["sentence"])}</p>']
        body += [f'<p class="meta">{esc(" ".join(s["meta"]))}</p>'] if s["meta"] else []
        if s["parts"]:
            body.append("<h4>Parts</h4><ul>" + "".join(part(n, p) for n, p in s["parts"]) + "</ul>")
        if s["timeline"]:
            body.append("<h4>What happened</h4><ol class=\"timeline\">" + "".join(
                f'<li><time datetime="{when:%Y-%m-%d}">{_day(when)}</time><b>{esc(headline)}</b>'
                + (f'<span class="detail">{esc(detail)}</span>' if detail else "") + "</li>"
                for when, headline, detail in s["timeline"]) + "</ol>")
        return f'<article class="card">{"".join(body)}</article>'

    note = ("" if prs is not None else '<p class="card note">GitHub couldn\'t be reached, so the list of '
            "finished work isn't available. This page shows the saved dates only.</p>")
    active = [fix for fix in fixes if not fix["finished"]]
    finished = [fix for fix in fixes if fix["finished"]]
    fixed = "".join(part(fix["name"], fix, _summary(fix["pr"] or {})) for fix in active)
    if finished:
        fixed += (f'<li><details><summary>{len(finished)} finished '
                  f'fix{"es" if len(finished) != 1 else ""}</summary><ul>'
                  + "".join(part(fix["name"], fix, _summary(fix["pr"] or {})) for fix in finished)
                  + "</ul></details></li>")
    now = _when(repo.now()) or datetime.now(timezone.utc)
    return Template((Path(__file__).parent / "board.html").read_text(encoding="utf-8")).substitute(
        updated=f"{_day(now)} at {now:%H:%M} UTC",
        numbers="".join(f"<li>{esc(_cap(number))}.</li>" for number in _numbers(stories, prs)),
        note=note,
        stories="".join(card(s) for s in stories) or '<p class="card">No story is on the roadmap yet.</p>',
        fixes=f'<section class="card"><ul>{fixed}</ul></section>' if fixed
        else '<p class="card">No small fixes yet.</p>')
