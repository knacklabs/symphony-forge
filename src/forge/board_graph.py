"""The roadmap's dependency order: every story's unfinished parts in columns by when they can start,
for `dependency_maps` in the board's facts."""
from __future__ import annotations


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
