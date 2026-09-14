"""Record plan approval emitted by a coordinator's native Plan Mode UI.

The runtime adapters deliberately end here.  Candidate selection, digest
binding, replay protection, attribution and storage are shared so Claude and
Codex cannot acquire subtly different approval semantics.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory_lib import (
    dump_json, evidence_path, load_json, now_iso,
    plan_digest_without_assumptions, protected_decomposition_state_path,
    run_state_path, task_frontier_state,
)


class ApprovalRefused(ValueError):
    """The event is not a complete, current, replay-safe native approval."""


@dataclass(frozen=True)
class ApprovalCandidate:
    kind: str
    story: str
    task: str
    path: Path
    digest: str
    evidence: Path


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _story_candidate(base: Path) -> ApprovalCandidate | None:
    state = load_json(run_state_path(base), default={})
    if state.get("plan_status") != "awaiting-approval":
        return None
    relative = state.get("plan_file")
    if not isinstance(relative, str) or not relative:
        return None
    path = base / relative
    if not path.is_file():
        return None
    story = _text(state.get("story")) or _text(state.get("issue_key"))
    if not story:
        return None
    return ApprovalCandidate(
        "story", story, "", path, plan_digest_without_assumptions(path),
        evidence_path(base, story, "plan-approval.json", for_write=True),
    )


def _task_candidate(base: Path) -> ApprovalCandidate | None:
    frontier = task_frontier_state(base)
    if frontier is None:
        return None
    _frontier_state, task = frontier
    state = load_json(run_state_path(base), default={})
    story = _text(state.get("story")) or _text(state.get("issue_key"))
    if not story:
        return None
    task_id = _text(task.get("id"))
    if not task_id:
        return None
    plan = evidence_path(base, story, f"task-plans/{task_id}.md")
    grill_path = evidence_path(base, story, f"grills/tasks/{task_id}.json")
    grill = load_json(grill_path, default={})
    if not plan.is_file() or grill.get("verdict") != "pass":
        return None
    digest = plan_digest_without_assumptions(plan)
    # The cold proof may bind either the original input plus an explicit
    # amendment bridge, or the final bytes in old pre-Lean records.
    if grill.get("task_plan_sha256") != digest:
        return None
    if grill.get("approved_task_plan_sha256") == digest:
        return None
    return ApprovalCandidate("task", story, task_id, plan, digest, grill_path)


def eligible_candidates(base: Path) -> list[ApprovalCandidate]:
    """Return all current-frontier candidates; the caller requires exactly one."""
    return [candidate for candidate in (_story_candidate(base), _task_candidate(base))
            if candidate is not None]


def _event_identity(payload: dict[str, Any]) -> tuple[str, str]:
    session = _text(payload.get("session_id")) or _text(payload.get("conversation_id"))
    event = (_text(payload.get("event_id")) or _text(payload.get("tool_use_id"))
             or _text(payload.get("call_id")) or _text(payload.get("tool_call_id")))
    if not session or not event:
        raise ApprovalRefused("native approval requires stable session and event identity")
    return session, event


def _claude_approved(payload: dict[str, Any]) -> bool:
    if payload.get("tool_name") != "ExitPlanMode":
        return False
    response = payload.get("tool_response")
    if payload.get("is_error") is True or payload.get("cancelled") is True:
        return False
    if isinstance(response, dict):
        if response.get("is_error") is True or response.get("cancelled") is True:
            return False
        status = _text(response.get("status")).lower()
        if status in {"cancelled", "rejected", "error", "failed"}:
            return False
    # PostToolUse is emitted only after a successful tool completion.  An
    # absent response is not success: tests and alternate hosts can call the
    # recorder directly, and must provide completion evidence.
    return response not in (None, False, "")


def _codex_approved(payload: dict[str, Any]) -> bool:
    if payload.get("tool_name") != "request_user_input":
        return False
    if payload.get("async") is True or payload.get("tool_name") == "request_user_input_async":
        return False
    tool_input = payload.get("tool_input")
    response = payload.get("tool_response")
    questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    answers = response.get("answers") if isinstance(response, dict) else None
    if not isinstance(questions, list) or len(questions) != 1 or not isinstance(answers, dict):
        return False
    question = questions[0]
    if not isinstance(question, dict):
        return False
    labels = [entry.get("label") if isinstance(entry, dict) else entry
              for entry in question.get("options", [])]
    if labels != ["Approve plan", "Request changes", "Stop"]:
        return False
    prompt = _text(question.get("question"))
    header = _text(question.get("header"))
    if header != "Approve plan" or not prompt:
        return False
    return answers.get(prompt) == "Approve plan"


def _event_runtime(payload: dict[str, Any], runtime: str | None) -> str:
    value = (runtime or _text(payload.get("runtime")) or
             _text(os.environ.get("FORGE_COORDINATOR"))).lower()
    if value not in {"claude", "codex"}:
        raise ApprovalRefused("native approval runtime must be claude or codex")
    approved = _claude_approved(payload) if value == "claude" else _codex_approved(payload)
    if not approved:
        raise ApprovalRefused(f"unsupported or unsuccessful {value} approval event")
    return value


def _approve_story(base: Path, candidate: ApprovalCandidate, record: dict[str, Any]) -> None:
    text = candidate.path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"(?m)^(status:\s*)awaiting-approval\s*$", r"\1approved", text, count=1,
    )
    if count != 1:
        raise ApprovalRefused("awaiting story plan has no awaiting-approval status")
    # The status line is frontmatter and excluded by the shared semantic digest.
    candidate.path.write_text(updated, encoding="utf-8")
    if plan_digest_without_assumptions(candidate.path) != candidate.digest:
        candidate.path.write_text(text, encoding="utf-8")
        raise ApprovalRefused("story plan digest changed while approval was recorded")
    dump_json(candidate.evidence, record)
    state_path = run_state_path(base)
    state = load_json(state_path, default={})
    state["plan_status"] = "approved"
    state["approved_plan_sha256"] = candidate.digest
    state["updated_at"] = record["approved_at"]
    dump_json(state_path, state)


def _approve_task(candidate: ApprovalCandidate, record: dict[str, Any]) -> None:
    grill = load_json(candidate.evidence, default={})
    if not grill:
        raise ApprovalRefused("task cold-read proof disappeared during approval")
    grill.update({
        "approved_task_plan_sha256": candidate.digest,
        "approved_by": record["approved_by"],
        "approved_at": record["approved_at"],
        "approval_runtime": record["runtime"],
        "approval_session_id": record["session_id"],
        "approval_event_id": record["event_id"],
    })
    dump_json(candidate.evidence, grill)


def _restore_files(snapshots: dict[Path, bytes | None]) -> None:
    """Best-effort rollback for a failed multi-file approval publication."""
    for path, body in snapshots.items():
        if body is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)


def record_native_approval(
    base: Path, payload: dict[str, Any], *, runtime: str | None = None,
) -> dict[str, Any]:
    """Validate and consume one native approval event.

    Raises :class:`ApprovalRefused` without mutation for every non-approval or
    ambiguous state.  The returned record is also the durable storage shape.
    """
    if not isinstance(payload, dict):
        raise ApprovalRefused("native approval payload must be an object")
    selected_runtime = _event_runtime(payload, runtime)
    session_id, event_id = _event_identity(payload)
    from .delegate import delegation_exclusion
    with delegation_exclusion(base, "native-approval", kind="approval"):
        candidates = eligible_candidates(base)
        if len(candidates) != 1:
            raise ApprovalRefused(
                "native approval requires exactly one eligible current-frontier "
                f"candidate; found {len(candidates)}"
            )
        candidate = candidates[0]
        supplied = _text(payload.get("plan_sha256")) or _text(payload.get("digest"))
        if supplied and supplied != candidate.digest:
            raise ApprovalRefused("native approval digest is stale")

        replay_dir = evidence_path(base, candidate.story, "approval-events", for_write=True)
        replay_dir.mkdir(parents=True, exist_ok=True)
        replay_key = __import__("hashlib").sha256(
            f"{selected_runtime}\0{session_id}\0{event_id}".encode("utf-8")
        ).hexdigest()
        replay_path = replay_dir / f"{replay_key}.json"
        if replay_path.exists():
            raise ApprovalRefused("native approval event was already consumed")

        record: dict[str, Any] = {
            "approved_plan_sha256": candidate.digest,
            "approved_by": f"human-via-{selected_runtime.capitalize()}",
            "approved_at": now_iso(),
            "runtime": selected_runtime,
            "session_id": session_id,
            "event_id": event_id,
            "plan_kind": candidate.kind,
            "story": candidate.story,
            "task": candidate.task,
        }
        authority_paths = {candidate.evidence}
        if candidate.kind == "story":
            authority_paths.update({candidate.path, run_state_path(base)})
        snapshots = {
            path: path.read_bytes() if path.is_file() else None
            for path in authority_paths
        }
        # Consume the event first. If authority publication fails, restore every
        # partially written authority file but retain the tombstone: the host
        # must emit a new approval event, never replay the old completion.
        dump_json(replay_path, record)
        try:
            if candidate.kind == "story":
                _approve_story(base, candidate, record)
            else:
                _approve_task(candidate, record)
        except Exception:
            _restore_files(snapshots)
            raise
        return record
