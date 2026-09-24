"""Record plan approval emitted by a coordinator's native Plan Mode UI.

The runtime adapters deliberately end here.  Candidate selection, digest
binding, replay protection, attribution and storage are shared so Claude and
Codex cannot acquire subtly different approval semantics.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory_lib import (
    _plan_body_digest_bytes, _safe_review_leaf, _task_plan_state,
    _windows_reparse_point, dump_json, evidence_path, factory_dir, git_control_dir,
    load_json, now_iso, story_dir,
    plan_digest_without_assumptions, protected_decomposition_state_path,
    approved_plan_digest,
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
        if relative.is_absolute() or ".." in relative.parts:
            raise ApprovalRefused(
                f"approval destination must be contained and non-linked: {path}"
            )
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


def _strict_run_state(base: Path) -> dict[str, Any]:
    """Read approval authority as one contained object or refuse cleanly."""
    path = run_state_path(base)
    _require_safe_destination(base, path, required=True)
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ApprovalRefused("native approval run state is unreadable") from exc
    if not isinstance(value, dict):
        raise ApprovalRefused("native approval run state must be a JSON object")
    return value


def _safe_key(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value))


def _legacy_plan_digest(path: Path, metadata: dict[str, Any]) -> str:
    """Recreate the old attested digest for a stripped legacy plan source."""
    decisions = metadata.get("decisions_reviewed")
    if not isinstance(decisions, list) or not all(isinstance(item, str) for item in decisions):
        return ""
    lines = "\n".join(f"  - {decision}" for decision in decisions)
    value = f"\n{lines}" if lines else " []"
    frontmatter = f"---\ndecisions_reviewed:{value}\n---\n"
    try:
        body = path.read_bytes()
    except OSError:
        return ""
    return _plan_body_digest_bytes(frontmatter.encode("utf-8") + body)


def _legacy_plan_approval(
        base: Path, issue: str, story: str, path: Path, evidence: Path,
        digest: str) -> bool:
    """Recognize one exact, old manual approval without treating it as authority."""
    if not _safe_key(issue) or not _safe_key(story):
        return False
    try:
        _require_safe_destination(base, path, required=True)
        _require_safe_destination(base, evidence, required=True)
        record = json.loads(evidence.read_text(encoding="utf-8"))
    except (ApprovalRefused, OSError, UnicodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(record, dict)
        and record.get("approved_plan_sha256") == digest
        and record.get("issue") == issue
        and record.get("story") == story
        and all(_text(record.get(field)) for field in ("approver", "at"))
        and "runtime" not in record
    )


def _completed_deleted_plan_approval(base: Path, story: str, evidence: Path) -> bool:
    """Use only validated migration lineage after the old approval was deleted."""
    if evidence.exists() or evidence.is_symlink():
        return False
    try:
        _require_safe_destination(base, evidence, required=False)
        relative = evidence.relative_to(base).as_posix()
    except (ApprovalRefused, ValueError):
        return False
    try:
        from .upgrade import _validate_completed_manifest
    except ImportError:
        return False
    for name in ("lean-workflow-v2.json", "lean-workflow-v2-supplement.json"):
        manifest = factory_dir(base) / "migrations" / name
        try:
            _require_safe_destination(base, manifest, required=True)
            value = json.loads(manifest.read_text(encoding="utf-8"))
        except (ApprovalRefused, OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict) or not value.get("completed_at"):
            continue
        try:
            _validate_completed_manifest(base, value)
        except SystemExit:
            continue
        current = value
        while isinstance(current, dict):
            for entry in current.get("entries") or []:
                if (isinstance(entry, dict)
                        and entry.get("path") == relative
                        and entry.get("family") == "manual-plan-approval"
                        and entry.get("classification") == "eligible"
                        and entry.get("preserve") is False
                        and isinstance(entry.get("sha256"), str)
                        and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])):
                    return True
            current = current.get("prior_completion")
    return False


def _story_candidate(
    base: Path, refusal_reasons: list[str] | None = None,
) -> ApprovalCandidate | None:
    state = _strict_run_state(base)
    status = state.get("plan_status")
    if status not in {"awaiting-approval", "approved"}:
        return None
    path = _plan_path(base, state.get("plan_file"))
    if path is None:
        return None
    story = _text(state.get("story")) or _text(state.get("issue_key"))
    if not story:
        return None
    # The issue owns the cold grill; the roadmap story owns approval authority.
    # They may differ when `plan save` receives both --issue and --story.
    issue = _text(state.get("issue_key")) or story
    if not _safe_key(issue) or not _safe_key(story):
        return None
    metadata_path = story_dir(base, story) / "plan-meta.json"
    try:
        _require_safe_destination(base, metadata_path, required=False)
    except ApprovalRefused:
        return None
    metadata = load_json(metadata_path, default={})
    if not isinstance(metadata, dict) or metadata.get("plan_file") != state.get("plan_file"):
        metadata = {}
    if (not metadata and not metadata_path.exists()
            and state.get("plan_file") == path.relative_to(base).as_posix()):
        metadata = {
            "issue": issue, "story": story, "status": status,
            "plan_file": state["plan_file"],
        }
    from .plans import parse_frontmatter

    fields, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    if metadata:
        if metadata.get("status") != status:
            return None
    elif (fields.get("status") not in {"awaiting-approval", "approved"}
          or (status == "awaiting-approval"
              and fields.get("status") != "awaiting-approval")):
        return None
    digest = plan_digest_without_assumptions(path)
    previous_digest = ""
    if status == "awaiting-approval":
        grill = load_json(
            evidence_path(base, issue, "grills/plan.json"), default={},
        )
        accepted_grill_digests = {digest}
        legacy_digest = _legacy_plan_digest(path, metadata)
        if legacy_digest:
            accepted_grill_digests.add(legacy_digest)
        if (not isinstance(grill, dict)
                or grill.get("issue") != issue
                or grill.get("input_sha256") not in accepted_grill_digests):
            return None
        try:
            require_grill(
                base, "plan",
                ("docs/product/", "docs/decisions/", "docs/architecture/"),
                ignore_names=("client-signoff", "epics-approved"),
            )
        except SystemExit as exc:
            if refusal_reasons is not None:
                refusal_reasons.append(str(exc))
            return None
    else:
        approved = state.get("approved_plan_sha256")
        if (not isinstance(approved, str)
                or re.fullmatch(r"[0-9a-f]{64}", approved) is None):
            return None
        evidence = evidence_path(base, story, "plan-approval.json", for_write=True)
        if approved == digest:
            if _legacy_plan_approval(
                    base, issue, story, path, evidence, digest):
                return ApprovalCandidate(
                    "story", story, "", path, digest, evidence,
                )
            if _completed_deleted_plan_approval(base, story, evidence):
                return ApprovalCandidate(
                    "story", story, "", path, digest, evidence,
                )
            return None
        previous_digest = approved
    return ApprovalCandidate(
        "story", story, "", path, digest,
        evidence_path(base, story, "plan-approval.json", for_write=True),
        previous_digest,
    )


def _task_candidate(base: Path) -> ApprovalCandidate | None:
    state = _strict_run_state(base)
    frontier = task_frontier_state(base)
    if frontier is None:
        return None
    frontier_state, task = frontier
    if frontier_state != "await-approval":
        return None
    story = _text(state.get("story")) or _text(state.get("issue_key"))
    if not story:
        return None
    story_plan = _plan_path(base, state.get("plan_file"))
    if (state.get("plan_status") != "approved"
            or story_plan is None):
        return None
    story_digest = plan_digest_without_assumptions(story_plan)
    if approved_plan_digest(base, state, story_plan) != story_digest:
        return None
    decomposition = load_json(
        protected_decomposition_state_path(base), default={},
    )
    if (not isinstance(decomposition, dict)
            or state.get("approved_plan_sha256") != story_digest
            or decomposition.get("plan_sha256") != story_digest):
        return None
    task_id = _text(task.get("id"))
    if not task_id:
        return None
    plan = evidence_path(base, story, f"task-plans/{task_id}.md")
    grill_path = evidence_path(base, story, f"grills/tasks/{task_id}.json")
    grill = load_json(grill_path, default={})
    if (not isinstance(grill, dict) or not plan.is_file()
            or grill.get("verdict") != "pass"):
        return None
    digest = plan_digest_without_assumptions(plan)
    if _task_plan_state(base, task, grill) != "await-approval":
        return None
    previous_digest = _text(grill.get("approved_task_plan_sha256"))
    if previous_digest == digest:
        previous_digest = ""
    return ApprovalCandidate(
        "task", story, task_id, plan, digest, grill_path, previous_digest,
    )


def eligible_candidates(base: Path) -> list[ApprovalCandidate]:
    """Return all current-frontier candidates for digest-bound resolution."""
    return [candidate for candidate in (_story_candidate(base), _task_candidate(base))
            if candidate is not None]


def _require_current_candidate(base: Path, candidate: ApprovalCandidate) -> None:
    """Re-select the exact digest-matching frontier authority before publication."""
    current = [
        row for row in eligible_candidates(base) if row.digest == candidate.digest
    ]
    if current != [candidate]:
        raise ApprovalRefused(
            "native approval candidate changed before publication"
        )
    _require_safe_plan(base, candidate.path)
    if plan_digest_without_assumptions(candidate.path) != candidate.digest:
        raise ApprovalRefused("native approval candidate digest changed before publication")


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
    tool_input = payload.get("tool_input")
    plan = tool_input.get("plan") if isinstance(tool_input, dict) else None
    # A no-argument ExitPlanMode call reaches PostToolUse without tool_input.plan;
    # the approved text is then only in the response.
    if plan is None:
        plan = response.get("plan")
    if not isinstance(plan, str) or not plan:
        return ""
    status_value = response.get("status")
    status = _text(status_value).lower()
    documented_response = (
        response.get("plan") == plan
        and isinstance(response.get("isAgent"), bool)
    )
    if ((status_value is not None
         and status not in {"success", "succeeded", "completed"})
            or (status_value is None and not documented_response)):
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
        status_value = response.get("status")
        status = _text(status_value).lower()
        if (status_value is not None
                and status not in {"success", "succeeded", "completed"}):
            return ""
    questions = tool_input.get("questions") if isinstance(tool_input, dict) else None
    answers = response.get("answers") if isinstance(response, dict) else None
    if not isinstance(questions, list) or len(questions) != 1 or not isinstance(answers, dict):
        return ""
    question = questions[0]
    if not isinstance(question, dict):
        return ""
    options = question.get("options")
    if not isinstance(options, list):
        return ""
    labels = [entry.get("label") if isinstance(entry, dict) else entry
              for entry in options]
    if labels != ["Approve plan", "Request changes", "Stop"]:
        return ""
    prompt = _text(question.get("question"))
    header = _text(question.get("header"))
    question_id = _text(question.get("id"))
    match = re.fullmatch(r"approve_plan_([0-9a-f]{64})", question_id)
    if header != "Approve plan" or match is None:
        return ""
    digest = match.group(1)
    if prompt not in {"Approve this plan?", f"Approve exact plan digest {digest}?"}:
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
    payload_runtime = _text(payload.get("runtime")).lower()
    adapter_runtime = _text(runtime).lower()
    if (adapter_runtime and payload_runtime
            and adapter_runtime != payload_runtime):
        raise ApprovalRefused("native approval payload runtime contradicts its adapter")
    value = (adapter_runtime or payload_runtime or
             _text(os.environ.get("FORGE_COORDINATOR"))).lower()
    if value not in {"claude", "codex"}:
        raise ApprovalRefused("native approval runtime must be claude or codex")
    displayed_digest = (
        _claude_approved(payload) if value == "claude" else _codex_approved(payload)
    )
    if not displayed_digest:
        raise ApprovalRefused(f"unsupported or unsuccessful {value} approval event")
    return value, displayed_digest


def _matching_candidate(
        base: Path, displayed_digest: str,
) -> tuple[Path, ApprovalCandidate, list[Path]]:
    """Find one digest-matching candidate in this checkout or its worktrees."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain", "-z"], cwd=base,
            capture_output=True, timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ApprovalRefused(
            f"native approval cannot list registered worktrees: {exc}"
        ) from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ApprovalRefused(
            "native approval cannot list registered worktrees: "
            f"{detail or 'git failed'}"
        )
    try:
        roots = {
            Path(field.removeprefix(b"worktree ").decode("utf-8")).resolve()
            for field in result.stdout.split(b"\0")
            if field.startswith(b"worktree ")
        }
    except UnicodeDecodeError as exc:
        raise ApprovalRefused(
            "native approval cannot inspect registered worktrees: "
            "git returned a non-UTF-8 path"
        ) from exc

    current = base.resolve()
    checkouts = [current, *sorted(roots - {current})]
    matches: list[tuple[Path, ApprovalCandidate]] = []
    findings: list[str] = []
    inspection_errors: list[str] = []
    for root in checkouts:
        try:
            candidates = eligible_candidates(root)
        except (ApprovalRefused, OSError, SystemExit) as exc:
            finding = f"{root}: could not inspect candidates ({exc})"
            findings.append(finding)
            inspection_errors.append(finding)
            continue
        if not candidates:
            refusal_reasons: list[str] = []
            _story_candidate(root, refusal_reasons)
            detail = f" ({refusal_reasons[0]})" if refusal_reasons else ""
            findings.append(f"{root}: no eligible candidate{detail}")
            continue
        labels = []
        for candidate in candidates:
            identity = (f"{candidate.kind} {candidate.story}/task {candidate.task}"
                        if candidate.kind == "task"
                        else f"{candidate.kind} {candidate.story}")
            labels.append(f"{identity} digest {candidate.digest}")
            if candidate.digest == displayed_digest:
                matches.append((root, candidate))
        findings.append(f"{root}: " + ", ".join(labels))

    if inspection_errors or len(matches) != 1:
        raise ApprovalRefused(
            "native approval requires exactly one eligible current-frontier "
            f"candidate; found {len(matches)} matching candidates; "
            f"checkout findings: {'; '.join(findings)}"
        )
    approval_base, candidate = matches[0]
    return approval_base, candidate, checkouts


