"""Inline, accessible pictures of the board's machine data."""
from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from string import Template
from textwrap import wrap

from forge.board_facts import IN_PROGRESS_STATES

ORDER = ("needs you", "blocked", "in progress", "planned", "no plan yet", "done")
# One line: the map's shapes, then the three words. Shapes are CSS, hidden from screen readers.
KEY = (" ".join(f'<span class="shape s-{name}" aria-hidden="true"></span>{word}' for name, word in (
    ("done", "done"), ("running", "running"), ("waiting", "waiting"), ("start", "can start"),
    ("not", "not started"), ("plan", "no plan yet"))) + " · part: a piece of a plan · fix: a small change · plan: a story's design")


def _svg(label: str, description: str, height: int, drawing: str) -> str:
    return (f'<svg class="board-picture" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{escape(label, quote=True)}" width="260" viewBox="0 0 260 {height}">'
            f'<title>{escape(label)}</title><desc>{escape(description)}</desc>{drawing}</svg>')


def duration(seconds: float | None) -> str:
    from forge.time_records import plain
    return plain(seconds)


def stage_seconds(stage: dict) -> float | None:
    seconds = stage.get("seconds")
    if stage.get("status") == "running" and stage.get("elapsed") is not None:
        seconds = (seconds or 0) + stage["elapsed"]
    return seconds


def stage_duration(stage: dict) -> str:
    return duration(stage_seconds(stage))


def timeline(item: dict) -> str:
    stages = item["stages"]
    current = {"work": "Build", "worker": "Build", "test": "Tests", "review": "Review", "ci": "CI"}.get(
        item["activity"].get("action"))
    if current is None:
        current = next((s["name"] for s in reversed(stages) if s["status"] == "running"), None)
    if current is None:
        current = {"working": "Build", "fixing": "Build", "started": "Build", "reviewing": "Review",
                   "waiting for checks": "CI", "checks failed": "CI", "ready": "Merge"}.get(item["stage"])
    largest = max((stage_seconds(s) or 0 for s in stages), default=0)
    drawing, descriptions = [], []
    for index, stage in enumerate(stages):
        name, seconds = stage["name"], stage_seconds(stage)
        shown = stage_duration(stage)
        label = name + ": " + shown + ("; current" if name == current else "")
        descriptions.append(label)
        y = index * 78
        text = wrap(shown, 32)
        drawing.append(f'<g class="stage-row" transform="translate(0 {y})"><title>{escape(label)}</title>'
                       f'<text x="0" y="18">{escape("Checks" if name == "CI" else name)}'
                       f'{" — current" if name == current else ""}</text>'
                       + ''.join(f'<text class="picture-detail" x="0" y="{36 + n * 16}">'
                                 f'{escape(line)}</text>' for n, line in enumerate(text)))
        if seconds is None:
            drawing.append('<path class="unknown-time" d="M0 62H260"/>')
        else:
            width = 260 * seconds / largest if largest else 0
            drawing.append(f'<rect class="recorded-time" x="0" y="58" width="{width:.2f}" height="6"/>')
        drawing.append('</g>')
    return ('<p class="detail">Recorded stage time in this round; unrecorded time is unknown.</p>'
            + _svg(item["title"] + " stage timeline", ". ".join(descriptions),
                   max(1, len(stages)) * 78, ''.join(drawing)))


def people(row: dict) -> str:
    said = " ".join(f"{label} {row[field]}." for field, label in (
        ("started_by", "Started by"), ("approved_by", "Approved by"), ("developer", "Assigned to"),
        ("merged_by", "Merged by")) if row.get(field))
    return f'<p class="people">{escape(said)}</p>' if said else ""


def times(row: dict) -> str:
    seconds = [row.get(f"{kind}_seconds") for kind in ("working", "waiting", "unknown")]
    if seconds == [None] * 3:
        return '<p class="times">No time recorded yet</p>'
    return '<p class="times">Working {} · waiting {} · unknown {}</p>'.format(*map(duration, seconds))


