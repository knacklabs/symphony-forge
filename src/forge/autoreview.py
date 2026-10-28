"""Autoreview's process output and finding schema at the external tool boundary."""
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from forge import machine, repo, score

PRIORITIES = ("P0", "P1", "P2", "P3")
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def spent(path: Path) -> dict[str, Any]:
    """The review engine's token use summed over its runs (a chunked review has one per pass,
    a retry one more) and its first chat, read once: Codex's `exec --json` events or Claude's
    results."""
    runs: list[dict[str, Any]] = []
    with contextlib.suppress(OSError):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            usage = event.get("usage")
            if event.get("type") == "thread.started":
                runs.append({"chat": event.get("thread_id")})
            elif event.get("type") == "turn.completed" and isinstance(usage, dict) and runs:
                # Codex reports the thread's running total, so its last turn holds the run's use.
                runs[-1].update({key: usage.get(key) for key in TOKENS})
            elif event.get("type") == "result" and isinstance(usage, dict):
                runs.append({"chat": event.get("session_id"), **repo.claude_tokens(usage)})
        path.unlink()
    if not runs:
        return {}
    return {"chat": runs[0]["chat"], **{key: sum(counts) if (counts := [
        run[key] for run in runs if isinstance(run.get(key), int)]) else None for key in TOKENS}}


def attempt(argv: list[str], cwd: Path, out: Path,
            selected: dict[str, str], top: Path, item: str, run_id: str,
            strict: bool = False) -> tuple[list[dict[str, Any]], str]:
    """Run Autoreview once: its findings, or the reason the run doesn't count."""
    from forge import codex  # importing it here avoids sync's hook-import cycle
    out.unlink(missing_ok=True)
    proc = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env={**os.environ, "FORGE_WORKER": "1"},
                            **codex.GROUP)
    with proc, machine.agent_process(proc):
        last = ""
        for line in proc.stdout or []:  # streamed as bytes: its progress is how a person watches it
            line = line.replace(b"\0", b"")
            sys.stderr.buffer.write(line)
            sys.stderr.flush()
            last = line.decode("utf-8", "replace").strip() or last
            if match := re.fullmatch(r"(model|thinking): (.*)", last):
                selected[{"model": "model", "thinking": "effort"}[match[1]]] = match[2]
            elif match := re.fullmatch(
                    r"codex model \S+ is unavailable for this account; retrying with (\S+)", last):
                selected["model"] = match[1]
            if line.strip():
                repo.record_progress(top, item, run_id, step=" ".join(last.split()), **selected)
        code = proc.wait()
    try:
        # Decode first: JSON represents null characters as escaped text.
        report = json.loads(out.read_text(encoding="utf-8"), object_hook=lambda fields: {
            key: value.replace("\0", "") if isinstance(value, str) else value
            for key, value in fields.items()})
    except (OSError, ValueError):
        report = None
    if code not in (0, 1, 2) or not isinstance(report, dict):
        return [], last or f"it exited with code {code}"
    # The helper moves a finding pinned outside the changed files to scope_rejected_findings and
    # calls the review incomplete for it. Ordinary reviews keep those findings; sign-off requires
    # a complete run even when rejected findings are present.
    rejected = report.get("scope_rejected_findings") or []
    if (strict or not rejected) and (code == 2 or report.get("review_status") == "incomplete"):
        return [], "it reported the review as incomplete"
    if strict and report.get("review_status") not in (
            "scoped-clean", "findings", "filtered", "incorrect"):
        return [], "it did not report a completed review"
    raw = report.get("findings")
    findings = ([_finding(f) for f in [*raw, *rejected]]
                if isinstance(raw, list) and isinstance(rejected, list) else [None])
    if None in findings:
        return [], "it wrote findings Forge cannot read"
    if not findings and report.get("overall_correctness") == "patch is incorrect":
        return [], "it called the patch incorrect without naming a finding"
    return findings, ""  # type: ignore[return-value]


def _finding(raw: Any) -> dict[str, Any] | None:
    """The fields Forge uses from one finding, or None when they can't be read."""
    where = raw.get("code_location") if isinstance(raw, dict) else None
    if not isinstance(where, dict) or raw.get("priority") not in PRIORITIES:
        return None
    title = str(raw.get("title", ""))
    body = str(raw.get("body", ""))
    category = str(raw.get("category", "")).strip().casefold().replace("_", " ").replace("-", " ")
    if category in ("security", "data loss") and not any(
            name == category and pattern.search(body) for pattern, name in score.FLOORS[:2]):
        body += f"\nRaise: {category.capitalize()}"
    scores, body = score.normalise(title, body)
    return {"priority": raw["priority"], "title": title, "body": body,
            **(dict(zip(("gain", "work", "harm"), scores)) if scores else {}),
            "file": str(where.get("file_path", "")), "line": where.get("line", 0)}
