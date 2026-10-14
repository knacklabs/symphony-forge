"""Pace, go-live and weekly trends for the board's team facts.

board_facts calls `facts` once per board with the weekly merged pull request searches.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

from forge import repo, time_records

Item = dict[str, Any]
WEEK = timedelta(weeks=1)


def _person(pr: Item) -> str:
    author = pr.get("author") or {}
    return author.get("name") or author.get("login") or "Unknown"


def _through(pr: Item) -> bool:
    from forge import board_facts

    return board_facts.through_forge(pr)


def _split(prs: list[Item]) -> Item:
    through = sum(map(_through, prs))
    return {"through": through, "around": len(prs) - through}


def _day(at: date) -> str:
    return f"{at.day} {at:%B}"


def facts(top: Path, history: Item, counts: Item, items: list[Item],
          github: Item | None) -> tuple[Item, str]:
    """The team keys `pace`, `go_live`, `trends` and `around_forge`, and the sentence's go-live
    clause. Pace and go-live read git; trends and the around-Forge list need GitHub."""
    from forge import board_facts

    now = time_records.when(repo.now()) or datetime.now(timezone.utc)
    starts = board_facts.full_weeks(now, 6)
    parts, fixes = [], []
    for rel, at in history["dates"].items():
        when = time_records.when(at)
        if when and rel.startswith(".factory/stories/") and "/tasks/" in rel:
            parts.append(when)
        elif (when and rel.startswith(".factory/fixes/")
              and history["states"].get(rel, {}).get("kind") != "story-done"):
            fixes.append(when)

    def tally(times: list[datetime], start: datetime) -> int:
        return sum(start <= at < start + WEEK for at in times)

    weeks = [{"week_start": start.date().isoformat(), "parts": tally(parts, start), "fixes": tally(fixes, start)}
             for start in starts]
    per = [week["parts"] for week in weeks]
    rate3, rate6 = Fraction(sum(per[3:]), 3), Fraction(sum(per), 6)
    pace = {"weeks": weeks, "parts_per_week_3": round(float(rate3), 2), "parts_per_week_6": round(float(rate6), 2)}

    remaining = sum(counts["parts"][state] for state in ("to do", "in progress", "ready to merge"))
    no_plan = [row["title"] for row in items if row["kind"] == "story" and row.get("state") == "no plan yet"]
    earliest = latest = None
    if not parts or min(parts) >= starts[3] or not rate3:
        status, clause = "not enough history", "Not enough history to estimate go-live"
    elif not remaining:
        status, clause = "done", "Planned work is done"
    else:
        earliest, latest = sorted(now.date() + timedelta(days=math.ceil(remaining / rate * 7))
                                  for rate in (rate3, rate6))
        status, clause = (("about", f"Planned work can go live about {_day(earliest)}; the two pace estimates agree")
                          if earliest == latest else
                          ("range", f"Planned work can go live between {_day(earliest)} and {_day(latest)}"))
    if no_plan:
        clause += f"; unknown: {len(no_plan)} {'story has' if len(no_plan) == 1 else 'stories have'} no plan yet"
    go_live = {"status": status, "earliest": earliest and earliest.isoformat(),
               "latest": latest and latest.isoformat(), "remaining_parts": remaining,
               "no_plan": {"count": len(no_plan), "titles": no_plan}}

    trends = around = None
    if github:
        found = [{**week, "prs": [pr for pr in week["prs"] if pr.get("state", "MERGED") == "MERGED"]}
                 for week in github["weeks"]]
        full = found[:6]
        # Grouped by login, which is unique; the display name is only the label.
        people = {(pr.get("author") or {}).get("login"): _person(pr)
                  for week in full if week["complete"] for pr in week["prs"]}
        trends = {"weeks": [week["start"][:10] for week in full],
                  "team": [_split(week["prs"]) if week["complete"] else None for week in full],
                  "people": [{"name": name, "weeks": [
                      _split([pr for pr in week["prs"] if (pr.get("author") or {}).get("login") == login])
                      if week["complete"] else None for week in full]}
                      for login, name in sorted(people.items(), key=lambda person: (person[1].casefold(),
                                                                                    str(person[0])))]}
        # Last week's and this week's searches hold the last 7 days; a capped one leaves it unknown.
        if all(week["complete"] for week in found[-2:]):
            around = sorted(({"title": pr.get("title"), "author": _person(pr), "merged_at": pr.get("mergedAt"),
                              "url": pr.get("url")} for week in found[-2:] for pr in week["prs"]
                             if not _through(pr) and (at := time_records.when(pr.get("mergedAt")))
                             and at >= now - WEEK),
                            key=lambda pr: time_records.when(pr["merged_at"]), reverse=True)
    return {"pace": pace, "go_live": go_live, "trends": trends, "around_forge": around}, clause + "."