def _day(at: datetime) -> str:
    return f"{at.day} {at:%B}"


def _lanes(name: str, heading: str, rows: list[str] | None, empty: str) -> str:
    """One first-screen list: five rows, then the rest behind "and N more", opening in place."""
    if rows is None:
        body = '<p class="empty">Not worked out by this release of Forge.</p>'
    elif not rows:
        body = f'<p class="empty">{empty}</p>'
    else:
        body = "".join(rows[:5]) + (f'<details class="rest"><summary>and {len(rows) - 5} more</summary>'
                                    + "".join(rows[5:]) + "</details>" if len(rows) > 5 else "")
    return f'<div class="lanes" id="{name}"><h2>{heading}</h2>{body}<!-- end {name} --></div>'


def first_screen(view: dict, now: datetime, group) -> str:
    """Needs you, In progress, Blocked or slow and go-live on one time axis with a today line."""
    from forge.time_records import plain, when
    team = view["team"]
    found = {row["id"]: row for parent in view["items"] for row in [parent, *parent["children"]]}
    plans = {entry["id"]: entry["parts"] for entry in view["dependency_maps"]}
    going = [row for row in view["items"] if group(row) == "in progress"]
    needs = [(row, when(row.get("since"))) for row in team.get("needs_you") or []]
    stuck = [(row, now - timedelta(seconds=row["seconds"]) if row.get("seconds") is not None else None)
             for row in team.get("blocked") or []]
    first = {row["id"]: when(row["intervals"][0]["start"]) for row in going if row.get("intervals")}
    floor = now - timedelta(weeks=6)
    start = max(min([at for at in [*first.values(), *(at for _, at in needs + stuck)] if at],
                    default=now - timedelta(days=1)), floor)
    start = min(start, now - timedelta(hours=1))
    go = team.get("go_live") or {}
    soon, late = (when(go[key] + "T12:00:00+00:00") if go.get(key) else None for key in ("earliest", "latest"))
    end = max(now + (now - start) / 4, late + (late - now) / 10 if late else now)
    span = (end - start).total_seconds()

    def x(at: datetime) -> float:
        return 100 * (min(max(at, start), end) - start).total_seconds() / span

    def bar(kind: str, a: datetime, b: datetime) -> str:
        return f'<span class="{kind}" style="left:{x(a):.2f}%;width:{max(x(b) - x(a), .25):.2f}%"></span>'

    def lane(title: str, words: str, track: str, row: dict | None) -> str:
        # A story's review rounds sit on its parts, so its detail lists each part's rounds.
        rounds = [line for owner in ([row, *row.get("children", [])] if row else [])
                  for line in ((owner is not row and f"{owner['title']}: " or "") + r["line"]
                               for r in owner.get("rounds") or [])]
        more = (times(row) + "".join(f'<p class="round">{escape(line)}</p>' for line in rounds)
                + people(row)) if row else f'<p class="times">{escape(words)}</p>'
        return (f'<details class="lane"><summary><span class="name" title="{escape(title, quote=True)}">'
                f'{escape(title)}</span><span class="what">{escape(words)}</span>'
                f'<span class="track" aria-hidden="true">{track}</span></summary>'
                f'<div class="more">{more}</div></details>')

    def waiting(row: dict, since: datetime | None) -> str:
        words = (f"{row.get('reason') or 'Waiting'}, waiting {plain(row.get('waited_seconds'))}"
                 if since else f"{row.get('reason') or 'Waiting'}, waiting, since unknown")
        return lane(row["title"], words, bar("wait", since, now) if since else "", found.get(row["id"]))

    def runway(row: dict) -> str:
        spans, track = [], ""
        for span in row.get("intervals") or []:
            a, b = when(span["start"]), when(span["end"])
            if spans and spans[-1][0] == span["kind"] and spans[-1][2] == a:
                spans[-1][2] = b
            else:
                spans.append([span["kind"], a, b])
        if spans:
            track = bar("runway", spans[0][1], now) + "".join(
                bar({"working": "work", "waiting": "idle"}[kind], a, b) for kind, a, b in spans if kind != "unknown")
        words = [row["state"].capitalize()]
        if row["kind"] == "story":
            parts = plans.get(row["id"], [])
            words.append(f"{sum(p['status'] == 'Merged' for p in parts)} of {len(parts)} parts done")
        if row.get("started_by"):
            words.append(f"started by {row['started_by']}")
        if spans and spans[0][1] < floor:
            words.append(f"started {(now - spans[0][1]).days // 7} weeks ago")
        return lane(row["title"], " · ".join(words), track, row).replace(
            'class="track"', f'class="track {row["kind"]}"', 1)

    def blocked(row: dict, since: datetime | None) -> str:
        words = " · ".join(str(part) for part in (row.get("reason", "").capitalize(), row.get("detail"),
                                                   plain(row.get("seconds"))) if part)
        return lane(row["title"], words, bar("since", since, now) if since else "", found.get(row["id"]))

    labels = [("start", 0, f"{(now - start).days // 7} weeks ago" if start == floor else _day(start)),
              ("today", x(now), "Today"), ("end", 100, _day(end))]
    axis = ('<div class="axis" aria-hidden="true"><span></span><span></span><span class="track">'
            + "".join(f'<span class="{kind}" style="left:{at:.2f}%">{text}</span>' for kind, at, text in labels)
            + "</span></div>")
    status = go.get("status")
    said = {"range": f"Between {_day(soon)} and {_day(late)}" if soon and late else "",
            "about": f"About {_day(soon)}; the two pace estimates agree" if soon else "",
            "done": "Planned work is done"}.get(status, "Not enough history to estimate go-live")
    if go.get("remaining_parts"):
        said += f" · {go['remaining_parts']} parts to go"
    if (go.get("no_plan") or {}).get("count"):
        said += f" · {go['no_plan']['count']} with no plan yet, unknown"
    band = (bar("band", soon, late) if status == "range" else bar("tick", soon, soon) if status == "about" else "")
    pace = team.get("pace") or {}
    weekly = " · ".join(f"{kind}: " + ", ".join(str(week[kind]) for week in pace.get("weeks", []))
                        for kind in ("parts", "fixes")) if pace.get("weeks") else ""
    goal = (f'<div class="lanes" id="go-live"><h2>Pace and go-live</h2><div class="lane static">'
            f'<span class="name">Go-live</span><span class="what">{escape(said)}</span>'
            f'<span class="track" aria-hidden="true">{band}</span></div>'
            + (f'<p class="pace">Merged per week, last six full weeks — {weekly}</p>' if weekly else "")
            + "<!-- end go-live --></div>")
    return (f'<div class="runway-axis" style="--today:{x(now):.2f}%">' + axis
            + _lanes("needs-you", "Needs you", [waiting(*pair) for pair in needs] if team.get("needs_you") is not None
                     else None, "Nothing needs a person.")
            + _lanes("in-progress", "In progress", [runway(row) for row in going], "Nothing in progress.")
            + _lanes("blocked", "Blocked or slow", [blocked(*pair) for pair in stuck]
                     if team.get("blocked") is not None else None, "Nothing is blocked or slow.")
            + goal + "</div>")


