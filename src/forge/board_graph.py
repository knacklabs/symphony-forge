"""The roadmap's dependency graph: every story's unfinished parts in columns by when they can start,
with arrows for what waits on what, drawn as one inline picture at its own size."""
from __future__ import annotations

from html import escape
from textwrap import shorten, wrap

WIDTH, GUTTER, LANE, BAND, LINE = 1350, 300, 28, 28, 20  # px; WIDTH fills a 1440-wide window's slot
SHAPES = {"Running": '<rect class="ink" width="16" height="16"/>',
          "Waiting": '<polygon points="4,0 12,0 16,8 12,16 4,16 0,8"/>',
          "Can start now": '<path d="M8,0L16,8L8,16L0,8Z"/>',
          "Not started": '<rect width="16" height="16" stroke-dasharray="3 2"/>'}


def place(maps: list[dict]) -> None:
    """Give each unfinished part its `column` and each entry its `done` count, over all maps at once."""
    # ponytail: longest-path columns over one graph; a smarter layout only if rows get crowded.
    parts = {p["id"]: p for m in maps for p in m["parts"]}
    live = {i: p for i, p in parts.items() if p.get("status") != "Merged"}
    waits = {i: [d for d in p["waits_for"] if d in live] for i, p in live.items()}

    def reach(start: str) -> set[str]:
        seen, todo = set(), list(waits[start])
        while todo:
            if (n := todo.pop()) not in seen:
                seen.add(n)
                todo.extend(waits[n])
        return seen

    reaches = {i: reach(i) for i in live}
    loop = {i: frozenset({i, *(j for j in reaches[i] if i in reaches[j])}) for i in live}
    columns: dict[frozenset, int] = {}

    def column(group: frozenset) -> int:
        if group not in columns:
            outside = {d for i in group for d in waits[i]} - group
            columns[group] = 1 + max(column(loop[d]) for d in outside) if outside else 0
        return columns[group]

    for m in maps:
        m["done"] = sum(p.get("status") == "Merged" for p in m["parts"])
    for i, p in parts.items():
        p["column"] = column(loop[i]) if i in live else None
        if i in live and len(loop[i]) > 1:
            p["note"] = "waits on each other"
        elif i in live and any(d not in parts for d in p["waits_for"]):
            p["note"] = "waits on a part no plan names"


def _lines(text: str, chars: int, most: int = 3) -> list[str]:
    lines = wrap(text, chars) or [""]
    if len(lines) > most:
        lines = lines[:most - 1] + [shorten(" ".join(lines[most - 1:]), chars, placeholder="…")]
    return lines


