"""forge stage — per-task execution tracker (.factory/stages.json).

The recorded decomposition is immutable evidence; this file is the mutable
execution state derived from it (one stage per leaf task, list order =
execution order). The loop per stage (WORKFLOW.md "Stage Loop", decision
0007): implement via /codex:rescue → inspect the diff → validate assumption
rows → smallest checks → LOCAL autoreview until clean → commit →
`forge stage done`. `pr_ready` refuses while any stage is not done. Task-
scoped: archived to .factory/history/<issue>/ and cleaned at ship.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from factory_lib import (
    active_story_key, clean_git_env, decomposition_state_path, dump_json,
    evidence_path, factory_dir, git_control_dir, head_sha, load_json, now_iso,
    raw_run_state,
    plan_digest_without_assumptions, product_tree_digest,
    protected_decomposition_state_path, repo_root, require_approved_plan_digest,
    require_ready_task, require_task_worktree, run_state_path,
    safe_factory_write_json, sha256_of, story_dir, task_digest,
    proof_path, proof_read_path, task_evidence_path, validate_payload,
)

from .common import fail
from .events import append_event

# The workflow writes these itself while a stage runs — the events ledger, the
# stage tracker, an assumption row appended to the active plan. They are not
# the product change under measurement, so write_scope does not have to name
# them. Deliberately NARROWER than pr_ready's EVIDENCE_PATHS: that list exempts
# all of `factory/` and `docs/`, which in the harness's own repo is the product
# — exempting it here would make the scope check vacuous exactly where it is
# being dogfooded.
# `docs/context/ledger.json` is written by `forge context scan`, which the
# harness runs itself during a stage — a coordinator never authors it as
# product, but stage done refused on it as an out-of-scope path, which is one of
# the refusals that made shipping around the flow look necessary. Named exactly,
# so the rest of `docs/` stays product.
WORKFLOW_PATHS = (".factory/", "plans/", "docs/context/ledger.json")
# In a repo that VENDORED the harness, factory/ and the vendored adapters/canon
# are infrastructure a `forge upgrade` may rewrite mid-task — not the task's
# product; pr_ready.EVIDENCE_PATHS already treats them so. The SOURCE harness
# repo builds these AS product (no constitution/VENDORED_FROM marker), so it
# keeps the strict set and the per-task scope check stays honest when dogfooding.
HARNESS_MACHINERY_PATHS = (
    "factory/", ".claude/", ".codex/", "constitution/",
    "harness/", ".gstack/",
    # NOT ".github/": the harness vendors no workflow into a client (no
    # VENDOR_MANIFEST.json entry is under .github/), so a client's CI is its
    # OWN product. Excluding the prefix reset it to the task base inside the
    # review bundle, which made any acceptance criterion that requires a CI
    # change permanently unprovable — the lens saw a local gate wired to a
    # step that was not there and correctly called the criterion partial.
    # Top-level vendored harness FILES (not directories) that `forge upgrade`
    # rewrites and a client never authors as its own product. Excluding them
    # keeps the per-task scope/dirt check honest when the coordinator's own
    # harness patch left one dirty at stage start (startswith matches the
    # exact filename; no product file shares these prefixes).
    "WORKFLOW.md",
)


def workflow_prefixes(base: Path) -> tuple[str, ...]:
    """Path prefixes that never count as a task's product change. Extended with
    the harness machinery only in a vendored client (see vendored_client)."""
    from factory_lib import vendored_client
    return (WORKFLOW_PATHS + HARNESS_MACHINERY_PATHS
            if vendored_client(base) else WORKFLOW_PATHS)


# A decision record written mid-stage is the workflow's own bookkeeping (the
# coordinator answering a signal), never a write_scope stray.
MEASURE_EXEMPT_PATHS = ("docs/decisions/",)


def measure_prefixes(base: Path) -> tuple[str, ...]:
    """Prefixes `stage done` leaves out of the measured product delta."""
    return workflow_prefixes(base) + MEASURE_EXEMPT_PATHS


DEFAULT_REVIEW_BUDGET_FILES = 8
DEFAULT_REVIEW_BUDGET_LINES = 400


def review_budget(task: dict) -> tuple[int, int, str]:
    """Return the validated per-task review budget, including defaults."""
    if "review_budget" not in task:
        return DEFAULT_REVIEW_BUDGET_FILES, DEFAULT_REVIEW_BUDGET_LINES, ""
    budget = task["review_budget"]
    if not isinstance(budget, dict):
        raise ValueError("must be an object")
    required = {"max_changed_files", "max_changed_lines"}
    if not required.issubset(budget) or not set(budget).issubset(
            required | {"reason"}):
        raise ValueError(
            "needs exactly max_changed_files, max_changed_lines, and optional reason"
        )
    max_files = budget["max_changed_files"]
    max_lines = budget["max_changed_lines"]
    if type(max_files) is not int or max_files <= 0:
        raise ValueError("max_changed_files must be a positive integer")
    if type(max_lines) is not int or max_lines <= 0:
        raise ValueError("max_changed_lines must be a positive integer")
    reason = budget.get("reason", "")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string when present")
    reason = reason.strip()
    if (max_files > DEFAULT_REVIEW_BUDGET_FILES
            or max_lines > DEFAULT_REVIEW_BUDGET_LINES) and not reason:
        raise ValueError(
            "raising the default 8 files / 400 lines needs a non-empty reason"
        )
    return max_files, max_lines, reason


@contextlib.contextmanager
def termination_signal_guard():
    """Turn wrapper termination into normal cleanup paths for proof children."""
    handled = [
        candidate for candidate in (
            signal.SIGINT,
            signal.SIGTERM,
            getattr(signal, "SIGHUP", None),
            getattr(signal, "SIGQUIT", None),
        )
        if candidate is not None
    ]
    previous = {candidate: signal.getsignal(candidate) for candidate in handled}

    def stop(signum, _frame):
        raise SystemExit(128 + signum)

    for candidate in handled:
        signal.signal(candidate, stop)
    try:
        yield
    finally:
        for candidate, prior in previous.items():
            signal.signal(candidate, prior)


def stages_path(base: Path) -> Path:
    return base / ".factory" / "stages.json"


def authoritative_stages_path(base: Path) -> Path:
    return git_control_dir(base) / "stages.json"


def story_stage_records_dir(base: Path, issue: str) -> Path:
    """The tracked, one-record-per-file stage snapshot of a story (decision
    0022): `.factory/stories/<key>/stages/<task>.json`. Two task worktrees
    that each commit their own record never touch one shared file."""
    return story_dir(base, issue) / "stages"


def _write_story_records(base: Path, issue: str, stages: list[dict],
                         only: str = "") -> None:
    records = story_stage_records_dir(base, issue)
    # The single-file snapshot this layout replaces is split ONCE, from the
    # story (trunk-side) worktree. A task worktree writes only its own record
    # and leaves the legacy file alone — `load_story_stages` merges the two
    # layouts until the split — so no sibling's record is ever written from a
    # task branch.
    legacy = story_dir(base, issue) / "stages.json"
    if not only and legacy.is_file():
        for stage in load_json(legacy, default={}).get("stages") or []:
            stage_id = stage.get("id") if isinstance(stage, dict) else None
            if isinstance(stage_id, str) and Path(stage_id).name == stage_id \
                    and not (records / f"{stage_id}.json").is_file():
                dump_json(records / f"{stage_id}.json", stage)
        legacy.unlink()
    for stage in stages:
        stage_id = stage.get("id")
        if not isinstance(stage_id, str) or Path(stage_id).name != stage_id:
            continue
        if only and stage_id != only:
            continue
        target = records / f"{stage_id}.json"
        if load_json(target, default=None) != stage:
            dump_json(target, stage)


def load_story_stages(base: Path, issue: str) -> dict:
    """The committed per-story snapshot, whichever layout wrote it."""
    records = story_stage_records_dir(base, issue)
    legacy = load_json(story_dir(base, issue) / "stages.json", default={})
    if records.is_dir():
        stages = [load_json(path, default={}) for path in sorted(records.glob("*.json"))]
        # Both layouts at once (a task worktree before the story-side split):
        # a per-task record wins for its id, the legacy file covers the rest.
        recorded = {s.get("id") for s in stages if isinstance(s, dict)}
        stages += [s for s in legacy.get("stages") or []
                   if isinstance(s, dict) and s.get("id") not in recorded]
        order = {
            task.get("id"): index for index, task in enumerate(
                load_json(story_dir(base, issue) / "decomposition.json",
                          default={}).get("tasks") or [])
            if isinstance(task, dict)
        }
        stages = [s for s in stages if isinstance(s, dict) and s.get("id")]
        if not order:  # no story decomposition beside it: the legacy list order
            order = {s.get("id"): i for i, s in enumerate(legacy.get("stages") or [])
                     if isinstance(s, dict)}
        stages.sort(key=lambda s: order.get(s.get("id"), len(order)))
        return {"issue": issue, "stages": stages}
    return legacy


def write_stages(base: Path, data: dict) -> None:
    """Publish protected authority first, then the committed snapshot.

    The git-local stages.json is per worktree (each task worktree has its own
    git control dir), so it never merges. What merges is the story's committed
    snapshot, kept as one record per task (`story_stage_records_dir`). A task
    worktree writes ONLY its own task's record and leaves the workspace mirror
    alone, so two parallel task PRs never rewrite the same file; the story
    worktree writes every record plus the `.factory/stages.json` mirror."""
    dump_json(authoritative_stages_path(base), data)
    own_task = raw_run_state(base).get("task_id")
    own_task = own_task if isinstance(own_task, str) else ""
    if not own_task:
        safe_factory_write_json(base, stages_path(base).name, data)
    # Only for a scoped-layout story (its dir already exists): creating the dir
    # would flip a legacy story to scoped and break its history archival.
    issue = data.get("issue")
    if issue and story_dir(base, issue).is_dir():
        _write_story_records(base, issue, data.get("stages") or [], only=own_task)


def write_skeleton(base: Path, issue: str, tasks: list[dict]) -> None:
    """Re-recording a decomposition after a mid-story scope change must not
    erase what is already built: surviving task ids keep their status and
    timestamps, new ids arrive pending, removed ids drop out."""
    existing = load_stages(base)
    # A story decomposed before per-story snapshots existed would lose its stages
    # when the singleton flips to this new story; preserve the outgoing one so a
    # legacy shipped story keeps its task-completion on the board.
    # The mirror, not `existing`, names the outgoing story: the git-local
    # authority is gone once that story shipped, and then nothing would be
    # archived before the flip.
    mirror = load_json(stages_path(base), default={})
    prior_issue = existing.get("issue") or mirror.get("issue")
    if prior_issue and prior_issue != issue:
        prior_dir = story_dir(base, prior_issue)
        if prior_dir.is_dir() and not load_story_stages(base, prior_issue):
            _write_story_records(base, prior_issue,
                                 (existing.get("stages")
                                  or mirror.get("stages") or []))
    previous = ({s.get("id"): s for s in existing.get("stages", [])}
                if existing.get("issue") == issue else {})
    if not previous:
        # The git-local authority is EPHEMERAL — `clear_story_authority` drops it
        # once a story ships, because it is what keeps reporting an active stage
        # after ship. So ship -> close -> re-record (the JIT contract for the
        # next task of a live story) read nothing and rewrote every shipped task
        # `pending`, destroying exactly the seal tokens #171 exists to preserve.
        # The committed per-story snapshot holds the same state durably, and it
        # is what this function is about to overwrite: read it before writing.
        previous = {s.get("id"): s
                    for s in (load_story_stages(base, issue).get("stages") or [])
                    if isinstance(s, dict) and s.get("id")}
    stages = []
    for task in tasks:
        stage = {"id": task["id"], "title": task["title"], "status": "pending"}
        old = previous.get(task["id"])
        if old:
            # Every seal token survives a re-record: the NEXT task's contract is
            # recorded while this one is done-but-unshipped, and dropping the
            # stage-local review stamp here left `task pr-ready` unable to seal
            # a task whose stage had closed clean (symphony-forge #171).
            stage.update({k: v for k, v in old.items()
                          if k in ("status", "started_at", "completed_at",
                                   "base_sha", "dirty_at_start", "task_sha256",
                                   "incomplete", "local_review_stamp",
                                   "contract_changed", "reopen_base_sha",
                                   "proof_receipts")})
            stage["title"] = task["title"]
        stages.append(stage)
    write_stages(base, {"issue": issue, "stages": stages})


def load_stages(base: Path) -> dict:
    protected = authoritative_stages_path(base)
    if protected.is_file():
        data = load_json(protected, default={})
        current_issue = raw_run_state(base).get("issue_key")
        # No active story means no active stage: leftover authority from a
        # shipped story (its clear never ran, or a stale git-local file) must
        # not report a phantom active stage that blocks every new work window.
        return (data if current_issue and data.get("issue") == current_issue
                else {})
    return {}


def clear_story_authority(base: Path) -> list[str]:
    """Remove the git-local Forge authority for a shipped or orphaned story.

    Idempotent. `.git/forge/stages.json` especially is what keeps reporting an
    active stage after ship — this drops it along with the git-local
    decomposition, delegation ledger and locks. Names what it removed.
    """
    from .delegate import delegations_path

    removed: list[str] = []
    for path in (authoritative_stages_path(base),
                 protected_decomposition_state_path(base),
                 delegations_path(base)):
        if path.exists():
            path.unlink()
            removed.append(path.name)
    locks = git_control_dir(base) / "locks"
    if locks.is_dir():
        shutil.rmtree(locks)
        removed.append("locks/")
    return removed


def _git(base: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=base, capture_output=True, text=True,
        env=clean_git_env(), encoding="utf-8", errors="surrogateescape")
    return proc.stdout if proc.returncode == 0 else ""


def dirty_paths(base: Path) -> list[str]:
    """Every dirty path, including both sides of renames, without quote parsing."""
    def product_path(rel: str) -> bool:
        return not (rel.endswith(".pyc") or "__pycache__" in rel.split("/"))

    raw = _git(base, "status", "--porcelain=v1", "-z", "-uall")
    entries = raw.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status, rel = entry[:2], entry[3:]
        if rel and product_path(rel):
            paths.append(rel)
        if any(flag in status for flag in "RC") and index < len(entries):
            source = entries[index]
            index += 1
            if source and product_path(source):
                paths.append(source)
    return sorted(set(paths))


def stage_ref(stage_id: str) -> str:
    """The stage's fixed point (decision 0023).

    Under `refs/forge/` so it is never confused with a branch, never fetched or
    pushed by default, and never rewritten by an ordinary git operation.
    """
    return f"refs/forge/stage/{stage_id}"


def write_stage_ref(base: Path, stage_id: str) -> str:
    """Pin HEAD as this stage's baseline and return the sha it points at."""
    head = head_sha(base) or ""
    if head:
        _git(base, "update-ref", stage_ref(stage_id), head)
    return head


def stage_baseline(base: Path, stage: dict) -> str:
    """The ref if it resolves, else the recorded sha.

    The fallback is what lets a stage started before 0023 — or one whose ref a
    worktree prune removed — still be measured and closed, rather than becoming
    the unrecoverable state this decision exists to remove.
    """
    resolved = _git(base, "rev-parse", "--verify", "--quiet",
                    stage_ref(stage.get("id", ""))).strip()
    return resolved or stage.get("base_sha", "") or ""


def committed_paths(base: Path, base_sha: str, head: str) -> set[str]:
    """Both sides of every change THIS BRANCH committed, renames and copies too.

    `--first-parent --no-merges`, not a plain range diff: merging upstream into
    a story worktree while a stage is open otherwise attributes every file that
    upstream touched to the stage, and `stage done` refuses a scope violation
    the worker never committed. A merge is something the branch received, not
    something the stage did.
    """
    raw = _git(base, "log", "--first-parent", "--no-merges", "--format=",
               "--name-status", "-z", "--find-renames", f"{base_sha}..{head}")
    entries = raw.split("\0")
    paths: set[str] = set()
    index = 0
    while index < len(entries):
        status = entries[index]
        index += 1
        if not status or index >= len(entries):
            continue
        rel = entries[index]
        index += 1
        if rel:
            paths.add(rel)
        if status[:1] in {"R", "C"} and index < len(entries):
            destination = entries[index]
            index += 1
            if destination:
                paths.add(destination)
    return paths


def _gitlink_entries(index_stage: str) -> dict[str, str]:
    """Gitlink metadata keyed by exact, unquoted path bytes decoded by Git."""
    result: dict[str, str] = {}
    for entry in index_stage.split("\0"):
        if "\t" not in entry:
            continue
        metadata, rel = entry.split("\t", 1)
        fields = metadata.split()
        if fields and fields[0] == "160000":
            result[rel] = metadata
    return result


def _gitlink_identities(base: Path, index_stage: str | None = None,
                        wanted: set[str] | None = None) -> dict[str, str]:
    entries = _gitlink_entries(
        index_stage
        if index_stage is not None
        else _git(base, "ls-files", "--stage", "-z")
    )
    result: dict[str, str] = {}
    for rel, metadata in entries.items():
        if wanted is not None and rel not in wanted:
            continue
        checkout = base / rel
        head = _git(base, "-C", str(checkout), "rev-parse", "HEAD")
        status = _git(
            base, "-C", str(checkout),
            "status", "--porcelain=v2", "-z", "-uall")
        digest = hashlib.sha256()
        digest.update("\0".join((metadata, head, status)).encode())
        result[rel] = digest.hexdigest()
    return result


