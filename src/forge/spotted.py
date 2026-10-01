"""The spotted list: problems workers and reviews noticed outside the change in hand.

One tracked file, plans/spotted.json, written only in close's review commits and merged by git
with the roadmap's rule. Workers report with `Spotted:` lines in their commit messages; reviews
report through their advice and blocking findings.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from forge import repo

PATH = "plans/spotted.json"
KINDS = ("bug", "simplify", "edge", "improve")
SOURCES = ("worker", "review", "blocking")
STATUSES = ("open", "done")
FIELDS = ("key", "kind", "path", "line", "text", "from", "item", "status", "closed_by")
LINE = re.compile(r"Spotted: (bug|simplify|edge|improve) (\S+):([0-9]+) (\S.*)")
FIX = re.compile(r"[a-z0-9][a-z0-9-]*")  # a fix name, "dismissed" included
SAFE = re.compile(r"[A-Za-z0-9._/-]+")  # a recorded path never needs quoting
REFUSALS = {
    "bad": ("plans/spotted.json isn't a list Forge can read: {problem}.",
            "{repair}, commit it, then forge close {item}"),
}


class Unreadable(Exception):
    """The list isn't one Forge wrote; its message says why."""


def key(kind: str, path: str, text: str, source: str, item: str) -> str:
    """One entry per kind, file and text; a serious finding counts once per change."""
    return "\t".join([kind, path, text] + ([item] if source == "blocking" else []))


def _parse(text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text)
    except ValueError:
        raise Unreadable("it isn't JSON") from None
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise Unreadable('it has no "items" list')
    for n, entry in enumerate(items, 1):
        if not isinstance(entry, dict) or sorted(entry) != sorted(FIELDS):
            raise Unreadable(f"entry {n} doesn't have exactly the fields {', '.join(FIELDS)}")
        strings = all(isinstance(entry[name], str) for name in FIELDS if name not in ("line", "closed_by"))
        line, closed = entry["line"], entry["closed_by"]
        if not (strings and isinstance(line, int) and not isinstance(line, bool)
                and entry["kind"] in KINDS and entry["from"] in SOURCES
                and entry["status"] in STATUSES
                and (closed is None or (isinstance(closed, str) and bool(FIX.fullmatch(closed))))
                and entry["key"] == key(entry["kind"], entry["path"], entry["text"],
                                        entry["from"], entry["item"])):
            raise Unreadable(f"entry {n} has a field of the wrong type or value")
    return items


def read(top: Path) -> list[dict[str, Any]]:
    """The checkout's list; no file is an empty one. Anything else is Unreadable."""
    path = top / PATH
    return _parse(path.read_text(encoding="utf-8")) if path.is_file() else []


def write(top: Path, items: list[dict[str, Any]]) -> None:
    data = {"items": sorted(items, key=lambda entry: entry["key"])}
    path = top / PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, indent=2) + "\n").encode("utf-8"))


def check(top: Path, item: str) -> None:
    """Refuse an unreadable list, naming the newest readable copy in the branch's history."""
    try:
        read(top)
    except Unreadable as problem:
        repair = f"git -C {top} rm -q {PATH}"
        for commit in repo.git("log", "--format=%H", "HEAD", "--", PATH, cwd=top).split():
            shown = repo.run("git", "show", f"{commit}:{PATH}", cwd=top)
            try:
                if shown.returncode == 0:
                    _parse(shown.stdout)
                    repair = f"git -C {top} checkout {commit} -- {PATH}"
                    break
            except Unreadable:
                continue
        repo.refuse(REFUSALS["bad"], problem=problem, repair=repair, item=item)


def record(top: Path, item: str, state: dict[str, Any], base: str,
           result: dict[str, Any]) -> bool:
    """Add what the worker's commits and this review spotted; True when the file changed."""
    from forge import review  # review imports spotted

    items = read(top)
    known = {entry["key"]: entry for entry in items}
    tree = set(repo.git("ls-tree", "-r", "-z", "--name-only", "--full-tree", "HEAD",
                        cwd=top).split("\0"))
    changed = False

    def add(kind: str, path: str, line: Any, text: str, source: str) -> None:
        nonlocal changed
        text = " ".join(text.split())
        entry_key = key(kind, path, text, source, item)
        if (path not in tree or not SAFE.fullmatch(path) or entry_key in known
                or not isinstance(line, int) or isinstance(line, bool)):
            return
        known[entry_key] = {"key": entry_key, "kind": kind, "path": path, "line": line,
                            "text": text, "from": source, "item": item, "status": "open",
                            "closed_by": None}
        items.append(known[entry_key])
        changed = True

    messages = repo.git("log", "--no-merges", "--reverse", "--format=%B%x00", f"{base}..HEAD",
                        cwd=top)
    for message in messages.split("\0"):
        for raw in message.split("\n"):
            if found := LINE.fullmatch(raw.rstrip()):
                path = found[2].replace("\\", "/").removeprefix("./")
                add(found[1], path, int(found[3]), found[4], "worker")
    for finding in result.get("findings", []):
        title = finding["title"]
        if finding["priority"] in ("P2", "P3") and not title.startswith("Later:"):
            kind = ("simplify" if title.startswith("Simpler")
                    else "edge" if finding["priority"] == "P2" else "improve")
            add(kind, finding["file"], finding["line"], title, "review")
    for _, finding in review.blocking(result):
        add("simplify" if finding["title"].startswith("Simpler") else "bug", finding["file"],
            finding["line"], finding["title"], "blocking")
    for dismissal in result.get("dismissals", []):  # close checked each finding number
        finding = result["findings"][dismissal["finding"] - 1]
        title = " ".join(finding["title"].split())
        kind = "simplify" if title.startswith("Simpler") else "bug"
        entry = known.get(key(kind, finding["file"], title, "blocking", item))
        if entry and entry["status"] == "open":
            entry.update(status="done", closed_by="dismissed")
            changed = True
    if changed:
        write(top, items)
    return changed
