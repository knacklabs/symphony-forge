"""One task journal, read by both agents (decision 0080).

Before this, the coordinator's reasoning reached the worker only through a
brief composed from lessons matched by path globs, and the worker's side came
back as a summary. On WF-BIO-1 T4 two instruction lists never arrived and
nothing said so; the worker never saw the full review output, the triage
evidence, the host's test failures, the user's decisions, or what earlier
rounds fixed or rejected. The review brief was composed from the whole story
and grew every round until the reviewer had to be split into one-file groups.

The journal is one append-only ledger per task. The harness appends what it
does (launches, exits, worker reports, proof output, review generations); the
coordinator appends what it decides (notes, decisions, triage, refusals, scope);
nothing is hand-written and nothing is composed from elsewhere. The delegate
brief carries the entries since the worker's last launch and points at the
rest; the review brief carries the task's journal beside the diff; the
coordinator reads the worker's side from the same file.

`journal.jsonl` is the record; `journal.md` is its rendering, regenerated on
every append so a reader who opens the tree sees the same thing the brief
inlined. Long bodies go to `journal/<id>.txt` with the tail inlined, so an
output log never makes the prompt unreadable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

from factory_lib import (
    active_story_key, load_json, now_iso, raw_open_flags, repo_root,
    task_evidence_path, validate_payload,
)

from .common import fail

ACTORS = ("harness", "coordinator", "worker", "reviewer", "human")

# kind -> (actors that may write it, fields it must carry beyond title/body)
KINDS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "contract": (("harness",), ()),
    "decision": (("coordinator", "human"), ("reason",)),
    "note": (("coordinator", "human"), ()),
    "brief": (("harness",), ("launch_id",)),
    "launch": (("harness",), ("launch_id",)),
    "exit": (("harness",), ("launch_id", "exit_code")),
    "report": (("harness", "worker"), ("launch_id",)),
    "proof": (("harness",), ("command", "exit_code")),
    "flake": (("harness",), ("command",)),
    "flake-accepted": (("coordinator", "human"), ("command", "reason")),
    "review": (("harness",), ("generation_id",)),
    "triage": (("coordinator",), ("finding", "verdict", "evidence")),
    "refusal": (("coordinator",), ("finding", "evidence")),
    "scope": (("coordinator", "harness"), ("paths", "reason")),
    "signal": (("worker", "harness"), ()),
    "signal-resolved": (("coordinator",), ()),
    "ci": (("coordinator",), ("status",)),
}
# What every brief carries in full, however old: the instructions that stand.
STANDING_KINDS = (
    "contract", "decision", "note", "scope", "refusal", "flake-accepted", "triage",
)
INLINE_LIMIT = 6000
TAIL_LINES = 40
ID_PATTERN = re.compile(r"^J-\d+$")


def journal_paths(base: Path, story: str, task_id: str) -> tuple[Path, Path, Path]:
    """(journal.jsonl, journal.md, attachments dir) for one task."""
    record = task_evidence_path(base, story, task_id, "journal.jsonl", for_write=True)
    return record, record.with_name("journal.md"), record.with_name("journal")


def entries(base: Path, story: str, task_id: str) -> list[dict]:
    record = task_evidence_path(base, story, task_id, "journal.jsonl")
    try:
        raw = record.read_bytes()
    except OSError:
        return []
    out: list[dict] = []
    for line in raw.replace(b"\r\n", b"\n").split(b"\n"):
        if not line.strip():
            continue
        try:
            entry = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            fail(f"{task_id} journal is corrupt at {record}: {exc}")
        if isinstance(entry, dict):
            out.append(entry)
    return out


def head_id(items: list[dict]) -> str:
    return str(items[-1].get("id") or "") if items else ""


def since(items: list[dict], last_id: str) -> list[dict]:
    """Entries after `last_id`; all of them when it is empty or unknown."""
    if not last_id:
        return list(items)
    for index, entry in enumerate(items):
        if entry.get("id") == last_id:
            return list(items[index + 1:])
    return list(items)


def standing(items: list[dict]) -> list[dict]:
    """The entries that instruct regardless of age: the latest contract, and
    every decision, note, scope change, refusal, accepted flake and triage."""
    latest_contract = next(
        (e for e in reversed(items) if e.get("kind") == "contract"), None)
    kept = [e for e in items if e.get("kind") in STANDING_KINDS
            and e.get("kind") != "contract"]
    return ([latest_contract] if latest_contract else []) + kept


def _next_id(items: list[dict]) -> str:
    highest = 0
    for entry in items:
        match = ID_PATTERN.match(str(entry.get("id") or ""))
        if match:
            highest = max(highest, int(str(entry["id"])[2:]))
    return f"J-{highest + 1}"


def _write_bytes(path: Path, body: bytes, *, append_mode: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append_mode else os.O_TRUNC)
    descriptor = os.open(path, raw_open_flags(flags), 0o600)
    try:
        view = memoryview(body)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
    finally:
        os.close(descriptor)


def _tail(text: str, lines: int = TAIL_LINES) -> str:
    return "\n".join(text.rstrip().splitlines()[-lines:])


def append(base: Path, story: str, task_id: str, *, kind: str, by: str,
           title: str, body: str = "", **fields) -> dict:
    """Append one entry, validated, and re-render the markdown view.

    A body over INLINE_LIMIT goes to an attachment with its tail inlined. An
    entry whose kind and body digest match the previous entry of that kind is
    not appended twice (a retried command must not double the record)."""
    if kind not in KINDS:
        fail(f"journal kind {kind!r} is not one of {', '.join(KINDS)}")
    actors, required = KINDS[kind]
    if by not in ACTORS:
        fail(f"journal actor {by!r} is not one of {', '.join(ACTORS)}")
    if by not in actors:
        fail(f"a {by} entry cannot be of kind {kind!r}; that kind is written by "
             f"{', '.join(actors)}")
    if not isinstance(title, str) or not title.strip():
        fail("journal entries need a title")
    if not isinstance(body, str):
        fail("journal body must be text")
    for field in required:
        value = fields.get(field)
        if value is None or value == "" or value == []:
            fail(f"journal {kind} entries need --{field.replace('_', '-')}")
    if not (story or "").strip() or not (task_id or "").strip():
        fail("journal entries belong to a story and a task")
    items = entries(base, story, task_id)
    for ref in fields.get("acted_on") or []:
        if not ID_PATTERN.match(str(ref)) or not any(e.get("id") == ref for e in items):
            fail(f"acted_on names {ref!r}, which is not an entry of this journal")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    previous = next((e for e in reversed(items) if e.get("kind") == kind), None)
    if (previous is not None and previous.get("digest") == digest
            and previous.get("title") == title.strip()
            and all(previous.get(k) == v for k, v in fields.items())):
        return previous
    record_path, md_path, attach_dir = journal_paths(base, story, task_id)
    entry = {
        "id": _next_id(items),
        "at": now_iso(),
        "kind": kind,
        "generated_by": by,
        "task_id": task_id,
        "title": title.strip(),
        "body": body,
        "digest": digest,
        **{k: v for k, v in fields.items() if v is not None},
    }
    if len(body) > INLINE_LIMIT:
        attachment = attach_dir / f"{entry['id']}.txt"
        _write_bytes(attachment, body.encode("utf-8"))
        entry["attachment"] = attachment.relative_to(base).as_posix()
        entry["body"] = _tail(body)
        entry["truncated"] = True
    validate_payload(base, "journal-entry", entry)
    line = (json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    _write_bytes(record_path, line, append_mode=True)
    _write_bytes(md_path, render(items + [entry], task_id).encode("utf-8"))
    return entry


def render(items: list[dict], task_id: str) -> str:
    lines = [f"# Journal — {task_id}", "",
             "Append-only record of everything both agents act on for this task "
             "(decision 0080). Written only through `forge journal add` and the "
             "harness; never by hand.", ""]
    for entry in items:
        lines.append(f"## {entry.get('id')} · {entry.get('kind')} · "
                     f"{entry.get('generated_by')} · {str(entry.get('at', ''))[:19]} — "
                     f"{entry.get('title', '')}")
        lines.append("")
        meta = []
        for key in ("launch_id", "exit_code", "command", "generation_id", "verdict",
                    "evidence", "paths", "reason", "status", "acted_on", "attachment",
                    "finding", "cite"):
            value = entry.get(key)
            if value not in (None, "", []):
                rendered = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
                meta.append(f"- {key}: {rendered}")
        if meta:
            lines.extend(meta)
            lines.append("")
        body = str(entry.get("body") or "").rstrip()
        if body:
            if entry.get("truncated"):
                lines.append(f"(tail; full text in `{entry.get('attachment')}`)")
                lines.append("")
            lines.append(body)
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_entries(items: list[dict], *, heading: str) -> str:
    """The brief's inline rendering of a subset: same shape as journal.md."""
    if not items:
        return f"### {heading}\n\n(none)\n"
    body = render(items, "")
    body = body.split("\n", 4)[-1] if body.startswith("# Journal") else body
    return f"### {heading}\n\n{body}"


