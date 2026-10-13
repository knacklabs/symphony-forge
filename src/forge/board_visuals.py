"""Inline, accessible pictures of the board's machine data."""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from string import Template
from textwrap import wrap

ORDER = ("needs you", "blocked", "in progress", "planned", "no plan yet", "done")
# One line: the map's shapes, then the three words. Shapes are CSS, hidden from screen readers.
KEY = (" ".join(f'<span class="shape s-{name}" aria-hidden="true"></span>{word}' for name, word in (
    ("done", "done"), ("running", "running"), ("waiting", "waiting"), ("start", "can start"),
    ("not", "not started"))) + " · part: a piece of a plan · fix: a small change · plan: a story's design")


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


def page(view: dict, numbers: str, github: bool, now: datetime) -> str:
    """The whole board page, from `machine_board(..., trim=False)` only."""
    from forge import board_graph
    team = view["team"]
    needs = {row.get("id") for row in team.get("needs_you") or []}
    blocked = {row.get("id") for row in team.get("blocked") or []}

    def group(row: dict) -> str:
        state = row.get("state")
        return ("needs you" if row["id"] in needs else "blocked" if row["id"] in blocked else
                state if state in ("done", "no plan yet") else
                "in progress" if state in ("building", "in progress", "ready to merge") else "planned")

    def people(row: dict) -> str:
        said = " ".join(f"{label} {row[field]}." for field, label in (
            ("started_by", "Started by"), ("approved_by", "Approved by"), ("developer", "Assigned to"),
            ("merged_by", "Merged by")) if row.get(field))
        return f'<p class="people">{escape(said)}</p>' if said else ""

    def waits(row: dict) -> str:
        """What a stalled item waits on in forge next's words, its pull request and a story's outcome."""
        url = (row.get("pr") or {}).get("url")
        return ((f'<p class="waits">{escape(row["waits_on"])}</p>' if row.get("stalled") and row.get("waits_on") else "")
                + (f'<p>Pull request: <a href="{escape(url, quote=True)}">{escape(row["title"])}</a></p>' if url else "")
                + (f'<p>The story was finished. {escape(row["outcome"])}</p>' if row.get("outcome") else ""))

    def times(row: dict) -> str:
        seconds = [row.get(f"{kind}_seconds") for kind in ("working", "waiting", "unknown")]
        if seconds == [None] * 3:
            return '<p class="times">No time recorded yet</p>'
        return '<p class="times">Working {} · waiting {} · unknown {}</p>'.format(*map(duration, seconds))

    def line(row: dict, name: str) -> str:
        state = (row.get("state") or "unknown").capitalize()
        status = row.get("status") or ""
        if row.get("stalled"):
            status = (status + ". " if status else "") + f"Stalled for {duration(row.get('idle_seconds'))}"
        return (f'<summary><span class="title">{escape(row["title"])}</span>'
                f'<span class="kind">{name}</span><span class="state">{escape(state)}</span>'
                f'<span class="status">{escape("" if status.lower() == state.lower() else status)}</span></summary>')

    def part(row: dict) -> str:
        more = waits(row) + times(row) + people(row)
        if row.get("state") in ("in progress", "ready to merge") and row.get("stages"):
            more += timeline(row)
        return f'<li><details>{line(row, "Part")}<div class="more">{more}</div></details></li>'

    def entry(row: dict) -> str:
        parts = "".join(part(child) for child in row["children"])
        more = waits(row) + times(row) + people(row) + (f'<ul class="parts">{parts}</ul>' if parts else "")
        if row["kind"] == "fix" and row.get("state") in ("in progress", "ready to merge") and row.get("stages"):
            more += timeline(row)
        name = "Story" if row["kind"] == "story" else "Fix"
        return (f'<div class="row" data-group="{group(row)}"><details>{line(row, name)}'
                f'<div class="more">{more}</div></details></div>')

    rows = sorted(view["items"], key=lambda row: ORDER.index(group(row)))
    shown, done = [], [row for row in rows if group(row) == "done"]
    for name in ORDER[:-1]:
        mine = [entry(row) for row in rows if group(row) == name]
        if mine:
            shown.append(f'<h3>{name.capitalize()}</h3>' + "".join(mine))
    if done:
        shown.append(f'<details class="done"><summary>Done ({len(done)})</summary>'
                     + "".join(entry(row) for row in done) + "</details>")
    labels = {"finished_last_7_days": "Finished in the last 7 days"}
    totals = " · ".join(labels.get(kind, kind.capitalize()) + " — " + "; ".join(
        f"{name.capitalize()}: {count}" for name, count in counts.items())
        for kind, counts in team["counts"].items())
    return Template((Path(__file__).parent / "board.html").read_text(encoding="utf-8")).substitute(
        updated=f"{now.day} {now:%B %Y} at {now:%H:%M} UTC",
        sentence=f'<p class="sentence">{escape(team["sentence"])}</p>' if team.get("sentence") else "",
        totals=escape(totals),
        note="" if github else ('<p class="note">GitHub couldn\'t be reached, so the list of finished '
                                "work isn't available. This page shows the saved dates only.</p>"),
        graph=board_graph.dependencies(view["dependency_maps"]),
        key=KEY,
        rows="".join(shown) or '<p class="empty">No story or fix yet. Start one with forge story new or forge fix start.</p>',
        numbers=escape(numbers))