def trends(team: dict) -> str:
    """Merged pull requests per week for the team and each person, through and around Forge, in
    the JSON's alphabetical order, beside this week's pull requests that went around Forge."""
    from forge.time_records import when
    data, around = team.get("trends"), team.get("around_forge")
    if data:
        top = max((w["through"] + w["around"] for row in [data["team"], *(p["weeks"] for p in data["people"])]
                   for w in row if w), default=0) or 1

        def cells(weeks: list) -> str:
            return "".join(
                '<td class="unknown">unknown</td>' if week is None else
                f'<td><span class="mark" aria-hidden="true"><span class="t" style="width:{100 * week["through"] / top:.1f}%">'
                f'</span><span class="a" style="width:{100 * week["around"] / top:.1f}%"></span></span>'
                f'<span class="through">{week["through"]}</span> through, <span class="around">{week["around"]}</span>'
                " around</td>" for week in weeks)
        heads = "".join(f'<th scope="col">{_day(when(day + "T00:00:00+00:00"))}</th>' for day in data["weeks"])
        table = (f'<div class="scroll" tabindex="0" role="region" aria-label="Merged pull requests per week">'
                 f'<table class="trends"><thead><tr><th scope="col">Week of</th>{heads}</tr>'
                 f'</thead><tbody><tr class="team"><th scope="row">Team</th>{cells(data["team"])}</tr>'
                 + "".join(f'<tr class="person"><th scope="row">{escape(p["name"])}</th>{cells(p["weeks"])}</tr>'
                           for p in data["people"]) + "</tbody></table></div>")
    else:
        table = '<p class="empty">GitHub couldn\'t be reached, so the weekly trends aren\'t available.</p>'
    if around is None:
        listed = '<p class="empty">Not known: GitHub couldn\'t list every pull request for the last 7 days.</p>'
    elif not around:
        listed = '<p class="empty">No pull requests merged around Forge this week.</p>'
    else:
        listed = "<ul>" + "".join(
            f'<li><a href="{escape(pr["url"] or "", quote=True)}">{escape(pr["title"] or "Untitled")}</a> '
            f'<span>{escape(pr["author"])}</span> <span>{_day(when(pr["merged_at"]))}</span></li>'
            for pr in around) + "</ul>"
    return (f'<div class="trends-grid"><div><p class="detail">Dark ink went through Forge, light ink went '
            f'around it. People are in alphabetical order.</p>{table}</div>'
            f'<div class="around"><h3>Merged around Forge in the last 7 days</h3>{listed}</div></div>')