def _story_and_task(base: Path, task_id: str) -> tuple[str, str]:
    story = active_story_key(base)
    if not story:
        fail("journal: no active story in this checkout")
    return story, task_id


def cmd_add(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    story, task_id = _story_and_task(base, args.task)
    body = args.body or ""
    if args.body_file:
        body = Path(args.body_file).expanduser().read_text(encoding="utf-8")
    fields = {}
    for name in ("reason", "evidence", "cite", "command", "finding", "verdict",
                 "status", "launch_id", "generation_id"):
        value = getattr(args, name, None)
        if value:
            fields[name] = value
    if args.paths:
        fields["paths"] = list(args.paths)
    if getattr(args, "exit_code", None) is not None:
        fields["exit_code"] = args.exit_code
    entry = append(base, story, task_id, kind=args.kind, by=args.by,
                   title=args.title, body=body, **fields)
    print(f"{entry['id']} {entry['kind']} recorded for {task_id}")


def cmd_show(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    story, task_id = _story_and_task(base, args.task)
    items = entries(base, story, task_id)
    if args.since:
        items = since(items, args.since)
    if args.kind:
        items = [e for e in items if e.get("kind") == args.kind]
    print(render(items, task_id).rstrip())


def cmd_status(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    story, task_id = _story_and_task(base, args.task)
    items = entries(base, story, task_id)
    counts: dict[str, int] = {}
    for entry in items:
        counts[str(entry.get("kind"))] = counts.get(str(entry.get("kind")), 0) + 1
    last_launch = next((e for e in reversed(items) if e.get("kind") == "launch"), None)
    last_exit = next((e for e in reversed(items) if e.get("kind") == "exit"), None)
    last_report = next((e for e in reversed(items) if e.get("kind") == "report"), None)
    print(f"{task_id}: {len(items)} entries; head {head_id(items) or '(empty)'}")
    if counts:
        print("  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if last_launch:
        head = last_launch.get("journal_head") or "(none)"
        print(f"  last launch {last_launch.get('launch_id')} at "
              f"{str(last_launch.get('at', ''))[:19]} received the journal up to {head}")
    if last_exit:
        print(f"  last exit {last_exit.get('launch_id')} code {last_exit.get('exit_code')} "
              f"at {str(last_exit.get('at', ''))[:19]}")
    if last_report:
        acted = last_report.get("acted_on") or []
        print(f"  last report cites {len(acted)} entr{'y' if len(acted) == 1 else 'ies'}"
              + ("" if acted else " — the worker did not say what it acted on"))