def _approve_story(base: Path, candidate: ApprovalCandidate, record: dict[str, Any]) -> None:
    _require_safe_plan(base, candidate.path)
    text = candidate.path.read_text(encoding="utf-8")
    metadata_path = story_dir(base, candidate.story) / "plan-meta.json"
    metadata = load_json(metadata_path, default={})
    from .plans import FRONTMATTER

    if isinstance(metadata, dict) and metadata.get("plan_file") == candidate.path.relative_to(base).as_posix():
        _require_safe_destination(base, metadata_path, required=True)
        if metadata.get("status") not in {"awaiting-approval", "approved"}:
            raise ApprovalRefused(
                "story plan metadata has neither awaiting-approval nor approved status"
            )
        from .plans import write_plan_metadata

        metadata["status"] = "approved"
        write_plan_metadata(base, candidate.story, metadata)
    elif not metadata_path.exists() and not FRONTMATTER.match(text):
        state = _strict_run_state(base)
        if (state.get("plan_file") != candidate.path.relative_to(base).as_posix()
                or state.get("plan_status") not in {"awaiting-approval", "approved"}):
            raise ApprovalRefused(
                "story plan has neither awaiting-approval nor approved status"
            )
    else:
        updated, count = re.subn(
            r"(?m)^(status:\s*)awaiting-approval\s*$", r"\1approved", text, count=1,
        )
        if count != 1:
            if re.search(r"(?m)^status:\s*approved\s*$", text) is None:
                raise ApprovalRefused(
                    "story plan has neither awaiting-approval nor approved status"
                )
            updated = text
        # The legacy status line is frontmatter and excluded from the digest.
        _require_safe_plan(base, candidate.path)
        candidate.path.write_text(updated, encoding="utf-8")
    if plan_digest_without_assumptions(candidate.path) != candidate.digest:
        _require_safe_plan(base, candidate.path)
        candidate.path.write_text(text, encoding="utf-8")
        raise ApprovalRefused("story plan digest changed while approval was recorded")
    dump_json(candidate.evidence, record)
    state_path = run_state_path(base)
    state = _strict_run_state(base)
    state["plan_status"] = "approved"
    state["approved_plan_sha256"] = candidate.digest
    state["updated_at"] = record["approved_at"]
    dump_json(state_path, state)


