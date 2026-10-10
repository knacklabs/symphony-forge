"""Elapsed time and review history, shared through pull requests and local observations."""
import json
import hashlib
import math
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from forge import repo

CATEGORIES = ("building", "own_tests", "reviewing", "fixing_findings", "waiting_for_ci",
              "waiting_in_line", "waiting_for_owner", "nothing_running")
LABELS = ("building", "own tests", "reviewing", "fixing findings", "waiting for CI",
          "waiting in line", "waiting for the owner", "nothing running")
HISTORY_SECTION = re.compile(
    r"## How it went\n.*?(?=\n(?:## |Proof list:|Functional check:|<!-- forge:end -->)|\Z)", re.S)
RESUMED = "<!-- forge:history-resumed -->"


def checkpoint(rows: list[dict[str, Any]]) -> list[Any]:
    return [len(rows), hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()]


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
    return plain(value)


def plain(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    value = max(0, round(seconds))
    if value < 60:
        return f"{value} second" + ("s" if value != 1 else "")
    minutes = round(value / 60)
    if minutes < 60:
        return f"{minutes} minute" + ("s" if minutes != 1 else "")
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} hour" + ("s" if hours != 1 else "") + (
            f" {minutes} minute" + ("s" if minutes != 1 else "") if minutes else "")
    days = round(value / 86400)
    return f"{days} day" + ("s" if days != 1 else "")


def pending_merge_wait(top: Path, key: str, published: str = "", *, reason: str = "merge") -> dict[str, Any] | None:
    events = [event for event in [*from_body(published).get("events", []), *read(top, "events")]
              if event.get("item") == key]
    ended = {event.get("wait_id") for event in events if event.get("event") == "owner wait end"}
    return next((event for event in reversed(events) if event.get("event") == "owner wait start"
                 and event.get("reason") == reason and event.get("id") not in ended), None)


