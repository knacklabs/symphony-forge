"""The journey step and active waits in Forge's text next-step view."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from forge import board, codex, design, machine, records, repo, review, story, time_records

STEPS = ("ideas and client notes", "brief", "canvas design", "sign-off", "build",
         "deploy on Mainline", "run and improve")


def step_line(top: Path, cfg: dict[str, Any], history: dict[str, Any] | None = None,
              *, idle: bool = False) -> str:
    """Name the first journey step whose landed facts still need work."""
    ref = story.landed_ref(top)
    brief = story.show(top, ref, "docs/product/BRIEF.md") or ""
    sections = records._sections(re.sub(r"<!--.*?-->", "", brief, flags=re.S))
    if cfg["repo"] == "forge-source":
        number = 5
    elif repo.is_prototype(top, cfg, (ref,)):
        context = repo.git("ls-tree", "-r", "--name-only", ref, "--", "docs/context/", cwd=top)
        if not context and not sections.get("Summary", "").strip():
            number = 1
        elif any(not sections.get(name, "").strip() for name in ("Summary", "Things it keeps track of")):
            number = 2
        else:
            try:
                design.require_prototype(top, ref)
            except repo.Refused:
                number = 3
            else:
                number = 4
    else:
        if history is not None:
            completed = history["stories"].values()
        else:
            names = repo.git("ls-tree", "-r", "--name-only", ref, "--", ".factory/stories/", cwd=top)
            completed = [story.completed(top, key, ref) for key in re.findall(
                r"^\.factory/stories/([A-Z][A-Z0-9-]*)/story\.json$", names, re.M)]
        # ponytail: "in progress" is forge next's own idle line, so the step follows what next lists.
        if not idle or not any(state.get("status") == "done" for state in completed):
            number = 5
        elif cfg["stage"] == "prototype" and not re.search(
                r"^- Address: https?://\S+\s*$", sections.get("Demo", ""), re.M):
            number = 6
        else:
            number = 7
    return f"Step {number} of 7: {STEPS[number - 1]}."


def started(top: Path, item: str, state: dict[str, Any], kind: str) -> str | None:
    """Use the live run's start, or the session entry that owns the native round."""
    kinds = ("read",) if kind == "read" else ("work", "worker")
    runs = board.active_runs(top, item, round_number=state.get("round"))
    if live := next((run for run in reversed(runs) if run.get("kind") in kinds), None):
        return live.get("at")
    path = codex._item_file(top, item, ".json", "Grill" if kind == "read" else "Build")
    pending = codex._json(path).get("pending") or {}
    entry = pending.get("entry") or {}
    if entry.get("native"):
        live = next((run for run in machine.entries() if run["id"] == entry["id"]), None)
        if live:
            return live.get("started_at") or live.get("joined_at")
    return None


def wait_line(top: Path, item: str, state: dict[str, Any], started: str | None,
              pr: dict[str, Any], checks: str, kind: str) -> str | None:
    """Describe the first recorded wait that applies to this item."""
    # ponytail: no machine-queue, test-progress or Claude rate-limit case;
    # add one when people ask why such a wait takes time.
    now = time_records.when(repo.now())
    began = time_records.when(started)
    elapsed = time_records.plain((now - began).total_seconds() if now and began else None)
    runs = board.active_runs(top, item, round_number=state.get("round"))
    work = next((run for run in reversed(runs) if run.get("kind") in ("work", "worker")), None)
    if work:
        progress = next((event for event in reversed(board._event_history(top)[1].get(item, []))
                         if event.get("event") == "progress" and event.get("run_id") == work["id"]), {})
        retry = time_records.when(progress.get("retry_at"))
        if retry and now and retry > now:
            return f"Codex is at capacity; Forge sends the turn again at {retry:%H:%M}."
    if kind == "read":
        return f"Cold read round {int(state.get('round') or 0) + 1} is running, {elapsed} so far."
    live = work is not None or started is not None
    blocking = review.blocking(state.get("review") or {})
    if blocking:
        titles = "; ".join(finding["title"] for _, finding in blocking[:3])
        if len(blocking) > 3:
            titles += f"; and {len(blocking) - 3} more"
        number = sum(step["step"] == "review" for step in state.get("steps", []))
        line = f"Review round {number}: {len(blocking)} problems found ({titles})."
        return line + (f" The worker is fixing them, {elapsed} so far." if live else "")
    if live:
        return f"The worker is building it, {elapsed} so far."
    if checks == "running":
        unfinished = [check for check in board._rollup(pr) if check.get("status") != "COMPLETED"
                      and check.get("state") not in ("SUCCESS", "FAILURE", "ERROR")]
        starts = [stamp for check in unfinished
                  if (stamp := time_records.when(check.get("startedAt") or check.get("createdAt")))]
        elapsed = time_records.plain((now - min(starts)).total_seconds()) if starts and now else None
        if unfinished and all((check.get("status") or check.get("state")) in
                              ("QUEUED", "WAITING", "PENDING", "REQUESTED") for check in unfinished):
            return "Waiting for a CI runner" + (f": queued {elapsed}." if elapsed else ": queued.")
        return "CI checks are running" + (f", {elapsed} so far." if elapsed else ".")
    return None