def page(view: dict, numbers: str, github: bool, now: datetime) -> str:
    """The whole board page, from `machine_board(..., trim=False)` only."""
    from forge import board_graph
    from forge.time_records import when
    team = view["team"]
    needs = {row.get("id") for row in team.get("needs_you") or []}
    blocked = {row.get("id") for row in team.get("blocked") or []}

    def group(row: dict) -> str:
        state = row.get("state")
        return ("needs you" if row["id"] in needs else "blocked" if row["id"] in blocked else
                state if state in ("done", "no plan yet") else
                "in progress" if state in IN_PROGRESS_STATES else "planned")

    def waits(row: dict) -> str:
        """What a stalled item waits on in forge next's words, its pull request and a story's outcome."""
        url = (row.get("pr") or {}).get("url")
        return ((f'<p class="waits">{escape(row["waits_on"])}</p>' if row.get("stalled") and row.get("waits_on") else "")
                + (f'<p>Pull request: <a href="{escape(url, quote=True)}">{escape(row["title"])}</a></p>' if url else "")
                + (f'<p>The story was finished. {escape(row["outcome"])}</p>' if row.get("outcome") else ""))

    def line(row: dict, name: str) -> str:
        state = (row.get("state") or "unknown").capitalize()
        status = row.get("status") or ""
        if row.get("stalled"):
            status = (status + ". " if status else "") + f"Stalled for {duration(row.get('idle_seconds'))}"
        title = f'<span class="title">{escape(row["title"])}</span>'
        if name == "Story":  # a story's own key, small and muted: the one ID the board shows
            title = f'<span class="named">{title} <span class="key">{escape(row["id"])}</span></span>'
        return (f'<summary>{title}'
                f'<span class="kind">{name}</span><span class="state">{escape(state)}</span>'
                f'<span class="status">{escape("" if status.lower() == state.lower() else status)}</span></summary>')

    def part(row: dict) -> str:
        more = waits(row) + times(row) + people(row)
        if row.get("state") in ("in progress", "ready to merge") and row.get("stages"):
            more += timeline(row)
        return f'<li><details>{line(row, "Part")}<div class="more">{more}</div></details></li>'

    def history(row: dict) -> str:
        """Each cold-read round of the plan with its findings and their answers, the approval,
        then the merged parts."""
        words = {"cut": "Cut.", "defer": "Deferred.", "keep": "Kept.", None: "Not answered yet."}
        lines = []
        for read in row.get("read_rounds") or []:
            said = "".join("<li>" + escape(f"{f['title']} " + (
                f"Kept: {f['reason'].rstrip('.')}." if f["disposition"] == "keep" and f["reason"]
                else words[f["disposition"]])) + "</li>" for f in read["findings"])
            on = f' on {_day(when(read["read_at"]))}' if when(read.get("read_at")) else ""
            lines.append(f'<li class="step">Cold read round {read["round"]}{on}: '
                         + (f"<ul>{said}</ul>" if said else "No findings.") + "</li>")
        if row.get("approved_by"):
            lines.append(f'<li class="step">Plan approved by {escape(row["approved_by"])}.</li>')
        for child in row["children"]:
            if child.get("state") == "done":
                on = f' on {_day(when(child["merged_at"]))}' if when(child.get("merged_at")) else ""
                lines.append(f'<li class="step">{escape(child["title"])} merged{on}.</li>')
        return f'<ol class="history">{"".join(lines)}</ol>' if lines else ""

    def entry(row: dict) -> str:
        parts = "".join(part(child) for child in row["children"])
        more = (waits(row) + times(row) + people(row) + (history(row) if row["kind"] == "story" else "")
                + (f'<ul class="parts">{parts}</ul>' if parts else ""))
        if row["kind"] == "fix" and row.get("state") in ("in progress", "ready to merge") and row.get("stages"):
            more += timeline(row)
        name = "Story" if row["kind"] == "story" else "Fix"
        return (f'<div class="row" data-group="{group(row)}"><details>{line(row, name)}'
                f'<div class="more">{more}</div></details></div>')

    def section(kind: str) -> tuple[str, str]:
        """One kind's rows sorted by state with no group headings, done ones in one closed fold,
        and the section's fold: open unless it holds more than 20 rows."""
        rows = sorted((row for row in view["items"] if row["kind"] == kind), key=lambda row: ORDER.index(group(row)))
        done = [row for row in rows if group(row) == "done"]
        shown = "".join(entry(row) for row in rows if group(row) != "done") + (
            f'<details class="done"><summary>Done ({len(done)})</summary>'
            + "".join(entry(row) for row in done) + "</details>" if done else "")
        empty = {"story": "No story yet. Start one with forge story new.",
                 "fix": "No fix yet. Start one with forge fix start."}[kind]
        return shown or f'<p class="empty">{empty}</p>', "" if len(rows) > 20 else " open"
    labels = {"finished_last_7_days": "Finished in the last 7 days"}
    totals = " ".join(f'<span><b>{labels.get(kind, kind.capitalize())}</b> — ' + escape("; ".join(
        f"{name.capitalize()}: {count}" for name, count in counts.items())) + "</span>"
        for kind, counts in team["counts"].items())
    (stories, stories_open), (fixes, fixes_open) = section("story"), section("fix")
    return Template((Path(__file__).parent / "board.html").read_text(encoding="utf-8")).substitute(
        updated=f"{now.day} {now:%B %Y} at {now:%H:%M} UTC",
        sentence=f'<p class="sentence">{escape(team["sentence"])}</p>' if team.get("sentence") else "",
        totals=totals,
        lanes=first_screen(view, now, group),
        trends=trends(team),
        note="" if github else ('<p class="note">GitHub couldn\'t be reached, so the list of finished '
                                "work isn't available. This page shows the saved dates only.</p>"),
        graph=board_graph.dependencies(view["dependency_maps"]),
        key=KEY,
        stories=stories, stories_open=stories_open, fixes=fixes, fixes_open=fixes_open,
        numbers=escape(numbers))
