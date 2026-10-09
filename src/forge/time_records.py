"""An item's elapsed time and review history, derived from its existing diagnostic logs."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from forge import repo

CATEGORIES = ("building", "own_tests", "reviewing", "fixing_findings", "waiting_for_ci",
              "waiting_in_line", "waiting_for_owner", "nothing_running")
LABELS = ("building", "own tests", "reviewing", "fixing findings", "waiting for CI",
          "waiting in line", "waiting for the owner", "nothing running")


def read(top: Path, name: str) -> list[dict[str, Any]]:
    path = repo.forge_dir(top) / f"{name}.jsonl"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        except ValueError:
            continue
    return rows


def when(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else None
    except (AttributeError, TypeError, ValueError):
        return None


def duration(value: float | None) -> str:
    return "unknown" if value is None else f"{value:g}s"


def pending_merge_wait(top: Path, key: str) -> dict[str, Any] | None:
    events = [event for event in read(top, "events") if event.get("item") == key]
    ended = {event.get("wait_id") for event in events if event.get("event") == "owner wait end"}
    return next((event for event in reversed(events) if event.get("event") == "owner wait start"
                 and event.get("reason") == "merge" and event.get("id") not in ended), None)


def item(top: Path, key: str, state: dict[str, Any], *,
         events: list[dict[str, Any]] | None = None,
         timings: list[dict[str, Any]] | None = None,
         ended_at: str | None = None) -> dict[str, Any]:
    events = [e for e in (read(top, "events") if events is None else events) if e.get("item") == key]
    timings = [t for t in (read(top, "timings") if timings is None else timings) if t.get("item") == key]
    now = when(repo.now())
    merged = state.get("status") in ("merged", "done")
    finished = next((e.get("at") for e in reversed(events) if e.get("event") == "item finished"), None)
    end = when(ended_at or finished) if merged else now
    starts = [at for r in [*events, *timings] if (at := when(r.get("at") or r.get("start")))]
    start = min(starts) if starts else None
    if start and (began := next((when(s.get("at")) for s in state.get("steps", [])
                                if s.get("step") == "start"), None)):
        start = min(start, began)
    # Intervals overlap: tests, lane and CI waits take precedence over their enclosing worker.
    spans: list[tuple[datetime, datetime, str, int | None]] = []
    # Old timing-only logs establish work intervals, never what happened between them.
    complete_since = min((at for e in events if e.get("event") in (
        "work phase", "lane joined", "run start", "owner wait start", "worker question")
        and (at := when(e.get("at")))), default=None)
    if any(e.get("event") == "lane joined" and e.get("history_complete") for e in events):
        complete_since = start
    phases = {e.get("round"): e.get("phase") for e in events if e.get("event") == "work phase"}

    def work_category(number: int | None) -> str:
        return phases.get(number, "building" if number == 1 else "unknown")

    run_ends = {e.get("run_id"): e for e in events if e.get("event") == "run end"}
    for index, e in enumerate(events):
        if e.get("event") != "run start":
            continue
        finish = run_ends.get(e.get("id"))
        a, b = when(e.get("at")), when(finish.get("at")) if finish else end
        category = {"work": work_category(e.get("round")),
                    "worker": work_category(e.get("round")),
                    "test": "own_tests", "review": "reviewing", "ci": "waiting_for_ci"}.get(e.get("kind"))
        if not finish and any(f.get("event") == "lane left" and f.get("end_known") is False
                              and f.get("round") == e.get("round") and
                              f.get("kind") == ("work" if e.get("kind") == "worker" else e.get("kind"))
                              for f in events[index + 1:]):
            category = "unknown"
        if a and b and category:
            spans.append((a, b, category, e.get("round")))
    for t in timings:
        step = t.get("step")
        category = {"worker round": work_category(t.get("round")),
                    "test run": "own_tests", "review": "reviewing", "CI wait": "waiting_for_ci"}.get(step)
        # Test timing includes queue time; use its actual process interval when recorded.
        if step == "test run" and (t.get("outcome") == "skipped" or any(
                e.get("event") == "run start" and e.get("kind") == "test"
                and e.get("round") == t.get("round") for e in events)):
            continue
        a, seconds = when(t.get("start")), t.get("seconds")
        if a and isinstance(seconds, (int, float)) and seconds >= 0 and category:
            spans.append((a, a + timedelta(seconds=seconds), category, t.get("round")))
    for e in events:
        if e.get("event") == "lane joined":
            finish = next((f for f in events if f.get("lane_id") == e.get("lane_id")
                           and f.get("event") in ("lane admitted", "lane left")), None)
            a = when(e.get("at"))
            b = when(finish.get("at")) if finish and finish.get("end_known", True) else end if not finish else None
            if a and b:
                spans.append((a, b, "waiting_in_line", e.get("round")))
            elif a and end:
                spans.append((a, end, "unknown", e.get("round")))
        elif e.get("event") in ("owner wait start", "worker question"):
            finish = next((f for f in events if f.get("event") == "owner wait end"
                           and f.get("wait_id") == e.get("id")), None)
            a, b = when(e.get("at")), when(finish.get("at")) if finish else end
            if a and b:
                spans.append((a, b, "waiting_for_owner", e.get("round")))
    # A worker turn can contain several closes. Each review result keeps its own line.
    numbers = sorted({r["round"] for r in [*events, *timings] if isinstance(r.get("round"), int)})
    if any(e.get("event") == "review result" and e.get("round") is None for e in events):
        numbers.append(None)
    attempts = []
    for worker_round in numbers:
        reviews = [(index, e) for index, e in enumerate(events)
                   if e.get("round") == worker_round and e.get("event") == "review result"]
        reviewed = [t for t in timings if t.get("round") == worker_round and t.get("step") == "review"]
        records = [r for r in [*events, *timings] if r.get("round") == worker_round]
        began = min((at for r in records if (at := when(r.get("at") or r.get("start")))), default=start)
        for position, (index, result) in enumerate(reviews or [(None, {})]):
            if position:
                previous = reviews[position - 1][0]
                trigger = next((e for e in events[previous + 1:index]
                                if e.get("round") == worker_round and e.get("kind") in ("test", "review")
                                and e.get("event") in ("lane joined", "run start")), {})
                began = when(trigger.get("at"))
                if began is None and position < len(reviewed):
                    began = when(reviewed[position].get("start"))
                began = began or when(result.get("at"))
            attempts.append({"worker_round": worker_round, "number": result.get("review_round"),
                             "result": result, "start": began,
                             "review_timings": reviewed[position:position + 1] if reviews else reviewed})

    def attempt(number: int | None, at: datetime) -> int | None:
        choices = [(index, r) for index, r in enumerate(attempts) if r["worker_round"] == number]
        return next((index for index, r in reversed(choices) if r["start"] and r["start"] <= at),
                    choices[0][0] if choices else None)

    totals: dict[str, float | None] = dict.fromkeys(CATEGORIES)
    per_attempt: dict[int, dict[str, float]] = {}
    owner_done: dict[int, float] = {}
    owner_open: set[int] = set()
    for event in events:
        if (not merged and event.get("event") in ("owner wait start", "worker question")
                and not any(e.get("event") == "owner wait end" and e.get("wait_id") == event.get("id") for e in events)
                and (at := when(event.get("at")))
                and (index := attempt(event.get("round"), at)) is not None):
            owner_open.add(index)
    for a, b, category, number in spans:
        if b >= a and category != "unknown":
            totals[category] = 0
            if (index := attempt(number, a)) is not None:
                per_attempt.setdefault(index, {}).setdefault(category, 0)
                if category == "waiting_for_owner" and index not in owner_open:
                    owner_done.setdefault(index, 0)
    recorded_end = max((b for _, b, _, _ in spans), default=None)
    if not merged and end and recorded_end:
        end = max(end, recorded_end)  # Completed monotonic durations are more precise than now's whole seconds.
    bound = end or recorded_end
    if start and bound:
        points = sorted({start, bound, *[max(start, min(bound, p)) for a, b, _, _ in spans for p in (a, b)],
                         *([max(start, min(bound, complete_since))] if complete_since else []),
                         *[max(start, min(bound, r["start"])) for r in attempts if r["start"]]})
        priority = ("own_tests", "waiting_in_line", "waiting_for_ci", "reviewing",
                    "fixing_findings", "building", "waiting_for_owner", "unknown")
        for a, b in zip(points, points[1:]):
            covering = [(category, number) for x, y, category, number in spans if x <= a and y >= b]
            category, number = min(covering, key=lambda c: priority.index(c[0])) if covering else (
                "nothing_running" if end and complete_since and a >= complete_since else "unknown", None)
            if category == "unknown":
                continue
            seconds = (b - a).total_seconds()
            totals[category] = (totals[category] or 0) + seconds
            if (index := attempt(number, a)) is not None:
                by_category = per_attempt.setdefault(index, {})
                by_category[category] = by_category.get(category, 0) + seconds
                if category == "waiting_for_owner":
                    waits = [e for e in events if e.get("round") == number
                             and e.get("event") in ("owner wait start", "worker question")
                             and (at := when(e.get("at"))) and at <= a]
                    finished_wait = any(any(f.get("event") == "owner wait end" and f.get("wait_id") == e.get("id")
                                           and (at := when(f.get("at"))) and at >= b for f in events) for e in waits)
                    if finished_wait or merged:
                        owner_done[index] = owner_done.get(index, 0) + seconds
                    else:
                        owner_open.add(index)
    totals = {k: round(v, 3) if v is not None else None for k, v in totals.items()}
    rounds, seen = [], set()
    first_review = next((r for r in attempts if r["result"]), {})
    known_history = first_review.get("number") == 1
    for index, current in enumerate(attempts):
        number, worker_round, result = current["number"], current["worker_round"], current["result"]
        findings = result.get("findings") if isinstance(result.get("findings"), list) else None
        comparable = findings is not None and (known_history or all(
            (f.get("file"), f.get("title")) in seen for f in findings))
        fresh = sum((f.get("file"), f.get("title")) not in seen for f in findings) if comparable else None
        observed_repeats = sum((f.get("file"), f.get("title")) in seen for f in findings or [])
        repeats = observed_repeats if comparable or observed_repeats else None
        seen.update((f.get("file"), f.get("title")) for f in findings or [])
        if result and findings is None:
            known_history = False
        steps = []
        for step, label in (("worker round", "work"), ("test run", "tests"), ("review", "review"), ("CI wait", "CI")):
            rows = [t for t in timings if t.get("round") == worker_round and t.get("step") == step
                    and (at := when(t.get("start"))) and attempt(worker_round, at) == index]
            if step == "review":
                rows = current["review_timings"]
            if rows:
                if step == "worker round":
                    label = work_category(worker_round).replace("_", " ")
                outcomes = []
                for timing in rows:
                    outcome = timing.get("outcome") or "unknown"
                    if step == "CI wait" and outcome == "failed":
                        matched = sum(e.get("event") == "CI result" and e.get("outcome") == "failed"
                                      and e.get("round") == worker_round and e.get("start") == timing.get("start")
                                      for e in events)
                        failed = sum(t.get("step") == step and t.get("outcome") == "failed"
                                     and t.get("round") == worker_round and t.get("start") == timing.get("start")
                                     for t in timings)
                        if matched != failed:
                            outcome = "unknown"
                    outcomes.append(str(outcome).replace("_", " "))
                outcomes = ", then ".join(outcomes)
                categories = {"worker round": ("building", "fixing_findings"), "test run": ("own_tests",),
                              "review": ("reviewing",), "CI wait": ("waiting_for_ci",)}[step]
                times = [per_attempt.get(index, {}).get(c) for c in categories]
                seconds = sum(t for t in times if t is not None) if any(t is not None for t in times) else None
                steps.append(f"{label} {outcomes} ({duration(round(seconds, 3) if seconds is not None else None)})")
        for category, label in (("waiting_in_line", "in line"), ("waiting_for_owner", "waiting for the owner")):
            seconds = (owner_done.get(index) if category == "waiting_for_owner"
                       else per_attempt.get(index, {}).get(category))
            if seconds is not None:
                steps.append(f"{label} {duration(round(seconds, 3))}")
            if category == "waiting_for_owner" and index in owner_open:
                steps.append(f"{label} (ongoing)")
        titles = "; ".join(f"{f.get('priority') or 'unknown'} {f.get('title') or 'unknown'} ({f.get('file') or 'unknown'})"
                           for f in findings or [])
        steps.append(f"findings: {fresh if fresh is not None else 'unknown'} new, {repeats if repeats is not None else 'unknown'} repeated"
                     + (f" — {titles}" if titles else ""))
        rounds.append({"round": number, "worker_round": worker_round,
                       "line": f"Round {number if number is not None else 'unknown'}: " + "; ".join(steps),
                       "findings": findings, "new_findings": fresh, "repeat_findings": repeats})
    return {"time_breakdown": totals, "rounds": rounds,
            "total_seconds": round((end - start).total_seconds(), 3) if start and end and end >= start else None}


def how_it_went(top: Path, key: str, state: dict[str, Any]) -> str:
    data = item(top, key, state)
    times = "; ".join(f"{label}: {duration(data['time_breakdown'][category])}"
                      for category, label in zip(CATEGORIES, LABELS))
    return "## How it went\n\n" + times + "\n\n" + "\n".join(r["line"] for r in data["rounds"])
