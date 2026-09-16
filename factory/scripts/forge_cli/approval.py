"""Record plan approval emitted by a coordinator's native Plan Mode UI.

The runtime adapters deliberately end here.  Candidate selection, digest
binding, replay protection, attribution and storage are shared so Claude and
Codex cannot acquire subtly different approval semantics.
"""
from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory_lib import (
    _plan_body_digest_bytes, _safe_review_leaf, _task_plan_state,
    _windows_reparse_point, dump_json, evidence_path, factory_dir, git_control_dir,
    load_json, now_iso,
    plan_digest_without_assumptions, protected_decomposition_state_path,
    require_grill, run_state_path, task_frontier_state,
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
    previous_digest: str = ""


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _plan_path(base: Path, relative: object) -> Path | None:
    if (not isinstance(relative, str) or not relative
            or Path(relative).is_absolute() or ".." in Path(relative).parts):
        return None
    path = base / relative
    return path if _safe_review_leaf(base, path, required=True) else None


def _require_safe_plan(base: Path, path: Path) -> None:
    if (".." in path.parts
            or not _safe_review_leaf(base, path, required=True)):
        raise ApprovalRefused("approval plan must be a contained regular non-linked file")


def _require_safe_destination(base: Path, path: Path, *, required: bool) -> None:
    try:
        boundary = base
        try:
            relative = path.relative_to(boundary)
        except ValueError:
            boundary = git_control_dir(base)
            relative = path.relative_to(boundary)
        current = boundary
        root_info = current.lstat()
        if (not stat.S_ISDIR(root_info.st_mode) or current.is_symlink()
                or _windows_reparse_point(current)):
            raise ApprovalRefused(
                f"approval destination must be contained and non-linked: {path}"
            )
        for index, part in enumerate(relative.parts):
            current /= part
            try:
                info = current.lstat()
            except FileNotFoundError:
                if required:
                    raise ApprovalRefused(
                        f"approval destination is missing: {path}"
                    )
                return
            leaf = index == len(relative.parts) - 1
            safe = (
                stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                if leaf else stat.S_ISDIR(info.st_mode)
            )
            if (not safe or current.is_symlink()
                    or _windows_reparse_point(current)):
                raise ApprovalRefused(
                    f"approval destination must be contained and non-linked: {path}"
                )
    except (OSError, ValueError) as exc:
        raise ApprovalRefused(
            f"approval destination must be contained and non-linked: {path}"
        ) from exc


def _story_candidate(base: Path) -> ApprovalCandidate | None:
    state = load_json(run_state_path(base), default={})
    status = state.get("plan_status")
    if status not in {"awaiting-approval", "approved"}:
        return None
    path = _plan_path(base, state.get("plan_file"))
    if path is None:
        return None
    story = _text(state.get("story")) or _text(state.get("issue_key"))
    if not story:
        return None
    digest = plan_digest_without_assumptions(path)
    previous_digest = ""
    if status == "awaiting-approval":
        grill = load_json(
            evidence_path(base, story, "grills/plan.json"), default={},
        )
        if (grill.get("issue") != story
                or grill.get("input_sha256") != digest):
            return None
        try:
            require_grill(
                base, "plan",
                ("docs/product/", "docs/decisions/", "docs/architecture/"),
                ignore_names=("client-signoff", "epics-approved"),
                expect_digest_of=path,
            )
        except SystemExit:
            return None
    else:
        approved = state.get("approved_plan_sha256")
        if (not isinstance(approved, str)
                or re.fullmatch(r"[0-9a-f]{64}", approved) is None
                or approved == digest):
            return None
        previous_digest = approved
    return ApprovalCandidate(
        "story", story, "", path, digest,
        evidence_path(base, story, "plan-approval.json", for_write=True),
        previous_digest,
    )


def _task_candidate(base: Path) -> ApprovalCandidate | None:
    frontier = task_frontier_state(base)
    if frontier is None:
        return None
    frontier_state, task = frontier
    if frontier_state != "await-approval":
        return None
    state = load_json(run_state_path(base), default={})
    story = _text(state.get("story")) or _text(state.get("issue_key"))
    if not story:
        return None
    story_plan = _plan_path(base, state.get("plan_file"))
    if (state.get("plan_status") != "approved"
            or story_plan is None):
        return None
    story_digest = plan_digest_without_assumptions(story_plan)
    decomposition = load_json(
        protected_decomposition_state_path(base), default={},
    )
    if (state.get("approved_plan_sha256") != story_digest
            or decomposition.get("plan_sha256") != story_digest):
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
    if _task_plan_state(base, task, grill) != "await-approval":
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


def _claude_approved(payload: dict[str, Any]) -> str:
    if payload.get("tool_name") != "ExitPlanMode":
        return ""
    response = payload.get("tool_response")
    if payload.get("is_error") is True or payload.get("cancelled") is True:
        return ""
    if not isinstance(response, dict):
        return ""
    if response.get("is_error") is True or response.get("cancelled") is True:
        return ""
    if _text(response.get("status")).lower() not in {
            "success", "succeeded", "completed"}:
        return ""
    tool_input = payload.get("tool_input")
    plan = tool_input.get("plan") if isinstance(tool_input, dict) else None
    if not isinstance(plan, str) or not plan:
        return ""
    return _plan_body_digest_bytes(plan.encode("utf-8"))


def _codex_approved(payload: dict[str, Any]) -> str:
    if payload.get("tool_name") != "request_user_input":
        return ""
    if payload.get("async") is True or payload.get("tool_name") == "request_user_input_async":
        return ""
    tool_input = payload.get("tool_input")
    response = payload.get("tool_response")
    if payload.get("is_error") is True or payload.get("cancelled") is True:
        return ""
    if isinstance(response, dict):
        if response.get("is_error") is True or response.get("cancelled") is True:
            return ""
        status = _text(response.get("status")).lower()
        if status in {"cancelled", "rejected", "error", "failed"}:
            return ""
    questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    answers = response.get("answers") if isinstance(response, dict) else None
    if not isinstance(questions, list) or len(questions) != 1 or not isinstance(answers, dict):
        return ""
    question = questions[0]
    if not isinstance(question, dict):
        return ""
    labels = [entry.get("label") if isinstance(entry, dict) else entry
              for entry in question.get("options", [])]
    if labels != ["Approve plan", "Request changes", "Stop"]:
        return ""
    prompt = _text(question.get("question"))
    header = _text(question.get("header"))
    question_id = _text(question.get("id"))
    match = re.fullmatch(r"approve_plan_([0-9a-f]{64})", question_id)
    if header != "Approve plan" or match is None:
        return ""
    digest = match.group(1)
    if prompt != f"Approve exact plan digest {digest}?":
        return ""
    if set(answers) != {question_id}:
        return ""
    answer = answers.get(question_id)
    selected = answer.get("answers") if isinstance(answer, dict) else None
    if (not isinstance(selected, list) or len(selected) != 1
            or not isinstance(selected[0], str)):
        return ""
    return digest if selected[0] == "Approve plan" else ""


def _event_runtime(payload: dict[str, Any], runtime: str | None) -> tuple[str, str]:
    value = (runtime or _text(payload.get("runtime")) or
             _text(os.environ.get("FORGE_COORDINATOR"))).lower()
    if value not in {"claude", "codex"}:
        raise ApprovalRefused("native approval runtime must be claude or codex")
    displayed_digest = (
        _claude_approved(payload) if value == "claude" else _codex_approved(payload)
    )
    if not displayed_digest:
        raise ApprovalRefused(f"unsupported or unsuccessful {value} approval event")
    return value, displayed_digest


def _approve_story(base: Path, candidate: ApprovalCandidate, record: dict[str, Any]) -> None:
    _require_safe_plan(base, candidate.path)
    text = candidate.path.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"(?m)^(status:\s*)awaiting-approval\s*$", r"\1approved", text, count=1,
    )
    if count != 1:
        if re.search(r"(?m)^status:\s*approved\s*$", text) is None:
            raise ApprovalRefused(
                "story plan has neither awaiting-approval nor approved status"
            )
        updated = text
    # The status line is frontmatter and excluded by the shared semantic digest.
    _require_safe_plan(base, candidate.path)
    candidate.path.write_text(updated, encoding="utf-8")
    if plan_digest_without_assumptions(candidate.path) != candidate.digest:
        _require_safe_plan(base, candidate.path)
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


