"""The spotted list: problems workers and reviews noticed outside the change in hand.

One file per change, written only in close's review commits. The old list stays readable.
Workers report with `Spotted:` lines in their commit messages; reviews report through their
advice and blocking findings.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from forge import repo

PATH = "plans/spotted.json"
DIRECTORY = "plans/spotted"
KINDS = ("bug", "simplify", "edge", "improve")
SOURCES = ("worker", "review", "blocking")
STATUSES = ("open", "done")
FIELDS = ("key", "kind", "path", "line", "text", "from", "item", "status", "closed_by")
LINE = re.compile(r"Spotted: (bug|simplify|edge|improve) (\S+):([0-9]+) (\S.*)")
FIX = re.compile(r"[a-z0-9][a-z0-9-]*")  # a fix name, "dismissed" included
SAFE = re.compile(r"[A-Za-z0-9._/-]+")  # a recorded path never needs quoting
REFUSALS = {
    "bad": ("{path} isn't a list Forge can read: {problem}.",
            "{repair}, commit it, then forge close {item}"),
    "link": ("{path} or plans/ is a link, so Forge won't write the list through it.",
             "replace the link with a real file or folder, commit it, then forge close {item}"),
}


class Unreadable(Exception):
    """The list isn't one Forge wrote; its message says why."""
    path = PATH


def own_path(item: str) -> str:
    return f"{DIRECTORY}/{item.replace('/', '.')}.json"


def key(kind: str, path: str, text: str, source: str, item: str) -> str:
    """One entry per kind, file and text; a serious finding counts once per change."""
    return "\t".join([kind, path, text] + ([item] if source == "blocking" else []))


def _path(path: str) -> bool:
    """A repo-relative, forward-slash path that never needs quoting."""
    return bool(SAFE.fullmatch(path)) and not path.startswith("/") and ".." not in path.split("/")


def _parse(raw: bytes) -> list[dict[str, Any]]:
    """The list's entries, when the file is exactly what Forge writes; anything else is Unreadable."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:  # UnicodeDecodeError included
        raise Unreadable("it isn't UTF-8 JSON") from None
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise Unreadable('it has no "items" list')
    for n, entry in enumerate(items, 1):
        if not isinstance(entry, dict) or sorted(entry) != sorted(FIELDS):
            raise Unreadable(f"entry {n} doesn't have exactly the fields {', '.join(FIELDS)}")
        if not (all(isinstance(entry[name], str) for name in FIELDS if name not in ("line", "closed_by"))
                and type(entry["line"]) is int
                and (entry["closed_by"] is None or isinstance(entry["closed_by"], str))):
            raise Unreadable(f"entry {n} has a field of the wrong type")
        item = repo.ITEM.fullmatch(entry["item"])
        wrong = [name for name, right in (
            ("kind", entry["kind"] in KINDS),
            ("path", _path(entry["path"])),
            ("text", entry["text"] != "" and entry["text"] == " ".join(entry["text"].split())),
            ("from", entry["from"] in SOURCES),
            ("item", bool(item and (item["task"] or item["fix"]))),
            ("status", entry["status"] in STATUSES),
            ("closed_by", entry["closed_by"] is None or bool(FIX.fullmatch(entry["closed_by"]))),
            ("key", entry["key"] == key(entry["kind"], entry["path"], entry["text"],
                                        entry["from"], entry["item"]))) if not right]
        if wrong:
            raise Unreadable(f"entry {n} has a wrong {wrong[0]}")
    return items


def read(top: Path, ref: str | None = None) -> list[dict[str, Any]]:
    """Join the old list and flat per-change records; a done copy wins, then its file path."""
    if ref is not None:
        paths = repo.git("ls-tree", "-r", "--name-only", "-z", ref, "--", DIRECTORY + "/",
                         cwd=top).split("\0")
        paths = [path for path in paths if Path(path).parent.as_posix() == DIRECTORY
                 and path.endswith(".json")]
        old = subprocess.run(["git", "show", f"{ref}:{PATH}"], cwd=top, capture_output=True)
        if old.returncode == 0:
            paths.append(PATH)
    else:
        paths = [path.relative_to(top).as_posix() for path in (top / DIRECTORY).glob("*.json")]
        if (top / PATH).exists():
            paths.append(PATH)
    entries: dict[str, dict[str, Any]] = {}
    for path in sorted(paths):
        try:
            if ref is None:
                raw = (top / path).read_bytes()
            else:
                shown = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=top, capture_output=True)
                if shown.returncode:
                    raise Unreadable("it cannot be read")
                raw = shown.stdout
            items = _parse(raw)
        except (Unreadable, OSError) as error:
            problem = error if isinstance(error, Unreadable) else Unreadable("it cannot be read")
            problem.path = path
            raise problem from None
        for entry in items:
            previous = entries.get(entry["key"])
            if previous is None or previous["status"] != "done" and entry["status"] == "done":
                entries[entry["key"]] = entry
    return sorted(entries.values(), key=lambda entry: entry["key"])


def hotspots(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Files with repeated open advice or the same serious finding across changes."""
    paths: dict[str, list[dict[str, Any]]] = {}
    for entry in sorted(items, key=lambda entry: entry["key"]):
        if entry["status"] == "open":
            paths.setdefault(entry["path"], []).append(entry)
    found = []
    for path, entries in sorted(paths.items()):
        count = sum(entry["from"] in ("worker", "review") for entry in entries)
        blocking = max((len({entry["item"] for entry in entries
                             if entry["from"] == "blocking" and entry["kind"] == kind})
                        for kind in KINDS), default=0)
        if count >= 3 or blocking >= 2:
            found.append({"path": path, "reason": "open" if count >= 3 else "blocking",
                          "count": count if count >= 3 else blocking,
                          "texts": [entry["text"] for entry in entries]})
    return found


