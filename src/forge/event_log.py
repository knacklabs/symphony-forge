"""Append-only event history and a small, atomic live record for each agent run."""
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from forge import codex, repo


def _append(path: Path, event: dict[str, Any]) -> None:
    with path.open("a+b") as out:
        end = out.tell()
        if end:
            out.seek(end - 1)
            if out.read(1) != b"\n":
                # An interrupted append can leave only its final line unfinished.
                cursor = end
                while cursor:
                    length = min(cursor, 8192)
                    cursor -= length
                    out.seek(cursor)
                    chunk = out.read(length)
                    newline = chunk.rfind(b"\n")
                    if newline >= 0:
                        cursor += newline + 1
                        break
                out.truncate(cursor)
        out.write((json.dumps(event) + "\n").encode("utf-8"))
        out.flush()
        os.fsync(out.fileno())  # Persist history before replacing or removing its live copy.


def _live(folder: Path, run_id: str) -> Path:
    path = folder / "progress" / f"{run_id}.json"
    path.parent.mkdir(exist_ok=True)
    return path


def append(top: Path, event: dict[str, Any]) -> None:
    folder = repo.forge_dir(top)
    history = folder / "events.jsonl"
    with codex._one_at_a_time(folder / "events.lock"):
        if event["event"] == "run end":
            live = _live(folder, event["run_id"])
            progress = codex._json(live).get("progress")
            if progress:
                _append(history, progress)
        _append(history, event)
        if event["event"] == "run start":
            codex._record(_live(folder, event["id"]), round=event.get("round"))
        elif event["event"] == "run end":
            live.unlink(missing_ok=True)


def progress(top: Path, item: str, run_id: str, fields: dict[str, Any]) -> None:
    folder = repo.forge_dir(top)
    history = folder / "events.jsonl"
    with codex._one_at_a_time(folder / "events.lock"):
        live = _live(folder, run_id)
        saved = codex._json(live)
        if not saved:
            # A run started on the earlier release may still be running after upgrade.
            events = _read(folder)
            start = next(row for row in events if row.get("id") == run_id)
            saved = {"round": start.get("round"), "progress": next((row for row in reversed(events)
                     if row.get("event") == "progress" and row.get("run_id") == run_id), None)}
        old = saved.get("progress") or {}
        stamp = repo.now()
        same = bool(old) and (datetime.fromisoformat(stamp) - datetime.fromisoformat(
            old["recorded_at"])).total_seconds() < 10
        if old and not same:
            _append(history, old)
        event = {**old, "id": old["id"] if same else str(uuid.uuid4()), "item": item,
                 "event": "progress", "run_id": run_id, "kind": "progress",
                 "round": saved["round"], "at": stamp, **fields}
        if not same:
            event.update(recorded_at=stamp, _position=[history.stat().st_size, time.time_ns()])
        codex._record(live, round=saved["round"], progress=event)


def _read(folder: Path) -> list[dict[str, Any]]:
    history = folder / "events.jsonl"
    rows, positions, progress_ids = [], [], {}
    offset = 0
    for line in history.read_bytes().splitlines(keepends=True) if history.is_file() else []:
        try:
            event = json.loads(line)
            if isinstance(event, dict):
                position = event.pop("_position", [offset, float("inf")])
                identity = event.get("id") if event.get("event") == "progress" else None
                if identity and identity in progress_ids:
                    rows[progress_ids[identity]] = event
                else:
                    if identity:
                        progress_ids[identity] = len(rows)
                    positions.append(position)
                    rows.append(event)
        except ValueError:
            pass
        offset += len(line)
    for path in (folder / "progress").glob("*.json"):
        event = codex._json(path).get("progress")
        if not event:
            continue
        position = event.pop("_position", [offset, float("inf")])
        if event["id"] in progress_ids:
            rows[progress_ids[event["id"]]] = event
        else:
            positions.append(position)
            rows.append(event)
    return [event for _, event in sorted(zip(positions, rows), key=lambda pair: pair[0])]


def read(top: Path) -> list[dict[str, Any]]:
    folder = repo.forge_dir(top)
    with codex._one_at_a_time(folder / "events.lock"):
        return _read(folder)