def _text(x: float, y: float, lines: list[str], cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    return "".join(f'<text{attr} x="{x:g}" y="{y + n * LINE:g}">{escape(line)}</text>'
                   for n, line in enumerate(lines))


def _rule(y: float, total: int) -> str:
    return f'<line class="row-rule" x1="0" x2="{total}" y1="{y:g}" y2="{y:g}"/>'


def dependencies(maps: list[dict]) -> str:
    fixes = [m for m in maps if m.get("kind") == "fixes" and m["parts"]]
    planned = [m for m in maps if m.get("kind") != "fixes" and m.get("planned", True)]
    unplanned = [m for m in maps if m.get("kind") != "fixes" and not m.get("planned", True)]
    finished = [m for m in planned if m.get("done") and all(p.get("column") is None for p in m["parts"])]
    planned = [m for m in planned if m not in finished]
    count = 1 + max([p["column"] for m in fixes + planned for p in m["parts"]
                     if p.get("column") is not None] or [0])
    # The layout, not a stretch, fills the width: columns share what the story titles leave.
    cell = max(250, (WIDTH - GUTTER) // count)
    total, chars = GUTTER + cell * count, int((cell - LANE - 36) / 7.8)
    titles = {p["id"]: p["title"] for m in maps for p in m["parts"]}
    drawing, nodes, bands, said, y = [], {}, {}, [], 8
    for m in fixes + planned:
        if y > 8:
            drawing.append(_rule(y - BAND / 2, total))
        heading = _lines(m["title"], 32, 2)
        drawing.append(_text(0, y + 13, heading, "row-title"))
        under = y + 13 + LINE * len(heading)
        if m.get("done"):
            said.append(f'{m["title"]}: {m["done"]} finished')
            drawing.append(f'<circle class="done" cx="6" cy="{under - 5}" r="5"/>'
                           + _text(18, under, [f'{m["done"]} done'], "picture-detail"))
            under += LINE
        live = [p for p in m["parts"] if p.get("column") is not None]
        if not live and not m.get("done"):
            drawing.append(_text(0, under, ["No parts planned yet."], "picture-detail"))
            under += LINE
        bands[m["id"]] = y - BAND / 2
        heights: dict[int, int] = {}
        for p in live:
            x, top = GUTTER + p["column"] * cell + LANE, y + heights.get(p["column"], 0)
            status = ("Running" if p.get("running") else "Waiting") if m.get("kind") == "fixes" else p["status"]
            extra = [f'started on {titles.get(p["started_on"], "a part with no name yet")}'] if p.get("started_on") else []
            extra += [p["note"]] if p.get("note") else []
            name, more = _lines(p["title"], chars), _lines(" · ".join([status.lower(), *extra]), chars + 4, 2)
            if m.get("kind") == "fixes":  # alone in their row, fixes take one line each
                name, more = _lines(" · ".join([p["title"], status.lower(), *extra]), 120, 2), []
            label = f'{p["title"]}: {status}' + (f' ({"; ".join(extra)})' if extra else "")
            said.append(label)
            nodes[p["id"]] = (x, top, m["id"])
            drawing.append(f'<g class="dependency-node" transform="translate({x} {top})">'
                           f'<title>{escape(label)}</title>{SHAPES.get(status, SHAPES["Not started"])}'
                           f'{_text(24, 13, name)}{_text(24, 13 + LINE * len(name), more, "picture-detail")}</g>')
            heights[p["column"]] = heights.get(p["column"], 0) + LINE * (len(name) + len(more)) + 16
        y = max(under, y + max(heights.values(), default=0)) + BAND
    edges = [(dep, p) for m in planned for p in m["parts"] for dep in p["waits_for"]
             if dep in nodes and p["id"] in nodes]
    for n, (dep, p) in enumerate(edges):
        (sx, sy, _), (tx, ty, row) = nodes[dep], nodes[p["id"]]
        lane, band = 6 + 4 * (n % 5), bands[row] + 4 * (n % 4) - 6
        label = f'{p["title"]} waits for {titles[dep]}'
        said.append(label)
        drawing.append(f'<g><title>{escape(label)}</title><path class="dependency-edge" '
                       f'marker-end="url(#roadmap-wait)" d="M{sx - 2} {sy + 8}H{sx - LANE + lane}'
                       f'V{band:g}H{tx - LANE + lane}V{ty + 8}H{tx - 3}"/></g>')
    for heading, group in (("Finished", finished), ("No plan yet", unplanned)):
        if not group:
            continue
        if y > 8:
            drawing.append(_rule(y - BAND / 2, total))
        drawing.append(_text(0, y + 13, [heading], "row-title"))
        y += 13 + LINE
        across = max(1, (total + 12) // 222)
        for n, m in enumerate(group):
            x, top = n % across * 222, y + n // across * (rows := 82 if group is finished else 62)
            what = f'{m["done"]} done' if group is finished else "No plan yet"
            said.append(f'{what}: {m["title"]}')
            drawing.append(f'<g class="{"finished" if group is finished else "no-plan"}" transform="translate({x} {top})">'
                           f'<title>{escape(what)}: {escape(m["title"])}</title><rect width="210" height="{rows - 10}"/>'
                           + (_text(10, 21, _lines(m["title"], 25, 2)) + _text(10, 61, [what], "picture-detail")
                              if group is finished else _text(10, 21, _lines(m["title"], 25, 2))) + '</g>')
        y += (len(group) + across - 1) // across * (82 if group is finished else 62) + BAND
    if not drawing:
        drawing.append(_text(0, 21, ["Nothing on the roadmap yet. Add a story with forge story new."]))
        y += 30 + BAND
    height = int(y - BAND + 12)
    svg = (f'<svg class="board-picture graph-picture" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="Roadmap dependencies" width="{total}" height="{height}" viewBox="0 0 {total} {height}">'
           f'<title>Roadmap dependencies</title><desc>{escape("; ".join(said))}</desc>'
           '<defs><marker id="roadmap-wait" markerWidth="6" markerHeight="6" refX="6" refY="3" orient="auto">'
           f'<path class="arrow" d="M0 0L6 3L0 6Z"/></marker></defs>{"".join(drawing)}</svg>')
    return ('<h3>What waits for what</h3><p class="detail">Parts in one column can run at the same time. '
            'Arrows point to the part that waits.</p><div class="graph-scroll" tabindex="0" role="region" '
            f'aria-label="Dependency graph; scrolls sideways on a narrow screen">{svg}</div>')
