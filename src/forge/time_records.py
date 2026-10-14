"""Elapsed time and review history, shared through pull requests and local observations."""
import functools
import json
import hashlib
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


SEEN = 300  # ponytail: a finding last seen over 300 findings ago counts as new again.
RECORD_BUDGET = 20_000  # bytes of shared time record; older detail folds into the totals line.


def _mark(finding: dict[str, Any]) -> str:
    """A finding's identity for repeat counts, short enough to keep many."""
    return hashlib.sha256(f"{finding.get('file')}\0{finding.get('title')}".encode()).hexdigest()[:12]


def _short(entry: dict[str, Any]) -> dict[str, Any]:
    """A summarised round: its plain line, cut to a fixed length, stands for its finding list."""
    line = entry["line"] if len(entry["line"]) <= 300 else entry["line"][:299] + "…"
    return {**entry, "line": line, "findings": None}


def _fold(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    seconds = {c: round(a["seconds"].get(c, 0) + b["seconds"].get(c, 0), 3)
               for c in CATEGORIES if c in a["seconds"] or c in b["seconds"]}
    counts = [None if a[k] is None or b[k] is None else a[k] + b[k] for k in ("new_findings", "repeat_findings")]
    first = a.get("first", a["round"])
    first = b.get("first", b["round"]) if first is None else first
    last = b.get("last", b["round"])
    last = a.get("last", a["round"]) if last is None else last
    line = (("Earlier rounds" if first is None else f"Round {first}" if first == last else f"Rounds {first}–{last}") + ": "
            + "".join(f"{label} {duration(seconds[c])}; " for c, label in zip(CATEGORIES, LABELS) if c in seconds)
            + "findings: " + " new, ".join("unknown" if n is None else str(n) for n in counts) + " repeated")
    return {"round": None, "worker_round": None, "line": line, "findings": None, "new_findings": counts[0],
            "repeat_findings": counts[1], "seconds": seconds, "first": first, "last": last}


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
         ended_at: str | None = None, summary: dict[str, Any] | None = None) -> dict[str, Any]:
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
    for index, e in enumerate(events):
        if e.get("event") == "lane joined":
            finish = next((f for f in events if f.get("lane_id") == e.get("lane_id")
                           and f.get("event") in ("lane admitted", "lane left")), None)
            a = when(e.get("at"))
            b = when(finish.get("at")) if finish and finish.get("end_known", True) else None
            if finish is None:
                # An abandoned wait cannot span later item activity.
                b = when(events[index + 1].get("at")) if index + 1 < len(events) else end
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

    @functools.cache  # Called per interval and per timing; a long round has hundreds of each.
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
    # A published summary carries the finding history of the rounds it replaced.
    rounds, seen = [], dict.fromkeys((summary or {}).get("seen", []))
    first_review = next((r for r in attempts if r["result"] or r["review_timings"]), {})
    known_history = summary["known"] if summary else first_review.get("number") == 1
    for index, current in enumerate(attempts):
        number, worker_round, result = current["number"], current["worker_round"], current["result"]
        findings = result.get("findings") if isinstance(result.get("findings"), list) else None
        comparable = findings is not None and (known_history or all(
            _mark(f) in seen for f in findings))
        fresh = sum(_mark(f) not in seen for f in findings) if comparable else None
        observed_repeats = sum(_mark(f) in seen for f in findings or [])
        repeats = observed_repeats if comparable or observed_repeats else None
        for mark in map(_mark, findings or []):  # A repeat moves to the newest end.
            seen.pop(mark, None)
            seen[mark] = None
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
                if len(outcomes) > 3:  # Many retries name their first and last result.
                    outcomes = [outcomes[0], f"{len(outcomes) - 2} more", outcomes[-1]]
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
                       "findings": findings, "new_findings": fresh, "repeat_findings": repeats,
                       "seconds": {c: round(v, 3) for c, v in per_attempt.get(index, {}).items()}})
    grouped = {f"{kind}_seconds": round(sum((when(span["end"]) - when(span["start"])).total_seconds()
                                           for span in intervals if span["kind"] == kind), 3)
               if intervals or (start and end) else None for kind in ("working", "waiting", "unknown")}
    return {"time_breakdown": totals, **grouped, "rounds": rounds, "intervals": intervals,
            "seen": list(seen)[-SEEN:], "known": known_history, "events": events, "timings": timings, "state": state, "ended_at": ended_at,
            "total_seconds": round((end - start).total_seconds(), 3) if start and end and end >= start else None}


