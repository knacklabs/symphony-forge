"""Inline, accessible pictures of the board's machine data."""
from __future__ import annotations

from html import escape
from textwrap import wrap


def _svg(label: str, description: str, height: int, drawing: str) -> str:
    return (f'<svg class="board-picture" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{escape(label, quote=True)}" viewBox="0 0 260 {height}">'
            f'<title>{escape(label)}</title><desc>{escape(description)}</desc>{drawing}</svg>')


def dependencies(story: dict, all_parts: dict) -> str:
    parts = list(story["parts"])
    local = {p["id"] for p in parts}
    for part in story["parts"]:
        for dep in part["waits_for"]:
            if dep not in local:
                source = all_parts.get(dep)
                parts.append({**source, "title": source["title"] + " (other story)"} if source else
                             {"id": dep, "title": "Unknown part", "status": "Unknown", "waits_for": []})
                local.add(dep)
    positions, lines, height = {}, {}, 16
    for part in parts:
        lines[part["id"]] = wrap(part["title"], 24) or ["Unknown part"]
        positions[part["id"]] = height
        height += 18 * len(lines[part["id"]]) + 42
    edges = [(p, dep) for p in story["parts"] for dep in p["waits_for"]]
    arrow = "wait-" + story["id"]
    drawing = [f'<defs><marker id="{escape(arrow, quote=True)}" markerWidth="6" markerHeight="6" '
               'refX="5" refY="3" orient="auto"><path class="arrow" d="M0 0L6 3L0 6Z"/></marker></defs>']
    descriptions = []
    for index, (part, dep) in enumerate(edges):
        source = next(p for p in parts if p["id"] == dep)
        label = part["title"] + " waits for " + source["title"]
        descriptions.append(label)
        gutter = 6 + 24 * index / max(1, len(edges))
        drawing.append(f'<g><title>{escape(label)}</title><path class="dependency-edge" '
                       f'd="M38 {positions[dep] + 8}H{gutter}V{positions[part["id"]] + 8}H38" '
                       f'marker-end="url(#{escape(arrow, quote=True)})"/></g>')
    for part in parts:
        y = positions[part["id"]]
        status = part["status"]
        label = part["title"] + ": " + status
        descriptions.append(label)
        shape = ('<circle cx="48" cy="8" r="10"/>' if status == "Merged" else
                 '<rect x="38" y="-2" width="20" height="20" rx="4"/>' if status == "Running" else
                 '<polygon points="38,-2 58,-2 63,8 58,18 38,18 33,8"/>' if status == "Waiting" else
                 '<rect x="38" y="-2" width="20" height="20" stroke-dasharray="3 2"/>'
                 if status == "Not started" else '<ellipse cx="48" cy="8" rx="10" ry="7"/>')
        text = ''.join(f'<tspan x="68" dy="{0 if n == 0 else 18}">{escape(line)}</tspan>'
                       for n, line in enumerate(lines[part["id"]]))
        drawing.append(f'<g class="dependency-node" transform="translate(0 {y})">'
                       f'<title>{escape(label)}</title>{shape}<text x="68" y="12">{text}</text>'
                       f'<text class="picture-detail" x="68" y="{18 * len(lines[part["id"]]) + 14}">'
                       f'{escape(status)}</text></g>')
    if not parts:
        height = 40
        drawing.append('<text x="0" y="24">No parts planned yet.</text>')
    return ('<h4>What waits for what</h4><p class="detail">Arrows point to the part waiting.</p>'
            + _svg(story["title"] + " dependencies", ". ".join(descriptions), height, ''.join(drawing)))


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    values = [(hours, "hour"), (minutes, "minute"), (seconds, "second")]
    return " ".join(f'{value:g} {unit}{"" if value == 1 else "s"}'
                    for value, unit in values if value) or "0 seconds"


def timeline(item: dict) -> str:
    stages = item["stages"]
    current = {"work": "Build", "worker": "Build", "test": "Tests", "review": "Review", "ci": "CI"}.get(
        item["activity"].get("action"))
    if current is None:
        current = next((s["name"] for s in reversed(stages) if s["status"] == "running"), None)
    if current is None:
        current = {"working": "Build", "fixing": "Build", "started": "Build", "reviewing": "Review",
                   "waiting for checks": "CI", "checks failed": "CI", "ready": "Merge"}.get(item["stage"])
    largest = max((s["seconds"] or 0 for s in stages), default=0)
    drawing, descriptions = [], []
    for index, stage in enumerate(stages):
        name, seconds = stage["name"], stage["seconds"]
        duration = _duration(seconds)
        label = name + ": " + duration + ("; current" if name == current else "")
        descriptions.append(label)
        y = index * 78
        text = wrap(duration, 32)
        drawing.append(f'<g class="stage-row" transform="translate(0 {y})"><title>{escape(label)}</title>'
                       f'<text x="0" y="18">{escape("Checks" if name == "CI" else name)}'
                       f'{" — current" if name == current else ""}</text>'
                       + ''.join(f'<text class="picture-detail" x="0" y="{36 + n * 16}">'
                                 f'{escape(line)}</text>' for n, line in enumerate(text)))
        if seconds is None:
            drawing.append('<path class="unknown-time" d="M0 62H260"/>')
        else:
            width = 260 * seconds / largest if largest else 0
            drawing.append(f'<rect class="recorded-time" x="0" y="58" width="{width}" height="6"/>')
        drawing.append('</g>')
    return ('<p class="detail">Recorded stage time in this round; unrecorded time is unknown.</p>'
            + _svg(item["title"] + " stage timeline", ". ".join(descriptions),
                   max(1, len(stages)) * 78, ''.join(drawing)))
