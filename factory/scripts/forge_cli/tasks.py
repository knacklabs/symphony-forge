"""forge task plan save/approve — per-task implementation plan evidence."""
from __future__ import annotations

import argparse
from pathlib import Path

from factory_lib import (
    dump_json, evidence_path, load_json, now_iso,
    plan_digest_without_assumptions, repo_root, require_ready_task,
    run_state_path, validate_payload,
)

from .common import fail


def _task_plan_path(base: Path, task_id: str, *, for_write: bool = False) -> Path:
    state = load_json(run_state_path(base), default={})
    story = state.get("issue_key") or state.get("story")
    if not isinstance(story, str) or not story:
        fail("task plan requires an active story — run intake first")
    return evidence_path(
        base, story, f"task-plans/{task_id}.md", for_write=for_write,
    )


def cmd_plan_save(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    require_ready_task(base, args.id, require_approval=False)
    source = Path(args.source).expanduser()
    if not source.is_file():
        fail(f"task plan source {source} not found — pass the plan-mode file via --from")
    try:
        content = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail("task plan source must be UTF-8 Markdown")
    if not content.strip():
        fail("task plan source must not be empty")
    dest = _task_plan_path(base, args.id, for_write=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    print(f"Saved task plan: {dest.relative_to(base)}")


def cmd_approve(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    require_ready_task(base, args.id, require_approval=False)
    approved_by = args.by.strip()
    if not approved_by:
        fail("task approval requires a non-empty human name via --by")
    plan = _task_plan_path(base, args.id)
    if not plan.is_file():
        fail(
            f"task approval refused: no saved task plan for {args.id}. "
            f"Run `./forge task plan save {args.id} --from <path>` first."
        )
    state = load_json(run_state_path(base), default={})
    story = state.get("issue_key") or state.get("story")
    grill_path = evidence_path(
        base, story, f"grills/tasks/{args.id}.json", for_write=True,
    )
    grill = load_json(grill_path, default={})
    grill["approved_task_plan_sha256"] = plan_digest_without_assumptions(plan)
    grill["approved_by"] = approved_by
    grill["approved_at"] = now_iso()
    validate_payload(base, "grill", grill)
    dump_json(grill_path, grill)
    print(f"Approved task plan for {args.id} by {approved_by}")