def fix_text(path: str, texts: list[str]) -> tuple[str, str]:
    """Plain fix text safe inside double quotes in POSIX, PowerShell and cmd."""
    cleaned = [" ".join(re.sub(r"[^A-Za-z0-9 .,:;/_-]", " ", text).split())
               for text in texts[:5]]
    done = f"{path} is simpler and none of these happen any more: " + "; ".join(cleaned)
    if len(texts) > 5:
        done += f"; and {len(texts) - 5} more"
    return f"Simplify {path}: problems keep turning up there", done


def names(done_when: str, path: str) -> bool:
    """A named file, without matching part of a longer path."""
    return re.search(r"(?<![A-Za-z0-9_./-])" + re.escape(path) + r"(?![A-Za-z0-9_./-])",
                     done_when) is not None


def write(top: Path, item: str, items: list[dict[str, Any]]) -> None:
    data = {"items": sorted(items, key=lambda entry: entry["key"])}
    path = top / own_path(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(data, indent=2) + "\n").encode("utf-8"))


def check(top: Path, item: str) -> None:
    """Refuse a linked list, which a write would follow out of the checkout, and an unreadable
    one, naming the newest readable copy in the branch's history."""
    for path in (PATH, DIRECTORY, own_path(item)):
        if (top / "plans").is_symlink() or (top / path).is_symlink():
            repo.refuse(REFUSALS["link"], path=path, item=item)
    try:
        read(top)
    except Unreadable as problem:
        path = problem.path
        if not _path(path):
            # A contributor's filename must not become shell code or another output line.
            repo.refuse(REFUSALS["bad"], path=json.dumps(path), problem=problem,
                        repair="remove or restore this file with your file manager", item=item)
        repair = f"git -C {top} rm -q {path}"
        for commit in repo.git("log", "--format=%H", "HEAD", "--", path, cwd=top).split():
            # Bytes, so a copy that isn't UTF-8 stays unreadable.
            shown = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=top, capture_output=True)
            try:
                if shown.returncode == 0:
                    _parse(shown.stdout)
                    repair = f"git -C {top} checkout {commit} -- {path}"
                    break
            except Unreadable:
                continue
        repo.refuse(REFUSALS["bad"], path=path, problem=problem, repair=repair, item=item)


def record(top: Path, item: str, state: dict[str, Any], base: str,
           result: dict[str, Any]) -> bool:
    """Add what the worker's commits and this review spotted; True when the file changed."""
    from forge import review  # review imports spotted

    items = read(top)
    known = {entry["key"]: entry for entry in items}
    path = top / own_path(item)
    own = {entry["key"]: entry for entry in _parse(path.read_bytes())} if path.is_file() else {}
    tree = set(repo.git("ls-tree", "-r", "-z", "--name-only", "--full-tree", "HEAD",
                        cwd=top).split("\0"))
    changed = False
    if "/" not in item:
        for entry in items:
            if (entry["status"] == "open" and entry["item"] != item
                    and names(state.get("done_when", ""), entry["path"])):
                own[entry["key"]] = {**entry, "status": "done", "closed_by": item}
                changed = True

    def add(kind: str, path: str, line: Any, text: str, source: str) -> None:
        nonlocal changed
        text = " ".join(text.split())
        entry_key = key(kind, path, text, source, item)
        if (path not in tree or not _path(path) or entry_key in known
                or not isinstance(line, int) or isinstance(line, bool)):
            return
        known[entry_key] = {"key": entry_key, "kind": kind, "path": path, "line": line,
                            "text": text, "from": source, "item": item, "status": "open",
                            "closed_by": None}
        own[entry_key] = known[entry_key]
        changed = True

    for _, message, _ in reversed(repo.commit_log(top, base)):
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
            own[entry["key"]] = {**entry, "status": "done", "closed_by": "dismissed"}
            changed = True
    if changed:
        write(top, item, list(own.values()))
    return changed
