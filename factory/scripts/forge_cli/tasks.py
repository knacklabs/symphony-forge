"""forge task plan save/approve — per-task implementation plan evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

from factory_lib import (
    _committed_task_marker, _windows_reparse_point,
    clean_git_env, default_trunk_branch, dump_json, evidence_path,
    git_control_dir, load_json, now_iso, raw_open_flags,
    repo_root, require_approved_plan_digest,
    require_ready_task, task_digest,
    require_task_sealed,
    protected_decomposition_state_path, run_state_path,
    task_marker_on_main, task_marker_path,
)

from .common import fail


def _git(base: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=base, capture_output=True, text=True,
        env=clean_git_env(), encoding="utf-8", errors="surrogateescape",
    )


def _require_git(
        base: Path, description: str, *args: str, strip: bool = True) -> str:
    proc = _git(base, *args)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        fail(f"{description} failed" + (f": {detail}" if detail else ""))
    return proc.stdout.strip() if strip else proc.stdout


def _contained_regular_bytes(base: Path, source: Path, label: str) -> bytes:
    """Snapshot one contained authority file without following links."""
    try:
        relative = source.relative_to(base)
    except ValueError:
        fail(f"task start refused: {label} escapes the source worktree")
    current = base
    for part in relative.parts[:-1]:
        current /= part
        try:
            info = current.lstat()
        except OSError as exc:
            fail(f"task start refused: {label} ancestor is unreadable: {exc}")
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode)
                or _windows_reparse_point(current)):
            fail(f"task start refused: {label} ancestor is linked or not a directory")
    try:
        leaf = source.lstat()
    except OSError as exc:
        fail(f"task start refused: {label} is unreadable: {exc}")
    if (stat.S_ISLNK(leaf.st_mode) or not stat.S_ISREG(leaf.st_mode)
            or leaf.st_nlink != 1 or _windows_reparse_point(source)):
        fail(f"task start refused: {label} is linked or not a regular file")
    flags = raw_open_flags(os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        descriptor = os.open(source, flags)
    except OSError as exc:
        fail(f"task start refused: {label} is not a readable regular file: {exc}")
    try:
        before = os.fstat(descriptor)
        if (stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or getattr(before, "st_file_attributes", 0)
                & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            fail(f"task start refused: {label} is linked or not a regular file")
        chunks = []
        while chunk := os.read(descriptor, 65536):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if ((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)):
            fail(f"task start refused: {label} changed during hydration")
        leaf = source.lstat()
        if ((leaf.st_dev, leaf.st_ino) != (after.st_dev, after.st_ino)
                or stat.S_ISLNK(leaf.st_mode) or leaf.st_nlink != 1
                or _windows_reparse_point(source)):
            fail(f"task start refused: {label} identity changed during hydration")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _optional_contained_regular_bytes(
        base: Path, source: Path, label: str) -> bytes | None:
    """Return one safe optional source snapshot, or None when it is absent.

    Checking the leaf with ``lstat`` alone would mistake a broken symlinked
    ancestor for an absent optional file. Walk existing ancestors first so a
    linked/reparse parent is still refused, then delegate the actual byte
    snapshot and identity checks to the shared contained-file helper.
    """
    try:
        relative = source.relative_to(base)
    except ValueError:
        return _contained_regular_bytes(base, source, label)
    current = base
    for part in relative.parts[:-1]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            return None
        except OSError:
            return _contained_regular_bytes(base, source, label)
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode)
                or _windows_reparse_point(current)):
            return _contained_regular_bytes(base, source, label)
    try:
        source.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        return _contained_regular_bytes(base, source, label)
    return _contained_regular_bytes(base, source, label)


def _default_branch(base: Path) -> str:
    """The integration branch a task PR targets: origin's default branch, not a
    hardcoded 'main'. Delegates to the single canonical resolver so PR targeting,
    the task-start base, task markers, and the review diff all agree on the trunk."""
    return default_trunk_branch(base)


def _task_plan_path(base: Path, task_id: str, *, for_write: bool = False) -> Path:
    state = load_json(run_state_path(base), default={})
    story = state.get("issue_key") or state.get("story")
    if not isinstance(story, str) or not story:
        from .story import ensure_active_pointer
        story = ensure_active_pointer(base)
    if not isinstance(story, str) or not story:
        fail("task plan requires an active story. Start a new one with intake, or "
             "if a decomposed story lost its git-local pointer on this checkout, "
             "rebuild it with `forge story resume <key>`.")
    return evidence_path(
        base, story, f"task-plans/{task_id}.md", for_write=for_write,
    )


# A task plan is read by two people the author is not: the human approving it,
# and whoever has to confirm the thing actually works. Neither is served by a
# file-by-file work order, so these sections are required rather than suggested
# (decision 0050). A diagram is asked for in words, not enforced: a fenced
# ```mermaid block is the cheap way to render one on the board, and demanding
# one mechanically would only produce box-and-arrow filler.
REQUIRED_TASK_PLAN_SECTIONS = (
    ("## Workflow", "the end-to-end flow this task builds or changes — what "
                    "moves through it, and where this task starts and stops. "
                    "A ```mermaid diagram renders on the board and is worth "
                    "far more than prose here"),
    ("## Manual Verification", "the steps a human runs to see it work, in "
                               "order, with what they should observe. "
                               "Automated tests prove it did not break; this "
                               "is how someone confirms it does the job"),
)


def require_task_plan_sections(content: str, task_id: str) -> None:
    lowered = content.lower()
    missing = [
        (heading, why) for heading, why in REQUIRED_TASK_PLAN_SECTIONS
        # Match the heading text, not its exact level: an author who writes
        # `### Workflow` inside a deeper structure has still written it.
        if heading.lstrip("# ").lower() not in lowered
    ]
    if missing:
        detail = "; ".join(f"{heading} — {why}" for heading, why in missing)
        fail(f"task plan for {task_id} is missing {len(missing)} required "
             f"section(s): {detail}. Add them and re-save.")


def cmd_plan_save(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    require_ready_task(
        base, args.id, require_approval=False, require_grill=False,
    )
    source = Path(args.source).expanduser()
    if not source.is_file():
        fail(f"task plan source {source} not found — pass the plan file via --from")
    try:
        content = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail("task plan source must be UTF-8 Markdown")
    if not content.strip():
        fail("task plan source must not be empty")
    require_task_plan_sections(content, args.id)
    dest = _task_plan_path(base, args.id, for_write=True)
    state = load_json(run_state_path(base), default={})
    story = state.get("issue_key") or state.get("story")
    grill_path = evidence_path(
        base, story, f"grills/tasks/{args.id}.json", for_write=True,
    )
    grill = load_json(grill_path, default={})
    if grill_path.exists() and (
            not isinstance(grill, dict) or "task_plan_sha256" not in grill):
        fail(f"task plan save refused: {args.id} has a legacy task grill. Run "
             "`forge upgrade` to retire the old format before saving.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    # The plan carries a RENDERED copy of its contract, never a hand-written
    # one, so the reader sees scope, tests and criteria that cannot drift.
    from factory_lib import (
        protected_decomposition_state_path, refresh_task_plan_contract,
    )
    contract = next((t for t in load_json(
        protected_decomposition_state_path(base), default={}).get("tasks", [])
        if isinstance(t, dict) and t.get("id") == args.id), None)
    if contract:
        refresh_task_plan_contract(base, args.id, contract)
    print(f"Saved task plan: {dest.relative_to(base)}")


def cmd_task_start(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    state = load_json(run_state_path(base), default={})
    key = state.get("issue_key") or state.get("story")
    if not isinstance(key, str) or not key:
        from .story import ensure_active_pointer
        key = ensure_active_pointer(base)
    if not isinstance(key, str) or not key:
        fail("task start requires an active story. Start a new one with intake, or "
             "if a decomposed story lost its git-local pointer on this checkout "
             "(e.g. a fresh trunk clone between tasks), rebuild it with "
             "`forge story resume <key>`.")
    bound_task = state.get("task_id")
    if bound_task not in (None, "", args.id):
        fail(f"task start refused: this checkout is owned by task {bound_task!r}, "
             f"not {args.id!r}")
    approved_plan_sha256 = require_approved_plan_digest(base)
    decomposition_path = protected_decomposition_state_path(base)
    decomposition_bytes = _contained_regular_bytes(
        git_control_dir(base), decomposition_path, "protected decomposition source",
    )
    try:
        decomposition = json.loads(decomposition_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail(f"task start refused: protected decomposition is invalid JSON: {exc}")
    if not isinstance(decomposition, dict):
        fail("task start refused: protected decomposition is not a JSON object")
    if decomposition.get("story") not in (None, key):
        fail(f"task start refused: protected decomposition belongs to "
             f"{decomposition.get('story')!r}, not {key!r}")
    if decomposition.get("plan_sha256") != approved_plan_sha256:
        fail("task start refused: protected decomposition is not bound to the "
             "approved story plan; re-record the decomposition")
    tasks = decomposition.get("tasks") or []
    index = next(
        (position for position, task in enumerate(tasks)
         if isinstance(task, dict) and task.get("id") == args.id),
        None,
    )
    if index is None:
        fail(f"{args.id!r} is not a task in the protected decomposition")
    task = tasks[index]
    if task.get("id") != args.id:
        fail("task start refused: task identity does not match the protected "
             "decomposition")
    task_marker_path(key, args.id)  # validates both branch/path components

    trunk = default_trunk_branch(base)
    _require_git(base, f"fetching origin/{trunk}", "fetch", "origin", trunk)
    # The gate is the dependency graph, not the list order: a task starts once
    # every task it depends on has its marker on the trunk, so independent
    # tasks start side by side in their own worktrees.
    from factory_lib import task_dependencies
    shipped = {
        task.get("id") for task in tasks
        if task_marker_on_main(base, key, task.get("id"), refresh=False)
    }
    waiting = [d for d in task_dependencies(tasks, args.id) if d not in shipped]
    if waiting:
        markers = ", ".join(task_marker_path(key, d).as_posix() for d in waiting)
        fail(
            f"task {args.id} cannot start: dependency {', '.join(waiting)} marker "
            f"is absent from fetched origin/{trunk} ({markers})"
        )
    scope = task.get("write_scope")
    if (not isinstance(scope, list) or not scope
            or any(not isinstance(path, str) or not path.strip()
                   or Path(path).is_absolute()
                   or ".." in Path(path).parts for path in scope)):
        fail(f"task start refused: {args.id} has no protected in-repository write_scope")
    base_main_sha = _require_git(
        base, f"resolving fetched origin/{trunk}", "rev-parse", "--verify",
        f"origin/{trunk}^{{commit}}",
    )

    branch = f"feat/{key}-{args.id}"
    worktree = base.parent / f"{base.name}-{key}-{args.id}"
    if _git(base, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
        fail(f"task branch already exists: {branch}")
    if worktree.exists() or worktree.is_symlink():
        fail(f"task worktree already exists: {worktree}")

    plan_file = state.get("plan_file")
    if not isinstance(plan_file, str) or not plan_file:
        fail("task start requires the approved plan path in the run pointer")
    plan_source = Path(plan_file)
    if not plan_source.is_absolute():
        plan_source = base / plan_source
    try:
        plan_relative = plan_source.relative_to(base)
    except ValueError:
        fail(f"approved plan path escapes the planning worktree: {plan_file!r}")
    if (
        plan_relative.parent.as_posix() != "plans/active"
        or not plan_relative.name.startswith(f"{key}-")
    ):
        fail(f"approved plan must be plans/active/{key}-*.md")
    plan_bytes = _contained_regular_bytes(
        base, plan_source, "approved plan source",
    )

    decomposition_relative = (
        Path(".factory") / "stories" / key / "decomposition.json"
    )
    approval_source = evidence_path(base, key, "plan-approval.json")
    approval_bytes = _contained_regular_bytes(
        base, approval_source, "story approval source",
    )
    try:
        approval = json.loads(approval_bytes)
    except (UnicodeError, json.JSONDecodeError) as exc:
        fail(f"task start refused: story approval source is invalid JSON: {exc}")
    if not isinstance(approval, dict):
        fail("task start refused: story approval source is not a JSON object")
    approval_event_key = hashlib.sha256(
        f"{approval.get('runtime')}\0{approval.get('session_id')}\0"
        f"{approval.get('event_id')}".encode("utf-8")
    ).hexdigest()
    approval_event_source = evidence_path(
        base, key, f"approval-events/{approval_event_key}.json",
    )
    approval_event_bytes = _contained_regular_bytes(
        base, approval_event_source, "story approval event source",
    )
    approval_relative = Path(".factory") / "stories" / key / "plan-approval.json"
    event_relative = (
        Path(".factory") / "stories" / key / "approval-events"
        / f"{approval_event_key}.json"
    )
    # Keep one no-follow byte snapshot for every source before the target
    # worktree is allocated. Approval bytes remain the authenticated records
    # selected above; they are intentionally copied verbatim into the target.
    authenticated = {
        approval_relative: approval_bytes,
        event_relative: approval_event_bytes,
    }
    snapshots: dict[Path, bytes] = {
        plan_relative: plan_bytes,
        decomposition_relative: decomposition_bytes,
        **authenticated,
    }
    # Plan content can hydrate a successor workspace, but its source grill is
    # approval authority and must be recorded afresh in the new target.
    optional_sources = {
        Path(".factory") / "stories" / key / "task-plans" / f"{args.id}.md":
            evidence_path(base, key, f"task-plans/{args.id}.md"),
    }
    for relative, source in optional_sources.items():
        optional_bytes = _optional_contained_regular_bytes(
            base, source, "optional source",
        )
        if optional_bytes is not None:
            snapshots[relative] = optional_bytes
    payloads: dict[Path, bytes] = dict(snapshots)
    stages_bytes = (json.dumps({
        "issue": key,
        "stages": [
            {
                "id": task.get("id"),
                "title": task.get("title"),
                "status": "done" if task.get("id") in shipped else "pending",
            }
            for task in tasks
        ],
    }, indent=2) + "\n").encode()

    _require_git(
        base, "creating task worktree", "worktree", "add", str(worktree),
        "-b", branch, base_main_sha,
    )
    try:
        # Preflight every destination before deleting inherited approval or
        # writing any hydration payload into the newly allocated worktree.
        from .scaffold import assert_target_file_destination
        target_grill = assert_target_file_destination(
            worktree,
            worktree / ".factory" / "stories" / key / "grills" / "tasks"
            / f"{args.id}.json",
        )
        destinations = {
            relative: assert_target_file_destination(worktree, worktree / relative)
            for relative in payloads
        }
        control = git_control_dir(worktree)
        control_destinations = {
            name: assert_target_file_destination(control, control / name)
            for name in ("decomposition.json", "stages.json", "run.json")
        }

        # A fetched trunk can contain this task's earlier approval record. Keep
        # it in Git history, but require a fresh target grill and approval.
        if target_grill.exists() or target_grill.is_symlink():
            target_grill.unlink()
        for relative, content in payloads.items():
            destination = destinations[relative]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        control.mkdir(parents=True, exist_ok=True)
        control_destinations["decomposition.json"].write_bytes(decomposition_bytes)
        control_destinations["stages.json"].write_bytes(stages_bytes)
        dump_json(control_destinations["run.json"], {
            **state,
            "issue_key": key,
            "story": key,
            "task_id": args.id,
            "branch": branch,
            "base_main_sha": base_main_sha,
            "approved_plan_sha256": approved_plan_sha256,
            "decomposition_plan_sha256": decomposition.get("plan_sha256"),
            "task_sha256": task_digest(task),
        })
    except BaseException:
        removed = _git(base, "worktree", "remove", "--force", str(worktree))
        if removed.returncode:
            detail = removed.stderr.strip() or removed.stdout.strip()
            fail("task start hydration refused and cleanup failed"
                 + (f": {detail}" if detail else ""))
        deleted = _git(base, "branch", "-D", branch)
        if deleted.returncode:
            detail = deleted.stderr.strip() or deleted.stdout.strip()
            fail("task start hydration refused and cleanup failed"
                 + (f": {detail}" if detail else ""))
        raise
    print(f"Started task {args.id}: {branch} at {worktree} ({base_main_sha})")


def cmd_task_reopen(args: argparse.Namespace) -> None:
    """Reopen a done-but-unshipped task: move the frontier back to it (and the
    unshipped done-tail built on top of it) so it can be re-grilled and
    re-implemented. Refused for shipped work — that is immutable; add a new
    follow-up task instead."""
    from forge_cli.stages import load_stages, write_stages
    base = Path(args.repo).resolve() if args.repo else repo_root()
    state = load_json(run_state_path(base), default={})
    key = state.get("issue_key") or state.get("story")
    if not isinstance(key, str) or not key.strip():
        from .story import ensure_active_pointer
        key = ensure_active_pointer(base)
    if not isinstance(key, str) or not key.strip():
        fail("reopen requires an active story. Start a new one with intake, or "
             "if a decomposed story lost its git-local pointer on this checkout, "
             "rebuild it with `forge story resume <key>`.")
    data = load_stages(base)
    stages = data.get("stages") or []
    idx = next((i for i, s in enumerate(stages) if s.get("id") == args.id), None)
    if idx is None:
        fail(f"task {args.id} is not in the current decomposition")
    target = stages[idx]
    # A done task reopens. So does an ACTIVE task that closed `--incomplete`: the
    # harness's own "partial work" marker leaves the stage active on purpose,
    # and the only way forward from a stage that cannot close (an empty
    # measured diff after a reopen) is to reopen it with the right base.
    status = target.get("status")
    if not (status == "done" or (status == "active" and target.get("incomplete"))):
        fail(f"task {args.id} is '{status}', not done (or active-and-incomplete). "
             "An active task's contract is amended in place, and a pending task "
             "has not started.")
    # The base the task's work started from survives the reopen: `stage start`
    # pins the stage ref to it, so the reopened stage measures the task's real
    # delta instead of an empty diff from today's HEAD (symphony-forge #171).
    # `--base` names it explicitly when the record no longer carries it.
    explicit = (getattr(args, "base", None) or "").strip()
    if explicit:
        resolved = _git(base, "rev-parse", "--verify", "--quiet", f"{explicit}^{{commit}}")
        if resolved.returncode != 0:
            fail(f"--base {explicit} is not a commit in this repository")
        explicit = resolved.stdout.strip()
        if _git(base, "merge-base", "--is-ancestor", explicit, "HEAD").returncode != 0:
            fail(f"--base {explicit[:12]} is not an ancestor of HEAD")
    reopen_base = explicit or target.get("reopen_base_sha") or target.get("base_sha") or ""
    # Shipped work is immutable. The task marker rides onto the integration branch
    # at merge; if it is there, the work is shipped — add a follow-up task instead.
    default_branch = _default_branch(base)
    marker = task_marker_path(key, args.id)
    fetched = _git(base, "fetch", "origin", default_branch)
    if fetched.returncode == 0:
        present = _git(base, "cat-file", "-e",
                       f"origin/{default_branch}:{marker.as_posix()}")
        if present.returncode == 0:
            fail(f"task {args.id} is already SHIPPED (its marker is on "
                 f"origin/{default_branch}); shipped work is immutable — add a new "
                 "follow-up task rather than reopening it.")
    else:
        print(f"WARNING: could not reach origin/{default_branch} to confirm "
              f"{args.id} is unshipped; proceeding on local state. Do NOT reopen a "
              "task whose PR has already merged.")
    if getattr(args, "review_fix", False):
        from forge_cli.stages import reopen_stage_for_review_fix
        target = reopen_stage_for_review_fix(base, args.id)
        print(f"Reopened {args.id} -> active for a review fix (round "
              f"{target['review_fix_count']}): base, contract and plan approval "
              f"stand. Delegate the fixes, commit, then `forge task close {args.id}` "
              "(it re-reviews the new diff, closes and seals).")
        return
    # Reopening ripples forward: the done-tail built on this task has a changed
    # base, so it returns to pending too. Clear the evidence so every reopened
    # stage is re-grilled + re-implemented from scratch.
    reopened = []
    for stage in stages[idx:]:
        if stage.get("status") not in ("done", "active"):
            continue
        for field in ("task_sha256", "local_review_stamp", "completed_at",
                      "started_at", "base_sha", "dirty_at_start",
                      "contract_changed", "incomplete"):
            stage.pop(field, None)
        stage["status"] = "pending"
        reopened.append(stage.get("id"))
    if reopen_base:
        stages[idx]["reopen_base_sha"] = reopen_base
    write_stages(base, data)
    print(
        f"Reopened {', '.join(reopened)} -> pending; the frontier is back at "
        f"{args.id}. Re-grill and re-implement from there. The plan approval is now "
        "STALE — re-present the change to the human and re-approve before the next "
        "stage start / delegate."
    )


def cmd_task_pr_ready(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    seal_task(base, args.id)


def seal_task(base: Path, task_id: str) -> None:
    """Write the task marker, push the branch, open (or find) its PR.

    Idempotent: a marker already committed at this HEAD is not rewritten, a
    push of an up-to-date branch is a no-op, and an open PR for the branch is
    reported rather than duplicated. `task close` ends here.
    """
    class _Args:
        pass
    args = _Args()
    args.id = task_id
    task = require_task_sealed(base, args.id)
    state = load_json(run_state_path(base), default={})
    key = state.get("issue_key") or state.get("story")
    if not isinstance(key, str) or not key.strip():
        fail("task PR marker requires a non-empty story in the task run pointer")

    # A task started via `forge stage start` (not `forge task start`) has no
    # branch/base pointer in run.json. Derive both from git so the stage-based
    # per-task PR flow seals cleanly instead of dead-ending — the branch is
    # wherever the sealed work lives, the base is where it forked from the
    # integration branch.
    default_branch = _default_branch(base)
    branch = state.get("branch")
    if not isinstance(branch, str) or not branch.strip():
        branch = _require_git(
            base, "resolving current branch", "rev-parse", "--abbrev-ref", "HEAD",
        )
        if branch == "HEAD":
            fail("task PR ready: detached HEAD — check out the task branch first")
    base_main_sha = state.get("base_main_sha")
    if not isinstance(base_main_sha, str) or not base_main_sha.strip():
        base_main_sha = _require_git(
            base, "resolving integration base", "merge-base",
            f"origin/{default_branch}", "HEAD",
        )

    commit = _require_git(
        base, "resolving task HEAD", "rev-parse", "--verify", "HEAD^{commit}",
    )
    marker = task_marker_path(key, args.id)
    try:
        existing = load_json(base / marker, default=None)
    except json.JSONDecodeError:
        existing = None
    reusable, marker_problem = _committed_task_marker(
        base, key, args.id, existing, None,
    )
    if marker_problem:
        fail(marker_problem)

    from factory_lib import (
        effective_review_base, product_delta_digest, task_proof_problems,
    )
    product_unchanged = bool(
        reusable
        and reusable["branch"] == branch
        and reusable["base_main_sha"] == base_main_sha
        and product_delta_digest(base, reusable["commit"], commit)
        == hashlib.sha256(b"").hexdigest()
    )
    same_seal = False
    if product_unchanged:
        proof_problems = task_proof_problems(base, key, task)
        if proof_problems:
            fail("Task proof changed after its marker:\n- " + "\n- ".join(proof_problems))
        same_seal = True
    if same_seal:
        commit = reusable["commit"]
        print(f"Task {args.id} already sealed at {commit[:12]}; the product "
              "and proof have not moved since. Marker committed.")
    else:
        from factory_lib import read_selected_review_generation, review_lineage_paths
        from .delegate import delegation_exclusion
        with delegation_exclusion(base, args.id, kind="review-selection"):
            task = require_task_sealed(base, args.id)
            generation, selection, review_problems = read_selected_review_generation(
                base, key, args.id,
            )
            if review_problems or not isinstance(generation, dict) \
                    or not isinstance(selection, dict):
                fail("task PR marker requires one valid selected review generation: "
                     + "; ".join(review_problems or ["selection is missing"]))
            payload = {
                "task_id": args.id,
                "branch": branch,
                "base_main_sha": base_main_sha,
                "review_base_sha": effective_review_base(base, args.id, commit),
                "commit": commit,
                "sealed_at": now_iso(),
            }
            if any(not isinstance(value, str) or not value.strip()
                   for value in payload.values()):
                fail("task PR marker fields must all be non-empty strings")
            selection_path = marker.parent / "reviews" / "selected.json"
            brief_path = Path(".factory/review-briefs/all.md")
            selected_paths = [
                selection_path, *review_lineage_paths(base, key, args.id), brief_path,
            ]
            if any(not (base / path).is_file() for path in selected_paths):
                fail("task PR marker requires the complete review lineage and saved brief")
            dump_json(base / marker, payload)
            # The proof `task close` recorded ships in the marker commit: the
            # PR gate reads verify.json and tests.json from the sealed tree and
            # refuses a path changed after the marker (0079).
            evidence_paths = [
                path for path in (marker.parent / "verify.json",
                                  marker.parent / "tests.json")
                if (base / path).is_file()
            ]
            proof_paths = [marker, *selected_paths, *evidence_paths]
            # Exclusion keeps the selected pointer and its complete lineage fixed
            # from proof validation through the marker commit.
            _require_git(base, "staging the task PR marker and selected review", "add", "--",
                         *(path.as_posix() for path in proof_paths))
            _require_git(
                base, "committing the task PR marker", "commit", "--only", "-m",
                f"{key} {args.id}: task PR marker", "--",
                *(path.as_posix() for path in proof_paths),
            )
    _require_git(base, "pushing the task branch", "push", "-u", "origin", branch)

    if shutil.which("gh", path=os.environ.get("PATH")) is None:
        fail(
            f"task {args.id} is sealed at {marker.as_posix()}, but gh is unavailable. "
            "Install GitHub CLI, run `gh auth login`, then retry to open the PR."
        )
    title = f"{key} {args.id}: {task.get('title', '').strip()}".rstrip(": ")
    from .review import rejected_findings_report
    rejected = rejected_findings_report(base, key, args.id)
    body = (
        f"Task marker: {marker.as_posix()}\n\n"
        f"Sealed commit: {commit}\n"
        + (f"\n{rejected}" if rejected else "")
    )
    # Resolve owner/repo from origin so `gh` targets THIS repo — a bare
    # `gh pr create` can resolve a PR number against the wrong repo when a
    # local checkout tracks a differently-numbered upstream.
    origin_url = _require_git(base, "resolving origin url", "remote", "get-url", "origin")
    slug = re.sub(r"^.*github\.com[:/]", "", origin_url).removesuffix(".git")
    cmd = ["gh", "pr", "create", "--base", default_branch, "--head", branch,
           "--title", title, "--body", body]
    if slug and "/" in slug:
        cmd += ["--repo", slug]
    proc = subprocess.run(
        cmd, cwd=base, capture_output=True, text=True,
        encoding="utf-8", errors="surrogateescape",
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        # A PR for this branch may already exist (a retry after a push that
        # succeeded, or a re-seal): that is the ship, not a failure.
        existing = subprocess.run(
            ["gh", "pr", "view", branch, "--json", "url,state",
             "--jq", 'select(.state == "OPEN") | .url']
            + (["--repo", slug] if slug and "/" in slug else []),
            cwd=base, capture_output=True, text=True, encoding="utf-8",
        )
        url = existing.stdout.strip() if existing.returncode == 0 else ""
        if url:
            print(f"Task {args.id} PR ready: {marker.as_posix()}")
            print(f"PR already open for {branch}: {url}")
            return
        auth_guidance = (
            "Run `gh auth login`, then retry."
            if re.search(
                r"(?i)authentication failed|not authenticated|not logged (?:in|into)|"
                r"bad credentials|http 401|gh auth login",
                detail,
            )
            else "Inspect the GitHub CLI failure, fix that exact cause, then retry."
        )
        fail(
            f"task {args.id} is sealed at {marker.as_posix()}, but opening the PR "
            f"to {default_branch} failed{f': {detail}' if detail else ''}. "
            f"{auth_guidance}"
        )
    print(f"Task {args.id} PR ready: {marker.as_posix()}")
    if proc.stdout.strip():
        print(proc.stdout.strip())


def cmd_task_reconcile(args: argparse.Namespace) -> None:
    """Adopt a task that was merged to the trunk OUT OF BAND — via a story-level
    PR or a direct PR — without ever running `forge task pr-ready`. It writes the
    task's completion marker and flips its stage to done so the frontier stops
    reporting the task 'await-merge' forever and advances to the next one.

    This is the sanctioned reconcile for the run-pointer drift that happens when
    work ships outside the per-task PR flow. It verifies the work is genuinely on
    the trunk, opens NO new PR, and records a `stage-reconciled` event so the
    bypass is on the timeline. The regular `stage done` gates (a non-empty delta,
    a bound delegate launch, a fresh review stamp) are all unsatisfiable for
    already-merged work, which is exactly why they cannot close it.
    """
    from forge_cli.stages import load_stages, write_stages, task_for
    from forge_cli.events import append_event
    from factory_lib import task_digest

    base = Path(args.repo).resolve() if args.repo else repo_root()
    state = load_json(run_state_path(base), default={})
    key = state.get("issue_key") or state.get("story")
    if not isinstance(key, str) or not key.strip():
        from .story import ensure_active_pointer
        key = ensure_active_pointer(base)
    if not isinstance(key, str) or not key.strip():
        fail("reconcile requires an active story. Start a new one with intake, or "
             "if a decomposed story lost its git-local pointer on this checkout, "
             "rebuild it with `forge story resume <key>`.")

    data = load_stages(base)
    stages = data.get("stages") or []
    idx = next((i for i, s in enumerate(stages) if s.get("id") == args.id), None)
    if idx is None:
        fail(f"task {args.id} is not in the current decomposition")
    stage = stages[idx]
    status = stage.get("status")

    task = task_for(base, args.id)
    if not task:
        fail(f"task {args.id} has no contract in the decomposition; cannot reconcile.")

    default_branch = _default_branch(base)
    marker = task_marker_path(key, args.id)

    fetched = _git(base, "fetch", "origin", default_branch)
    if fetched.returncode != 0:
        fail(f"reconcile needs origin/{default_branch} to confirm {args.id} shipped, "
             "but the fetch failed. Reconcile only a task whose PR has actually "
             "merged, on a checkout that can reach origin.")

    already = _git(
        base, "cat-file", "-e", f"origin/{default_branch}:{marker.as_posix()}",
    ).returncode == 0
    readopt = (getattr(args, "readopt", None) or "").strip()
    if readopt and not already:
        fail(f"--readopt adopts a task whose marker is already on origin/"
             f"{default_branch}; {args.id} has none there. Reconcile it plainly.")
    if readopt and len(readopt) < 12:
        fail("--readopt takes the reason (a dozen characters at least): why this "
             "task's recorded proof cannot satisfy the current proof predicate")

    # A task whose work shipped out of band is PENDING on every checkout that did
    # not run it — a fresh clone, a sibling worktree, or this one after a
    # decomposition re-record rebuilt the tracker. Refusing pending outright made
    # reconcile unusable in exactly the case it exists for. The marker already on
    # the trunk is the proof that it shipped, so pending is allowed when it is
    # there; without it, a pending task still has nothing to adopt.
    if status not in ("active", "done") and not already:
        fail(f"task {args.id} is '{status}' and no marker for it is on origin/"
             f"{default_branch} — reconcile adopts a task whose work already "
             "SHIPPED; a task that never started has nothing to reconcile.")

    if not already:
        # Confirm the task's work is genuinely on the trunk before adopting it: at
        # least one of its write_scope paths must resolve on origin/<trunk>. This
        # guards against reconciling work that never actually shipped.
        write_scope = [p.rstrip("/") for p in (task.get("write_scope") or [])
                       if isinstance(p, str) and p.strip()]
        on_trunk = any(
            _git(base, "cat-file", "-e",
                 f"origin/{default_branch}:{path}").returncode == 0
            for path in write_scope
        )
        if write_scope and not on_trunk:
            fail(f"none of {args.id}'s write_scope paths are on origin/"
                 f"{default_branch} — its work does not look shipped. Reconcile "
                 "only a genuinely merged task (or ship it with `forge task "
                 "pr-ready`).")

        commit = args.commit or _require_git(
            base, "resolving trunk head", "rev-parse", "--verify",
            f"origin/{default_branch}^{{commit}}")
        if args.commit:
            anc = _git(base, "merge-base", "--is-ancestor", commit,
                       f"origin/{default_branch}")
            if anc.returncode != 0:
                fail(f"--commit {commit} is not an ancestor of origin/"
                     f"{default_branch}; pass the merge commit of the task's PR.")
        recorded_base = stage.get("base_sha")
        pointer_base = state.get("base_main_sha")
        base_main_sha = (
            (recorded_base if isinstance(recorded_base, str) and recorded_base else None)
            or (pointer_base if isinstance(pointer_base, str) and pointer_base else None)
            or _require_git(base, "resolving integration base", "merge-base",
                            f"origin/{default_branch}", commit)
        )
        branch = args.branch or f"feat/{key}-{args.id}"
        payload = {
            "task_id": args.id,
            "branch": branch,
            "base_main_sha": base_main_sha,
            "commit": commit,
            "sealed_at": now_iso(),
        }
        if any(not isinstance(value, str) or not value.strip()
               for value in payload.values()):
            fail("reconcile marker fields must all be non-empty strings")
        # Marks the marker as ADOPTED, not sealed: the PR proof gate
        # (check_task_proof.py) does not demand recorded proof for work that was
        # already on the trunk before the harness learned about it. It cannot be
        # abused to skip proof for new work — reconcile refuses unless the work
        # is genuinely on the trunk already.
        payload["reconciled"] = True
        dump_json(base / marker, payload)
    elif readopt:
        # The marker on the trunk is real and its work shipped; only its proof
        # predates the current predicate (a proof-format change, or proof that
        # never reached the trunk). Re-mark it ADOPTED with its own identity
        # untouched, so every gate reads it the way it reads any adopted task.
        shipped = _require_git(
            base, "reading the trunk marker", "show",
            f"origin/{default_branch}:{marker.as_posix()}")
        try:
            payload = json.loads(shipped)
        except json.JSONDecodeError as exc:
            fail(f"the marker for {args.id} on origin/{default_branch} is not JSON: {exc}")
        if not isinstance(payload, dict) or payload.get("task_id") != args.id:
            fail(f"the marker for {args.id} on origin/{default_branch} is not its own")
        if payload.get("reconciled") is True:
            print(f"{args.id} is already adopted on origin/{default_branch}.")
        payload["reconciled"] = True
        dump_json(base / marker, payload)

    # Flip the stage to done directly (bypassing the unsatisfiable stage-done
    # gates) and stamp its task digest so the row reads 'done' locally too.
    if status != "done":
        stage["status"] = "done"
        stage["completed_at"] = now_iso()
    if not stage.get("task_sha256"):
        stage["task_sha256"] = task_digest(task)
    write_stages(base, data)
    append_event(base, "stage-reconciled", actor="orchestrator", story=key,
                 detail=(f"{args.id} re-adopted: {readopt} (trunk marker re-marked "
                         "reconciled, no PR)" if readopt else
                         f"{args.id} adopted as shipped out of band "
                         f"(marker {'confirmed on trunk' if already else 'written'}, "
                         "no PR)"))

    # Commit the marker + committed stage mirror as an evidence-only commit the
    # command owns. No push, no PR — the work already shipped; this records it so
    # the marker can land on the trunk via the reconcile PR.
    candidates = [marker.as_posix(), ".factory/stages.json",
                  f".factory/stories/{key}/stages.json"]
    to_add = [path for path in candidates if (base / path).is_file()]
    if to_add:
        _git(base, "add", "--", *to_add)
    if _git(base, "diff", "--cached", "--quiet").returncode != 0:
        _require_git(base, "committing the reconcile marker", "commit", "-m",
                     f"{key} {args.id}: task reconcile marker "
                     f"({'re-adopted: ' + readopt if readopt else 'adopted as shipped'})")
        print(f"Reconciled {args.id}: marker {marker.as_posix()} written, stage "
              "done, evidence committed. Push this branch and open a PR so the "
              f"marker lands on origin/{default_branch}, then rerun `forge next`.")
    else:
        print(f"Reconciled {args.id}: stage done and marker present; nothing new "
              "to commit.")
