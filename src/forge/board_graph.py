"""The roadmap's dependency map: which part waits for which, drawn as one inline picture."""
from __future__ import annotations

from html import escape
from textwrap import wrap

from forge.board_visuals import _svg


def dependencies(stories: list[dict]) -> str:
    parts = [part for story in stories for part in story["parts"]]
    local = {p["id"] for p in parts}
    for part in list(parts):
        for dep in part["waits_for"]:
            if dep not in local:
                parts.append({"id": dep, "title": "Unknown part", "status": "Unknown", "waits_for": []})
                local.add(dep)
    positions, lines, headings, height = {}, {}, [], 20
    groups = [(s["title"], s["parts"]) for s in stories]
    unknown = [p for p in parts if p["status"] == "Unknown"]
    if unknown:
        groups.append(("Unknown dependencies", unknown))
    for title, group in groups:
        for line in wrap(title, 30) or ["A story with no title yet"]:
            headings.append(f'<text x="0" y="{height}">{escape(line)}</text>')
            height += 18
        height += 16
        if not group:
            headings.append(f'<text class="picture-detail" x="0" y="{height}">No parts planned yet.</text>')
            height += 34
        for part in group:
            lines[part["id"]] = wrap(part["title"], 24) or ["Unknown part"]
            positions[part["id"]] = height
            height += 18 * len(lines[part["id"]]) + 42
    edges = [(p, dep) for p in parts for dep in p["waits_for"]]
    arrow = "roadmap-wait"
    drawing = [f'<defs><marker id="{escape(arrow, quote=True)}" markerWidth="6" markerHeight="6" '
               'refX="6" refY="3" orient="auto"><path class="arrow" d="M0 0L6 3L0 6Z"/></marker></defs>', *headings]
    descriptions = []
    for index, (part, dep) in enumerate(edges):
        source = next(p for p in parts if p["id"] == dep)
        label = part["title"] + " waits for " + source["title"]
        descriptions.append(label)
        gutter = 6 + 24 * index / max(1, len(edges))
        drawing.append(f'<g><title>{escape(label)}</title><path class="dependency-edge" '
                       f'd="M38 {positions[dep] + 8}H{gutter:.2f}V{positions[part["id"]] + 8}H32" '
                       f'marker-end="url(#{escape(arrow, quote=True)})"/></g>')
    for part in parts:
        y = positions[part["id"]]
        status = part["status"]
        label = part["title"] + ": " + status
        descriptions.append(label)
        shape = ('<circle cx="48" cy="8" r="10"/>' if status == "Merged" else
                 '<rect x="38" y="-2" width="20" height="20" rx="4"/>' if status == "Running" else
                 '<polygon points="38,-2 58,-2 63,8 58,18 38,18 33,8"/>' if status == "Waiting" else
                 '<path d="M48,-3L59,8L48,19L37,8Z"/>' if status == "Can start now" else
                 '<rect x="38" y="-2" width="20" height="20" stroke-dasharray="3 2"/>'
                 if status == "Not started" else '<ellipse cx="48" cy="8" rx="10" ry="7"/>')
        text = ''.join(f'<tspan x="68" dy="{0 if n == 0 else 18}">{escape(line)}</tspan>'
                       for n, line in enumerate(lines[part["id"]]))
        drawing.append(f'<g class="dependency-node" transform="translate(0 {y})">'
                       f'<title>{escape(label)}</title>{shape}<text x="68" y="12">{text}</text>'
                       f'<text class="picture-detail" x="68" y="{18 * len(lines[part["id"]]) + 14}">'
                       f'{escape(status)}</text></g>')
    if not stories:
        height = 40
        drawing.append('<text x="0" y="24">No parts planned yet.</text>')
    return ('<h3>What waits for what</h3><p class="detail">Arrows point to the part waiting.</p>'
            + _svg("Roadmap dependencies", ". ".join(descriptions), height, ''.join(drawing)))
