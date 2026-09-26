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
import re
import shutil
import statistics
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Template
from typing import Any

from forge import repo, story, task

CHECK_DATE = "2026-11-15"  # ponytail: the rebuild's check date, from the spec's success measure
PREFIXES = ("story/", "task/", "fix/", "forge/")  # the branches Forge starts; forge/ is migrate's
STATE = re.compile(r"\.factory/(?:stories/(?P<key>[A-Z][A-Z0-9-]*)/(?:story|tasks/(?P<task>[A-Z0-9][A-Z0-9-]*))"
                   r"|fixes/(?P<fix>[a-z0-9][a-z0-9-]*))\.json")
# ponytail: a merged fix "fixed Forge" when it changed Forge's own files; widen once a miss shows up.
FORGE_FILES = ("forge.toml", ".claude/", ".codex/", ".github/workflows/forge.yml", "src/forge/")
WAITING = "Waiting for someone to accept it"
STATUS = {"started": "Started, not built yet", "working": "Being built", "reviewing": "Being reviewed",
          "fixing": "Being fixed after its review", "waiting for checks": "Being checked",
          "ready": "Being checked"}

Item = dict[str, Any]


def board(args: Any) -> int:
    top = repo.root()
    stories, fixes, prs = _gather(top)
    out = Path(args.out) if args.out else repo.forge_dir(top) / "board.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(_page(stories, fixes, prs).encode("utf-8"))  # bytes: the same file on Windows
    print(f"Wrote the board to {out}")
    if sys.stdout.isatty():  # ponytail: open it for a person at a terminal; never in a pipe or a test
        webbrowser.open(out.resolve().as_uri())
    return 0


def numbers_line(top: Path) -> str:
    """The three success numbers in one line, for `forge next`."""
    stories, _, prs = _gather(top)
    return "How the factory is doing: " + "; ".join(_numbers(stories, prs)) + "."


# --- reading the state and GitHub ------------------------------------------------------------


def _gather(top: Path) -> tuple[list[Item], list[Item], list[Item] | None]:
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
    titles = {item["key"]: item.get("title") for item in repo.roadmap(top)}
    stories = []
    for key in [*titles, *sorted((set(found) | set(tasks)) - set(titles))]:
        state, where = found.get(key, ({}, landed))
        rows = task.rows(task.sections(_read(top, where, f"plans/{key}.md")))
        names = {cell.strip("` "): row.get("Name") or "" for cell, row in rows.items()}
        mine = tasks.get(key, {})
        parts = [(names.get(tid) or "A part with no name yet", mine.get(tid))
                 for tid in [*names, *sorted(set(mine) - set(names))]]
        stories.append(_story(top, key, state, state.get("title") or titles.get(key), parts))
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
    # ponytail: the newest 1,000 pull requests in one call; page by date once a repo outgrows it.
    done = repo.run("gh", "pr", "list", "--state", "all", "--limit", "1000", "--json",
                    "headRefName,state,title,body,mergedAt,files,statusCheckRollup", cwd=top)
    try:
        prs = json.loads(done.stdout) if done.returncode == 0 else None
    except ValueError:
        prs = None
    return prs if isinstance(prs, list) and all(isinstance(pr, dict) for pr in prs) else None


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
        sentence = "Being planned." if state.get("status") == "planning" else "Planned, and waiting for approval."
    elif parts and len(finished) == len(parts):
        sentence = "Every part is finished; waiting for someone to write down what it achieved."
    elif not started:
        sentence = "Approved; no part has started yet."
    else:
        sentence = (f"Being built: {len(finished)} of {len(parts)} parts finished"
                    + (f", {len(waiting)} waiting for someone to accept it" if waiting else "") + ".")
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
            "parts": parts, "timeline": timeline, "touches": touches, "approved": bool(approved)}


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
    """A pull request's summary: the first line of its body, which close writes in plain English."""
    line = (str(pr.get("body") or "").strip().splitlines() or [""])[0].strip()
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
        return f'<li><b>{esc(name)}</b>: <span class="status">{esc(item["status"])}.</span>{"".join(lines)}</li>'

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
    fixed = "".join(part(fix["name"], fix, _summary(fix["pr"] or {})) for fix in fixes)
    now = _when(repo.now()) or datetime.now(timezone.utc)
    return Template((Path(__file__).parent / "board.html").read_text(encoding="utf-8")).substitute(
        updated=f"{_day(now)} at {now:%H:%M} UTC",
        numbers="".join(f"<li>{esc(_cap(number))}.</li>" for number in _numbers(stories, prs)),
        note=note,
        stories="".join(card(s) for s in stories) or '<p class="card">No story is on the roadmap yet.</p>',
        fixes=f'<section class="card"><ul>{fixed}</ul></section>' if fixed
        else '<p class="card">No small fixes yet.</p>')