def _digest(base: Path, rel: str,
            gitlinks: dict[str, str] | None = None) -> str | None:
    if gitlinks is None:
        gitlinks = _gitlink_identities(base, wanted={rel})
    if rel in gitlinks:
        return gitlinks[rel]
    path = base / rel
    try:
        digest = hashlib.sha256()
        mode = path.lstat().st_mode
        if path.is_symlink():
            digest.update(str(mode).encode())
            digest.update(os.readlink(path).encode())
        elif path.is_dir():
            # Git does not record directory modes. Replacement descendants are
            # measured separately, so chmod on their container is not product
            # work and must not satisfy the contribution gate.
            digest.update(b"directory")
        else:
            digest.update(str(mode).encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()
    except FileNotFoundError:
        return ""
    except OSError:
        return None


def _git_path_identity(base: Path, rel: str) -> str:
    return "\0".join((
        _git(base, "status", "--porcelain=v2", "-z", "-uall", "--", rel),
        _git(base, "ls-files", "--stage", "-z", "--", rel),
        _git(base, "ls-files", "-v", "-z", "--", rel),
    ))


def dirty_digests(base: Path) -> dict[str, dict[str, str]]:
    """Content and Git identity of every dirty path when the stage starts.

    Names alone are not enough: subtracting a NAME would hide every later edit
    or index transition to that file. Digests plus porcelain/index identity
    distinguish "still exactly as I found it" from "this stage changed it
    too", even when bytes stay equal."""
    result: dict[str, dict[str, str]] = {}
    paths = dirty_paths(base)
    gitlinks = _gitlink_identities(base, wanted=set(paths))
    for rel in paths:
        digest = _digest(base, rel, gitlinks)
        if digest is None:
            fail(f"cannot read dirty path {rel!r}; stage measurement refuses "
                 "to treat unreadable content as absent")
        result[rel] = {
            "digest": digest,
            "git": _git_path_identity(base, rel),
        }
    return result


def product_tree_snapshot(base: Path) -> dict:
    """The exact Git-visible product tree attested by proof commands.

    WORKFLOW_PATHS (.factory/, plans/) are excluded from EVERY field, not just
    `dirty`: proof commands legitimately churn them — verify.py appends a
    .factory/events/ entry on every run, the stage tracker and events ledger
    move — so including them made the read-only check flag its own bookkeeping
    ("proof commands changed the product tree") for exactly the read-only runs
    it is meant to pass. This check judges PRODUCT read-only-ness only. Git
    pathspec `:(exclude)` drops the workflow paths at the git level so raw
    status/diff output never carries them.
    """
    exclude = ["--"] + [f":(exclude){p.rstrip('/')}" for p in WORKFLOW_PATHS]
    tracked = [
        rel for rel in _git(base, "ls-files", "-z", "--cached", *exclude).split("\0")
        if rel
    ]
    index_stage = _git(base, "ls-files", "--stage", "-z", *exclude)
    dirty = [
        rel for rel in dirty_paths(base)
        if not rel.startswith(workflow_prefixes(base))
    ]
    digests: dict[str, str] = {}
    gitlinks = _gitlink_identities(
        base, index_stage=index_stage, wanted=set(tracked) | set(dirty))
    for rel in sorted(set(tracked) | set(dirty)):
        digest = _digest(base, rel, gitlinks)
        if digest is None:
            fail(f"cannot read product path {rel!r}; proof cannot attest an "
                 "unreadable final tree")
        digests[rel] = digest
    return {
        "head": head_sha(base) or "",
        "status": _git(base, "status", "--porcelain=v2", "-z", "-uall", *exclude),
        "worktree_raw": _git(base, "diff", "--raw", "-z", *exclude),
        "index_raw": _git(base, "diff", "--cached", "--raw", "-z", *exclude),
        "index_stage": index_stage,
        "index_flags": _git(base, "ls-files", "-v", "-z", *exclude),
        "tracked": {rel: digests[rel] for rel in tracked},
        "dirty": {rel: digests[rel] for rel in dirty},
    }


def changed_paths(base: Path, base_sha: str, already_dirty) -> list[str]:
    """Everything this stage moved: commits since base_sha plus the working
    tree. Pre-existing dirt is subtracted only from the working-tree side:
    once a path enters a commit it is stage work and must be scope-checked."""
    committed: set[str] = set()
    head = head_sha(base)
    if base_sha and head and base_sha != head:
        committed.update(committed_paths(base, base_sha, head))
    working = set(dirty_paths(base))
    measured_paths = (
        working
        | (set(already_dirty) if isinstance(already_dirty, dict) else set())
    )
    gitlinks = _gitlink_identities(base, wanted=measured_paths)
    current_digests: dict[str, str] = {}
    for path in measured_paths:
        digest = _digest(base, path, gitlinks)
        if digest is None:
            fail(f"cannot read changed path {path!r}; stage measurement refuses "
                 "to treat unreadable content as absent")
        current_digests[path] = digest
    if isinstance(already_dirty, dict):
        working = {
            path for path in working
            if (
                current_digests[path]
                != (
                    already_dirty.get(path, {}).get("digest", "\0")
                    if isinstance(already_dirty.get(path), dict)
                    else already_dirty.get(path, "\0")
                )
                or (
                    isinstance(already_dirty.get(path), dict)
                    and _git_path_identity(base, path)
                    != already_dirty[path].get("git", "\0")
                )
            )
        }
        for path, baseline in already_dirty.items():
            digest = (
                baseline.get("digest", "\0")
                if isinstance(baseline, dict) else baseline)
            git_identity = (
                baseline.get("git", "\0")
                if isinstance(baseline, dict) else None)
            if (current_digests[path] != digest
                    or (git_identity is not None
                        and _git_path_identity(base, path) != git_identity)):
                working.add(path)
    return sorted(committed | working)


def contribution_paths(base: Path, paths: list[str], already_dirty,
                       base_sha: str) -> list[str]:
    """Paths whose current bytes differ from the pre-stage workspace.

    A pre-existing dirty file may be committed during a stage for workspace
    hygiene. If its bytes never changed, that commit is still scope-checked but
    it cannot masquerade as the task's implementation.
    """
    if not isinstance(already_dirty, dict):
        already_dirty = {}
    gitlinks = _gitlink_identities(base, wanted=set(paths))
    worktree_changed = {
        rel for rel in _git(
            base, "diff", "--name-only", "-z", base_sha, "--").split("\0")
        if rel
    }
    tracked_at_start = {
        rel for rel in _git(
            base, "ls-tree", "-r", "--name-only", "-z",
            base_sha).split("\0")
        if rel
    }
    result = []
    for path in paths:
        baseline = already_dirty.get(path)
        if baseline is None:
            current = _digest(base, path, gitlinks)
            if current is None:
                fail(f"cannot read changed path {path!r}; stage measurement "
                     "refuses to treat unreadable content as absent")
            if path in worktree_changed or (
                    path not in tracked_at_start and current != ""):
                result.append(path)
            continue
        before = baseline.get("digest") if isinstance(baseline, dict) else baseline
        current = _digest(base, path, gitlinks)
        if current is None:
            fail(f"cannot read changed path {path!r}; stage measurement refuses "
                 "to treat unreadable content as absent")
        if current != before:
            result.append(path)
    return result


def split_index_paths(base: Path) -> list[str]:
    """Paths with staged content different from the tested worktree content."""
    def exact_path_exists(rel: str) -> bool:
        current = base
        for part in Path(rel).parts:
            try:
                entries = os.listdir(current)
            except FileNotFoundError:
                return False
            except OSError:
                return True
            if part not in entries:
                return False
            current /= part
        return os.path.lexists(current)

    staged = {
        rel for rel in _git(
            base, "diff", "--cached", "--name-only", "-z").split("\0")
        if rel
    }
    unstaged = {
        rel for rel in _git(
            base, "diff", "--name-only", "-z").split("\0")
        if rel
    }
    unstaged.update(
        rel for rel in _git(
            base, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
        if rel
    )
    staged_deletions = {
        rel for rel in _git(
            base, "diff", "--cached", "--no-renames", "--diff-filter=D",
            "--name-only", "-z").split("\0")
        if rel
    }
    index_paths = {
        rel for rel in _git(
            base, "ls-files", "--cached", "-z").split("\0")
        if rel
    }
    gitlink_paths = set(_gitlink_entries(
        _git(base, "ls-files", "--stage", "-z")
    ))

    def directory_matches_index(rel: str) -> bool:
        root = base / rel
        if not root.is_dir() or root.is_symlink():
            return False
        prefix = f"{rel.rstrip('/')}/"
        indexed = {
            path for path in index_paths if path.startswith(prefix)
        }
        if not indexed:
            return False
        actual: set[str] = set()
        actual_directories: set[str] = set()
        expected_directories: set[str] = set()
        for indexed_path in indexed:
            parent = Path(indexed_path).parent.as_posix()
            while parent != rel and parent.startswith(prefix):
                expected_directories.add(parent)
                parent = Path(parent).parent.as_posix()
        walk_errors: list[OSError] = []
        for current, directories, files in os.walk(
                root, followlinks=False, onerror=walk_errors.append):
            current_path = Path(current)
            gitlink_directories = [
                name for name in directories
                if (current_path / name).relative_to(base).as_posix()
                in gitlink_paths
            ]
            actual.update(
                (current_path / name).relative_to(base).as_posix()
                for name in gitlink_directories
            )
            symlink_directories = [
                name for name in directories
                if (current_path / name).is_symlink()
            ]
            ordinary_directories = [
                name for name in directories
                if (
                    name not in symlink_directories
                    and name not in gitlink_directories
                )
            ]
            actual_directories.update(
                (current_path / name).relative_to(base).as_posix()
                for name in ordinary_directories
            )
            directories[:] = ordinary_directories
            for name in [*files, *symlink_directories]:
                actual.add(
                    (current_path / name).relative_to(base).as_posix()
                )
        return (
            not walk_errors
            and actual == indexed
            and actual_directories == expected_directories
        )

    recreated = {
        rel for rel in staged_deletions
        if (
            exact_path_exists(rel)
            and not directory_matches_index(rel)
        )
    }
    return sorted((staged & unstaged) | recreated)


def protected_authority_snapshot(base: Path) -> dict[str, str]:
    """Exact protected state before proof code receives execution."""
    control = git_control_dir(base)
    if not control.exists():
        fail("protected Forge authority is missing")
    result: dict[str, str] = {}
    for path in sorted(control.rglob("*")):
        rel = path.relative_to(control).as_posix()
        # The locks/ subtree is transient coordination state, not attested
        # authority. The delegation machinery holds these lock files open — with
        # an EXCLUSIVE handle on Windows — for the duration of the very operation
        # that snapshots the tree, so reading them here attests nothing durable
        # and races that open handle (a hard OSError on Windows: a stage could
        # never close). Proof commands never touch locks/, so excluding it keeps
        # the tamper check honest while making stage close work cross-platform.
        if rel == "locks" or rel.startswith("locks/"):
            continue
        try:
            info = path.lstat()
            if path.is_symlink():
                body = f"symlink:{os.readlink(path)}".encode()
            elif path.is_dir():
                body = b"directory"
            else:
                body = path.read_bytes()
        except OSError:
            fail(f"cannot read protected authority path {rel!r}")
        digest = hashlib.sha256()
        digest.update(str(info.st_mode).encode())
        digest.update(body)
        result[rel] = digest.hexdigest()
    return result


def _covered(path: str, scope: list[str]) -> bool:
    for entry in scope:
        prefix = entry.strip().rstrip("/")
        if prefix and (path == prefix or (entry.strip().endswith("/")
                                          and path.startswith(prefix + "/"))):
            return True
    return False


def scope_amendments_path(base: Path):
    """Protected, like the decomposition it annotates."""
    from factory_lib import git_control_dir
    return git_control_dir(base) / "scope_amendments.json"


def amended_scope_paths(base: Path, task_id: str) -> list[str]:
    """Measured paths this task touched that its declared scope did not name.

    Recorded ALONGSIDE the contract rather than edited into it, and that is the
    whole point. `stage done` measures the diff, finds an under-declared path,
    and tells the operator to re-record the decomposition -- but re-recording
    changes the contract digest, which invalidates the delegate launch bound to
    it and stales the grill ground on it. `stage done` then demands a fresh
    Codex run for a correction it demanded itself, and any further correction
    restarts the loop. There is no flag out of that.

    Leaving the contract untouched keeps both bindings valid and keeps the
    record of what was actually grilled, delegated and approved. The amendment
    records what the work really touched. Two honest records beat one rewritten
    one -- editing the contract after the fact destroys the evidence of what
    was approved.
    """
    from factory_lib import load_json
    record = load_json(scope_amendments_path(base), default={})
    entry = (record.get("tasks") or {}).get(task_id) or {}
    paths = entry.get("added_paths") or []
    return [p for p in paths if isinstance(p, str) and p]


def effective_scope(base: Path, task_id: str, scope: list[str]) -> list[str]:
    return list(scope) + amended_scope_paths(base, task_id)


def _at_revision(base: Path, revision: str, path: str) -> bool:
    return subprocess.run(
        ["git", "cat-file", "-e", f"{revision}:{path}"], cwd=base,
        capture_output=True, env=clean_git_env(),
    ).returncode == 0


def _overlap_scope(base: Path, task: dict, stage: dict | None = None) -> list[str]:
    """Everything a task may write: its area prefixes, its amendments and the
    test files it must create. This is what two parallel tasks must not share."""
    task_id = str(task.get("id") or "")
    scope = effective_scope(base, task_id, task.get("write_scope") or [])
    # A required test that already exists at the BASE the task builds on is a
    # proof the task must not break, not a file it writes
    # (required_tests_outside_scope draws the same line). Judged at the stage's
    # base — or, for a task not yet started, the trunk commit its worktree was
    # cut from — never at this checkout's working tree: a file one branch
    # created is still new to every sibling until it reaches the trunk.
    revision = stage_baseline(base, stage) if stage else str(
        load_json(run_state_path(base), default={}).get("base_main_sha") or "HEAD")
    scope += [
        path for path in (str((test or {}).get("path") or "")
                          for test in task.get("required_tests") or [])
        if path and not _at_revision(base, revision, path)
    ]
    from factory_lib import classify_scope_entries
    return classify_scope_entries(base, scope, revision)


def scope_overlap(left: list[str], right: list[str]) -> list[str]:
    """Pairs where one entry covers the other (same path, or a prefix)."""
    return sorted({
        f"{a} ~ {b}" for a in left for b in right
        if _covered(a, [b]) or _covered(b, [a])
    })


def active_stages_everywhere(base: Path) -> list[tuple[Path, dict]]:
    """(worktree, stage) for every active stage of THIS story, across this
    checkout and every linked worktree — a parallel task's stage is active in
    its own worktree's tracker, invisible to the tracker here."""
    from factory_lib import linked_worktree_roots
    issue = load_json(run_state_path(base), default={}).get("issue_key")
    found: list[tuple[Path, dict]] = []
    seen: set[str] = set()
    for root in linked_worktree_roots(base):
        # A pruned or deleted worktree keeps its git bookkeeping for a while.
        try:
            data = load_stages(root) if root.is_dir() else {}
        except (SystemExit, OSError):
            continue
        if not issue or data.get("issue") != issue:
            continue
        for stage in data.get("stages", []):
            if stage.get("status") == "active" and stage.get("id") not in seen:
                seen.add(stage.get("id"))
                found.append((root, stage))
    return found


def scope_conflicts(base: Path, task_id: str) -> list[str]:
    """Why `task_id` may not run beside the stages active right now: one line
    per sibling whose write scope overlaps, naming the overlap. Empty means
    the scopes are disjoint and the task may start in parallel."""
    task = task_for(base, task_id)
    mine = _overlap_scope(base, task)
    conflicts: list[str] = []
    for root, stage in active_stages_everywhere(base):
        sibling = stage.get("id", "")
        if sibling == task_id:
            continue
        theirs = _overlap_scope(
            root, task_for(root, sibling) or task_for(base, sibling), stage)
        overlap = scope_overlap(mine, theirs)
        if overlap:
            conflicts.append(f"{sibling} ({root.name}): {', '.join(overlap)}")
    return conflicts


def out_of_scope(
    base: Path, paths: list[str], scope: list[str], revision: str = "HEAD",
) -> list[str]:
    """Product paths this sequential task touched but never declared."""
    from factory_lib import classify_scope_entries
    classified = classify_scope_entries(base, scope, revision)
    return [p for p in paths
            if not p.startswith(measure_prefixes(base))
            and not _covered(p, classified)]


def _numstat_lines(raw: str) -> int:
    total = 0
    for entry in raw.split("\0"):
        fields = entry.split("\t", 2)
        if len(fields) != 3:
            continue
        additions, deletions = fields[:2]
        if additions.isdigit() and deletions.isdigit():
            total += int(additions) + int(deletions)
    return total


def _changed_line_count(base: Path, base_sha: str, product: list[str]) -> int:
    """Additions plus deletions for the exact product paths `_measure` found."""
    if not product:
        return 0
    lines = _numstat_lines(
        _git(base, "diff", "--numstat", "-z", base_sha, "--", *product)
    )
    untracked = {
        rel for rel in _git(
            base, "ls-files", "--others", "--exclude-standard", "-z", "--",
            *product,
        ).split("\0")
        if rel
    }
    for rel in sorted(untracked):
        proc = subprocess.run(
            ["git", "diff", "--no-index", "--numstat", "-z", "--",
             os.devnull, rel],
            cwd=base, capture_output=True, text=True, env=clean_git_env(),
            encoding="utf-8", errors="surrogateescape",
        )
        if proc.returncode not in {0, 1}:
            fail(f"cannot count changed lines for untracked path {rel!r}; "
                 "stage measurement refuses an incomplete review budget")
        lines += _numstat_lines(proc.stdout)
    return lines


def task_for(base: Path, stage_id: str) -> dict:
    tasks = load_json(
        protected_decomposition_state_path(base), default={}).get("tasks", [])
    return next((t for t in tasks if t.get("id") == stage_id), {})


def stage_review_binding(base: Path, stage: dict, task: dict) -> dict[str, str]:
    """What a review stamp attests: THIS diff, from THIS base, for THIS stage.

    It used to also hash the contract text, the brief text and every tracked
    file. None of those is what the reviewer read, so each could stale a
    review of unchanged code: a scope widening, a decision record, a contract
    re-record. On T2 that cost three re-reviews and a no-op delegate in one
    morning. The reviewer read the product diff; the stamp binds to the
    product diff.
    """
    from factory_lib import effective_review_base, product_delta_digest
    base_sha = effective_review_base(base, str(stage.get("id") or ""))
    return {
        "stage_id": stage.get("id", ""),
        "base_sha": base_sha,
        "delta_id": product_delta_digest(base, base_sha),
    }


_BOOKKEEPING_KEYS = {
    "at", "recorded_at", "updated_at", "selected_at", "completed_at",
    "approved_at",
    "generated_by", "commit",
}


def _canonical_review_value(value):
    if isinstance(value, dict):
        return {key: _canonical_review_value(item)
                for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_canonical_review_value(item) for item in value]
    return value


def _canonical_review_envelope(value, *, nested: frozenset[str] = frozenset()):
    """Remove recorder metadata only from known artifact envelope levels."""
    if not isinstance(value, dict):
        return _canonical_review_value(value)
    return {
        key: (_canonical_review_envelope(item)
              if key in nested else _canonical_review_value(item))
        for key, item in sorted(value.items())
        if key not in _BOOKKEEPING_KEYS
    }


def _canonical_review_dataset(dataset: bytes) -> bytes:
    """Ignore recorder bookkeeping only inside the two rendered JSON artifacts."""
    try:
        text = dataset.decode("utf-8")
    except UnicodeDecodeError:
        return dataset
    headings = {
        "#### Full grill and approval record (untrusted data)": frozenset(),
        "#### Full task-owned automated report (implementer-authored evidence)":
            frozenset(),
    }
    for heading, nested in headings.items():
        start = 0
        while (section := text.find(heading, start)) >= 0:
            fence = re.search(r"(?m)^(?P<fence>`{3,})json\n", text[section:])
            if fence is None:
                break
            body_start = section + fence.end()
            marker = fence.group("fence")
            close = text.find(f"\n{marker}", body_start)
            if close < 0:
                break
            try:
                value = json.loads(text[body_start:close])
            except json.JSONDecodeError:
                start = close + len(marker) + 1
                continue
            if heading == "#### Full task-owned automated report (implementer-authored evidence)":
                # Functional evidence is recorded independently after the code
                # review.  Keep it in tests.json for the task-proof gate, but
                # do not make that later report invalidate the review's code
                # meaning or its rendered approved-input bytes.
                if isinstance(value, dict):
                    value = dict(value)
                    value.pop("functional", None)
            canonical = json.dumps(
                _canonical_review_envelope(value, nested=nested),
                indent=2, sort_keys=True,
            )
            text = text[:body_start] + canonical + text[close:]
            start = body_start + len(canonical) + len(marker) + 1
    return text.encode("utf-8")


def reviewed_meaning_identity(
        base: Path, stage: dict, task: dict, helper: dict | None = None, *,
        review_dataset: bytes | None = None,
) -> dict[str, object]:
    """Meaning a selected review covers, excluding recorder-only bookkeeping."""
    from factory_lib import active_story_key, proof_path
    story = active_story_key(base)
    task_id = str(task.get("id") or stage.get("id") or "")
    plan = evidence_path(base, story, f"task-plans/{task_id}.md")
    plan_digest = plan_digest_without_assumptions(plan) if plan.is_file() else ""
    automated = load_json(
        proof_path(base, story, "tests.json", task_id=task_id), default={},
    )
    grill = load_json(
        evidence_path(base, story, f"grills/tasks/{task_id}.json"), default={},
    )
    instruction_paths = (
        "factory/prompts/reviewer.md",
        "factory/scripts/record_review_from_json.py",
        "factory/scripts/forge_cli/review.py",
        "factory/scripts/forge_cli/review_brief.py",
        "factory/scripts/forge_cli/review_groups.py",
        "factory/schemas/review.json",
    )
    instructions = {
        relative: sha256_of(base / relative)
        for relative in instruction_paths if (base / relative).is_file()
    }
    from .review_brief import _current_decision_inputs
    decision_inputs = _current_decision_inputs(base)
    helper_identity = helper if isinstance(helper, dict) else {}
    helper_path = Path(str(helper_identity.get("path") or ""))
    if helper_path and not helper_path.is_absolute():
        helper_path = base / helper_path
    if helper_path.is_file():
        helper_identity = {
            **helper_identity, "current_sha256": sha256_of(helper_path),
        }
    generated = {}
    for relative in task.get("generated_semantic_inputs") or []:
        if not isinstance(relative, str):
            continue
        path = base / relative
        generated[relative] = (
            sha256_of(path) if path.is_file() else "absent"
        )
    automated_meaning = dict(automated) if isinstance(automated, dict) else {}
    automated_meaning.pop("functional", None)
    inputs = {
        "task_plan_sha256": plan_digest,
        "task_semantics": _canonical_review_value({
            key: task.get(key) for key in (
                "objective", "acceptance_criteria", "plan_contracts",
                "reviewer_focus", "write_scope", "required_tests",
                "verify_commands", "generated_semantic_inputs",
            )
        }),
        "task_grill": _canonical_review_envelope(grill),
        "automated_evidence": _canonical_review_envelope(
            automated_meaning, nested=frozenset({"automated"}),
        ),
        "review_instructions": instructions,
        "accepted_decisions": [
            {
                "id": item["id"],
                "source": item["source"],
                "detached": item["detached"],
                "sha256": item["sha256"],
                "bytes": len(item["body"]),
            }
            for item in decision_inputs
        ],
        "helper": helper_identity,
        "generated_semantic_inputs": generated,
        "product_delta": stage_review_binding(base, stage, task)["delta_id"],
    }
    dataset = review_dataset
    if dataset is None:
        dataset_path = factory_dir(base) / "review-briefs" / "all.md"
        try:
            dataset_info = dataset_path.lstat()
        except FileNotFoundError:
            from .review_brief import render_review_dataset
            dataset = render_review_dataset(base, task_id)
        except OSError:
            dataset = b"invalid-review-dataset:unreadable"
        else:
            if (stat.S_ISREG(dataset_info.st_mode) and dataset_info.st_nlink == 1
                    and not stat.S_ISLNK(dataset_info.st_mode)):
                try:
                    dataset = dataset_path.read_bytes()
                except OSError:
                    dataset = b"invalid-review-dataset:unreadable"
            else:
                dataset = b"invalid-review-dataset:linked-or-nonregular"
    inputs["review_dataset_sha256"] = hashlib.sha256(
        _canonical_review_dataset(dataset)
    ).hexdigest()
    canonical = json.dumps(
        inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    from .review import _combined_prompt
    semantic_identity = hashlib.sha256(canonical).hexdigest()
    prompts = [_combined_prompt(task, repo_readable=readable,
                                semantic_identity=semantic_identity)
               for readable in (True, False)]
    prompt = prompts[0]
    return {
        "identity": hashlib.sha256(prompt).hexdigest(), "bytes": len(prompt),
        "accepted_inputs": [
            {"sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
            for body in prompts
        ],
        "semantic_identity": semantic_identity,
        "semantic_bytes": len(canonical), "inputs": inputs,
    }


def selected_meaning_current(
        base: Path, stage: dict, task: dict, generation: dict, *,
        meaning: dict | None = None,
) -> bool:
    """Does a selected combined review still bind the current meaning?"""
    if generation.get("origin") not in {"combined", "rejection"}:
        return True
    current = meaning or reviewed_meaning_identity(
        base, stage, task, generation.get("helper"),
    )
    return generation.get("input") in current["accepted_inputs"]


def require_current_review_meaning(
        base: Path, stage: dict, task: dict, generation: dict,
) -> dict:
    """Require the immutable prompt hash to bind the meaning being published."""
    meaning = reviewed_meaning_identity(base, stage, task, generation.get("helper"))
    if not selected_meaning_current(base, stage, task, generation, meaning=meaning):
        fail("review generation input does not match the current reviewed meaning; "
             "run a fresh review before publishing or stamping")
    return meaning


def stamp_is_fresh(base: Path, stage: dict, task: dict) -> bool:
    """Does the current-format stage stamp cover the selected review and diff?"""
    stamp = stage.get("local_review_stamp")
    if not isinstance(stamp, dict) or "delta_id" not in stamp:
        return False
    expected = stage_review_binding(base, stage, task)
    if not all(stamp.get(key) == value for key, value in expected.items()):
        return False
    from factory_lib import (
        active_story_key, read_selected_review_generation, selected_review_problems,
    )
    story = active_story_key(base)
    if not story or selected_review_problems(
            base, story, str(stage.get("id") or ""), expected["delta_id"]):
        return False
    generation, _selection, generation_problems = read_selected_review_generation(
        base, story, str(stage.get("id") or ""), expected_delta_id=expected["delta_id"],
    )
    if generation_problems or not isinstance(generation, dict):
        return False
    if generation.get("origin") in {"combined", "rejection"}:
        meaning = reviewed_meaning_identity(base, stage, task, generation.get("helper"))
        if (not selected_meaning_current(
                    base, stage, task, generation, meaning=meaning,
                )
                or stamp.get("reviewed_meaning") != meaning["semantic_identity"]):
            return False
    return True

def stamp_stage_review(base: Path, stage_id: str, *, generated_by: str = "autoreview",
                       lenses: tuple[str, ...] | list[str] = ()) -> dict:
    """Bind a clean review to the stage's current product tree.

    `forge review` calls this when no lens reports a blocking finding, so ONE
    review per task both records the lens artifacts and satisfies the stage
    seal; the separate stage-local autoreview loop is no longer required. An
    active stage is stamped ahead of `stage done`; a done stage is stamped so
    `task pr-ready` seals the reviewed tree. Returns the stamp."""
    from .delegate import delegation_exclusion
    with delegation_exclusion(base, "stages", kind="stage-state", namespace="state"):
        data = load_stages(base)
        stage = _find(data, stage_id)
        if stage.get("status") not in ("active", "done"):
            fail(f"{stage_id} is {stage.get('status', 'pending')!r}; only an active "
                 "or done stage takes a review stamp")
        task = task_for(base, stage_id)
        if not task:
            fail(f"{stage_id} has no recorded task contract to bind the review to")
        stamp = {
            **stage_review_binding(base, stage, task),
            # Evidence, not binding: which contract the review ran under.
            "contract_sha256": task_digest(task),
            "recorded_at": now_iso(),
            "generated_by": generated_by,
            "lenses": list(lenses),
        }
        from factory_lib import active_story_key, read_selected_review_generation
        generation, _selection, problems = read_selected_review_generation(
            base, active_story_key(base), stage_id,
            expected_delta_id=stamp["delta_id"],
        )
        if not problems and isinstance(generation, dict) \
                and generation.get("origin") in {"combined", "rejection"}:
            stamp["reviewed_meaning"] = require_current_review_meaning(
                base, stage, task, generation,
            )["semantic_identity"]
        stage["local_review_stamp"] = stamp
        write_stages(base, data)
    append_event(base, "review-stage-local", actor=generated_by,
                 story=data.get("issue", ""), detail=stage_id)
    return stamp


def revoke_stage_review_stamp(base: Path, stage_id: str) -> bool:
    """Drop a stage's review stamp because a later review blocks; True when
    a stamp was there. The seal follows the latest verdict, not the first."""
    from .delegate import delegation_exclusion
    with delegation_exclusion(base, "stages", kind="stage-state", namespace="state"):
        data = load_stages(base)
        stage = _find(data, stage_id)
        had = stage.pop("local_review_stamp", None) is not None
        if had:
            write_stages(base, data)
    if had:
        append_event(base, "review-stamp-revoked", actor="autoreview",
                     story=data.get("issue", ""), detail=stage_id)
    return had


def _require_reviewed_commit(base: Path, stage: dict, task: dict) -> None:
    stage_id = stage.get("id")
    stamp = stage.get("local_review_stamp")
    if not isinstance(stamp, dict):
        fail(f"{stage_id} has no stage-local review stamp. Run `forge review "
             f"{stage_id}` on the committed tree -- a run with no blocking finding "
             f"stamps the stage -- or `forge task close {stage_id}`, which runs "
             "the review only when the diff has moved, then closes and seals.")
    if not stamp_is_fresh(base, stage, task):
        meaning_changed = False
        if stamp.get("delta_id") == stage_review_binding(base, stage, task)["delta_id"]:
            from factory_lib import active_story_key, read_selected_review_generation
            story = active_story_key(base)
            generation, _selection, problems = read_selected_review_generation(
                base, story, str(stage_id or ""),
                expected_delta_id=str(stamp.get("delta_id") or ""),
            ) if story else (None, None, ["no active story"])
            if (not problems and isinstance(generation, dict)
                    and generation.get("origin") in {"combined", "rejection"}):
                meaning = reviewed_meaning_identity(
                    base, stage, task, generation.get("helper"),
                )
                meaning_changed = (
                    not selected_meaning_current(
                        base, stage, task, generation, meaning=meaning,
                    ) or stamp.get("reviewed_meaning") != meaning["semantic_identity"]
                )
        reason = (
            "the reviewed meaning changed while the product diff stayed the same"
            if meaning_changed else
            "the product diff changed since the review read it"
        )
        if meaning_changed:
            fail(f"{stage_id} has a STALE stage-local review stamp: {reason}. Run "
                 f"`forge task close {stage_id}` to review the current meaning, or "
                 f"`forge review {stage_id}` then retry.")
        fail(f"{stage_id} has a STALE stage-local review stamp: {reason}. Commit "
             "the final tree and run "
             f"`forge task close {stage_id}` (it re-reviews exactly the new diff, "
             f"reopening a done stage itself), or `forge review {stage_id}` then retry.")
    product_dirt = sorted(product_tree_snapshot(base)["dirty"])
    if product_dirt:
        fail(f"{stage.get('id')} has uncommitted or staged PRODUCT changes: "
             f"{', '.join(product_dirt[:10])}. Commit exactly the reviewed tree "
             "before closing the stage.")
    base_sha = stage_baseline(base, stage)
    head = head_sha(base) or ""
    committed_product = [
        path for path in committed_paths(base, base_sha, head)
        if not path.startswith(workflow_prefixes(base))
    ] if base_sha and head and base_sha != head else []
    if not committed_product:
        fail(f"{stage.get('id')} closes on an EMPTY committed delta -- stage work "
             "must be committed before completion.")

def _find(data: dict, stage_id: str) -> dict:
    stage = next((s for s in data.get("stages", []) if s.get("id") == stage_id), None)
    if stage is None:
        known = ", ".join(s.get("id", "?") for s in data.get("stages", []))
        fail(f"stage {stage_id!r} is not in .factory/stages.json ({known or 'empty'})")
    return stage


def _cmd_start_locked(args: argparse.Namespace, base: Path) -> None:
    from factory_lib import require_task_start_recorded
    trunk = bool(getattr(args, "trunk", False))
    require_task_start_recorded(base, args.id, trunk=trunk)
    require_task_worktree(base)
    data = load_stages(base)
    if not data:
        fail("no .factory/stages.json — record the decomposition first "
             "(record_decomposition_from_json.py creates the stage tracker)")
    stage = _find(data, args.id)
    if stage.get("status") == "done":
        fail(f"{args.id} is already done — stages don't restart. Review fixes: "
             f"`forge task reopen {args.id} --review-fix` (back to active, same "
             "base and contract). New work: a follow-up stage in a re-recorded "
             "decomposition.")
    if stage.get("status") == "active":
        # No re-baselining, ever (decision 0023). The baseline is a ref written
        # once at start; a contract that changes mid-stage is LEDGERED, not
        # replayed onto a new fixed point. Coupling the two is what stranded a
        # stage whose work was complete, reviewed and committed: the repair
        # rebaselined onto the finished commit, so the delta it was protecting
        # no longer existed and nothing could measure it again.
        fail(f"{args.id} is already active — restarting would erase the measured "
             "delta, and the baseline is not something to move. Re-record a "
             "changed contract if the scope was wrong: the change is ledgered "
             f"and `forge stage done {args.id}` still measures against the ref "
             "this stage started from.")
    # The order is the dependency graph, not the list: a task starts once its
    # dependencies are done (stage done + marker on the trunk in a task
    # worktree; stage done in the story tracker), and it may run BESIDE another
    # active stage when their write scopes are disjoint.
    from factory_lib import task_dependencies, task_done_ids
    done = task_done_ids(base)
    tasks = load_json(protected_decomposition_state_path(base),
                      default={}).get("tasks", [])
    waiting = [d for d in task_dependencies(tasks, args.id) if d not in done]
    if waiting:
        fail(f"{args.id} waits on unfinished dependency task(s): "
             f"{', '.join(waiting)} — finish them (stage done + merged) first")
    # Parallel means a DIFFERENT worktree: one checkout runs one stage.
    running_here = [s["id"] for s in data.get("stages", [])
                    if s is not stage and s.get("status") == "active"]
    if running_here:
        fail(f"worktree {base} already runs {', '.join(running_here)}; start "
             f"parallel tasks in their own worktree (`forge task start {args.id}`)")
    conflicts = scope_conflicts(base, args.id)
    if conflicts:
        fail(f"{args.id} cannot start beside an active stage whose write scope "
             f"overlaps its own: {'; '.join(conflicts)}. Finish that stage, or "
             "re-plan the two tasks with disjoint areas.")
    approved_sha256 = require_approved_plan_digest(base)
    decomposition = load_json(protected_decomposition_state_path(base), default={})
    if not decomposition:
        decomposition = load_json(decomposition_state_path(base), default={})
    if decomposition.get("plan_sha256") != approved_sha256:
        fail(f"{args.id} cannot start: the decomposition is not bound to the current "
             "approved plan. Re-record the decomposition, then start the stage.")
    current_task = require_ready_task(base, args.id)
    stage["status"] = "active"
    stage["started_at"] = now_iso()
    # `stage done` measures the diff, and a measurement needs a fixed point —
    # plus the dirt that was already there, which is not this stage's work.
    # The fixed point is a REF (decision 0023): a sha in stages.json can be
    # rewritten by the next `stage start`, which is how re-recording a contract
    # once destroyed the delta it was supposed to protect. A ref is written
    # once per stage and survives commits, rebases and worktree switches.
    # A REOPENED task keeps the base its work started from: measuring a
    # reopened stage from today's HEAD reports an empty diff for work that is
    # already on the branch, and the stage can then neither close nor seal
    # (symphony-forge #171). `task reopen` records that base; it must still be
    # an ancestor of HEAD, else the ref pins HEAD as for a fresh stage.
    reopen_base = stage.pop("reopen_base_sha", None)
    pinned = ""
    if isinstance(reopen_base, str) and reopen_base:
        # stages' `_git` returns stdout (empty on failure); an ancestor check is
        # a return code, so ask subprocess directly, as the done path does.
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", reopen_base, "HEAD"],
            cwd=base, capture_output=True, text=True, encoding="utf-8",
            env=clean_git_env(),
        ).returncode == 0
        if ancestor:
            _git(base, "update-ref", stage_ref(args.id), reopen_base)
            pinned = reopen_base
            print(f"Stage baseline restored to {reopen_base[:12]} (reopened task): "
                  "the diff is measured from where the task's work started")
        else:
            print(f"WARNING: reopened base {reopen_base[:12]} is not an ancestor of "
                  "HEAD; measuring from HEAD instead")
    stage["base_sha"] = pinned or write_stage_ref(base, args.id) or ""
    stage["dirty_at_start"] = dirty_digests(base)
    stage["task_sha256"] = task_digest(current_task)
    append_event(base, "stage-start", actor="implementer", story=data.get("issue", ""),
                 detail=f"{args.id} {stage.get('title', '')}")
    stage.pop("parallel", None)
    write_stages(base, data)
    print(f"Stage {args.id} active — {stage.get('title')}")


def stage_admission_lock_path(base: Path) -> Path:
    """One lock for the whole repo: under git's COMMON dir, which every
    linked worktree shares, so two `stage start`s in two worktrees serialise."""
    common = _git(base, "rev-parse", "--git-common-dir").strip()
    return (base / common).resolve() / "forge" / "stage-admission.lock"


@contextlib.contextmanager
def stage_admission(base: Path, *, timeout: float = 120.0):
    """Hold the story-wide admission lock across check + activate, so the
    disjointness scan and the tracker write are one step across worktrees.
    A contender waits, then re-checks against what the winner activated."""
    import time
    from .delegate import _lock_file, _unlock_file
    path = stage_admission_lock_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+", encoding="utf-8")
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                _lock_file(handle)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    fail(f"another `stage start` has held {path} for {timeout:.0f}s; "
                         "retry once it finishes")
                time.sleep(0.2)
        yield
    finally:
        try:
            _unlock_file(handle)
        finally:
            handle.close()


def cmd_start(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    from .delegate import delegation_exclusion

    with stage_admission(base):
        with delegation_exclusion(base, args.id, kind="stage-state"):
            with delegation_exclusion(
                    base, "stages", kind="stage-state", namespace="state"):
                _cmd_start_locked(args, base)


def _measure(base: Path, stage_id: str, stage: dict, task: dict) -> dict:
    """Closing a stage is a measurement, not an assertion.

    Every other diff-based check in this repo fires when TOO MUCH changed.
    None fired when too little did — which is exactly what a stalled or
    half-finished delegation looks like, and it signed itself off.

    Returns what it measured (strays, files, lines, budget). Strays and a
    budget overrun are RECORDED on the stage and printed as notes, not
    refused: the review has already read the diff, and refusing here only
    ever produced a re-record/re-grill loop. The one measure that still
    refuses is a delta above twice the declared line budget."""
    base_sha = stage_baseline(base, stage)
    if not base_sha:
        fail(f"{stage_id} was started before its base commit was recorded, so "
             "there is nothing to measure against. Re-run "
             f"`forge stage start {stage_id}` (it is still active) and close it again.")
    if not task:
        fail(f"{stage_id} has no task in the recorded decomposition, so there is "
             "no contract to measure it against — a stage with no boundary is "
             "not something that can be attested. Re-record the decomposition "
             "with this task, then re-start the stage.")
    if not (task.get("write_scope") or []):
        fail(f"{stage_id} declares no write_scope, so nothing bounds what it may "
             "change. Re-record the decomposition with the paths this task owns, "
             f"then `forge stage start {stage_id}` again.")
    # NOTE: _measure must stay PURE. It runs several times per close — before
    # the proof, after it, and again under the lock — and product_tree_snapshot
    # digests every TRACKED file, .factory/events.jsonl included. Appending an
    # event here changed the tree between the proof snapshot and the final
    # check, so the stage refused itself. The contract change is ledgered once,
    # in the serialization block, where stages.json is written anyway.
    # Emptiness is judged on PRODUCT paths only. A stalled run still churns
    # .factory/ — the stage tracker and the events ledger move on every
    # command — so counting workflow paths would make this check pass for
    # exactly the runs it exists to catch.
    baseline = stage.get("dirty_at_start", {})
    split = [
        path for path in split_index_paths(base)
        if not path.startswith(workflow_prefixes(base))
    ]
    if split:
        fail(f"{stage_id} has staged content that differs from the tested "
             f"worktree for: {', '.join(split[:10])}. Make the index and "
             "worktree agree before closing the stage.")
    product = [
        path for path in changed_paths(base, base_sha, baseline)
        if not path.startswith(measure_prefixes(base))
    ]
    contributions = contribution_paths(base, product, baseline, base_sha)
    if not contributions:
        fail(f"{stage_id} closes on an EMPTY diff — no product path changed since "
             f"{base_sha[:8]}, in commits or in the working tree. That is what a "
             "stalled or read-only run looks like. If the work is genuinely "
             f"partial, say so: forge stage done {stage_id} --incomplete \"<what "
             "is missing>\".")
    # A recorded amendment is measured fact, not a widened permission: it
    # only ever names paths a previous measurement already found changed.
    scope = task.get("write_scope") or []
    strays = out_of_scope(
        base, product, effective_scope(base, stage_id, scope), base_sha,
    )
    try:
        max_files, max_lines, _reason = review_budget(task)
    except ValueError as exc:
        fail(f"{stage_id} carries an invalid review_budget ({exc}); re-record "
             "the decomposition before closing the stage")
    changed_lines = _changed_line_count(base, base_sha, product)
    if changed_lines > 2 * max_lines:
        fail(
            f"{stage_id} changed {changed_lines} lines, more than TWICE its "
            f"{max_lines}-line review budget (additions + deletions; excluding "
            ".factory/, plans/ and docs/decisions/). A delta this size is not "
            "one reviewable change. Split the task: re-run the task grill with "
            "decision=split, append new skeletal task(s) after the frozen graph "
            f"prefix, and return this stage incomplete with `forge stage done "
            f"{stage_id} --incomplete \"<what remains>\"`."
        )
    return {
        "strays": strays,
        "files": len(product),
        "lines": changed_lines,
        "budget": {"files": max_files, "lines": max_lines},
    }


def _measure_notes(stage_id: str, measured: dict) -> list[str]:
    """What `stage done` says about a measurement it recorded but did not
    refuse. Kept out of `_measure`, which runs several times per close."""
    notes: list[str] = []
    strays = measured.get("strays") or []
    if strays:
        notes.append(
            f"NOTE: {stage_id} changed {len(strays)} path(s) outside its declared "
            f"write_scope: {', '.join(strays[:10])}"
            f"{'…' if len(strays) > 10 else ''}. Recorded on the stage for "
            "review (`forge stage list`). If the scope was under-declared, say "
            f"why: `forge stage amend-scope {stage_id} --reason \"<why these "
            "paths belong>\"` — it records EXACTLY the paths measured, leaving "
            "the contract (and so the grill and the delegate launch bound to "
            "it) intact. Do NOT re-record the decomposition to fix this: that "
            "changes the contract digest and invalidates the launch.")
    budget = measured.get("budget") or {}
    files, lines = measured.get("files", 0), measured.get("lines", 0)
    if files > budget.get("files", files) or lines > budget.get("lines", lines):
        notes.append(
            f"NOTE: {stage_id} exceeds its review budget: measured files={files}, "
            f"lines={lines}; budget files={budget.get('files')}, "
            f"lines={budget.get('lines')}. The default 8 files / 400 lines is "
            "the policy target; recorded on the stage for review.")
    for miss in measured.get("test_id_misses") or []:
        notes.append(f"NOTE: {stage_id} required test {miss}; recorded on the "
                     "stage — the run itself passed.")
    return notes


def _host_window_covering(base: Path, stage: dict, task: dict) -> dict | None:
    """A ledgered degraded (host-fix) window CLOSED during this stage, bounded
    to the window's file cap and to the task's effective write scope.

    Codex's sandbox cannot see every defect — a failure that only appears against
    a real database, or a check that only runs on the host — so the coordinator
    fixes those itself inside a bounded, ledgered window. That window IS a
    sanctioned write path, but `stage done` used to demand a Codex launch that
    could not exist for such a fix, leaving no way to close the stage and making
    shipping around the flow look like the only option. Accepting the window
    keeps the evidence (it is ledgered and bounded) without the dead end."""
    from .quickfix import DEGRADED, MAX_FILES, closed_windows, profile_of

    started = str(stage.get("started_at") or "")
    scope = effective_scope(base, str(stage.get("id") or ""),
                            task.get("write_scope") or [])
    for window in closed_windows(base):
        if profile_of(window) != DEGRADED and window.get("kind") != DEGRADED:
            continue
        # Opened while THIS stage was active (the stage is still active now,
        # so a later start is enough) and tied to it by what it touched: a
        # NON-EMPTY file list, every file inside the effective scope. An empty
        # list proves nothing; a foreign file is another task's work.
        if not started or str(window.get("started_at") or "") < started:
            continue
        # Bound to THIS stage at open time (quickfix records task_id when a
        # degraded window opens mid-stage); an older, unbound window is
        # refused — reopen one.
        if window.get("task_id") != stage.get("id"):
            continue
        files = [f for f in (window.get("files") or []) if isinstance(f, str)]
        if not files or len(files) > MAX_FILES:
            continue
        if all(_covered(path, scope) for path in files):
            return window
    return None


def _successful_launch_entry_valid(
        base: Path, stage_id: str, stage: dict, entry: dict | None) -> bool:
    """Return whether this exact terminal row proves a stage-bound write.

    The recorded brief digest is historical launch evidence; later brief
    regeneration must not rewrite that stage-bound anchor.
    """
    from .codex_runtime import native_argv_valid, parse_native_result
    from .delegate import argv_digest, brief_path, delegations_path

    brief = brief_path(base, stage_id)
    launch_id = entry.get("launch_id") if entry else None
    if not isinstance(launch_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", launch_id):
        return False
    argv = entry.get("argv")
    transport = entry.get("transport") if entry else None
    if transport == "native":
        launch_scope = entry.get("write_scope")
        scope_valid = (
            isinstance(launch_scope, list)
            and bool(launch_scope)
            and all(isinstance(path, str) and path.strip() for path in launch_scope)
        )
        expected_output = (delegations_path(base).parent / "native-runs" /
                           f"{launch_id}.jsonl")
        expected_stderr = (delegations_path(base).parent / "native-runs" /
                           f"{launch_id}.stderr.log")
        try:
            session_id = parse_native_result(expected_output)
        except ValueError:
            session_id = ""
        argv_valid = (
            scope_valid
            and native_argv_valid(entry, base, launch_scope)
            and entry.get("write") is True
            and not entry.get("resume_session")
            and entry.get("brief_path") == brief.relative_to(base).as_posix()
            and entry.get("output_path") == str(expected_output)
            and entry.get("stderr_path") == str(expected_stderr)
            and entry.get("session_id") == session_id
            and entry.get("argv_sha256") == argv_digest(argv)
        )
    elif transport is None:
        context = entry.get("context")
        context_opaque = ""
        context_valid = context is None
        if (isinstance(context, dict)
                and set(context) == {"supplied", "bytes", "snapshot_id"}
                and context.get("supplied") is True
                and isinstance(context.get("bytes"), int)
                and context["bytes"] >= 0
                and isinstance(context.get("snapshot_id"), str)
                and re.fullmatch(
                    r"context-[0-9a-f]{32}(?:[0-9a-f]{32})?",
                    context["snapshot_id"],
                )
                ):
            context_opaque = context["snapshot_id"].removeprefix("context-")
            context_valid = True
        base_argv = [
            argv[0] if isinstance(argv, list) and argv else "",
            entry.get("companion_path"), "task", "--json", "--cwd", str(base),
            "--model", entry.get("model"), "--effort", entry.get("effort"),
        ]
        expected = []
        if context_valid and not context_opaque:
            expected = [base_argv + ["--prompt-file", prompt, "--write"]
                        for prompt in (
                            str(brief), brief.relative_to(base).as_posix(),
                        )]
        elif len(context_opaque) == 64 and re.fullmatch(
                r"[0-9a-f]{64}", str(entry.get("prompt_sha256") or "")):
            expected = [base_argv + ["--write"]]
        elif len(context_opaque) == 32:
            historical = (Path(tempfile.gettempdir()).resolve()
                          / f"forge-context-{context_opaque}" / "brief.md")
            expected = [base_argv + [
                "--prompt-file", str(historical), "--write",
            ]]
        argv_valid = (
            isinstance(argv, list)
            and bool(argv)
            and all(isinstance(token, str) for token in argv)
            and Path(argv[0]).stem.lower() == "node"
            and argv in expected
            and entry.get("argv_sha256") == argv_digest(argv)
        )
    else:
        argv_valid = False
    brief_digest = entry.get("brief_sha256") if entry else None
    brief_valid = (isinstance(brief_digest, str)
                   and re.fullmatch(r"[0-9a-f]{64}", brief_digest) is not None)
    valid = (
        entry
        and entry.get("launch_status") == "succeeded"
        and entry.get("exit_code") == 0
        and entry.get("write") is True
        and entry.get("stage_started_at") == stage.get("started_at")
        and brief_valid
        and argv_valid
    )
    return bool(valid)


def _host_native_preparation_scope(
        base: Path, stage_id: str, stage: dict, task: dict) -> list[str] | None:
    """Return the validated scope from the latest native preparation."""
    from .delegate import argv_digest, brief_path, load_delegations
    from factory_lib import classify_scope_entries

    try:
        candidates = [
            row for row in load_delegations(base)
            if row.get("transport") == "host-native"
            and row.get("task") == stage_id
            and row.get("stage_started_at") == stage.get("started_at")
            and row.get("write") is True
        ]
    except (OSError, SystemExit, ValueError):
        return None
    if not candidates:
        return None
    entry = candidates[-1]
    brief = brief_path(base, stage_id)
    scope = entry.get("write_scope")
    effective = classify_scope_entries(
        base, effective_scope(base, stage_id, task.get("write_scope") or []),
        stage_baseline(base, stage),
    )
    if (
        entry.get("launch_status") != "prepared"
        or entry.get("write") is not True
        or entry.get("task_sha256") != task_digest(task)
        or entry.get("model") != ""
        or entry.get("effort") != ""
        or entry.get("argv") != []
        or entry.get("argv_sha256") != argv_digest([])
        or any(key in entry for key in (
            "pid", "pgid", "pid_started", "process_token", "session_id",
            "output_path", "stderr_path", "executable_path", "companion_path",
        ))
        or not isinstance(scope, list)
        or not scope
        or any(not isinstance(item, str) or not item.strip() for item in scope)
        or any(not _covered(item.rstrip("/"), effective) for item in scope)
        or brief.is_symlink()
        or not brief.is_file()
        or entry.get("brief_path") != brief.relative_to(base).as_posix()
        or entry.get("brief_sha256") != sha256_of(brief)
    ):
        return None
    return list(scope)


def _host_native_preparation_valid(
        base: Path, stage_id: str, stage: dict, task: dict) -> bool:
    """Validate the latest process-free host-native dispatch preparation."""
    return _host_native_preparation_scope(base, stage_id, stage, task) is not None


def _require_successful_launch(base: Path, stage_id: str, stage: dict,
                               task: dict) -> str:
    """Require current native preparation or completed companion write proof."""
    from .codex_runtime import coordinator_runtime
    if coordinator_runtime() == "codex":
        if _host_native_preparation_valid(base, stage_id, stage, task):
            return ""
        fail(
            f"{stage_id} has no current host-native preparation bound to this "
            "stage, brief, task contract, and effective write scope. Run "
            f"`forge delegate {stage_id}`, dispatch its spawn_agent/followup_task "
            "descriptor through the host, then retry stage close."
        )

    from .delegate import current_delegation

    # Any contract version: the launch proves Codex wrote inside THIS stage.
    # Binding it to the contract digest orphaned every launch the moment the
    # contract was re-recorded, and the only way back was a Codex launch that
    # did nothing but produce a row with the new digest. The contract at
    # launch time stays on the row as evidence; `stage done` records a
    # contract that moved (decision 0023).
    entry = current_delegation(
        base,
        stage_id,
        stage_started_at=stage.get("started_at", ""),
        ignore_lock=True,
    )
    if _successful_launch_entry_valid(base, stage_id, stage, entry):
        return ""
    window = _host_window_covering(base, stage, task)
    if window:
        return str(window.get("id") or "?")
    fail(f"{stage_id} has no successful write launch bound to this stage. "
         "Either run `forge delegate "
         f"{stage_id}` successfully (`--print-only` is diagnostic only), or "
         "— when the fix is one Codex's sandbox cannot make (a DB-surfaced "
         "defect, a host-only check) — make it inside a ledgered window: "
         "`forge mode degraded start --reason \"<why Codex cannot>\"`, fix, "
         "`forge mode done` (opened while THIS stage is active so it is bound "
         "to it, closed with one to five files, all inside the task's write "
         "scope; a window opened before this binding existed does not count — "
         "reopen one).")


def _junit_case_name_parts(case) -> tuple[str, str]:
    """Return the qualified-name context and leaf for one JUnit case."""
    name = " ".join(str(case.get("name", "")).split())
    separators = (" > ", " › ", "::")
    position, separator = max(
        ((name.rfind(value), value) for value in separators),
        default=(-1, ""),
    )
    if position < 0:
        return "", name
    return name[:position].strip(), name[position + len(separator):].strip()


def _junit_case_matches_id(case, test_id: str) -> bool:
    """A JUnit <testcase> identifies the required test when its name equals the
    id, its leaf name does, OR the recorded id is a prefix of either (after
    normalising whitespace). Vitest/Jest prefix the testcase name with the
    describe path (e.g. 'application backbone > t1-boot-migrate'), so matching
    only the exact full name forces a describe-free test structure for no real
    gain — the leaf is what the required-test id names. Parametrised runners
    append a case suffix ('t1-boot-migrate [sqlite]'), which is why a prefix
    still identifies the test."""
    def norm(text: str) -> str:
        return " ".join(text.split())

    wanted = norm(test_id)
    if not wanted:
        return False
    name = norm(str(case.get("name", "")))
    candidates = [name]
    for sep in (" > ", " › ", "::"):
        if sep in name:
            candidates.append(name.rsplit(sep, 1)[-1].strip())
    # A prefix counts only when a parameter suffix follows — '[' or '(' after
    # optional whitespace — so neither 'test_slice_extra' nor 'test_slice more'
    # satisfies 'test_slice'.
    return any(
        c == wanted or (c.startswith(wanted)
                        and re.match(r"\s*[\[(]", c[len(wanted):]) is not None)
        for c in candidates
    )


def _junit_required_case_matches(
        cases: list[ET.Element], test_id: str, rel: str,
) -> tuple[list[ET.Element], str]:
    """Return all distinct, same-owner cases for one required test.

    A bare required id may represent a parametrized function, but it must not
    collapse duplicate cases or cases from another file/class/describe owner.
    """
    matches = [case for case in cases
               if _junit_case_matches_id(case, test_id)]
    if not matches:
        return [], "missing"
    owners: list[tuple[str, str, str]] = []
    leaves: list[str] = []
    for case in matches:
        if not _junit_case_attributed(case, rel):
            return [], "unattributed"
        context, leaf = _junit_case_name_parts(case)
        file_name = " ".join(str(case.get("file", "")).split())
        class_name = " ".join(str(case.get("classname", "")).split())
        owners.append((file_name, class_name, context))
        leaves.append(leaf)
    if len(set(owners)) != 1 or len(set(leaves)) != len(leaves):
        return [], "ambiguous"
    return matches, ""


def _junit_case_attributed(case, rel: str) -> bool:
    """Attribute a <testcase> to its declared source path. Runners record the
    file in `file` (some) or `classname` (vitest/jest), often RELATIVE TO THE
    RUNNER ROOT rather than the repo (vitest with a subdir `root:` emits
    'test/x.spec.ts' for a repo path 'apps/api/test/x.spec.ts'). Match by exact
    or path-suffix equality so a runner rooted in a subdirectory still attributes
    correctly, without forcing every project to reconfigure its test runner."""
    candidate = (str(case.get("file", "")) or str(case.get("classname", ""))
                 ).removeprefix("./").replace("\\", "/")
    if not candidate:
        return False
    declared = rel.replace("\\", "/")
    return (candidate == declared
            or declared.endswith("/" + candidate)
            or candidate.endswith("/" + declared))


def _require_test_input(base: Path, stage_id: str, proof: dict) -> None:
    """Validate a test input both before proof and immediately before use."""
    if not isinstance(proof, dict) or not all(
            isinstance(proof.get(key), str) for key in ("id", "path", "command")):
        fail(f"{stage_id} carries a legacy or malformed required_tests entry "
             f"{proof!r}. Re-record the decomposition with id, path and command.")
    if not (base / proof["path"]).is_file():
        fail(f"{stage_id} required test {proof['id']!r} is missing: {proof['path']}")


def _run_required_tests(
        base: Path, stage_id: str, task: dict) -> tuple[list[str], list[dict]]:
    """Run every required test and return only uniquely proven declarations."""
    from .delegate import (
        blocked_termination_signals, _capture_spawn_identity, _process_table,
        _terminate_observed_process_tree, _wait_and_reap,
        unblock_termination_signals_in_child,
    )

    misses: list[str] = []
    results: list[dict] = []
    for proof in task.get("required_tests") or []:
        _require_test_input(base, stage_id, proof)
        test_id = proof["id"]
        rel = proof["path"]
        command = proof["command"]
        with tempfile.TemporaryDirectory(prefix="forge-required-test-") as tmp:
            report = Path(tmp) / "junit.xml"
            tokens = [token.replace("{report}", str(report))
                      .replace("{path}", rel).replace("{id}", test_id)
                      for token in shlex.split(command)]
            env = os.environ.copy()
            process_token = f"proof-{uuid.uuid4().hex}"
            env["FORGE_PROCESS_TOKEN"] = process_token
            # Required selectors run with the same canonical-JUnit contract as
            # the aggregate verifier.  Bind the fresh report path even when a
            # caller inherited a stale value; an explicit leading assignment
            # remains authoritative because the shell-free runner applies it
            # below exactly as _proof_environment models it.
            env["FORGE_CANONICAL_JUNIT"] = str(report)
            while tokens and "=" in tokens[0] and not tokens[0].startswith("="):
                name, value = tokens.pop(0).split("=", 1)
                env[name] = value
            env["PYTHONUTF8"] = "1"
            proc: subprocess.Popen[str] | None = None
            process_baseline: dict[int, tuple[int, str]] | None = None
            process_identity = ""
            stdout = ""
            stderr = ""
            with tempfile.TemporaryFile(
                    mode="w+t", encoding="utf-8", errors="replace"
            ) as stdout_log, tempfile.TemporaryFile(
                    mode="w+t", encoding="utf-8", errors="replace"
            ) as stderr_log:
                try:
                    with blocked_termination_signals():
                        process_baseline = _process_table()
                        spawn_options = (
                            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                            if os.name == "nt"
                            else {"start_new_session": True,
                                  "preexec_fn": unblock_termination_signals_in_child}
                        )
                        if os.name == "nt":
                            # Windows CreateProcess cannot launch npm-style .cmd
                            # shims (npx, tsc, vitest, ...) directly with
                            # shell=False, so a bare `npx ...` required-test
                            # command fails with WinError 2. Run the command line
                            # through the shell so PATHEXT resolves the shim. The
                            # reaper works off a process-table snapshot, so the
                            # extra cmd.exe layer is still terminated.
                            proc = subprocess.Popen(
                                subprocess.list2cmdline(tokens), cwd=base,
                                stdout=stdout_log, stderr=stderr_log, text=True,
                                env=env, shell=True, **spawn_options,
                            )
                        else:
                            proc = subprocess.Popen(
                                tokens, cwd=base, stdout=stdout_log,
                                stderr=stderr_log, text=True, env=env,
                                **spawn_options,
                            )
                        process_identity = _capture_spawn_identity(proc)
                    if not _wait_and_reap(
                            proc, process_token, process_baseline,
                            process_identity):
                        fail(f"{stage_id} required test {test_id!r} left a "
                             "process tree alive; proof must be terminal")
                except OSError as exc:
                    if proc is not None:
                        with blocked_termination_signals():
                            _terminate_observed_process_tree(
                                proc, process_token, process_baseline,
                                process_identity)
                    action = (
                        "could not start" if proc is None
                        else "could not be registered"
                    )
                    fail(f"{stage_id} required test {test_id!r} "
                         f"{action}: {exc}")
                except BaseException:
                    if proc is not None:
                        with blocked_termination_signals():
                            _terminate_observed_process_tree(
                                proc, process_token, process_baseline,
                                process_identity)
                    raise
                stdout_log.seek(0)
                stderr_log.seek(0)
                stdout = stdout_log.read()
                stderr = stderr_log.read()
            if proc.returncode != 0:
                tail = (stderr or stdout or "").strip().splitlines()
                fail(f"{stage_id} required test {test_id!r} failed "
                     f"(exit {proc.returncode}): {command}\n"
                     + "\n".join(tail[-15:]))
            if not report.is_file():
                fail(f"{stage_id} required test {test_id!r} produced no fresh "
                     "JUnit report; its command must write {report}")
            try:
                root = ET.parse(report).getroot()
            except (ET.ParseError, OSError) as exc:
                fail(f"{stage_id} required test {test_id!r} produced invalid "
                     f"JUnit proof: {exc}")
            matches, match_problem = _junit_required_case_matches(
                list(root.iter("testcase")), test_id, rel,
            )
            if match_problem == "missing":
                misses.append(f"{test_id!r} was not present in the fresh JUnit "
                              "report (exact id or id-prefix)")
                results.append({"id": test_id, "path": rel, "status": "unmatched"})
                continue
            if match_problem == "ambiguous":
                misses.append(f"{test_id!r} was ambiguous in the fresh JUnit "
                              "report")
                results.append({"id": test_id, "path": rel, "status": "ambiguous"})
                continue
            if match_problem == "unattributed":
                misses.append(f"{test_id!r} was not attributed to its declared "
                              f"path {rel!r} in the fresh JUnit report")
                results.append({"id": test_id, "path": rel, "status": "unattributed"})
                continue
            if any(case.find("failure") is not None
                   or case.find("error") is not None
                   or case.find("skipped") is not None for case in matches):
                fail(f"{stage_id} required test {test_id!r} did not pass in the "
                     "fresh JUnit report")
            results.append({"id": test_id, "path": rel, "status": "passed"})
    return misses, results


def _canonical_verify_command(base: Path, command: str) -> bool:
    """Whether a command is the repository's direct canonical verifier."""
    return _canonical_verifier_identity(base, command) is not None


def _canonical_verifier_identity(
        base: Path, command: str,
) -> tuple[list[tuple[str, str]], list[str]] | None:
    """Return its allowed leading assignments and exact uv launcher, if any."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    prefix = _canonical_verifier_prefix(tokens)
    if prefix is None:
        return None
    assignments, remaining = prefix
    python = re.compile(r"python(?:3(?:\.\d+)?)?(?:\.exe)?", re.IGNORECASE)
    launcher: list[str] = []
    if (len(remaining) >= 2
            and Path(remaining[0]).name.lower() in {"uv", "uv.exe"}
            and remaining[1] == "run"):
        index = 2
        with_count = 0
        python_option = False
        python_index = -1
        while index < len(remaining):
            token = remaining[index]
            if python.fullmatch(Path(token).name):
                python_index = index
                break
            if (token == "--python" and not python_option
                    and index + 1 < len(remaining)):
                if not re.fullmatch(r"\d+(?:\.\d+){0,2}", remaining[index + 1]):
                    return None
                python_option = True
                index += 2
                continue
            if token == "--with" and index + 1 < len(remaining):
                package = remaining[index + 1]
                if (not package or package.startswith("-")
                        or any(character.isspace() for character in package)
                        or any(character in package for character in ";&|<>`\n")):
                    return None
                with_count += 1
                index += 2
                continue
            return None
        if python_index < 0 or with_count == 0:
            return None
        launcher = remaining[:python_index]
        remaining = remaining[python_index:]
    if (len(remaining) != 2
            or not python.fullmatch(Path(remaining[0]).name)
            or os.path.abspath(base / remaining[1]) != os.path.abspath(
                base / "factory/scripts/verify.py")):
        return None
    return assignments, launcher


def _canonical_verifier_prefix(
        tokens: list[str],
) -> tuple[list[tuple[str, str]], list[str]] | None:
    """Strip the small launcher prefix the canonical verifier owns.

    The close command is launched with uv's cache and tool directories in its
    environment.  Those two values affect which interpreter and distributions
    the verifier can load, so they belong in the producer identity.  Other
    inline assignments can change the verifier's selected command or pytest's
    semantics; an unknown assignment is therefore an explicit conservative
    fallback rather than something this parser guesses about.
    """
    assignments: list[tuple[str, str]] = []
    remaining = list(tokens)
    while remaining and re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*=.*", remaining[0]):
        name, value = remaining.pop(0).split("=", 1)
        if name not in {"UV_CACHE_DIR", "UV_TOOL_DIR"}:
            return None
        if (not value or not Path(value).is_absolute()
                or any(character in value for character in ";&|<>`\n")):
            return None
        if any(previous == name for previous, _value in assignments):
            return None
        assignments.append((name, value))
    return assignments, remaining


def _factory_env_from_envrc(base: Path) -> dict[str, str]:
    """Read the simple FACTORY exports that verify.py loads from .envrc."""
    path = base / ".envrc"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    vendored = (base / "constitution" / "VENDORED_FROM").is_file()
    skipping = False
    found: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("if ") and "VENDORED_FROM" in stripped:
            skipping = vendored
            continue
        if stripped in {"fi", "else"}:
            skipping = False
            continue
        if skipping or not stripped.startswith("export FACTORY_"):
            continue
        name, _, value = stripped[len("export "):].partition("=")
        if not name.endswith("_CMD"):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if "$" not in value:
            found[name] = value
    return found


def _factory_test_command(base: Path) -> str:
    """Resolve the declared full test command without executing a shell."""
    current = (os.environ.get("FACTORY_TEST_CMD") or "").strip()
    if current:
        return current
    return _factory_env_from_envrc(base).get("FACTORY_TEST_CMD", "")


def _canonical_test_command_for_task(base: Path, task: dict) -> str:
    """Resolve a full-suite command only when the verifier producer is unique.

    ``verify.py`` reads its test command in the verifier subprocess. A leading
    assignment on the task's verifier command, or an inherited ``PYTEST_*``
    override, can therefore produce a JUnit report under different semantics
    from the command visible to close. Dedicated selectors are cheap and are
    the safe fallback whenever that producer binding is ambiguous.
    """
    # These are assigned by pytest-xdist for the hosting worker. They do not
    # alter collection or test semantics of the child verifier; every proof
    # identity still binds their actual values through _proof_environment.
    pytest_runtime_keys = {
        "PYTEST_CURRENT_TEST", "PYTEST_VERSION", "PYTEST_XDIST_WORKER",
        "PYTEST_XDIST_WORKER_COUNT", "PYTEST_XDIST_TESTRUNUID",
    }
    if any(key.startswith("PYTEST_") and key not in pytest_runtime_keys and value
           for key, value in os.environ.items()):
        return ""
    candidates = [
        str(command) for command in task.get("verify_commands") or []
        if str(command).strip() and _canonical_verify_command(base, str(command))
    ]
    if len(candidates) != 1:
        return ""
    identity = _canonical_verifier_identity(base, candidates[0])
    if identity is None:
        return ""
    assignments, _launcher = identity
    command = _factory_test_command(base)
    if not command:
        return ""
    try:
        producer = shlex.split(command)
    except ValueError:
        return ""
    if not producer:
        return ""
    # The verifier launcher is bound separately in proof_identity; do not wrap
    # the test command again because .envrc may already provide its own uv run.
    return shlex.join([*(f"{name}={value}" for name, value in assignments),
                       *producer])


def _canonical_verifier_launcher_for_task(base: Path, task: dict) -> list[str] | None:
    candidates = [
        str(command) for command in task.get("verify_commands") or []
        if str(command).strip() and _canonical_verify_command(base, str(command))
    ]
    if len(candidates) != 1:
        return None
    identity = _canonical_verifier_identity(base, candidates[0])
    return identity[1] if identity is not None else None


def _pytest_collection_path_candidates(
        base: Path, args: list[str],
) -> list[tuple[Path, Path]] | None:
    """Return lexical and resolved explicit pytest collection paths."""
    value_options = {
        "-c", "--config-file", "-o", "--override-ini", "--junitxml",
        "--maxfail", "-n", "--dist", "--durations", "--tb", "--color",
        "--capture", "--log-level", "--basetemp", "--cov", "--cov-report",
        "-k", "--keyword", "-m", "--markexpr", "--ignore", "--deselect",
    }
    paths: list[tuple[Path, Path]] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token in value_options:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        raw = token.split("::", 1)[0]
        candidate = Path(raw)
        lexical = candidate if candidate.is_absolute() else base / candidate
        resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()
        if resolved.exists() or resolved == base.resolve() \
                or base.resolve() in resolved.parents:
            paths.append((lexical, resolved))
        index += 1
    return paths or None


def _pytest_collection_has_node_selector(args: list[str]) -> bool:
    """Whether explicit pytest collection names include a ``::`` node."""
    value_options = {
        "-c", "--config-file", "-o", "--override-ini", "--junitxml",
        "--maxfail", "-n", "--dist", "--durations", "--tb", "--color",
        "--capture", "--log-level", "--basetemp", "--cov", "--cov-report",
        "-k", "--keyword", "-m", "--markexpr", "--ignore", "--deselect",
    }
    index = 0
    while index < len(args):
        token = args[index]
        if token in value_options:
            index += 2
            continue
        if not token.startswith("-") and "::" in token:
            return True
        index += 1
    return False


def _pytest_collection_paths(
        base: Path, command: str, *, require_broad: bool = False,
) -> list[Path] | None:
    """Return explicit pytest collection roots for a shell-free command."""
    try:
        tokens, environment, _identity = _proof_environment(
            command, fixed_after_assignments=True,
        )
    except ValueError:
        return None
    if any(character in command for character in ";|&<>`\n") or "$(" in command:
        return None
    module = next((index for index, token in enumerate(tokens[:-1])
                   if token == "-m" and tokens[index + 1] == "pytest"), -1)
    if module < 0:
        return None
    args = tokens[module + 2:]
    if not _pytest_collection_inputs_known(base, args, environment):
        return None
    if require_broad and _pytest_collection_has_node_selector(args):
        return None
    selectors = ("-k", "--keyword", "-m", "--markexpr", "--ignore",
                 "--deselect", "--pyargs")
    if require_broad and any(
            token in selectors or token.startswith(
                ("--ignore=", "--deselect=", "-k=", "--keyword=", "-m="))
            for token in args):
        return None
    paths: list[Path] = []
    for lexical, resolved in _pytest_collection_path_candidates(base, args) or ():
        if _pytest_path_has_linked_component(base, lexical):
            return None
        paths.append(resolved)
    return paths or None


def _pytest_path_has_linked_component(base: Path, candidate: Path) -> bool:
    """Reject a collection path whose Git-visible spelling follows a link."""
    try:
        relative = candidate.relative_to(base)
    except ValueError:
        return True
    current = base
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _pytest_directory_has_linked_input(directory: Path) -> bool:
    """Reject directory collection when any descendant follows a symlink."""
    try:
        for current, directories, files in os.walk(directory, followlinks=False):
            current_path = Path(current)
            if any((current_path / name).is_symlink() for name in directories):
                return True
            if any((current_path / name).is_symlink() for name in files):
                return True
    except OSError:
        return True
    return False


def _pytest_collection_inputs_known(
        base: Path, args: list[str], environment: dict[str, str],
) -> bool:
    """Reject collection reuse when pytest adds unknown collection inputs.

    The normal direct command binds its explicit collection paths.  Pytest
    configuration can add paths and collection rules through several formats
    and multiline syntaxes; treating an unparsed config as empty would make a
    stale receipt look complete.  Dedicated selectors are the conservative
    fallback for any nonempty addopts or discovered/explicit config.
    """
    try:
        if shlex.split(environment.get("PYTEST_ADDOPTS", "")):
            return False
    except ValueError:
        return False
    override_values: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token in {"-o", "--override-ini"}:
            if index + 1 >= len(args):
                return False
            override_values.append(args[index + 1])
            index += 2
            continue
        if token.startswith("--override-ini="):
            override_values.append(token.split("=", 1)[1])
        elif token.startswith("-o="):
            override_values.append(token[3:])
        elif token.startswith("-o") and len(token) > 2:
            override_values.append(token[2:])
        index += 1
    for value in override_values:
        key, separator, setting = value.partition("=")
        if (not separator or key.strip().casefold() != "junit_family"
                or setting.strip().casefold() != "legacy"):
            return False
    config_requested = any(
        token == "-c" or token == "--config-file"
        or token.startswith("--config-file=")
        or (token.startswith("-c") and token != "-c")
        for token in args
    )
    if config_requested:
        return False
    config_names = (
        "pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml",
        "pyproject.toml", "tox.ini", "setup.cfg",
    )
    scan_roots = [base.resolve()]
    for lexical, _resolved in _pytest_collection_path_candidates(base, args) or ():
        scan_roots.append(lexical if lexical.is_dir() else lexical.parent)
    seen_roots: set[Path] = set()
    for root in scan_roots:
        current = root.absolute()
        while current not in seen_roots:
            seen_roots.add(current)
            if any((current / name).exists() or (current / name).is_symlink()
                   for name in config_names):
                return False
            if current == current.parent:
                break
            current = current.parent
    return True


def _proof_command_with_test_inputs(command: str, path: str, test_id: str) -> str:
    """Resolve the recorder's test placeholders before binding collection paths."""
    try:
        return command.format(path=path, id=test_id, report="{report}")
    except (IndexError, KeyError, ValueError):
        return command


def _ignored_pytest_sources(base: Path, directory: Path) -> bool:
    """Refuse a directory proof when Git reports an ignored collection input."""
    try:
        relative = directory.relative_to(base).as_posix() or "."
        proc = subprocess.run(
            ["git", "status", "--porcelain=v1", "--ignored",
             "--untracked-files=normal", "-z", "--", relative],
            cwd=base, capture_output=True, env=clean_git_env(), timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return True
    if proc.returncode != 0:
        return True
    for entry in proc.stdout.split(b"\0"):
        if not entry.startswith(b"!! "):
            continue
        return True
    return False


def _pytest_identity_projection(identity: dict[str, object]) -> dict[str, object]:
    """Keep the runtime/config identity while ignoring command spelling."""
    return {
        key: identity.get(key)
        for key in ("environment", "interpreter", "python_version",
                    "dependencies", "uv_bootstrap", "uv_overlay_sha256",
                    "pytest_config", "pytest_semantics",
                    "canonical_verifier_launcher")
        if key in identity
    }


def _pytest_semantic_args(command: str) -> list[str] | None:
    """Normalize pytest options that can change what a run executes."""
    try:
        tokens, _environment, _identity = _proof_environment(
            command, fixed_after_assignments=True,
        )
    except ValueError:
        return None
    module = next((index for index, token in enumerate(tokens[:-1])
                   if token == "-m" and tokens[index + 1] == "pytest"), -1)
    if module < 0:
        return None
    args = tokens[module + 2:]
    collection = ("-k", "--keyword", "-m", "--markexpr", "--ignore",
                  "--deselect", "--pyargs")
    safe_with_value = {
        "-n", "--numprocesses", "--dist", "--durations", "--junitxml",
        "--tb", "--color", "--capture", "--show-capture", "--log-level",
        "--maxfail", "--basetemp", "--cov", "--cov-report",
    }
    result: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token.startswith("--") and "=" in token:
            option, value = token.split("=", 1)
            if option in collection:
                index += 1
                continue
            if option in safe_with_value or option in {"--disable-warnings",
                                                        "--no-header", "--no-summary"}:
                index += 1
                continue
            result.append(token)
            index += 1
            continue
        if token in collection:
            index += 2
            continue
        if token in safe_with_value:
            index += 2
            continue
        if token in {"-q", "--quiet", "-v", "--verbose", "--disable-warnings",
                     "--no-header", "--no-summary"}:
            index += 1
            continue
        if token in {"-o", "--override-ini"}:
            value = args[index + 1] if index + 1 < len(args) else ""
            if value == "junit_family=legacy":
                index += 2
                continue
            result.extend((token, value))
            index += 2
            continue
        if token.startswith("-"):
            result.append(token)
            if index + 1 < len(args) and not args[index + 1].startswith("-"):
                result.append(args[index + 1])
                index += 2
            else:
                index += 1
            continue
        # Collection paths and node ids are intentionally excluded: the
        # canonical report is accepted only after each declared path is covered.
        index += 1
    return result


def _compileall_source_inputs(
        base: Path, python_args: list[str],
        allowed_product_paths: set[Path] | None,
) -> list[str] | None:
    """Resolve the complete, Git-visible Python inputs of compileall.

    ``compileall`` without an explicit source reads ``sys.path`` and a
    directory recursively reads every Python file beneath it.  Neither is a
    complete proof input unless the files can be enumerated and every source
    is part of the product snapshot.  Refuse symlinks, external paths,
    options with runner-specific semantics, and untracked/ignored sources;
    explicit regular files and ordinary tracked directories remain reusable.
    """
    if len(python_args) < 3 or python_args[0:2] != ["-m", "compileall"]:
        return None
    if allowed_product_paths is None:
        snapshot = product_tree_snapshot(base)
        allowed_product_paths = {
            (base / relative).resolve()
            for field in ("tracked", "dirty")
            for relative in (snapshot.get(field) or {})
        }
    product_paths = {path.resolve() for path in allowed_product_paths}
    inputs: set[Path] = set()
    for raw in python_args[2:]:
        if raw.startswith("-"):
            return None
        candidate = Path(raw)
        candidate = candidate if candidate.is_absolute() else base / candidate
        try:
            relative_candidate = candidate.relative_to(base)
        except ValueError:
            return None
        current_candidate = base
        if any(
                (current_candidate := current_candidate / part).is_symlink()
                for part in relative_candidate.parts
        ):
            return None
        try:
            candidate = candidate.resolve(strict=True)
        except OSError:
            return None
        if base.resolve() not in candidate.parents and candidate != base.resolve():
            return None
        if candidate.is_file():
            if candidate.suffix != ".py" or candidate not in product_paths:
                return None
            inputs.add(candidate)
            continue
        if not candidate.is_dir():
            return None
        found = False
        for current, directories, files in os.walk(candidate, followlinks=False):
            current_path = Path(current)
            if any((current_path / name).is_symlink() for name in directories):
                return None
            for name in files:
                path = current_path / name
                if path.is_symlink():
                    return None
                if path.suffix != ".py":
                    continue
                found = True
                resolved = path.resolve()
                if resolved not in product_paths:
                    return None
                inputs.add(resolved)
        if not found:
            return None
    if not inputs:
        return None
    return sorted(path.relative_to(base.resolve()).as_posix() for path in inputs)


def _run_verify_commands(
    base: Path, stage_id: str, task: dict, canonical_junit: Path | None = None,
) -> list[dict]:
    from .delegate import (
        blocked_termination_signals, _capture_spawn_identity, _process_table,
        _terminate_observed_process_tree, _wait_and_reap,
        unblock_termination_signals_in_child,
    )

    results: list[dict] = []
    for command in task.get("verify_commands") or []:
        if not str(command).strip():
            continue
        proc: subprocess.Popen[str] | None = None
        process_baseline: dict[int, tuple[int, str]] | None = None
        process_identity = ""
        process_token = f"verify-{uuid.uuid4().hex}"
        env = os.environ.copy()
        env["FORGE_PROCESS_TOKEN"] = process_token
        env["PYTHONUTF8"] = "1"
        if canonical_junit is not None and _canonical_verify_command(
                base, str(command)):
            env["FORGE_CANONICAL_JUNIT"] = str(canonical_junit)
        with tempfile.TemporaryFile(
                mode="w+t", encoding="utf-8", errors="replace"
        ) as stdout_log, tempfile.TemporaryFile(
                mode="w+t", encoding="utf-8", errors="replace"
        ) as stderr_log:
            try:
                with blocked_termination_signals():
                    process_baseline = _process_table()
                    spawn_options = (
                        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                        if os.name == "nt"
                        else {"start_new_session": True,
                              "preexec_fn": unblock_termination_signals_in_child}
                    )
                    proc = subprocess.Popen(
                        str(command), cwd=base, shell=True, stdout=stdout_log,
                        stderr=stderr_log, text=True, env=env,
                        **spawn_options,
                    )
                    process_identity = _capture_spawn_identity(proc)
                if not _wait_and_reap(
                        proc, process_token, process_baseline,
                        process_identity):
                    fail(f"{stage_id} verify command left a process tree alive; "
                         "verification must be terminal")
            except OSError as exc:
                if proc is not None:
                    with blocked_termination_signals():
                        _terminate_observed_process_tree(
                            proc, process_token, process_baseline,
                            process_identity)
                action = (
                    "could not start" if proc is None
                    else "could not be registered"
                )
                fail(f"{stage_id} verify command {action}: {exc}")
            except BaseException:
                if proc is not None:
                    with blocked_termination_signals():
                        _terminate_observed_process_tree(
                            proc, process_token, process_baseline,
                            process_identity)
                raise
            stdout_log.seek(0)
            stderr_log.seek(0)
            stdout = stdout_log.read()
            stderr = stderr_log.read()
        if proc.returncode != 0:
            tail = (stderr or stdout or "").strip().splitlines()
            fail(f"{stage_id} verify command failed (exit {proc.returncode}): "
                 f"{command}\n" + "\n".join(tail[-15:]))
        results.append({
            "command": str(command), "exit_code": proc.returncode,
            "output_tail": _output_tail(stdout, stderr),
        })
    return results


def _output_tail(stdout: str, stderr: str, lines: int = 40) -> str:
    """The end of a proof command's output: enough to read a failure from the
    record, small enough that verify.json stays a record and not a log."""
    text = (stderr or "").rstrip()
    if stdout and stdout.strip():
        text = (text + "\n" if text else "") + stdout.rstrip()
    return "\n".join(text.splitlines()[-lines:])


STAGE_PROOF = "stage-proof"


def proof_key(
        base: Path, task: dict, *,
        verify_identity: dict[str, object] | None = None,
        test_identity: dict[str, object] | None = None,
) -> str:
    """Return a provenance key derived from the complete proof identities.

    This key is descriptive evidence only. Reuse is authorized by the typed
    receipts below, which bind command, environment, tool, distribution,
    generated-input, and product identities independently for verify and tests.
    """
    snapshot = None
    if verify_identity is None or test_identity is None:
        snapshot = product_tree_snapshot(base)
    memo: dict[tuple[tuple[str, ...], str], dict[str, object]] = {}
    verify_identity = verify_identity or proof_identity(
        base, task, "verify", product_tree=snapshot, tool_probe_memo=memo,
    )
    test_identity = test_identity or proof_identity(
        base, task, "tests", product_tree=snapshot, tool_probe_memo=memo,
    )
    bound = {
        "verify": {"identity": verify_identity.get("identity"),
                   "inputs": verify_identity.get("inputs")},
        "tests": {"identity": test_identity.get("identity"),
                  "inputs": test_identity.get("inputs")},
    }
    return hashlib.sha256(
        json.dumps(bound, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _close_proof_results_match(
        task: dict, verify_results: object, test_results: object,
) -> bool:
    commands = [str(command) for command in task.get("verify_commands") or []
                if str(command).strip()]
    required = [proof for proof in task.get("required_tests") or []
                if isinstance(proof, dict)]
    if not (commands or required):
        return False
    return (_close_verify_results_match(commands, verify_results)
            and _close_test_results_match(required, test_results))


def _close_verify_results_match(commands: list[str], results: object) -> bool:
    return (isinstance(results, list) and len(results) == len(commands)
            and all(isinstance(result, dict)
                    and result.get("command") == command
                    and result.get("exit_code") == 0
                    for result, command in zip(results, commands)))


def _close_test_results_match(required: list[dict], results: object) -> bool:
    return (isinstance(results, list) and len(results) == len(required)
            and all(isinstance(result, dict)
                    and result.get("id") == proof.get("id")
                    and result.get("path") == proof.get("path")
                    and result.get("status") == "passed"
                    for result, proof in zip(results, required)))


def record_stage_proof(base: Path, stage_id: str, task: dict, *, key: str,
                       verify_results: list[dict], test_results: list[dict],
                       test_id_misses: list[str],
                       close_owned: bool = False,
                       commands_run: list[str] | None = None) -> None:
    """Write what the proof ran as the task's verify.json, re-bind the worker's
    tests.json record to the measured commit, or write one where none exists.

    The review gate and the task proof predicate read these two files; before
    this they came from a separate `verify.py` run and a hand-typed record, so
    the same commands ran two or three more times per close. The measurement
    lives in verify.json. The worker's record keeps its narrative; its commit
    binds it to a tree, and after a fix commit the review brief refuses the
    stale binding -- the coordinator re-recorded the same report at every
    commit by hand. The proof re-binds it instead, and only while no review
    covers the tree: the brief renders the record verbatim inside its
    approved-input section, so an edit after a review would stale that
    brief. A task without a record gets a harness record at close. Outside
    close, a user-facing task still owes its own design-skill attestation."""
    story = active_story_key(base)
    if not story:
        return
    head = head_sha(base)
    now = now_iso()
    tree = product_tree_digest(base)
    dump_json(
        task_evidence_path(base, story, stage_id, "verify.json", for_write=True),
        {
            "ok": True, "completed_at": now, "commit": head, "task_id": stage_id,
            "recorded_by": STAGE_PROOF, "tree_digest": tree, "proof_key": key,
            "results": verify_results, "required_tests": test_results,
            "test_id_misses": list(test_id_misses),
        },
    )
    tests_path = task_evidence_path(base, story, stage_id, "tests.json", for_write=True)
    tests = load_json(tests_path, default={})
    if not isinstance(tests, dict):
        tests = {}
    automated = tests.get("automated")
    if isinstance(automated, dict):
        if _review_covers_tree(base, stage_id, task):
            return
        if close_owned:
            if (automated.get("status") != "passed"
                    or automated.get("blocking_findings")):
                fail(
                    f"{stage_id} has an existing automated report that is not "
                    "a passing close-owned proof; refusing to overwrite it"
                )
            worker_commit = automated.get("commit")
            if worker_commit and worker_commit != head:
                automated.setdefault("worker_commit", worker_commit)
            actual_commands = [
                str(command) for command in (commands_run or [])
                if str(command).strip()
            ]
            existing_commands = [
                str(command) for command in automated.get("commands_run") or []
                if str(command).strip()
            ]
            for command in actual_commands:
                if command not in existing_commands:
                    existing_commands.append(command)
            automated["commands_run"] = existing_commands
            summary = str(automated.get("pass_fail_summary") or "").rstrip()
            covered = [
                str(result.get("id")) for result in test_results
                if isinstance(result, dict) and str(result.get("id") or "").strip()
            ]
            marker = (
                "close-owned proof: "
                f"{len(verify_results)} verifier result(s), "
                f"{len(test_results)} required test result(s) passed; "
                f"covered ids={','.join(covered) if covered else '<none>'}; "
                f"executed commands={len(actual_commands)}; backing=verify.json"
            )
            if marker not in summary:
                automated["pass_fail_summary"] = (
                    f"{summary}\n{marker}" if summary else marker
                )
            automated["bound_by"] = STAGE_PROOF
            automated["bound_at"] = now
            automated["commit"] = head
            tests["commit"] = head
            tests["updated_at"] = now
            validate_payload(base, "test-automated", automated)
            dump_json(tests_path, tests)
            return
        if automated.get("commit") == head:
            return
        automated.setdefault("worker_commit", automated.get("commit"))
        automated["commit"] = head
        automated["bound_by"] = STAGE_PROOF
        automated["bound_at"] = now
        tests["commit"] = head
        tests["updated_at"] = now
        dump_json(tests_path, tests)
        return
    if bool(task.get("user_facing")) and not close_owned:
        return
    actual_commands = [
        str(command) for command in (commands_run or [])
        if str(command).strip()
    ]
    commands = actual_commands if close_owned else [
        str(c) for c in task.get("verify_commands") or [] if str(c).strip()
    ]
    if not close_owned:
        commands += [str(p.get("command")) for p in task.get("required_tests") or []
                     if isinstance(p, dict)]
    covered_ids = ",".join(
        str(result.get("id")) for result in test_results
        if isinstance(result, dict) and str(result.get("id") or "").strip()
    ) or "<none>"
    summary = (
        "close-owned proof: "
        f"{len(verify_results)} verifier result(s), "
        f"{len(test_results)} required test result(s) passed; "
        f"covered ids={covered_ids}; "
        f"executed commands={len(actual_commands)}; backing=verify.json"
        if close_owned else
        f"task close ran {len(verify_results)} verify command(s) and "
        f"{len(test_results)} required test(s) at {head[:12]}; all passed"
    )
    automated = {
        "generated_by": STAGE_PROOF, "status": "passed",
        "summary": summary,
        "blocking_findings": [], "commands_run": commands,
        "tests_added_or_updated": [], "remaining_gaps": [],
        # The review brief refuses an empty scope; the harness ran the
        # proof over the contract's write scope.
        "reviewed_scope": [str(s) for s in task.get("write_scope") or []],
        "recorded_at": now, "commit": head,
    }
    if close_owned:
        automated["pass_fail_summary"] = summary
    validate_payload(base, "test-automated", automated)
    tests["automated"] = automated
    tests["commit"] = head
    tests["updated_at"] = now
    dump_json(tests_path, tests)


def _review_covers_tree(base: Path, stage_id: str, task: dict) -> bool:
    """Whether the stage's review stamp covers the product delta as it stands."""
    stage = next((item for item in load_stages(base).get("stages", [])
                  if item.get("id") == stage_id), None)
    return isinstance(stage, dict) and stamp_is_fresh(base, stage, task)


_CANONICAL_JUNIT_IDENTITY = "<forge-canonical-junit>"


def _canonical_junit_environment(report: Path | None = None) -> dict[str, str]:
    """Return the JUnit environment the canonical proof actually receives.

    The report path is temporary and must not become durable proof input.  A
    stable marker is used while building a receipt; the live report path is
    used while comparing a fresh report with required selectors.
    """
    return {
        "FORGE_CANONICAL_JUNIT": (
            str(report) if report is not None else _CANONICAL_JUNIT_IDENTITY
        ),
    }


def _canonical_junit_satisfies_required_tests(
        report: Path, task: dict, *, base: Path | None = None,
        canonical_command: str = "",
) -> bool:
    """Accept a full-suite report only when its runtime and collection cover match."""
    if base is None or not canonical_command:
        return False
    generated_paths = {
        (base / str(relative)).resolve()
        for relative in task.get("generated_semantic_inputs") or []
    }
    canonical_paths = _pytest_collection_paths(
        base, canonical_command, require_broad=True,
    )
    if canonical_paths is None:
        return False
    junit_environment = _canonical_junit_environment(report)
    canonical_environment = _factory_env_from_envrc(base)
    canonical_environment.update(junit_environment)
    canonical_tool = _proof_tool_identity(
        base, canonical_command, fixed_after_assignments=False,
        allowed_generated_paths=generated_paths,
        environment_overrides=canonical_environment,
    )
    if canonical_tool.get("reusable") is not True:
        return False
    verifier_launcher = _canonical_verifier_launcher_for_task(base, task)
    if verifier_launcher is None:
        return False
    canonical_tool["canonical_verifier_launcher"] = verifier_launcher
    try:
        root = ET.parse(report).getroot()
    except (ET.ParseError, OSError):
        return False
    cases = list(root.iter("testcase"))
    for proof in task.get("required_tests") or []:
        if not isinstance(proof, dict):
            return False
        test_id = proof.get("id")
        rel = proof.get("path")
        if not isinstance(test_id, str) or not isinstance(rel, str):
            return False
        required_path = (base / rel).resolve()
        if not any(
            candidate == required_path
            or (candidate.is_dir() and required_path == candidate)
            or (candidate.is_dir() and candidate in required_path.parents)
            for candidate in canonical_paths
        ):
            return False
        required_command = _proof_command_with_test_inputs(
            str(proof.get("command") or ""), rel, test_id,
        )
        required_tool = _proof_tool_identity(
            base, required_command, fixed_after_assignments=True,
            allowed_generated_paths=generated_paths,
            environment_overrides={
                **_factory_env_from_envrc(base), **junit_environment,
            },
        )
        required_tool["canonical_verifier_launcher"] = verifier_launcher
        if (required_tool.get("reusable") is not True
                or _pytest_identity_projection(required_tool)
                != _pytest_identity_projection(canonical_tool)):
            return False
        matches, match_problem = _junit_required_case_matches(
            cases, test_id, rel,
        )
        if match_problem or not matches:
            return False
        if any(case.find(outcome) is not None
               for case in matches
               for outcome in ("failure", "error", "skipped")):
            return False
    return True


def _file_identity(path: Path) -> dict[str, object]:
    info = path.stat()
    return {
        "path": str(path), "size": info.st_size, "mtime_ns": info.st_mtime_ns,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _stable_pytest_config_identity(path: Path) -> dict[str, object]:
    """Hash one regular config through the same no-follow file identity."""
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)
            or info.st_nlink != 1):
        raise ValueError("pytest config is linked or nonregular")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        body = b""
        while chunk := os.read(descriptor, 65536):
            body += chunk
        current = path.lstat()
    finally:
        os.close(descriptor)
    if ((opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            != (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
            or opened.st_nlink != 1):
        raise ValueError("pytest config identity changed")
    return {
        "size": opened.st_size, "sha256": hashlib.sha256(body).hexdigest(),
    }


def _explicit_pytest_config_identity(
    base: Path, python_args: list[str], environment: dict[str, str],
) -> dict[str, object] | None:
    """Bind one explicit pytest config without following or trusting its location."""
    values: list[str] = []

    def collect(args: list[str]) -> None:
        index = 0
        while index < len(args):
            token = args[index]
            if token in {"-c", "--config-file"}:
                if index + 1 >= len(args):
                    raise ValueError("missing pytest config path")
                values.append(args[index + 1])
                index += 2
                continue
            if token.startswith("--config-file="):
                values.append(token.split("=", 1)[1])
            elif token.startswith("-c") and token != "-c":
                values.append(token[2:])
            index += 1

    collect(python_args[2:])
    addopts = environment.get("PYTEST_ADDOPTS", "")
    try:
        collect(shlex.split(addopts))
    except ValueError as exc:
        raise ValueError("malformed PYTEST_ADDOPTS") from exc
    if not values:
        return None
    if len(values) != 1 or not values[0]:
        raise ValueError("ambiguous pytest config path")
    path = Path(values[0])
    path = path if path.is_absolute() else base / path
    return _stable_pytest_config_identity(path)


def _implicit_pytest_config_identity(base: Path) -> list[dict[str, object]]:
    """Bind every config pytest can discover from the invocation directory."""
    identities: list[dict[str, object]] = []
    current = base.resolve()
    ancestor = 0
    while True:
        for name in ("pytest.ini", ".pytest.ini", "pyproject.toml", "tox.ini",
                     "setup.cfg"):
            path = current / name
            if not path.exists() and not path.is_symlink():
                continue
            identity = _stable_pytest_config_identity(path)
            identities.append({
                "name": name, "ancestor": ancestor,
                **identity,
            })
        if current == current.parent:
            return identities
        current = current.parent
        ancestor += 1


def _proof_environment(
        command: str, *, fixed_after_assignments: bool,
        environment_overrides: dict[str, str] | None = None,
) -> tuple[list[str], dict[str, str], dict[str, object]]:
    """Return parsed argv and a secret-free identity for its effective env."""
    tokens = shlex.split(command)
    environment = os.environ.copy()
    if environment_overrides:
        for key, value in environment_overrides.items():
            # The canonical verifier unconditionally injects this value into
            # its child environment.  A caller may have inherited a stale
            # value, but it cannot replace the value the verifier actually
            # uses.  Other overrides retain the existing envrc semantics:
            # exported process values win over declarations from .envrc.
            if key == "FORGE_CANONICAL_JUNIT":
                environment[key] = value
            else:
                environment.setdefault(key, value)
    # Proof runners replace this nonce and force UTF-8 mode. Bind the full
    # environment they pass to the child, not values they have overwritten.
    environment["FORGE_PROCESS_TOKEN"] = "<forge-generated>"
    if not fixed_after_assignments:
        environment["PYTHONUTF8"] = "1"
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        key, value = tokens.pop(0).split("=", 1)
        environment[key] = value
    if fixed_after_assignments:
        environment["PYTHONUTF8"] = "1"
    canonical = json.dumps(
        sorted(environment.items()), separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    identity = {"sha256": hashlib.sha256(canonical).hexdigest(),
                "entries": len(environment)}
    return tokens, environment, identity


_PYTHON_IMPORT_SUFFIXES = {
    ".py", ".pyi", ".pyc", ".pth", ".so", ".pyd", ".dll", ".dylib",
    ".zip", ".egg", ".whl", ".pyz",
}


def _linked_path_component(path: Path, *, stop: Path | None = None) -> bool:
    """Whether a source path or one of its ancestors is a filesystem link."""
    current = path.absolute()
    stop_at = stop.absolute() if stop is not None else None
    while True:
        if stop_at is not None and current == stop_at:
            return False
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                return True
        except OSError:
            return True
        if current == current.parent:
            return False
        current = current.parent


def _python_import_files(root: Path) -> set[Path] | None:
    """Enumerate importable files below one path without following links."""
    try:
        if _linked_path_component(root):
            return None
        info = root.lstat()
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode):
        return None
    if stat.S_ISREG(info.st_mode):
        return {root.resolve()} if root.suffix.lower() in _PYTHON_IMPORT_SUFFIXES \
            else set()
    if not stat.S_ISDIR(info.st_mode):
        return None
    found: set[Path] = set()
    try:
        for current, directories, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            if any((current_path / name).is_symlink() for name in directories):
                return None
            for name in files:
                path = current_path / name
                if path.suffix.lower() not in _PYTHON_IMPORT_SUFFIXES:
                    continue
                leaf = path.lstat()
                if (stat.S_ISLNK(leaf.st_mode) or not stat.S_ISREG(leaf.st_mode)
                        or leaf.st_nlink != 1):
                    return None
                # Bytecode caches are derived from their source and are not a
                # distribution source in their own right.
                if path.suffix.lower() == ".pyc" \
                        and "__pycache__" in path.parts:
                    continue
                found.add(path.resolve())
    except OSError:
        return None
    return found


def _recorded_distribution_files(root: Path) -> set[Path] | None:
    """Read regular, single-link files named by RECORD below an import root."""
    records: set[Path] = set()
    found_record = False
    try:
        for current, _directories, files in os.walk(root, followlinks=False):
            current_path = Path(current)
            if any((current_path / name).is_symlink() for name in files):
                return None
            if "RECORD" not in files \
                    or not current_path.name.endswith(".dist-info"):
                continue
            found_record = True
            for row in csv.reader((current_path / "RECORD").read_text(
                    encoding="utf-8").splitlines()):
                if not row or not row[0]:
                    continue
                path = (current_path.parent / row[0]).resolve()
                root_path = root.resolve()
                if path != root_path and root_path not in path.parents:
                    if path.suffix.lower() in _PYTHON_IMPORT_SUFFIXES:
                        return None
                    continue
                info = path.lstat()
                if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
                        or info.st_nlink != 1):
                    return None
                records.add(path)
    except (OSError, UnicodeError, csv.Error):
        return None
    return records if found_record else None


def _pythonpath_sources_reusable(
        base: Path, environment: dict[str, str],
        allowed_product_paths: set[Path] | None,
) -> bool:
    """Reject mutable external PYTHONPATH roots without distribution records.

    Product-tree roots are covered by the product snapshot.  An external root
    is reusable only when every importable file is named by a regular,
    single-link distribution RECORD; an unknown root can change imports between
    proof runs even when the interpreter and installed distribution list stay
    unchanged.
    """
    raw = environment.get("PYTHONPATH", "")
    if not raw:
        return True
    base_path = base.resolve()
    if allowed_product_paths is None:
        snapshot = product_tree_snapshot(base)
        allowed_product_paths = {
            (base / relative).resolve()
            for field in ("tracked", "dirty")
            for relative in (snapshot.get(field) or {})
        }
    product_paths = {path.resolve() for path in allowed_product_paths}
    for entry in raw.split(os.pathsep):
        candidate = (base_path if not entry else Path(entry))
        if not candidate.is_absolute():
            candidate = base_path / candidate
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            return False
        if _linked_path_component(candidate):
            return False
        import_files = _python_import_files(resolved)
        if import_files is None:
            return False
        if not import_files:
            continue
        if resolved == base_path or base_path in resolved.parents:
            # Keep this check tied to the supplied snapshot so an external
            # path cannot be smuggled in through a spelling that resolves into
            # the product tree.
            if import_files.issubset(product_paths):
                continue
        recorded = _recorded_distribution_files(resolved)
        if recorded is None or not import_files.issubset(recorded):
            return False
    return True


def _proof_tool_identity(
        base: Path, command: str, *, fixed_after_assignments: bool = False,
        probe_memo: dict[tuple[tuple[str, ...], str], dict[str, object]] | None = None,
        allowed_generated_paths: set[Path] | None = None,
        allowed_product_paths: set[Path] | None = None,
        environment_overrides: dict[str, str] | None = None,
) -> dict[str, object]:
    """Resolve only the Python command shapes Forge declares for proof reuse."""
    try:
        tokens, environment, environment_identity = _proof_environment(
            command, fixed_after_assignments=fixed_after_assignments,
            environment_overrides=environment_overrides,
        )
    except ValueError:
        return {"command": command, "reusable": False}
    if not tokens:
        return {"command": "", "environment": environment_identity,
                "reusable": False}
    if not _pythonpath_sources_reusable(
            base, environment, allowed_product_paths):
        return {"command": tokens[0], "environment": environment_identity,
                "reusable": False}
    if allowed_product_paths is None:
        snapshot = product_tree_snapshot(base)
        allowed_product_paths = {
            (base / relative).resolve()
            for field in ("tracked", "dirty")
            for relative in (snapshot.get(field) or {})
        }
    if (any(character in command for character in ";|&<>`\n")
            or "$(" in command):
        return {"command": tokens[0], "environment": environment_identity,
                "reusable": False}
    outer = shutil.which(tokens[0], path=environment.get("PATH"))
    if not outer:
        return {"command": tokens[0], "environment": environment_identity,
                "reusable": False}
    outer_path = Path(outer)
    resolved_outer_path = outer_path.resolve()
    try:
        # Keep the command's executable path for the probe. Resolving a venv
        # symlink here can silently replace its interpreter with the base
        # Python, changing its installed distributions while the command still
        # names the venv entry point. Hash the resolved target for stable
        # runner identity, but execute the path the command actually resolved.
        runner = _file_identity(resolved_outer_path)
    except OSError:
        return {"command": tokens[0], "environment": environment_identity,
                "reusable": False}
    name = Path(tokens[0]).name.lower()
    if name in {"git", "git.exe"} and tokens == ["git", "diff", "--check"]:
        probe_argv = (str(outer_path), "config", "--list", "--show-origin", "--null")
        memo_key = (probe_argv, str(environment_identity["sha256"]))
        if probe_memo is not None and memo_key in probe_memo:
            return {**probe_memo[memo_key], "command": tokens[0],
                    "environment": environment_identity}
        try:
            config = subprocess.run(
                list(probe_argv),
                cwd=base, capture_output=True, check=True, timeout=20,
                env=environment,
            ).stdout
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            result = {"command": tokens[0], "runner": runner,
                      "environment": environment_identity, "reusable": False}
        else:
            result = {"command": tokens[0], "runner": runner,
                      "environment": environment_identity,
                      "config_sha256": hashlib.sha256(config).hexdigest(),
                      "reusable": True}
        if probe_memo is not None:
            probe_memo[memo_key] = result
        return dict(result)
    probe: list[str]
    python_args: list[str]
    if re.fullmatch(r"python(?:3(?:\.\d+)?)?(?:\.exe)?", name):
        python_args = tokens[1:]
        probe = [str(outer_path)]
    elif name in {"uv", "uv.exe"} and len(tokens) > 2 and tokens[1] == "run":
        python_index = next((index for index, token in enumerate(tokens[2:], 2)
                             if re.fullmatch(r"python(?:3(?:\.\d+)?)?(?:\.exe)?",
                                             Path(token).name.lower())), -1)
        if python_index < 0:
            return {"command": tokens[0], "runner": runner,
                    "environment": environment_identity, "reusable": False}
        python_args = tokens[python_index + 1:]
        probe = tokens[:python_index + 1]
    else:
        return {"command": tokens[0], "runner": runner,
                "environment": environment_identity, "reusable": False}
    canonical_verify = (
        len(python_args) == 1
        and os.path.abspath(base / python_args[0])
        == os.path.abspath(base / "factory/scripts/verify.py")
    )
    board_check = (
        len(python_args) == 1
        and os.path.abspath(base / python_args[0])
        == os.path.abspath(base / "factory/scripts/check_board_complete.py")
    )
    module = python_args[1] if len(python_args) >= 2 \
        and python_args[0] == "-m" else ""
    if not canonical_verify and not board_check \
            and module not in {"pytest", "compileall"}:
        return {"command": tokens[0], "runner": runner,
                "environment": environment_identity, "reusable": False}
    compileall_inputs = None
    if module == "compileall":
        compileall_inputs = _compileall_source_inputs(
            base, python_args, allowed_product_paths,
        )
        if compileall_inputs is None:
            return {"command": tokens[0], "runner": runner,
                    "environment": environment_identity, "reusable": False}
    if module == "pytest":
        collection_paths = _pytest_collection_paths(base, command)
        if collection_paths is None:
            return {"command": tokens[0], "runner": runner,
                    "environment": environment_identity, "reusable": False}
        allowed = {path.resolve() for path in (allowed_generated_paths or set())}
        if allowed_product_paths is None:
            snapshot = product_tree_snapshot(base)
            visible = {
                (base / relative).resolve()
                for field in ("tracked", "dirty")
                for relative in (snapshot.get(field) or {})
            }
        else:
            visible = {path.resolve() for path in allowed_product_paths}
        for candidate in collection_paths:
            if candidate in allowed:
                continue
            if candidate.is_dir():
                inside_base = (candidate == base.resolve()
                               or base.resolve() in candidate.parents)
                visible_under = inside_base and not _ignored_pytest_sources(
                    base, candidate,
                ) and not _pytest_directory_has_linked_input(candidate) and any(
                    path == candidate or candidate in path.parents
                    for path in visible
                )
            else:
                visible_under = candidate in visible
            if not visible_under:
                return {"command": tokens[0], "runner": runner,
                        "environment": environment_identity, "reusable": False}
    canonical_inputs = _canonical_verify_inputs(base) if canonical_verify else None
    if canonical_verify:
        if canonical_inputs is None:
            return {"command": tokens[0], "runner": runner,
                    "environment": environment_identity, "reusable": False}
        # The verifier is an aggregate shell pipeline whose phase tools and
        # effective environment are not completely modeled by this helper.
        # Preserve workflow-input metadata, but never reuse its receipt.
        return {
            "command": tokens[0], "runner": runner,
            "environment": environment_identity,
            "canonical_verify_inputs": canonical_inputs,
            "reusable": False,
        }
    try:
        pytest_config = None
        pytest_semantics = None
        if module == "pytest":
            pytest_config = _explicit_pytest_config_identity(
                base, python_args, environment,
            )
            if pytest_config is None:
                pytest_config = _implicit_pytest_config_identity(base)
            pytest_semantics = _pytest_semantic_args(command)
            if pytest_semantics is None:
                return {"command": tokens[0], "runner": runner,
                        "environment": environment_identity, "reusable": False}
    except (OSError, ValueError):
        return {"command": tokens[0], "runner": runner,
                "environment": environment_identity, "reusable": False}
    memo_probe = tuple(probe)
    if pytest_config is not None:
        memo_probe += ("<pytest-config>", hashlib.sha256(json.dumps(
            pytest_config, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest())
    memo_key = (memo_probe, str(environment_identity["sha256"]))
    if probe_memo is not None and memo_key in probe_memo:
        cached = {**probe_memo[memo_key], "command": tokens[0],
                  "environment": environment_identity}
        if canonical_inputs is not None:
            cached["canonical_verify_inputs"] = canonical_inputs
        if pytest_config is not None:
            cached["pytest_config"] = pytest_config
        if pytest_semantics is not None:
            cached["pytest_semantics"] = pytest_semantics
        return cached
    script = (
        "import csv,hashlib,importlib.metadata as m,json,os,pathlib,re,stat,sys,sysconfig\n"
        "def digest(d, name):\n"
        "    value = d.read_text(name)\n"
        "    if value is None:\n"
        "        raise ValueError(name)\n"
        "    return hashlib.sha256(value.encode()).hexdigest()\n"
        "recorded_paths = set()\n"
        "bootstrap_paths = set()\n"
        "def recorded_files(d, dist_name):\n"
        "    raw = d.read_text('RECORD')\n"
        "    if raw is None:\n"
        "        raise ValueError('RECORD')\n"
        "    rows = []\n"
        "    for fields in csv.reader(raw.splitlines()):\n"
        "        if not fields or not fields[0]:\n"
        "            continue\n"
        "        relative = fields[0]\n"
        "        is_pth = pathlib.PurePosixPath(relative).suffix == '.pth'\n"
        "        if (is_pth and (dist_name != 'setuptools'\n"
        "                or pathlib.PurePosixPath(relative).name\n"
        "                != 'distutils-precedence.pth')):\n"
        "            raise ValueError('unmodeled path entry')\n"
        "        path = pathlib.Path(d.locate_file(relative))\n"
        "        distribution_root = pathlib.Path(d.locate_file('')).absolute().resolve()\n"
        "        resolved_path = path.absolute().resolve()\n"
        "        if (resolved_path != distribution_root\n"
        "                and distribution_root not in resolved_path.parents\n"
        "                and pathlib.PurePosixPath(relative).suffix.lower()\n"
        "                    in {'.py', '.pyi', '.pyc', '.pth', '.so', '.pyd',\n"
        "                       '.dll', '.dylib', '.zip', '.egg', '.whl', '.pyz'}):\n"
        "            raise ValueError('recorded import path escaped distribution root')\n"
        "        optional_bytecode = (pathlib.PurePosixPath(relative).suffix\n"
        "                             == '.pyc'\n"
        "                             and '__pycache__' in pathlib.PurePosixPath(\n"
        "                                 relative).parts)\n"
        "        try:\n"
        "            info = path.lstat()\n"
        "        except FileNotFoundError:\n"
        "            if optional_bytecode:\n"
        "                continue\n"
        "            raise ValueError('missing recorded file')\n"
        "        except OSError:\n"
        "            raise ValueError('unreadable recorded file')\n"
        "        if path.is_symlink() or not stat.S_ISREG(info.st_mode):\n"
        "            raise ValueError('linked or non-regular recorded file')\n"
        "        if info.st_nlink != 1:\n"
        "            raise ValueError('multiply-linked recorded file')\n"
        "        body = path.read_bytes()\n"
        "        if is_pth:\n"
        "            expected = (\"import os; var = 'SETUPTOOLS_USE_DISTUTILS'; \"\n"
        "                        \"enabled = os.environ.get(var, 'local') == 'local'; \"\n"
        "                        \"enabled and __import__('_distutils_hack').add_shim();\")\n"
        "            if body.decode('utf-8').strip() != expected:\n"
        "                raise ValueError('unmodeled pth contents')\n"
        "        recorded_paths.add(path.resolve())\n"
        "        rows.append([relative, len(body), hashlib.sha256(body).hexdigest()])\n"
        "    if not rows:\n"
        "        raise ValueError('empty RECORD')\n"
        "    rows.sort(key=lambda row: row[0])\n"
        "    encoded = json.dumps(rows, separators=(',', ':'),\n"
        "                          ensure_ascii=False).encode()\n"
        "    return len(rows), hashlib.sha256(encoded).hexdigest()\n"
        "rows = []\n"
        "for d in m.distributions():\n"
        "    raw_name = d.metadata.get('Name', '')\n"
        "    name = re.sub(r'[-_.]+', '-', raw_name).lower()\n"
        "    if not name or not d.version:\n"
        "        raise ValueError('distribution identity')\n"
        "    direct_url = d.read_text('direct_url.json')\n"
        "    if direct_url:\n"
        "        info = json.loads(direct_url)\n"
        "        if (isinstance(info, dict) and isinstance(\n"
        "                info.get('dir_info'), dict)\n"
        "                and info['dir_info'].get('editable') is True):\n"
        "            raise ValueError('editable distribution')\n"
        "    files_count, files_sha256 = recorded_files(d, name)\n"
        "    rows.append({'name': name, 'version': d.version, "
        "'metadata_sha256': digest(d, 'METADATA'), "
        "'record_sha256': digest(d, 'RECORD'), "
        "'files_count': files_count, 'files_sha256': files_sha256})\n"
        "rows.sort(key=lambda row: row['name'])\n"
        "def under(path, roots):\n"
        "    return any(path == root or root in path.parents for root in roots)\n"
        "uv_roots = []\n"
        "for name in ('UV_CACHE_DIR', 'UV_TOOL_DIR'):\n"
        "    value = os.environ.get(name)\n"
        "    if value:\n"
        "        uv_roots.append(pathlib.Path(value).absolute().resolve())\n"
        "def under_uv(path):\n"
        "    return any(path == root or root in path.parents for root in uv_roots)\n"
        "uv_overlay_digests = set()\n"
        "def uv_overlay_name(path):\n"
        "    for index, root in enumerate(uv_roots):\n"
        "        if path == root or root in path.parents:\n"
        "            return (index, path.relative_to(root).as_posix())\n"
        "    raise ValueError('uv overlay path escaped root')\n"
"def bind_uv_overlay(path, sources):\n"
"    for source in sources:\n"
"        if source in recorded_paths or source in bootstrap_paths:\n"
"            continue\n"
"        if source.suffix.lower() == '.pth':\n"
"            # A path configuration file executes at interpreter startup.\n"
"            # Only the explicitly modelled bootstrap files and recorded\n"
"            # distribution entries may introduce one; an arbitrary uv\n"
"            # overlay .pth is an unbound import/code injection surface.\n"
"            raise ValueError('unmodeled uv overlay pth')\n"
"        body = regular_bytes(source)\n"
        "        uv_overlay_digests.add((uv_overlay_name(source), len(body),\n"
        "                                hashlib.sha256(body).hexdigest()))\n"
        "def regular_bytes(path):\n"
        "    try:\n"
        "        info = path.lstat()\n"
        "    except OSError:\n"
        "        raise ValueError('unreadable bootstrap file')\n"
        "    if (path.is_symlink() or not stat.S_ISREG(info.st_mode)\n"
        "            or info.st_nlink != 1):\n"
        "        raise ValueError('linked or non-regular bootstrap file')\n"
        "    return path.read_bytes()\n"
        "def collect_uv_bootstrap():\n"
        "    # uv's ephemeral environment overlays two unrecorded virtualenv\n"
        "    # shims into site-packages.  Bind only those exact filenames and\n"
        "    # their bytes; every other importable source still needs RECORD.\n"
        "    rows = []\n"
        "    seen = set()\n"
        "    for index, raw in enumerate(sys.path):\n"
        "        root = pathlib.Path(raw or '.').absolute()\n"
        "        if root.name != 'site-packages' or not root.is_dir():\n"
        "            continue\n"
        "        virtualenv_pth = root / '_virtualenv.pth'\n"
        "        if virtualenv_pth.is_file() and regular_bytes(virtualenv_pth).decode(\n"
        "                'utf-8').strip() == 'import _virtualenv':\n"
        "            candidate = root / '_virtualenv.py'\n"
        "            if not candidate.is_file():\n"
        "                raise ValueError('missing uv virtualenv bootstrap')\n"
        "            paths = (virtualenv_pth, candidate)\n"
        "        else:\n"
        "            paths = ()\n"
        "        overlay = root / '_uv_ephemeral_overlay.pth'\n"
        "        if overlay.is_file():\n"
        "            body = regular_bytes(overlay).decode('utf-8').strip()\n"
        "            values = re.findall(r'site\\.addsitedir\\(\\\"([^\\\"]+)\\\"\\)', body)\n"
        "            expected = 'import site; ' + '; '.join(\n"
        "                'site.addsitedir(\\\"' + value + '\\\")'\n"
        "                for value in values)\n"
        "            if (not values or body != expected\n"
        "                    or any(pathlib.Path(value).resolve()\n"
        "                           not in {pathlib.Path(item or '.').absolute().resolve()\n"
        "                                  for item in sys.path}\n"
        "                           for value in values)):\n"
        "                raise ValueError('unmodeled uv overlay')\n"
        "            paths += (overlay,)\n"
        "        for path in paths:\n"
        "            resolved = path.resolve()\n"
        "            if resolved in seen:\n"
        "                continue\n"
        "            body = regular_bytes(path)\n"
        "            seen.add(resolved)\n"
        "            bootstrap_paths.add(resolved)\n"
        "            rows.append({\n"
        "                'path': f'site-packages[{index}]/{path.name}',\n"
        "                'size': len(body),\n"
        "                'sha256': hashlib.sha256(body).hexdigest(),\n"
        "            })\n"
        "    rows.sort(key=lambda row: row['path'])\n"
        "    return rows\n"
        "uv_bootstrap = collect_uv_bootstrap()\n"
        "product_import_paths = []\n"
        "import_suffixes = {'.py', '.pyi', '.pyc', '.pth', '.so', '.pyd',\n"
        "                   '.dll', '.dylib', '.zip', '.egg', '.whl', '.pyz'}\n"
        "def importable_sources(root):\n"
        "    if root.is_file():\n"
        "        if root.suffix.lower() not in import_suffixes:\n"
        "            return []\n"
        "        try:\n"
        "            info = root.lstat()\n"
        "        except OSError:\n"
        "            return None\n"
        "        if (root.is_symlink() or not stat.S_ISREG(info.st_mode)\n"
        "                or info.st_nlink != 1):\n"
        "            return None\n"
        "        return [root.resolve()]\n"
        "    if not root.is_dir():\n"
        "        return None\n"
        "    found = []\n"
        "    try:\n"
        "        for current, directories, files in os.walk(\n"
        "                root, followlinks=False):\n"
        "            current_path = pathlib.Path(current)\n"
        "            if any((current_path / name).is_symlink()\n"
        "                   for name in directories):\n"
        "                return None\n"
        "            for name in files:\n"
        "                candidate = current_path / name\n"
        "                if candidate.suffix.lower() not in import_suffixes:\n"
        "                    continue\n"
        "                try:\n"
        "                    info = candidate.lstat()\n"
        "                except OSError:\n"
        "                    return None\n"
        "                if (candidate.is_symlink()\n"
        "                        or not stat.S_ISREG(info.st_mode)\n"
        "                        or info.st_nlink != 1):\n"
        "                    return None\n"
        "                if (candidate.suffix.lower() == '.pyc'\n"
        "                        and '__pycache__' in candidate.parts):\n"
        "                    continue\n"
        "                found.append(candidate.resolve())\n"
        "    except OSError:\n"
        "        return None\n"
        "    return found\n"
        "def import_sources_known():\n"
        "    cwd = pathlib.Path.cwd().resolve()\n"
        "    roots = []\n"
        "    for key in ('stdlib', 'platstdlib'):\n"
        "        value = sysconfig.get_paths().get(key)\n"
        "        if value:\n"
        "            roots.append(pathlib.Path(value).resolve())\n"
        "    for raw in sys.path:\n"
        "        raw_path = pathlib.Path(raw or '.').absolute()\n"
        "        try:\n"
        "            current = raw_path\n"
        "            while True:\n"
        "                if current.is_symlink() and not under_uv(raw_path.resolve()):\n"
        "                    return False\n"
        "                if current == current.parent:\n"
        "                    break\n"
        "                current = current.parent\n"
        "            path = raw_path.resolve()\n"
        "            if path.is_symlink() and not under_uv(path):\n"
        "                return False\n"
        "        except OSError:\n"
        "            return False\n"
        "        if under(path, roots):\n"
        "            continue\n"
        "        if path == cwd or cwd in path.parents:\n"
        "            sources = importable_sources(path)\n"
        "            if sources is None:\n"
        "                return False\n"
        "            product_import_paths.extend(str(item) for item in sources)\n"
        "            continue\n"
        "        if not path.exists():\n"
        "            # Python commonly includes a not-yet-created stdlib zip.\n"
        "            if path.suffix == '.zip' and any(\n"
        "                    path.parent == root.parent for root in roots):\n"
        "                continue\n"
        "            return False\n"
        "        if path.is_file():\n"
        "            if (path.resolve() not in recorded_paths\n"
        "                    and path.resolve() not in bootstrap_paths):\n"
        "                return False\n"
        "            continue\n"
        "        sources = importable_sources(path)\n"
        "        if sources is None:\n"
        "            return False\n"
        "        if under_uv(path):\n"
        "            bind_uv_overlay(path, sources)\n"
        "            continue\n"
        "        if any(source not in recorded_paths\n"
        "                   and source not in bootstrap_paths for source in sources):\n"
        "            return False\n"
        "    return True\n"
        "p = pathlib.Path(sys.executable)\n"
        "print(json.dumps({'interpreter_sha256': "
        "hashlib.sha256(p.read_bytes()).hexdigest(), "
        "'interpreter_size': p.stat().st_size, 'version': sys.version, "
        "'dependencies': rows, 'uv_bootstrap': uv_bootstrap,\n"
        "'uv_overlay_sha256': hashlib.sha256(json.dumps(\n"
        "    sorted(uv_overlay_digests), separators=(',', ':')).encode()\n"
        ").hexdigest(),\n"
        "'import_sources_known': import_sources_known(),\n"
        "'product_import_paths': sorted(set(product_import_paths))},\n"
        "              sort_keys=True))\n"
    )
    try:
        resolved = subprocess.run(
            [*probe, "-c", script], cwd=base,
            capture_output=True, text=True, encoding="utf-8", timeout=60,
            env=environment,
        )
        detail = json.loads(resolved.stdout) if resolved.returncode == 0 else None
        if (not isinstance(detail, dict)
                or not re.fullmatch(r"[0-9a-f]{64}", detail["interpreter_sha256"])
                or not isinstance(detail["interpreter_size"], int)
                or detail["interpreter_size"] <= 0
                or not isinstance(detail["version"], str)
                or not detail["version"]
                or not isinstance(detail["dependencies"], list)):
            raise ValueError
        if ("import_sources_known" in detail
                and detail["import_sources_known"] is not True):
            raise ValueError("unidentified Python import source")
        product_imports = detail.get("product_import_paths")
        if product_imports is not None:
            if (not isinstance(product_imports, list)
                    or any(not isinstance(path, str) for path in product_imports)):
                raise ValueError("invalid product import sources")
            product_paths = {
                path.resolve() for path in (allowed_product_paths or set())
            }
            for raw_path in product_imports:
                path = Path(raw_path)
                if not path.is_absolute() or path.resolve(strict=True) not in product_paths:
                    raise ValueError("unbound product import source")
        names: set[str] = set()
        for row in detail["dependencies"]:
            if (not isinstance(row, dict)
                    or set(row) != {"name", "version", "metadata_sha256",
                                    "record_sha256", "files_count",
                                    "files_sha256"}
                    or not isinstance(row["name"], str)
                    or row["name"] != re.sub(r"[-_.]+", "-", row["name"]).lower()
                    or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", row["name"])
                    or row["name"] in names
                    or not isinstance(row["version"], str)
                    or not row["version"]
                    or not re.fullmatch(r"[0-9a-f]{64}", row["metadata_sha256"])
                    or not re.fullmatch(r"[0-9a-f]{64}", row["record_sha256"])
                    or not isinstance(row["files_count"], int)
                    or isinstance(row["files_count"], bool)
                    or row["files_count"] <= 0
                    or not re.fullmatch(r"[0-9a-f]{64}", row["files_sha256"])):
                raise ValueError
            names.add(row["name"])
        if detail["dependencies"] != sorted(
                detail["dependencies"], key=lambda row: row["name"]):
            raise ValueError
        bootstrap = detail.get("uv_bootstrap", [])
        if (not isinstance(bootstrap, list)
                or any(
                    not isinstance(row, dict)
                    or set(row) != {"path", "size", "sha256"}
                    or not isinstance(row["path"], str)
                    or not re.fullmatch(
                        r"site-packages\[\d+\]/(?:_virtualenv\.py|"
                        r"_virtualenv\.pth|_uv_ephemeral_overlay\.pth)",
                        row["path"],
                    )
                    or not isinstance(row["size"], int)
                    or isinstance(row["size"], bool)
                    or row["size"] <= 0
                    or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                    for row in bootstrap
                )
                or bootstrap != sorted(bootstrap, key=lambda row: row["path"])
                or len({row["path"] for row in bootstrap}) != len(bootstrap)):
            raise ValueError("invalid uv bootstrap identity")
        overlay_sha256 = detail.get(
            "uv_overlay_sha256", hashlib.sha256(b"[]").hexdigest(),
        )
        if not isinstance(overlay_sha256, str) \
                or not re.fullmatch(r"[0-9a-f]{64}", overlay_sha256):
            raise ValueError("invalid uv overlay identity")
        result = {
            "command": tokens[0], "runner": runner,
            "environment": environment_identity,
            "interpreter": {"sha256": detail["interpreter_sha256"],
                            "size": detail["interpreter_size"]},
            "python_version": detail["version"],
            "dependencies": detail["dependencies"],
            "uv_bootstrap": bootstrap,
            "uv_overlay_sha256": overlay_sha256,
            "reusable": True,
        }
        if compileall_inputs is not None:
            result["compileall_inputs"] = compileall_inputs
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            TypeError, subprocess.TimeoutExpired):
        result = {"command": tokens[0], "runner": runner,
                  "environment": environment_identity, "reusable": False}
    if probe_memo is not None:
        probe_memo[memo_key] = result
    if canonical_inputs is not None:
        result["canonical_verify_inputs"] = canonical_inputs
    if pytest_config is not None:
        result["pytest_config"] = pytest_config
    if pytest_semantics is not None:
        result["pytest_semantics"] = pytest_semantics
    return dict(result)


def _canonical_verify_inputs(base: Path) -> dict[str, object] | None:
    """Bind the workflow state read by the repository's canonical verifier."""
    try:
        from factory_lib import (
            client_signoff, evidence_path, plan_digest_without_assumptions,
            protected_decomposition_state_path, run_state_path,
        )

        state = load_json(run_state_path(base), default={})
        story = str(state.get("story") or state.get("issue_key") or "")
        plan_file = state.get("plan_file")
        plan = base / plan_file if isinstance(plan_file, str) else None
        approval = evidence_path(base, story, "plan-approval.json") if story else None
        decomposition = protected_decomposition_state_path(base)

        def identity(path: Path | None) -> dict[str, object] | None:
            if path is None or not path.is_file():
                return None
            body = path.read_bytes()
            return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}

        signed, signoff_reason = client_signoff(base)
        return {
            "run": {key: state.get(key) for key in (
                "issue_key", "story", "plan_status", "plan_file",
                "approved_plan_sha256", "decomposition_status",
            )},
            "plan_digest": (
                plan_digest_without_assumptions(plan)
                if plan is not None and plan.is_file() else None
            ),
            "approval": identity(approval),
            "decomposition": identity(decomposition),
            "signoff": {"accepted": signed, "reason": signoff_reason},
        }
    except (OSError, TypeError, ValueError, SystemExit):
        return None


def _board_proof_inputs(base: Path) -> dict[str, object]:
    """Capture the non-product inputs read by check_board_complete.py."""
    from .events import load_events
    from .roadmap import load_items
    from factory_lib import factory_dir, story_dir

    done = [item for item in load_items(base) if item.get("status") == "done"]
    linked = sorted({event.get("story") for event in
                     load_events(base, event="pr-linked")
                     if isinstance(event.get("story"), str)})
    return {
        "done": done, "linked": linked,
        "archives": {str(item.get("key", "?")):
                     [story_dir(base, str(item.get("key", "?"))).is_dir(),
                      (factory_dir(base) / "history" /
                       str(item.get("key", "?"))).is_dir()]
                     for item in done},
    }


def _board_command_kind(base: Path, command: str) -> str:
    """Classify direct Board invocation without treating unknown shapes as reusable."""
    if "check_board_complete.py" not in command:
        return "absent"
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "unknown"
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens.pop(0)
    if (len(tokens) == 2
            and re.fullmatch(r"python(?:3(?:\.\d+)?)?(?:\.exe)?",
                             Path(tokens[0]).name.lower())
            and os.path.abspath(base / tokens[1]) ==
            os.path.abspath(base / "factory/scripts/check_board_complete.py")):
        return "direct"
    return "unknown"


def proof_identity(
        base: Path, task: dict, kind: str, *, product_tree: dict | None = None,
        tool_probe_memo: dict[
            tuple[tuple[str, ...], str], dict[str, object]
        ] | None = None,
) -> dict[str, object]:
    """Content identity for one independently reusable proof type."""
    if kind not in {"tests", "verify"}:
        raise ValueError("proof kind must be tests or verify")
    snapshot = (
        product_tree if product_tree is not None else product_tree_snapshot(base)
    )
    # HEAD still participates in the before/after read-only guard, but a
    # metadata-only commit must not invalidate byte-identical product proof.
    reuse_tree = {key: value for key, value in snapshot.items() if key != "head"}
    if kind == "tests":
        declarations = task.get("required_tests") or []
        commands = [
            _proof_command_with_test_inputs(
                str(entry.get("command") or ""),
                str(entry.get("path") or ""),
                str(entry.get("id") or ""),
            )
            for entry in declarations if isinstance(entry, dict)
        ]
        semantic = {"required_tests": declarations}
    else:
        commands = [str(command) for command in task.get("verify_commands") or []]
        semantic = {
            "verify_commands": commands,
            "generated_inputs": task.get("generated_semantic_inputs") or [],
        }
    generated: dict[str, dict[str, object] | None] = {}
    generated_paths: set[Path] = set()
    for relative in task.get("generated_semantic_inputs") or []:
        path = base / str(relative)
        generated_paths.add(path.resolve())
        try:
            data = path.read_bytes()
            generated[str(relative)] = {
                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            }
        except OSError:
            generated[str(relative)] = None
    allowed_product_paths = {
        (base / relative).resolve()
        for field in ("tracked", "dirty")
        for relative in (snapshot.get(field) or {})
    }
    tools = [
        _proof_tool_identity(
            base, command, fixed_after_assignments=(kind == "tests"),
            probe_memo=tool_probe_memo,
            allowed_generated_paths=generated_paths,
            allowed_product_paths=allowed_product_paths,
            environment_overrides=(
                _canonical_junit_environment()
                if kind == "tests" or _canonical_verify_command(base, command)
                else None
            ),
        )
        for command in commands
    ]
    if kind == "tests":
        # The full-suite command is an input to the required-test receipt only
        # when one of this task's verify commands can actually produce the
        # canonical JUnit report consumed by close. Dedicated compile/build
        # verifiers do not read FACTORY_TEST_CMD; binding an unrelated producer
        # would make their receipt drift when pytest creates its own caches.
        canonical_command = _canonical_test_command_for_task(base, task)
        semantic["canonical_test_command_sha256"] = (
            hashlib.sha256(canonical_command.encode("utf-8")).hexdigest()
            if canonical_command else ""
        )
        semantic["canonical_verifier_launcher"] = (
            _canonical_verifier_launcher_for_task(base, task)
            if canonical_command else None
        )
        if canonical_command:
            canonical_tool = _proof_tool_identity(
                base, canonical_command, fixed_after_assignments=False,
                probe_memo=tool_probe_memo,
                allowed_generated_paths=generated_paths,
                allowed_product_paths=allowed_product_paths,
                environment_overrides={
                    **_factory_env_from_envrc(base),
                    **_canonical_junit_environment(),
                },
            )
            semantic["canonical_test_tool"] = {
                key: value for key, value in canonical_tool.items()
                if key not in {"command", "runner"}
            }
    board_commands = ([_board_command_kind(base, command) for command in commands]
                      if kind == "verify" else [])
    board_inputs = None
    if "direct" in board_commands:
        try:
            board_inputs = _board_proof_inputs(base)
        except (OSError, ValueError, TypeError, KeyError):
            board_inputs = None
    reusable = (all(tool.get("reusable") is True for tool in tools)
                and all(value is not None for value in generated.values())
                and "unknown" not in board_commands
                and ("direct" not in board_commands or board_inputs is not None))
    inputs: dict[str, object] = {
        "kind": kind,
        "product_tree": reuse_tree,
        "semantic": semantic,
        "generated_inputs": generated,
        "board_inputs": board_inputs,
        "tools": tools,
    }
    canonical = json.dumps(
        inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return {"identity": hashlib.sha256(canonical).hexdigest(), "inputs": inputs,
            "reusable": reusable}


def _proof_receipt(base: Path, stage_id: str, kind: str) -> dict:
    stage = _find(load_stages(base), stage_id)
    receipts = stage.get("proof_receipts")
    value = receipts.get(kind) if isinstance(receipts, dict) else None
    if (not isinstance(value, dict)
            or value.get("status") != "passed"
            or not isinstance(value.get("inputs"), dict)
            or not re.fullmatch(r"[0-9a-f]{64}", str(value.get("identity", "")))):
        return {}
    canonical = json.dumps(
        value["inputs"], sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != value["identity"]:
        return {}
    return value


def _store_proof_receipt(
        base: Path, stage_id: str, kind: str, identity: dict[str, object]) -> None:
    from .delegate import delegation_exclusion
    with delegation_exclusion(base, "stages", kind="stage-state", namespace="state"):
        data = load_stages(base)
        stage = _find(data, stage_id)
        receipts = stage.setdefault("proof_receipts", {})
        receipts[kind] = {
            **identity, "status": "passed", "recorded_at": now_iso(),
        }
        write_stages(base, data)


def run_stage_proof(
        base: Path, stage_id: str, task: dict, *,
        record_close_evidence: bool = False,
        proof_context: dict[str, object] | None = None,
) -> tuple[dict, dict, list[str]]:
    """Run the task's verify commands and required tests, read-only.

    Returns the product and authority snapshots the proof ran against and the
    required-test ids that matched no case, for the close to record. Factored
    out so `task close` can run the proof BEFORE spending a review on a tree
    that would have failed it anyway.

    A passing receipt is reused only when its complete command, environment,
    tool, distribution, generated-input, and product identities match (0079).
    Unknown command shapes remain conservative and run again. Before this
    integrated proof, the full suite ran here, again in `verify.py` so the
    review had a verify.json, and again by hand before each close: four to five
    runs per fix cycle on WF-BIO-1 T4.
    """
    for proof in task.get("required_tests") or []:
        _require_test_input(base, stage_id, proof)
    state = raw_run_state(base)
    story = str(state.get("issue_key") or state.get("story") or "")
    if active_story_key(base) != story:
        fail(f"{stage_id} active story authority changed; refusing to record proof")
    proof_tree = product_tree_snapshot(base)
    authority_tree = protected_authority_snapshot(base)
    tool_probe_memo: dict[
        tuple[tuple[str, ...], str], dict[str, object]
    ] = {}
    verify_identity = proof_identity(
        base, task, "verify", product_tree=proof_tree,
        tool_probe_memo=tool_probe_memo,
    )
    test_identity = proof_identity(
        base, task, "tests", product_tree=proof_tree,
        tool_probe_memo=tool_probe_memo,
    )
    verify_receipt = _proof_receipt(base, stage_id, "verify")
    test_receipt = _proof_receipt(base, stage_id, "tests")
    reuse_verify = (verify_identity.get("reusable") is True
                    and verify_receipt.get("status") == "passed"
                    and verify_receipt.get("identity") == verify_identity["identity"]
                    and verify_receipt.get("inputs") == verify_identity["inputs"])
    reuse_tests = (test_identity.get("reusable") is True
                   and test_receipt.get("status") == "passed"
                   and test_receipt.get("identity") == test_identity["identity"]
                   and test_receipt.get("inputs") == test_identity["inputs"])
    test_id_misses = list(test_receipt.get("test_id_misses") or []) \
        if reuse_tests else []
    key = proof_key(
        base, task, verify_identity=verify_identity,
        test_identity=test_identity,
    )
    close_owned = record_close_evidence or proof_context is not None
    verify_results: list[dict] = []
    test_results: list[dict] = []
    commands_run: list[str] = []
    if close_owned and (reuse_verify or reuse_tests):
        existing = load_json(
            task_evidence_path(base, story, stage_id, "verify.json"),
            default={},
        ) if story else {}
        existing_tests = load_json(
            task_evidence_path(base, story, stage_id, "tests.json"),
            default=None,
        ) if story else None
        saved_verify = existing.get("results") if isinstance(existing, dict) else None
        saved_tests = existing.get("required_tests") if isinstance(existing, dict) else None
        if (not isinstance(existing, dict)
                or not isinstance(existing_tests, dict)
                or existing.get("recorded_by") != STAGE_PROOF
                or existing.get("task_id") != stage_id
                or existing.get("ok") is not True):
            reuse_verify = reuse_tests = False
        else:
            commands = [str(command) for command in task.get("verify_commands") or []
                        if str(command).strip()]
            required = [proof for proof in task.get("required_tests") or []
                        if isinstance(proof, dict)]
            reuse_verify = reuse_verify and _close_verify_results_match(
                commands, saved_verify)
            reuse_tests = reuse_tests and _close_test_results_match(
                required, saved_tests)
            if reuse_verify:
                verify_results = saved_verify
            if reuse_tests:
                test_results = saved_tests
    with tempfile.TemporaryDirectory(prefix="forge-canonical-junit-") as tmp:
        canonical_junit = Path(tmp) / "pytest.xml"
        with termination_signal_guard():
            if not reuse_verify:
                result = _run_verify_commands(
                    base, stage_id, task, canonical_junit,
                )
                verify_results = result if isinstance(result, list) else []
                commands_run.extend(
                    str(command) for command in task.get("verify_commands") or []
                    if str(command).strip()
                )
            if not reuse_tests:
                if canonical_junit.is_file() and \
                        _canonical_junit_satisfies_required_tests(
                            canonical_junit, task, base=base,
                            canonical_command=_canonical_test_command_for_task(
                                base, task)):
                    test_id_misses = []
                    test_results = [
                        {"id": str(proof.get("id")),
                         "path": str(proof.get("path")), "status": "passed"}
                        for proof in task.get("required_tests") or []
                        if isinstance(proof, dict)
                    ]
                else:
                    result = _run_required_tests(base, stage_id, task)
                    if not isinstance(result, tuple) or len(result) != 2:
                        fail(f"{stage_id} required-test runner returned malformed "
                             "proof results")
                    test_id_misses, test_results = result
                    commands_run.extend(
                        str(proof.get("command"))
                        for proof in task.get("required_tests") or []
                        if isinstance(proof, dict)
                        and str(proof.get("command") or "").strip()
                    )
    if product_tree_snapshot(base) != proof_tree:
        fail(f"{stage_id} proof commands changed the product tree; verification "
             "must be read-only")
    if protected_authority_snapshot(base) != authority_tree:
        fail(f"{stage_id} proof commands changed protected Forge authority; "
             "stage completion refused")
    if test_id_misses:
        fail(f"{stage_id} required-test identity was not proven by the fresh "
             "JUnit report: " + "; ".join(test_id_misses))
    if not reuse_verify:
        _store_proof_receipt(base, stage_id, "verify", verify_identity)
    if not reuse_tests:
        test_identity = {**test_identity, "test_id_misses": test_id_misses}
        _store_proof_receipt(base, stage_id, "tests", test_identity)
    close_record_needed = close_owned
    if close_owned and reuse_verify and reuse_tests:
        existing = load_json(
            task_evidence_path(base, story, stage_id, "tests.json"),
            default={},
        ) if story else {}
        automated = existing.get("automated") if isinstance(existing, dict) else {}
        close_record_needed = (
            not isinstance(automated, dict)
            or "close-owned proof:" not in str(
                automated.get("pass_fail_summary") or ""
            )
        )
    if close_owned and not _close_proof_results_match(
            task, verify_results, test_results):
        fail(f"{stage_id} close-owned proof results are incomplete; "
             "refusing to record passing evidence")
    if close_record_needed or not reuse_verify or not reuse_tests:
        if proof_tree.get("dirty"):
            print(f"{stage_id}: proof ran against uncommitted product paths; "
                  "not recorded. Commit, then close.")
        else:
            record_stage_proof(
                base, stage_id, task, key=key,
                verify_results=verify_results,
                test_results=test_results,
                test_id_misses=test_id_misses,
                close_owned=close_record_needed,
                commands_run=commands_run,
            )
    authority_tree = protected_authority_snapshot(base)
    if proof_context is not None:
        proof_context.clear()
        proof_context.update({
            "product_tree": proof_tree,
            "authority_tree": authority_tree,
            "proofs": {
                "verify": {
                    "status": "passed",
                    "executed": not reuse_verify,
                    "identity": verify_identity["identity"],
                    "inputs": verify_identity["inputs"],
                },
                "tests": {
                    "status": "passed",
                    "executed": not reuse_tests,
                    "identity": test_identity["identity"],
                    "inputs": test_identity["inputs"],
                },
            },
        })
    return proof_tree, authority_tree, test_id_misses


def _finish_stage(base: Path, args: argparse.Namespace, data: dict,
                  stage: dict, task: dict, *,
                  proof: tuple[dict, dict, list[str]] | None = None) -> None:
    # Validate the input tree, run the task proof once, then validate again.
    # Verify commands are executable shell and may mutate files; only the
    # post-command measurement is allowed to authorize completion.
    #
    # `task close` runs the proof BEFORE spending a review and hands it in
    # here, so a proof-driven fix never costs a review that ran too early;
    # a standalone `stage done` keeps its own refusal order.
    # A corrupt delegation ledger refuses before any other verdict: nothing
    # below can be trusted against it. The old stamp binding read the ledger
    # incidentally and so failed here by accident; now it is deliberate.
    from .delegate import load_delegations
    load_delegations(base)
    _measure(base, args.id, stage, task)
    _require_reviewed_commit(base, stage, task)
    _require_successful_launch(base, args.id, stage, task)
    if proof is None:
        proof = run_stage_proof(base, args.id, task)
    proof_tree, authority_tree, test_id_misses = proof
    if product_tree_snapshot(base) != proof_tree:
        fail(f"{args.id}'s product tree changed after its required proof; "
             "rerun stage completion against the final snapshot")
    _measure(base, args.id, stage, task)
    final_task = task_for(base, args.id)
    _measure(base, args.id, stage, final_task)
    _require_successful_launch(base, args.id, stage, final_task)
    _require_reviewed_commit(base, stage, final_task)
    from .delegate import delegation_exclusion

    with delegation_exclusion(
            base, "stages", kind="stage-state", namespace="state"):
        data = load_stages(base)
        current = _find(data, args.id)
        identity = ("started_at", "base_sha", "dirty_at_start", "task_sha256")
        if (current.get("status") != "active"
                or any(current.get(key) != stage.get(key) for key in identity)):
            fail(f"{args.id} changed identity before its done transition could "
                 "be serialized; inspect `forge stage list` and retry.")
        locked_task = task_for(base, args.id)
        # A RACE guard, not a contract-drift guard: the decomposition must not
        # move between the measurement above and the write below. Comparing to
        # the digest recorded at stage START conflated the two, so a contract
        # legitimately re-recorded mid-stage (decision 0023 ledgers those)
        # could never be closed at all.
        if task_digest(locked_task) != task_digest(final_task):
            fail(f"{args.id}'s task contract changed while its done transition "
                 "was being serialized; nothing was written — retry.")
        measured = _measure(base, args.id, current, locked_task)
        window = _require_successful_launch(base, args.id, current, locked_task)
        _require_reviewed_commit(base, current, locked_task)
        if product_tree_snapshot(base) != proof_tree:
            fail(f"{args.id}'s product tree changed after its required proof; "
                 "rerun stage completion against the final snapshot")
        current.pop("incomplete", None)
        current.pop("attested_digests", None)
        current["status"] = "done"
        current["completed_at"] = now_iso()
        # What the close MEASURED, recorded for review rather than refused:
        # strays, the budget it used, required-test ids that matched no case.
        current["measured"] = {**measured, "test_id_misses": test_id_misses}
        if window:
            # No Codex write launch; a bounded, ledgered host-fix window was the
            # sanctioned write path. Say which one.
            current["host_window"] = window
            print(f"{args.id}: no Codex write launch; ledgered host-fix window "
                  f"{window} (closed, in scope) is the sanctioned write path.")
        notes = _measure_notes(args.id, current["measured"])
        for note in notes:
            print(note)
        if notes:
            append_event(base, "stage-measured", actor="implementer",
                         story=data.get("issue", ""),
                         detail=f"{args.id}: " + "; ".join(
                             note.removeprefix("NOTE: ").split(". ")[0]
                             for note in notes))
        # A contract that moved mid-stage is EVIDENCE, not a refusal (0023):
        # review sees the widened scope and can ask why. Recorded HERE, past
        # the last snapshot check, because every write before it changes a
        # tracked file the proof already attested.
        started_digest = current.get("task_sha256")
        if started_digest and started_digest != task_digest(locked_task):
            current["contract_changed"] = {
                "at": current["completed_at"],
                "from": started_digest,
                "to": task_digest(locked_task),
            }
            # The stage was MEASURED and closed against the current contract,
            # so that is the digest it carries. Leaving the start digest here
            # made the completed stage permanently un-re-recordable: the
            # frozen-contract guard compares against task_sha256 and would see
            # a change that was already ledgered and closed over.
            current["task_sha256"] = task_digest(locked_task)
            append_event(base, "stage-contract-changed", actor="implementer",
                         story=data.get("issue", ""),
                         detail=f"{args.id}: task contract re-recorded mid-stage")
            print(f"NOTE: {args.id}'s task contract changed after the stage "
                  "started; recorded for review. The measured diff is unaffected.")
        append_event(base, "stage-done", actor="implementer",
                     story=data.get("issue", ""),
                     detail=f"{args.id} {current.get('title', '')}")
        write_stages(base, data)
    remaining = [s for s in data["stages"] if s.get("status") != "done"]
    if remaining:
        print(f"Stage {args.id} done; next: {remaining[0]['id']} "
              f"({len(remaining)} pending)")
    else:
        print(f"Stage {args.id} done — all {len(data['stages'])} stage(s) complete")


def _refuse_incomplete_against_complete_proof(base: Path, task_id: str) -> None:
    """`--incomplete` is the only escape from a refusing seal, and using it on
    finished work writes a false record.

    It exists so a worker that genuinely finished only part of the job can say
    so. But it is also the sole way out when a gate refuses, so it becomes the
    tempting move for work that IS complete -- and the frontier and the PR gate
    then read a finished task as unfinished. The evidence already answers the
    question: if verify passed, tests are recorded, and all three lenses are
    clean, then "work remains" contradicts the proof on disk.

    Judged on RECORDED PROOF, not on a guess about intent, and it refuses only
    when every one of those is present -- a genuinely partial task has not got
    them, so the honest use is untouched.
    """
    from factory_lib import load_json, selected_review_problems
    from .readiness import verify_passed

    key = load_json(run_state_path(base), default={}).get("issue_key", "")
    if not key:
        return
    verify_ok = verify_passed(load_json(
        proof_read_path(base, key, "verify.json"), default={}))
    tests = load_json(proof_read_path(base, key, "tests.json"), default={})
    stage = next((item for item in load_stages(base).get("stages", [])
                  if item.get("id") == task_id), {})
    review_ok = bool(stage) and not selected_review_problems(
        base, key, task_id, stage_review_binding(base, stage, {})["delta_id"],
    )
    if not (verify_ok and tests and review_ok):
        return
    fail(
        f"--incomplete records that WORK REMAINS on {task_id}, and the recorded "
        "proof says the opposite: verify passed, tests are recorded, and all "
        "three review lenses are clean. Writing it anyway makes the frontier "
        "and the PR gate read a finished task as unfinished.\n"
        "If a gate is refusing a task this complete, the gate has a cause worth "
        "naming rather than stepping around: `forge audit --state` re-derives "
        "every recorded claim and reports which one disagrees with the repo. "
        "Use --incomplete only when work genuinely remains."
    )


def reopen_stage_for_review_fix(base: Path, stage_id: str) -> dict:
    """A done, unshipped stage goes back to active so a fix can land.

    Identity stays: base, contract digest, start time, plan approval. Only the
    review stamp goes -- it is bound to the pre-fix diff. `task close` calls
    this itself when a done stage's diff has moved; `task reopen --review-fix`
    remains as the explicit verb.
    """
    data = load_stages(base)
    stages = data.get("stages") or []
    idx = next((i for i, st in enumerate(stages) if st.get("id") == stage_id), None)
    if idx is None:
        fail(f"task {stage_id} is not in the current decomposition")
    if stages[idx].get("status") != "done":
        status = stages[idx].get("status")
        fail(f"task {stage_id} is '{status}', not done -- a review "
             "fix reopens a stage that closed clean and then failed its review")
    state = load_json(run_state_path(base), default={})
    story = data.get("issue") or state.get("issue_key") or state.get("story") or ""
    if not isinstance(story, str) or not story.strip():
        fail(f"cannot check whether task {stage_id} is unshipped without a story key")
    from .tasks import _require_unshipped
    _require_unshipped(base, story, stage_id, require_fetch_success=True)

    from .delegate import delegation_exclusion
    with delegation_exclusion(base, "stages", kind="stage-state", namespace="state"):
        data = load_stages(base)
        stages = data.get("stages") or []
        idx = next((i for i, st in enumerate(stages) if st.get("id") == stage_id), None)
        if idx is None:
            fail(f"task {stage_id} is not in the current decomposition")
        target = stages[idx]
        if target.get("status") != "done":
            fail(f"task {stage_id} is '{target.get('status')}', not done -- a review "
                 "fix reopens a stage that closed clean and then failed its review")
        state = load_json(run_state_path(base), default={})
        current_story = (data.get("issue") or state.get("issue_key")
                         or state.get("story") or "")
        if not isinstance(current_story, str) or current_story != story:
            fail(f"task {stage_id}'s story changed while checking shipped status; "
                 "retry the review fix")
        later = [st.get("id") for st in stages[idx + 1:]
                 if st.get("status") in ("done", "active")]
        if later:
            fail(f"task {stage_id} cannot take a review fix while "
                 f"{', '.join(later)} already built on it; reopen without "
                 "--review-fix to move the frontier back")
        for field in ("local_review_stamp", "completed_at"):
            target.pop(field, None)
        target["status"] = "active"
        target["review_fix_reopened_at"] = now_iso()
        target["review_fix_count"] = int(target.get("review_fix_count") or 0) + 1
        # The marker the seal this fix supersedes left on disk. Until the
        # stage seals again, the brief and the pre-seal proof check read the
        # task's inputs from the current tree, not from that marker's commit
        # (the seal refused every resealed task otherwise, 2026-09-15).
        marker = None
        if story:
            try:
                from factory_lib import proof_path
                marker = load_json(
                    proof_path(base, story, "pr-ready.json", task_id=stage_id),
                    default=None)
            except (SystemExit, ValueError, OSError):
                marker = None
        if isinstance(marker, dict) and isinstance(marker.get("commit"), str):
            target["superseded_marker_commit"] = marker["commit"]
        write_stages(base, data)
    append_event(base, "stage-reopened", actor="implementer",
                 story=data.get("issue", ""),
                 detail=f"{stage_id}: review fix round {target['review_fix_count']}")
    return target


def cmd_amend_scope(args) -> None:
    """Record the paths this task really touched that its scope did not name.

    Bounded by measurement, not by assertion: it re-runs the SAME diff `stage
    done` runs and adds exactly the out-of-scope paths that measurement
    reports. Nothing can be pre-authorised, because a path that was not changed
    is never added.
    """
    from factory_lib import (protected_decomposition_state_path,
                             require_task_worktree, repo_root)

    base = Path(args.repo).resolve() if args.repo else repo_root()
    require_task_worktree(base, allow_completed=True)
    reason = (args.reason or "").strip()
    if len(reason) < 12:
        fail("--reason must say why these paths belong to this task (a dozen "
             "characters at least); it is the only part of this record a "
             "measurement cannot supply.")

    stages = load_stages(base)
    stage = next((item for item in stages.get("stages", [])
                  if item.get("id") == args.id), None)
    if stage is None:
        fail(f"{args.id} is not a recorded stage")
    tasks = load_json(protected_decomposition_state_path(base),
                      default={}).get("tasks", [])
    task = next((t for t in tasks if t.get("id") == args.id), None)
    if task is None:
        fail(f"{args.id} is not a task in the protected decomposition")
    scope = task.get("write_scope") or []
    if not scope:
        fail(f"{args.id} declares no write_scope; there is nothing to amend — "
             "record the contract first.")

    base_sha = stage_baseline(base, stage)
    if not base_sha:
        fail(f"{args.id} has no stage baseline to measure from; start the stage "
             "before amending its scope.")
    # The SAME measurement `stage done` performs -- that is what bounds this.
    product = [
        path for path in changed_paths(base, base_sha,
                                       stage.get("dirty_at_start", {}))
        if not path.startswith(workflow_prefixes(base))
    ]
    strays = out_of_scope(
        base, product, effective_scope(base, args.id, scope), base_sha,
    )
    if not strays:
        fail(f"{args.id} has no measured path outside its scope — nothing to "
             "amend. If `stage done` is refusing, it is refusing for another "
             "reason; read the refusal.")

    record = load_json(scope_amendments_path(base), default={})
    if not isinstance(record, dict):
        record = {}
    by_task = record.setdefault("tasks", {})
    entry = by_task.setdefault(args.id, {"added_paths": [], "amendments": []})
    already = set(entry.get("added_paths") or [])
    entry["added_paths"] = sorted(already | set(strays))
    entry.setdefault("amendments", []).append({
        "at": now_iso(),
        "by": args.by or "",
        "reason": reason,
        "added_paths": sorted(strays),
        "measured_from": base_sha,
        "measured_head": head_sha(base),
    })
    dump_json(scope_amendments_path(base), record)
    from factory_lib import refresh_task_plan_contract
    refresh_task_plan_contract(base, args.id, task)
    print(f"Amended {args.id} scope with {len(strays)} measured path(s): "
          f"{', '.join(sorted(strays)[:6])}"
          f"{'…' if len(strays) > 6 else ''} — contract, grill and delegate "
          f"launch untouched; `forge stage done {args.id}` can proceed")


def cmd_done(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    data = load_stages(base)
    if not data:
        fail("no .factory/stages.json — record the decomposition first")
    stage = _find(data, args.id)
    if stage.get("status") != "active":
        fail(f"{args.id} is {stage.get('status', 'pending')!r}, not active — "
             "`forge stage start` it first; done attests a stage that actually ran.")
    incomplete = (getattr(args, "incomplete", None) or "").strip()
    if incomplete:
        _refuse_incomplete_against_complete_proof(base, args.id)
        # A worker that genuinely finished part of the job had no vocabulary for
        # it: every signal kind presumes it wants to continue. This says so and
        # leaves the stage open, so nothing downstream reads it as delivered.
        from .delegate import delegation_exclusion
        with delegation_exclusion(base, args.id, kind="stage-close"):
            with delegation_exclusion(
                    base, "stages", kind="stage-state", namespace="state"):
                data = load_stages(base)
                stage = _find(data, args.id)
                if stage.get("status") != "active":
                    fail(f"{args.id} changed state before its incomplete note "
                         "could be serialized; inspect `forge stage list` and retry.")
                stage["incomplete"] = incomplete
                stage["updated_at"] = now_iso()
                append_event(base, "stage-incomplete", actor="implementer",
                             story=data.get("issue", ""),
                             detail=f"{args.id}: {incomplete}")
                write_stages(base, data)
        print(f"Stage {args.id} recorded INCOMPLETE and left active: {incomplete}")
        return
    from .delegate import delegation_exclusion

    # This is the commit point for a stage. The same per-task exclusion used by
    # `forge delegate` stays held from the first measurement through the
    # persisted done status, so no new writer can enter after the final check.
    with delegation_exclusion(base, args.id, kind="stage-close"):
        data = load_stages(base)
        stage = _find(data, args.id)
        if stage.get("status") != "active":
            fail(f"{args.id} changed state while stage close was waiting for "
                 "exclusive access; inspect `forge stage list` and retry.")
        _finish_stage(base, args, data, stage, task_for(base, args.id))


def cmd_list(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    data = load_stages(base)
    if not data:
        print("No stage tracker (.factory/stages.json) — it is created when the "
              "decomposition is recorded.")
        return
    marks = {"pending": " ", "active": ">", "done": "x"}
    # A parallel task is active in ITS worktree's tracker, not this one.
    elsewhere = {
        stage.get("id"): root for root, stage in active_stages_everywhere(base)
        if root.resolve() != base.resolve()
    }
    for stage in data.get("stages", []):
        status = stage.get("status", "pending")
        where = elsewhere.get(stage["id"])
        if where is not None and status != "active":
            status = "active"
        note = f" (active in {where})" if where is not None else ""
        print(f"[{marks.get(status, '?')}] {stage['id']} — {stage.get('title')}{note}")
        measured = stage.get("measured")
        if isinstance(measured, dict):
            budget = measured.get("budget") or {}
            line = (f"    measured: files={measured.get('files')}/"
                    f"{budget.get('files')} lines={measured.get('lines')}/"
                    f"{budget.get('lines')}")
            if measured.get("strays"):
                line += f"; strays: {', '.join(measured['strays'])}"
            if measured.get("test_id_misses"):
                line += (f"; required-test id misses: "
                         f"{'; '.join(measured['test_id_misses'])}")
            if stage.get("host_window"):
                line += f"; host-fix window: {stage['host_window']}"
            print(line)


def _cmd_migrate_locked(args: argparse.Namespace, base: Path) -> None:
    if not args.confirm_workspace_state:
        fail("migration trusts legacy workspace state exactly once; inspect "
             ".factory/decomposition.json and .factory/stages.json, then pass "
             "--confirm-workspace-state")
    resolved_base = _git(
        base, "rev-parse", "--verify", "--end-of-options",
        f"{args.base}^{{commit}}")
    if not resolved_base:
        fail(f"--base {args.base!r} does not resolve to a commit")
    resolved_base = resolved_base.strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", resolved_base, "HEAD"],
        cwd=base, capture_output=True, text=True, env=clean_git_env(), encoding="utf-8")
    if ancestor.returncode == 1:
        fail(f"--base {resolved_base!r} is not an ancestor of HEAD")
    if ancestor.returncode != 0:
        fail(f"could not validate --base {resolved_base!r} against HEAD")
    protected_decomposition = protected_decomposition_state_path(base)
    protected_stages = authoritative_stages_path(base)
    if protected_decomposition.exists() != protected_stages.exists():
        fail("partial protected stage authority exists; Forge will not combine "
             "one protected artifact with one worker-writable workspace mirror. "
             "Restore or remove the incomplete protected migration as a unit, "
             "then retry.")
    if protected_decomposition.exists() and protected_stages.exists():
        fail("protected decomposition and stage authority already exist")
    decomposition = load_json(decomposition_state_path(base), default={})
    stages = load_json(stages_path(base), default={})
    issue = load_json(run_state_path(base), default={}).get("issue_key")
    tasks = {
        task.get("id"): task for task in decomposition.get("tasks") or []
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }
    stage_ids = {
        stage.get("id") for stage in stages.get("stages") or []
        if isinstance(stage, dict)
    }
    if (
        not tasks
        or not stages.get("stages")
        or stages.get("issue") != issue
        or stage_ids != set(tasks)
    ):
        fail("legacy workspace decomposition/stages do not form one complete "
             "tracker for the active story; migration refused")
    for stage in stages["stages"]:
        if stage.get("status") not in {"pending", "active", "done"}:
            fail(f"legacy stage {stage.get('id')} has invalid status")
        if stage.get("status") in {"active", "done"}:
            stage["base_sha"] = resolved_base
            stage["task_sha256"] = task_digest(tasks[stage["id"]])
        stage.pop("parallel", None)
        stage.pop("attested_digests", None)
    if not protected_decomposition.exists():
        dump_json(protected_decomposition, decomposition)
    if not protected_stages.exists():
        write_stages(base, stages)
    append_event(base, "stage-authority-migrated", actor="orchestrator",
                 story=issue or "", detail=f"{len(tasks)} task(s)")
    print(f"Migrated {len(tasks)} task(s) into protected story authority.")


def cmd_clear(args: argparse.Namespace) -> None:
    """Drop a shipped or orphaned story's git-local authority.

    The escape hatch for a story that shipped before `pr_ready` learned to
    clear it: removes the git-local authority WITHOUT a write_scope diff check
    (it retires authority, it does not close a stage) and is idempotent.
    """
    base = Path(args.repo).resolve() if args.repo else repo_root()
    removed = clear_story_authority(base)
    if removed:
        print(f"Cleared git-local story authority: {', '.join(removed)}")
    else:
        print("No git-local story authority to clear.")


def cmd_migrate(args: argparse.Namespace) -> None:
    """Explicit one-time adoption of a pre-protected story workspace."""
    base = Path(args.repo).resolve() if args.repo else repo_root()
    from .delegate import delegation_exclusion

    with delegation_exclusion(
            base, "stages", kind="stage-state", namespace="state"):
        _cmd_migrate_locked(args, base)