def _restore_files(snapshots: dict[Path, bytes | None], base: Path) -> None:
    """Best-effort rollback for a failed multi-file approval publication."""
    for path, body in snapshots.items():
        try:
            _require_safe_destination(
                base, path, required=path.exists() or path.is_symlink())
        except ApprovalRefused:
            continue
        if body is None:
            path.unlink(missing_ok=True)
        else:
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
    selected_runtime, displayed_digest = _event_runtime(payload, runtime)
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
        _require_safe_plan(base, candidate.path)
        if displayed_digest != candidate.digest:
            raise ApprovalRefused("native approval displayed digest is stale")

        replay_key = __import__("hashlib").sha256(
            f"{selected_runtime}\0{session_id}\0{event_id}".encode("utf-8")
        ).hexdigest()
        # The host event is global to this checkout, not to the current story.
        # Check all live layouts before creating even the current directory.
        root = factory_dir(base)
        previous = [root / "approval-events" / f"{replay_key}.json"]
        for parent in (root / "stories", root / "history"):
            if parent.is_dir():
                previous.extend(parent.glob(f"*/approval-events/{replay_key}.json"))
        if any(path.exists() or path.is_symlink() for path in previous):
            raise ApprovalRefused("native approval event was already consumed")
        replay_dir = evidence_path(
            base, candidate.story, "approval-events", for_write=True,
        )
        replay_path = replay_dir / f"{replay_key}.json"
        if replay_path.exists() or replay_path.is_symlink():
            raise ApprovalRefused("native approval event was already consumed")

        authority_paths = {candidate.evidence}
        if candidate.kind == "story":
            authority_paths.update({candidate.path, run_state_path(base)})
        for authority_path in authority_paths:
            _require_safe_destination(
                base, authority_path, required=authority_path.exists())
        _require_safe_destination(base, replay_path, required=False)
        replay_dir.mkdir(parents=True, exist_ok=True)
        _require_safe_destination(base, replay_path, required=False)

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
        if candidate.kind == "story" and candidate.previous_digest:
            record["previous_approved_plan_sha256"] = candidate.previous_digest
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
                from .events import append_event
                append_event(
                    base, "plan-approved", actor="planner-high",
                    story=candidate.story,
                    detail=candidate.path.relative_to(base).as_posix(),
                )
            else:
                _approve_task(candidate, record)
        except Exception:
            _restore_files(snapshots, base)
            raise
        return record