def how_it_went(top: Path, key: str, state: dict[str, Any], published: str = "", *,
               preserve_ready: bool = False) -> str:
    records = {name: [row for row in read(top, name) if row.get("item") == key]
               for name in ("events", "timings")}
    data = combined(top, key, state, published, **records)
    data["clean_reviews"] = list({r.get("id") or r.get("commit"): r
                                  for r in [*data.get("clean_reviews", []),
                                            *[e for e in data["events"] if e.get("event") == "review result"
                                              and e.get("outcome") == "clean"]]}.values())
    # Only close publishes readiness; a history refresh may come from an older checkout.
    if not preserve_ready:
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
    # The whole published record is measured, and each entry in it has a fixed maximum size.
    # An earlier release's retained history text is one entry with a larger fixed limit.
    legacy = data.get("legacy_text") or None
    base = {**_capped({**{name: data.get(name) for name in ("ready", "rebuilt", "truncated")},
                       "state": {"steps": [{"step": "start", "at": s.get("at")}
                                           for s in data["state"].get("steps", []) if s.get("step") == "start"]}}),
            "legacy_text": legacy[:7999] + "…" if legacy and len(legacy) > 8000 else legacy}
    clean = [{k: r[k] for k in ("id", "commit", "at", "round", "outcome") if k in r} for r in data["clean_reviews"]]
    # Close's saved review snapshot has no round or time: keep only the newest one.
    clean = [r for r in clean if r.get("at")] + [r for r in clean if not r.get("at")][-1:]
    summary, rows, clean = _compact(data, base, clean)
    # Show what the pull request keeps, so the visible history stays as bounded as the record.
    view = merged({"ended_at": data.get("ended_at")}, {**rows, "summary": summary, "state": data["state"]}) \
        if summary else data
    times = "; ".join(f"{label}: {duration(view['time_breakdown'][category])}"
                      for category, label in zip(CATEGORIES, LABELS))
    times = "; ".join(f"{kind}: {duration(view[f'{kind}_seconds'])}"
                      for kind in ("working", "waiting", "unknown")) + "\n\n" + times
    current = times + "\n\n" + "\n".join(r["line"] for r in view["rounds"])
    if retained:
        current = (retained + "\n\n" + RESUMED + "\n\n"
                   "Observed after resuming in this checkout (totals are separate from the "
                   "published measurements above):\n\n" + current)
    if data.get("rebuilt"):
        current = "Rebuilt from history.\n\n" + current
    if data.get("truncated"):
        current = "Older time detail was shortened to fit GitHub; missing time is unknown.\n\n" + current
    saved = {name: checkpoint(found) for name, found in records.items()}
    shared = {**base, "clean_reviews": clean, **rows, "summary": summary}
    return "## How it went\n\n" + current.rstrip() + "\n<!-- forge:history " + json.dumps(saved) + " -->" + \
        "\n<!-- forge:time-record " + json.dumps(shared, separators=(",", ":")) + " -->"


TEN_YEARS = 10 * 365 * 86400


def _sane(text: str) -> float:
    """Every number in the record is a duration or a count: never negative, never over ten years."""
    value = float(text)
    if not 0 <= value <= TEN_YEARS:  # also refuses NaN and infinity
        raise ValueError(f"{text} is outside the record's range")
    return value


def from_body(body: str) -> dict[str, Any]:
    block = re.search(r"<!-- forge:begin -->.*?<!-- forge:end -->", body or "", re.S)
    match = re.search(r"<!-- forge:time-record (\{.*?\}) -->", block[0], re.S) if block else None
    if not match:
        return {}
    # One guard for every reader: anyone can edit a PR body, so the record is read once the way
    # board, next and close read it, and any wrong type, null or out-of-range number makes it no
    # record instead of a crash.
    try:
        data = json.loads(match[1], parse_float=_sane, parse_int=lambda text: int(_sane(text)), parse_constant=_sane)
        # A folded entry without valid times and seconds counts as unknown time.
        if isinstance(summary := data.get("summary"), dict) and (folded := summary.get("folded")) is not None and not (
                isinstance(folded, dict) and when(folded.get("start")) and when(folded.get("end"))
                and all(type(folded.get(kind, 0)) in (int, float) and folded.get(kind, 0) >= 0
                        for kind in ("working", "waiting", "unknown"))):
            summary["folded"] = None
        merged({}, data)
        (data.get("ready") or {}).get("commit")
        "".join([data.get("legacy_text") or ""])
        return data
    except Exception:  # a PR body is user-editable text, so no record shape may crash a reader
        return {}