def item(top: Path, key: str, state: dict[str, Any], *,
         events: list[dict[str, Any]] | None = None,
         timings: list[dict[str, Any]] | None = None,
         ended_at: str | None = None) -> dict[str, Any]:
    events = [e for e in (read(top, "events") if events is None else events) if e.get("item") == key]
    timings = [t for t in (read(top, "timings") if timings is None else timings) if t.get("item") == key]
    lane_rounds = {e["lane_id"]: e["round"] for e in events if e.get("event") == "work phase"
                   and e.get("lane_id") and isinstance(e.get("round"), int)}
    events = [{**e, "round": lane_rounds[e["lane_id"]]}
              if e.get("event", "").startswith("lane ") and e.get("lane_id") in lane_rounds
              else e for e in events]
    now = when(repo.now())
    merged = state.get("status") in ("merged", "done")
    finished = next((e.get("at") for e in reversed(events) if e.get("event") == "item finished"), None)
    end = when(ended_at or finished) if merged else now
    starts = [at for r in [*events, *timings] if (at := when(r.get("at") or r.get("start")))]
    start = min(starts) if starts else None
    if began := next((when(s.get("at")) for s in state.get("steps", [])
                      if s.get("step") == "start"), None):
        start = min(start, began) if start else began
    # Intervals overlap: tests, lane and CI waits take precedence over their enclosing worker.
    spans: list[tuple[datetime, datetime, str, int | None]] = []
    # Only the new lifecycle records establish complete activity recording.
    complete_since = min((at for e in events if e.get("event") in (
        "work phase", "lane joined", "owner wait start")
        and (at := when(e.get("at")))), default=None)
    phases = {e.get("round"): e.get("phase") for e in events if e.get("event") == "work phase"}

    def work_category(number: int | None) -> str:
        return phases.get(number, "unknown")

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
            if e.get("event") == "worker question" and not finish and (
                    not a or not complete_since or a < complete_since):
                continue  # Earlier workers answered questions without recording their end.
            if a and b:
                spans.append((a, b, "waiting_for_owner", e.get("round")))
    # A worker turn can contain several closes. Each review result keeps its own line.
    numbers = sorted({r["round"] for r in [*events, *timings] if isinstance(r.get("round"), int)})
    if (any(e.get("event") == "review result" and e.get("round") is None for e in events)
            or any(t.get("round") is None and when(t.get("start")) for t in timings)):
        numbers.append(None)
    attempts = []
    for worker_round in numbers:
        reviews = [(index, e) for index, e in enumerate(events)
                   if e.get("round") == worker_round and e.get("event") == "review result"]
        reviewed = [t for t in timings if t.get("round") == worker_round and t.get("step") == "review"]
        records = [r for r in [*events, *timings] if r.get("round") == worker_round]
        began = min((at for r in records if (at := when(r.get("at") or r.get("start")))), default=start)
        observed = [{"index": None, "result": {}, "timing": timing} for timing in reviewed]
        # Results were added after timing-only releases; match recorded starts, never positions.
        for index, result in reversed(reviews):
            at = when(result.get("at"))
            match = next((one for one in reversed(observed) if not one["result"]
                          and at and (a := when(one["timing"].get("start"))) and a <= at), None)
            if match is None:
                observed.append({"index": index, "result": result, "timing": {}})
            else:
                match.update(index=index, result=result)
        observed.sort(key=lambda one: (when(one["timing"].get("start"))
                      or when(one["result"].get("at")) or began,
                      one["index"] if one["index"] is not None else -1))
        previous = None
        for current in observed or [{"index": None, "result": {}, "timing": {}}]:
            index, result, timing = current["index"], current["result"], current["timing"]
            if previous is not None:
                prior = previous["index"]
                prior_at = when(previous["result"].get("at"))
                if prior_at is None and (a := when(previous["timing"].get("start"))):
                    prior_at = a + timedelta(seconds=previous["timing"].get("seconds", 0))
                trigger = next((e for e in events[prior + 1 if prior is not None else 0:index]
                                if e.get("round") == worker_round and e.get("kind") in ("test", "review")
                                and e.get("event") in ("lane joined", "run start")
                                and (at := when(e.get("at"))) and (prior_at is None or at >= prior_at)), {})
                starts = [at for value in (trigger.get("at"), timing.get("start"), result.get("at"))
                          if (at := when(value))]
                began = min(starts) if starts else None
            attempts.append({"worker_round": worker_round, "number": result.get("review_round"),
                             "result": result, "start": began,
                             "review_timings": [timing] if timing else []})
            previous = current

    attempts.sort(key=lambda current: (current["start"] is None, current["start"]))

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
                and (event.get("event") == "owner wait start" or complete_since and at >= complete_since)
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
    intervals = []
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
            intervals.append({"start": a.isoformat(), "end": b.isoformat(), "category": category,
                              "kind": "working" if category in CATEGORIES[:4] else
                                      "waiting" if category in CATEGORIES[4:7] else "unknown"})
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
    first_review = next((r for r in attempts if r["result"] or r["review_timings"]), {})
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
        if (result or current["review_timings"]) and findings is None:
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
    return {"time_breakdown": totals, "rounds": rounds, "intervals": intervals,
            "events": events, "timings": timings, "state": state, "ended_at": ended_at,
            "total_seconds": round((end - start).total_seconds(), 3) if start and end and end >= start else None}