def _approve_task(candidate: ApprovalCandidate, record: dict[str, Any]) -> None:
    grill = load_json(candidate.evidence, default={})
    if not grill:
        raise ApprovalRefused("task cold-read proof disappeared during approval")
    if candidate.previous_digest:
        grill["previous_approved_task_plan_sha256"] = candidate.previous_digest
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
    recorded_in: list[str] | None = None,
) -> dict[str, Any]:
    """Validate and consume one native approval event.

    Raises :class:`ApprovalRefused` without mutation for every non-approval or
    ambiguous state.  The returned record is also the durable storage shape.
    When supplied, ``recorded_in`` receives the target checkout root.
    """
    if not isinstance(payload, dict):
        raise ApprovalRefused("native approval payload must be an object")
    selected_runtime, displayed_digest = _event_runtime(payload, runtime)
    session_id, event_id = _event_identity(payload)
    from .delegate import delegation_exclusion
    approval_base, candidate, checkouts = _matching_candidate(base, displayed_digest)

    with delegation_exclusion(approval_base, "native-approval", kind="approval"):
        _require_current_candidate(approval_base, candidate)
        _require_safe_plan(approval_base, candidate.path)

        replay_key = __import__("hashlib").sha256(
            f"{selected_runtime}\0{session_id}\0{event_id}".encode("utf-8")
        ).hexdigest()
        # The host event is global to all registered checkouts, not to one story.
        # Check all live layouts before creating even the current directory.
        previous = []
        for checkout in checkouts:
            root = factory_dir(checkout)
            previous.append(root / "approval-events" / f"{replay_key}.json")
            for parent in (root / "stories", root / "history"):
                if parent.is_dir():
                    previous.extend(parent.glob(
                        f"*/approval-events/{replay_key}.json"
                    ))
        if any(path.exists() or path.is_symlink() for path in previous):
            raise ApprovalRefused("native approval event was already consumed")
        replay_dir = evidence_path(
            approval_base, candidate.story, "approval-events", for_write=True,
        )
        replay_path = replay_dir / f"{replay_key}.json"
        if replay_path.exists() or replay_path.is_symlink():
            raise ApprovalRefused("native approval event was already consumed")

        authority_paths = {candidate.evidence}
        if candidate.kind == "story":
            authority_paths.update({
                candidate.path, run_state_path(approval_base),
                story_dir(approval_base, candidate.story) / "plan-meta.json",
            })
        for authority_path in authority_paths:
            _require_safe_destination(
                approval_base, authority_path, required=authority_path.exists())
        _require_safe_destination(approval_base, replay_path, required=False)
        _require_current_candidate(approval_base, candidate)
        replay_dir.mkdir(parents=True, exist_ok=True)
        _require_safe_destination(approval_base, replay_path, required=False)

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
        if candidate.previous_digest:
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
                _approve_story(approval_base, candidate, record)
                from .events import append_event
                append_event(
                    approval_base, "plan-approved", actor="planner-high",
                    story=candidate.story,
                    detail=candidate.path.relative_to(approval_base).as_posix(),
                )
            else:
                _approve_task(candidate, record)
        except Exception:
            _restore_files(snapshots, approval_base)
            raise
        if recorded_in is not None:
            recorded_in.append(str(approval_base.resolve()))
        return record