SUMMED = ("working_seconds", "waiting_seconds", "unknown_seconds", "total_seconds")


def _add(a: float | None, b: float | None) -> float | None:
    return None if a is None and b is None else round((a or 0) + (b or 0), 3)


def _joined(older: list[dict[str, Any]], newer: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A review round cut part-way continues in its own line: later rows with no review of their
    own (such as CI retries) add their steps and times to it, and it keeps its number."""
    if older and newer and newer[0]["round"] is None and newer[0]["worker_round"] == older[-1]["worker_round"] \
            and older[-1]["round"] is not None:
        a, b = older[-1], newer[0]
        head, _, tail = a["line"].partition("; findings: ")
        steps = [step for step in b["line"].removeprefix("Round unknown: ").split("; ")
                 if not step.startswith("findings: ") and step not in head.split("; ")]
        line = "; ".join([head, *steps]) + ("; findings: " + tail if tail else "")
        seconds = _fold(a, {**b, "new_findings": 0, "repeat_findings": 0})["seconds"]
        return [*older[:-1], {**a, "line": line[:300], "seconds": seconds}, *newer[1:]]
    return [*older, *newer]


def _summed(summary: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """The summarised earlier rounds followed by what the remaining rows show."""
    return {**data, **{name: _add(summary[name], data[name]) for name in SUMMED},
            "time_breakdown": {name: _add(summary["time_breakdown"][name], data["time_breakdown"][name])
                               for name in CATEGORIES},
            "rounds": _joined(summary["rounds"], data["rounds"]),
            "intervals": [*summary["intervals"], *data["intervals"]], "folded_seconds": summary.get("folded")}


def _settled(row: dict[str, Any], number: int, until: datetime) -> bool:
    """A row a summary replaces: an earlier worker round's, or any row before its cut."""
    mark = row.get("round")
    if isinstance(mark, int) and not isinstance(mark, bool) and mark < number:
        return True
    at = when(row.get("at") or row.get("start"))
    return at is not None and at < until


def _capped(value: Any) -> Any:
    """Free text in a published row has a fixed maximum length."""
    if isinstance(value, dict):
        return {key: _capped(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_capped(item) for item in value]
    return value[:299] + "…" if isinstance(value, str) and len(value) > 300 else value


def _compact(data: dict[str, Any], base: dict[str, Any], clean: list[dict[str, Any]],
             ) -> tuple[dict[str, Any] | None, dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Keep the published record under a fixed size: while it is over, fold the oldest detail
    of any kind (summarised rounds, then their intervals, then raw rows) into the totals."""
    summary = json.loads(json.dumps(data["summary"])) if data.get("summary") else None
    # Progress is live-only: the board reads it locally, and a long round records it every ten
    # seconds. Stage events stay.
    rows = {"events": [_capped(e) for e in data["events"] if e.get("event") != "progress"],
            "timings": [_capped(t) for t in data["timings"]]}
    def kept() -> list[dict[str, Any]]:
        return [r for r in clean if not summary or not _settled(r, summary["round"], when(summary["until"]))]

    while len(json.dumps({**base, "clean_reviews": kept(), **rows, "summary": summary}, separators=(",", ":"))) \
            > RECORD_BUDGET:
        if summary and len(summary["rounds"]) > 2:  # The newest summarised line stays its own.
            summary["rounds"][:2] = [_fold(*summary["rounds"][:2])]
        elif summary and summary["intervals"]:
            # Dropped intervals keep their range and per-kind seconds for the story's time.
            dropped = summary["intervals"][:max(1, len(summary["intervals"]) // 2)]
            del summary["intervals"][:len(dropped)]
            folded = summary.get("folded") or {"start": dropped[0]["start"]}
            for span in dropped:
                folded[span["kind"]] = round(folded.get(span["kind"], 0)
                                             + (when(span["end"]) - when(span["start"])).total_seconds(), 3)
            summary["folded"] = {**folded, "end": dropped[-1]["end"]}
        else:
            times = sorted(at for name in rows for r in rows[name] if (at := when(r.get("at") or r.get("start"))))
            ends = sorted(at for r in rows["events"] if r.get("event") == "review result" and (at := when(r.get("at"))))
            # Fold the whole review rounds before the newest, each with the CI wait after its
            # review, up to where the newest round's work, tests or review start; when none is
            # left to cut, the newest round folds whole into its own line.
            starts = sorted(at for name in rows for r in rows[name] if r.get("kind") != "ci" and (
                r.get("event") in ("run start", "lane joined", "work phase")
                or r.get("step") in ("worker round", "test run", "review")) and (at := when(r.get("at") or r.get("start"))))
            cuts = [next((at for at in starts if at > end), None) for end in ends]
            until = next((at for at in reversed(cuts) if at), None)
            if until is None and times:  # One round is still too big, such as a huge review or many CI retries.
                until = times[-1] + timedelta(microseconds=1)
            if until is None:
                break
            number = max([summary["round"]] if summary else [], default=0)
            number = max([number, *[r["round"] for name in rows for r in rows[name] if isinstance(r.get("round"), int)
                          and not isinstance(r["round"], bool) and (at := when(r.get("at") or r.get("start")))
                          and at < until]])
            summary, rows = _summarised(data, summary, rows, number, until)
    return summary, rows, kept()


def _summarised(data: dict[str, Any], summary: dict[str, Any] | None, rows: dict[str, list[dict[str, Any]]],
                number: int, until: datetime) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Move the rows before the cut into the summary, one short line per review round."""
    past = {name: [{**r, "item": ""} for r in rows[name] if _settled(r, number, until)] for name in rows}
    start = summary["until"] if summary else next(
        (s.get("at") for s in data["state"].get("steps", []) if s.get("step") == "start"), None)
    part = item(Path("."), "", {"status": "merged", "steps": [{"step": "start", "at": start}] if start else []},
                ended_at=until.isoformat(), summary=summary, **past)
    intervals: list[dict[str, Any]] = []
    # Adjacent intervals of one category join; a short step keeps its own boundaries, since
    # waits and stages are told apart by where they start and end.
    for span in part["intervals"]:
        if intervals and intervals[-1]["end"] == span["start"] and intervals[-1]["category"] == span["category"]:
            intervals[-1]["end"] = span["end"]
        else:
            intervals.append({**span})
    part["intervals"] = intervals
    part["rounds"] = [_short(entry) for entry in part["rounds"]]
    whole = _summed(summary, part) if summary else part
    kept = {name: whole[name] for name in ("time_breakdown", *SUMMED, "rounds", "intervals", "seen", "known")}
    return ({**kept, "until": until.isoformat(), "round": number, "folded": (summary or {}).get("folded")},
            {name: [r for r in rows[name] if not _settled(r, number, until)] for name in rows})


def combined(top: Path, key: str, state: dict[str, Any], published: str, *,
             events: list[dict[str, Any]] | None = None, timings: list[dict[str, Any]] | None = None,
             ended_at: str | None = None) -> dict[str, Any]:
    """The item's time from local logs and its pull request, derived once; a published summary
    replaces its rounds' local rows, so long items stay quick to read."""
    record = from_body(published)
    if not record:
        return merged(item(top, key, state, events=events, timings=timings, ended_at=ended_at), {})
    rows = {name: [r for r in (read(top, name) if given is None else given) if r.get("item") == key]
            for name, given in (("events", events), ("timings", timings))}
    return merged({**rows, "state": state, "ended_at": ended_at}, record)


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
    summary = published.get("summary")
    until = when((summary or {}).get("until"))
    if summary:  # The summary stands for every row it replaced, on any machine.
        rows = {name: [r for r in found if not _settled(r, summary["round"], until)] for name, found in rows.items()}
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
    if summary:
        state = {**state, "steps": [{"step": "start", "at": summary["until"]}]}
    data = item(Path("."), "", state, events=[{**r, "item": ""} for r in rows["events"]],
                timings=[{**r, "item": ""} for r in rows["timings"]], ended_at=local.get("ended_at"),
                summary=summary)
    if summary:
        data = {**_summed(summary, data), "summary": summary}
    data.update(rows, source="pull request and local" if local.get("events") or local.get("timings")
                else "pull request", rebuilt=bool(local.get("rebuilt") or published.get("rebuilt")))
    data["ready"] = published.get("ready")
    data["legacy_text"] = published.get("legacy_text")
    data["truncated"] = bool(local.get("truncated") or published.get("truncated"))
    data["clean_reviews"] = list({r.get("id") or r.get("commit"): r for r in
                                  [*published.get("clean_reviews", []), *local.get("clean_reviews", [])]}.values())
    return data


def refresh_record(top: Path, key: str, state: dict[str, Any], body: str) -> str:
    history = how_it_went(top, key, state, body, preserve_ready=True)
    def replace(block: re.Match[str]) -> str:
        text, count = HISTORY_SECTION.subn(lambda _: history + "\n", block[0], count=1)
        return text if count else text.replace("<!-- forge:end -->", history + "\n<!-- forge:end -->", 1)
    return re.sub(r"<!-- forge:begin -->.*?<!-- forge:end -->", replace, body, count=1, flags=re.S)


def _claim(intervals: list[dict[str, Any]], fold: dict[str, Any]) -> list[dict[str, Any]]:
    """Give a folded part's working and waiting seconds to still-unknown instants in its range,
    so each instant is counted once even where parts' folded ranges overlap."""
    need = {kind: fold.get(kind, 0) for kind in ("working", "waiting")}
    low, high = when(fold["start"]), when(fold["end"])
    out = []
    for interval in intervals:
        a, b = when(interval["start"]), when(interval["end"])
        x, y = max(a, low), min(b, high)
        if interval["kind"] != "unknown" or x >= y:
            out.append(interval)
            continue
        pieces, at = [(a, x, "unknown")], x
        for kind in need:
            take = min(need[kind], (y - at).total_seconds())
            if take > 0:
                pieces.append((at, at + timedelta(seconds=take), kind))
                at, need[kind] = at + timedelta(seconds=take), need[kind] - take
        pieces += [(at, y, "unknown"), (y, b, "unknown")]
        out += [{"start": p.isoformat(), "end": q.isoformat(), "kind": kind} for p, q, kind in pieces if q > p]
    return out


def story(parts: list[dict[str, Any]], read_rounds: list[dict[str, Any]], *, unfinished: bool = True,
          started_at: str | None = None, finished_at: str | None = None) -> dict[str, Any]:
    spans = [span for part in parts for span in part.get("intervals", [])]
    # A part's folded intervals keep only their range and per-kind seconds.
    folds = [f for part in parts if isinstance(f := part.get("folded_seconds"), dict)
             and when(f.get("start")) and when(f.get("end"))]
    spans += [{"start": f["start"], "end": f["end"], "kind": "unknown"} for f in folds]
    for read in read_rounds:
        end, seconds = when(read.get("read_at")), read.get("seconds")
        if end:
            known = isinstance(seconds, (float, int)) and seconds >= 0
            spans.append({"start": (end - timedelta(seconds=seconds if known else 0)).isoformat(),
                          "end": end.isoformat(), "kind": "working" if known else "unknown"})
    points = sorted({at for span in spans for name in ("start", "end") if (at := when(span.get(name)))})
    if start := when(started_at):
        points = sorted({start, *points})
    # A done story ends when it was recorded done, which may come after its last part merged.
    end = when(repo.now()) if unfinished else when(finished_at)
    if points and end and end > points[-1]:
        points.append(end)
    intervals, totals = [], dict.fromkeys(("working", "waiting", "unknown"), 0.0)
    parsed = [(x, y, span.get("kind")) for span in spans
              if (x := when(span.get("start"))) and (y := when(span.get("end")))]
    for a, b in zip(points, points[1:]):
        kinds = {kind for x, y, kind in parsed if x <= a and y >= b}
        kind = "working" if "working" in kinds else "waiting" if "waiting" in kinds else "unknown"
        totals[kind] += (b - a).total_seconds()
        intervals.append({"start": a.isoformat(), "end": b.isoformat(), "kind": kind})
    for fold in folds:  # Unknown instants in a part's folded range take its working, then waiting.
        intervals = _claim(intervals, fold)
    totals = {kind: sum((when(i["end"]) - when(i["start"])).total_seconds() for i in intervals if i["kind"] == kind)
              for kind in totals}
    return {"intervals": intervals, "time_breakdown": totals,
            **{f"{kind}_seconds": seconds if points else None for kind, seconds in totals.items()},
            "total_seconds": sum(totals.values()) if points else None}