def how_it_went(top: Path, key: str, state: dict[str, Any], published: str = "") -> str:
    records = {name: [row for row in read(top, name) if row.get("item") == key]
               for name in ("events", "timings")}
    data = merged(item(top, key, state, **records), from_body(published))
    data["clean_reviews"] = list({r.get("id") or r.get("commit"): r
                                  for r in [*data.get("clean_reviews", []),
                                            *[e for e in data["events"] if e.get("event") == "review result"
                                              and e.get("outcome") == "clean"]]}.values())
    try:
        ready = json.loads(repo.ready_path(key, top).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ready = {}
    head = repo.git("rev-parse", "HEAD", cwd=top)
    data["ready"] = None
    if ready.get("commit") == head and ready.get("review") == "clean":
        data["ready"] = {"commit": head, "review": "clean"}
        if review := state.get("review"):
            data["clean_reviews"] = list({r.get("id") or r.get("commit"): r
                                          for r in [*data["clean_reviews"], review]}.values())
    times = "; ".join(f"{label}: {duration(data['time_breakdown'][category])}"
                      for category, label in zip(CATEGORIES, LABELS))
    current = times + "\n\n" + "\n".join(r["line"] for r in data["rounds"])
    managed = re.search(r"<!-- forge:begin -->.*?<!-- forge:end -->", published, re.S)
    previous = HISTORY_SECTION.search(managed[0]) if managed else None
    retained = data.get("legacy_text") or ""
    if previous and not from_body(published):
        text = previous[0].removeprefix("## How it went\n").strip()
        marker = re.search(r"\n<!-- forge:history (\{.*\}) -->\s*$", text)
        complete = False
        if marker:
            try:
                saved = json.loads(marker[1])
                complete = all(isinstance(saved[name][0], int) and saved[name][0] >= 0
                               and checkpoint(records[name][:saved[name][0]]) == saved[name]
                               for name in records)
            except (ValueError, KeyError, TypeError, IndexError):
                pass
            text = text[:marker.start()].rstrip()
        # Old rendered totals have no interval boundaries: retain them, never add them.
        retained = text.rsplit(RESUMED, 1)[0].rstrip() if complete else text
        if complete and RESUMED not in text:
            retained = ""
    if retained:
        data["legacy_text"] = retained
        current = (retained + "\n\n" + RESUMED + "\n\n"
                   "Observed after resuming in this checkout (totals are separate from the "
                   "published measurements above):\n\n" + current)
    if data.get("rebuilt"):
        current = "Rebuilt from history.\n\n" + current
    saved = {name: checkpoint(rows) for name, rows in records.items()}
    shared = {**data, "state": {"steps": [s for s in data["state"].get("steps", []) if s.get("step") == "start"]}}
    return "## How it went\n\n" + current.rstrip() + "\n<!-- forge:history " + json.dumps(saved) + " -->" + \
        "\n<!-- forge:time-record " + json.dumps(shared, separators=(",", ":")) + " -->"


def from_body(body: str) -> dict[str, Any]:
    block = re.search(r"<!-- forge:begin -->.*?<!-- forge:end -->", body or "", re.S)
    match = re.search(r"<!-- forge:time-record (\{.*?\}) -->", block[0], re.S) if block else None
    try:
        data = json.loads(match[1]) if match else {}
        if not isinstance(data, dict) or not all(
            isinstance(data.get(name), list) and all(isinstance(row, dict) for row in data[name])
            for name in ("events", "timings")):
            return {}
        if not isinstance(data.get("state", {}), dict) or not isinstance(data.get("ready") or {}, dict):
            return {}
        steps = data.get("state", {}).get("steps", [])
        reviews = data.get("clean_reviews", [])
        if not isinstance(steps, list) or not isinstance(reviews, list):
            return {}
        if not isinstance(data.get("legacy_text") or "", str):
            return {}
        for row in [*data["events"], *data["timings"], *steps, *reviews]:
            if not isinstance(row, dict) or any(row.get(key) is not None and not isinstance(row[key], str)
                    for key in ("id", "run_id", "lane_id", "wait_id", "at", "start", "step", "event",
                                "kind", "phase", "outcome", "commit")):
                return {}
            if any(row.get(key) is not None and not isinstance(row[key], int)
                   for key in ("round", "review_round")):
                return {}
            if row.get("phase") is not None and row["phase"] not in ("building", "fixing_findings", "unknown"):
                return {}
            seconds = row.get("seconds")
            if seconds is not None and (not isinstance(seconds, (int, float)) or
                                        not math.isfinite(seconds) or seconds < 0):
                return {}
            findings = row.get("findings")
            if findings is not None and (not isinstance(findings, list) or any(
                    not isinstance(f, dict) or any(f.get(key) is not None and not isinstance(f[key], str)
                        for key in ("file", "title", "priority")) for f in findings)):
                return {}
        return data
    except (ValueError, TypeError):
        return {}


def merged(local: dict[str, Any], published: dict[str, Any]) -> dict[str, Any]:
    """Union observations, then derive once so overlapping snapshots never add time."""
    if not published:
        return {**local, "source": "local"}
    rows = {}
    for name in ("events", "timings"):
        unique = {}
        for row in [*published.get(name, []), *local.get(name, [])]:
            identity = row.get("id") if name == "events" else None
            unique.setdefault(identity or json.dumps(row, sort_keys=True), {**row})
        rows[name] = sorted(unique.values(), key=lambda row: row.get("at") or row.get("start") or "")
    reviews = [r for r in rows["events"] if r.get("event") == "review result"]
    if reviews and reviews[0].get("review_round") == 1:
        for number, result in enumerate(reviews, 1):
            if result.get("review_round") is None and isinstance(result.get("findings"), list):
                result["review_round"] = number
    state = {**published.get("state", {}), **local.get("state", {})}
    starts = [step for data in (local, published) for step in data.get("state", {}).get("steps", [])
              if step.get("step") == "start" and when(step.get("at"))]
    if starts:
        state = {**state, "steps": [min(starts, key=lambda step: step["at"])]}
    data = item(Path("."), "", state, events=[{**r, "item": ""} for r in rows["events"]],
                timings=[{**r, "item": ""} for r in rows["timings"]], ended_at=local.get("ended_at"))
    data.update(rows, source="pull request and local" if local.get("events") or local.get("timings")
                else "pull request", rebuilt=bool(local.get("rebuilt") or published.get("rebuilt")))
    data["ready"] = published.get("ready")
    data["legacy_text"] = published.get("legacy_text")
    data["clean_reviews"] = list({r.get("id") or r.get("commit"): r for r in
                                  [*published.get("clean_reviews", []), *local.get("clean_reviews", [])]}.values())
    return data


def refresh_record(top: Path, key: str, state: dict[str, Any], body: str) -> str:
    history = how_it_went(top, key, state, body)
    def replace(block: re.Match[str]) -> str:
        text, count = HISTORY_SECTION.subn(lambda _: history + "\n", block[0], count=1)
        return text if count else text.replace("<!-- forge:end -->", history + "\n<!-- forge:end -->", 1)
    return re.sub(r"<!-- forge:begin -->.*?<!-- forge:end -->", replace, body, count=1, flags=re.S)


def story(parts: list[dict[str, Any]], read_rounds: list[dict[str, Any]]) -> dict[str, Any]:
    spans = [span for part in parts for span in part.get("intervals", [])]
    for read in read_rounds:
        end, seconds = when(read.get("read_at")), read.get("seconds")
        if end:
            known = isinstance(seconds, (float, int)) and seconds >= 0
            spans.append({"start": (end - timedelta(seconds=seconds if known else 0)).isoformat(),
                          "end": end.isoformat(), "kind": "working" if known else "unknown"})
    points = sorted({at for span in spans for name in ("start", "end") if (at := when(span.get(name)))})
    intervals, totals = [], dict.fromkeys(("working", "waiting", "unknown"), 0.0)
    for a, b in zip(points, points[1:]):
        kinds = {span.get("kind") for span in spans if (x := when(span.get("start")))
                 and (y := when(span.get("end"))) and x <= a and y >= b}
        kind = "working" if "working" in kinds else "waiting" if "waiting" in kinds else "unknown"
        totals[kind] += (b - a).total_seconds()
        intervals.append({"start": a.isoformat(), "end": b.isoformat(), "kind": kind})
    return {"intervals": intervals, "time_breakdown": totals,
            "total_seconds": sum(totals.values()) if points else None}
