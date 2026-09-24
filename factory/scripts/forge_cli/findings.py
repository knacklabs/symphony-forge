"""forge findings — review-finding pattern detection across tasks.

Recurring findings are a design signal, not a fix queue. Review artifacts
accumulate per task under .factory/history/<issue>/reviews/ (plus the active
task's .factory/reviews/); this module clusters their findings by
(category, area) and flags any CLASS that keeps respawning — the trigger to
stop patching individual findings and either CONSOLIDATE (write the
invariant, audit every site) or SPLIT OUT the entangled scope. Doctrine:
WORKFLOW.md "Recurring Findings — a design signal".
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from factory_lib import (
    _active_story_key, _git_is_ancestor, _read_review_bytes,
    evidence_path, factory_dir,
    has_completed_lean_migration_manifest, head_sha, load_json,
    product_delta_digest, read_selected_review_generation, repo_root,
    review_generation_id, run_state_path, story_dir,
    unmigrated_fixed_review_paths, validated_task_marker_commit,
    validate_payload, validate_review_document,
)
from .roadmap import load_items

RECURRING_AT = 3  # same class a third time = stop patching, consolidate
WATCH_AT = 2
REVIEW_ASPECTS = ("quality", "performance", "security")


def repeated_finding_files(base: Path, story: str, task_id: str, *,
                           lite: bool = False) -> list[str]:
    """Files with findings in the last two complete reviews, if any."""
    def files(artifacts: dict) -> set[str]:
        return {
            finding["file_path"].strip()
            for aspect in REVIEW_ASPECTS
            for field in ("blocking_findings", "non_blocking_findings")
            for finding in (artifacts.get(aspect, {}).get(field) or [])
            if isinstance(finding, dict)
            and str(finding.get("category", "")).casefold() != "simplification-debt"
            and isinstance(finding.get("file_path"), str)
            and finding["file_path"].strip()
        }

    if lite:
        from .quickfix import LITE, closed_windows, load_active, profile_of

        window = load_active(base)
        head = head_sha(base) or ""
        window_base = str(window.get("base_sha") or "")
        if (not window or profile_of(window) != LITE or not head or not window_base
                or head == window_base or not _git_is_ancestor(base, window_base, head)):
            return []
        delta = product_delta_digest(base, window_base, head)
        current = {aspect: load_json(evidence_path(
            base, _active_story_key(base) or None, f"reviews/{aspect}.json",
        ), default={}) for aspect in REVIEW_ASPECTS}
        def bindings(rows: dict) -> set[tuple]:
            return {
                tuple(rows[aspect].get(field) for field in (
                    "review_run_id", "brief_sha256", "branch_diff_digest",
                    "review_base_sha", "commit",
                )) for aspect in REVIEW_ASPECTS
            }

        if (not all(isinstance(current.get(aspect), dict) for aspect in REVIEW_ASPECTS)
                or len(bindings(current)) != 1
                or any(current[aspect].get("review_base_sha") != window_base
                       or current[aspect].get("commit") != head
                       or current[aspect].get("branch_diff_digest") != delta
                       for aspect in REVIEW_ASPECTS)):
            return []
        try:
            for artifact in current.values():
                validate_payload(base, "review", artifact)
        except SystemExit:
            return []
        previous = [
            event for event in closed_windows(base)
            if event.get("profile") == LITE
            and str(event.get("completed_at") or "") <= str(window.get("started_at") or "")
            and isinstance(event.get("reviews"), dict)
            and set(event["reviews"]) == set(REVIEW_ASPECTS)
            and all(isinstance(event["reviews"].get(aspect), dict)
                    for aspect in REVIEW_ASPECTS)
            and len(bindings(event["reviews"])) == 1
            and _git_is_ancestor(
                base,
                str(event["reviews"]["quality"].get("commit") or ""),
                window_base,
            )
        ]
        if not previous:
            return []
        last = max(previous, key=lambda event: str(event.get("completed_at") or ""))
        return sorted(files(last["reviews"]) & files(current))
    if not story or not task_id:
        return []
    generation, _selection, problems = read_selected_review_generation(
        base, story, task_id,
    )
    if problems or not isinstance(generation, dict):
        return []
    source_id = (generation.get("rejection") or {}).get("source_generation_id")
    if generation.get("origin") == "rejection" and isinstance(source_id, str) and source_id:
        source_path = (story_dir(base, story) / "tasks" / task_id / "reviews"
                       / "generations" / f"{source_id}.json")
        try:
            previous = json.loads(_read_review_bytes(base, source_path))
        except (OSError, UnicodeError, json.JSONDecodeError, SystemExit):
            return []
        if not isinstance(previous, dict):
            return []
        return sorted(
            files(previous.get("lenses") or {})
            & files(generation.get("lenses") or {})
        )

    directory = (story_dir(base, story) / "tasks" / task_id / "reviews"
                 / "generations")
    selected_recorded_at = str(generation.get("recorded_at") or "")
    candidates: list[tuple[str, str, dict]] = []
    if not directory.is_dir():
        return []
    for path in directory.glob("*.json"):
        try:
            candidate = json.loads(_read_review_bytes(base, path))
            if not isinstance(candidate, dict):
                continue
            validate_review_document(base, candidate)
        except (OSError, UnicodeError, json.JSONDecodeError, SystemExit):
            continue
        run_id = candidate.get("review_run_id")
        generation_id = candidate.get("generation_id")
        recorded_at = str(candidate.get("recorded_at") or "")
        if (candidate.get("story") != story or candidate.get("task_id") != task_id
                or not isinstance(run_id, str) or not run_id
                or not isinstance(generation_id, str)
                or path.stem != generation_id
                or generation_id != review_generation_id(candidate)
                or not recorded_at or recorded_at >= selected_recorded_at):
            continue
        candidates.append((recorded_at, generation_id, candidate))
    if not candidates:
        return []
    previous = max(candidates, key=lambda item: (item[0], item[1]))[2]
    return sorted(
        files(previous.get("lenses") or {})
        & files(generation.get("lenses") or {})
    )


def choice_error(file_paths: list[str], choice: str | None) -> str:
    if file_paths and not choice:
        return (
            f"{', '.join(file_paths)} drew findings in two consecutive reviews. "
            "Ask the user: "
            "refactor it, or patch once more? Then re-run with "
            "--choice refactor|patch."
        )
    return ""


def _finding_rows(task: str, aspect: str, data: dict) -> list[dict]:
    rows: list[dict] = []
    for field, blocking in (("blocking_findings", True), ("non_blocking_findings", False),
                            ("rejected_findings", False)):
        for entry in data.get(field) or []:
            # A rejected finding is recorded as {finding, reason, cite, ...}; it
            # clusters on the finding it wrapped, flagged so the pattern report
            # shows what reviewers keep raising against settled text.
            rejected = field == "rejected_findings"
            if rejected and isinstance(entry, dict) and isinstance(entry.get("finding"), dict):
                entry = entry["finding"]
            if isinstance(entry, dict):
                rows.append({
                    "task": task, "aspect": aspect, "blocking": blocking,
                    "rejected": rejected,
                    "category": str(entry.get("category", "")).strip(),
                    "area": str(entry.get("area", "")).strip(),
                    "summary": str(entry.get("summary", "")).strip(),
                })
            elif isinstance(entry, str) and entry.strip():
                # Legacy plain-string findings cluster on exact text only.
                rows.append({
                    "task": task, "aspect": aspect, "blocking": blocking,
                    "category": "", "area": "", "summary": entry.strip(),
                })
    return rows


def collect(base: Path) -> list[dict]:
    """Every finding ever recorded: shipped tasks (history) + the active task."""
    rows: list[dict] = []
    history = factory_dir(base) / "history"
    task_keys = {
        str(item["key"])
        for item in load_items(base)
        if item.get("key") and story_dir(base, str(item["key"])).is_dir()
    }
    if history.is_dir():
        task_keys.update(p.name for p in history.iterdir() if p.is_dir())
    active_issue = load_json(run_state_path(base), default={}).get("issue_key", "")
    if active_issue:
        task_keys.add(active_issue)
    for task in sorted(task_keys):
        task_root = story_dir(base, task) / "tasks"
        fixed = [
            evidence_path(base, task, f"reviews/{aspect}.json")
            for aspect in REVIEW_ASPECTS
        ]
        task_candidates: list[Path] = []
        if task_root.is_dir():
            for task_dir in sorted(task_root.iterdir()):
                task_candidates.extend(
                    task_dir / "reviews" / f"{aspect}.json"
                    for aspect in REVIEW_ASPECTS
                )
        candidates = [path.relative_to(base).as_posix()
                      for path in fixed + task_candidates]
        fixed_paths = [base / relative for relative in
                       unmigrated_fixed_review_paths(base, candidates)]
        if fixed_paths:
            task_ids = sorted({
                path.relative_to(task_root).parts[0]
                for path in fixed_paths
                if path.is_relative_to(task_root)
            })
            if task_ids:
                detail = f"story {task} task {', '.join(task_ids)}"
            else:
                detail = f"story {task}"
            if not has_completed_lean_migration_manifest(base):
                guidance = "run forge upgrade"
            elif task_ids:
                review_commands = ", ".join(
                    f"forge review {task_id}" for task_id in task_ids
                )
                guidance = f"record a fresh review with {review_commands}"
            else:
                guidance = "record a fresh review for the story's current task"
            raise SystemExit(
                f"{detail} has legacy fixed review files that are not proof; "
                f"{guidance} before reading live findings"
            )
        selected_tasks = [
            path.parent.parent.name
            for path in sorted(task_root.glob("*/reviews/selected.json"))
        ]
        if selected_tasks:
            for task_id in selected_tasks:
                generation, _selection, problems = read_selected_review_generation(
                    base, task, task_id,
                    sealed_commit=validated_task_marker_commit(
                        base, task, task_id,
                    ),
                )
                if problems or not isinstance(generation, dict):
                    continue
                for aspect, data in (generation.get("lenses") or {}).items():
                    if aspect in {"quality", "performance", "security"} \
                            and isinstance(data, dict):
                        rows += _finding_rows(f"{task}/{task_id}", aspect, data)
            continue
    if not active_issue:
        for review in sorted((factory_dir(base) / "reviews").glob("*.json")):
            data = load_json(review, default={})
            rows += _finding_rows("<active>", review.stem, data)
    return rows


def clusters(base: Path) -> list[dict]:
    """Findings grouped into classes: (category, area) for structured ones,
    exact text for legacy strings. Sorted most-recurring first."""
    grouped: dict[tuple[str, str], dict] = {}
    for row in collect(base):
        key = (row["category"], row["area"]) if row["category"] \
            else ("", row["summary"].lower())
        cluster = grouped.setdefault(key, {
            "category": row["category"] or "(uncategorized)",
            "area": row["area"], "count": 0, "tasks": [], "examples": [],
        })
        cluster["count"] += 1
        if cluster["count"] == RECURRING_AT:
            # The task at which the class crossed the line — the audit measures
            # how many ships have ignored the escalation since this point.
            cluster["flagged_at"] = row["task"]
        if row["task"] not in cluster["tasks"]:
            cluster["tasks"].append(row["task"])
        if row["summary"] and len(cluster["examples"]) < 3:
            cluster["examples"].append(row["summary"])
    return sorted(grouped.values(), key=lambda c: -c["count"])


def recurring(base: Path) -> list[dict]:
    return [c for c in clusters(base) if c["count"] >= RECURRING_AT]


def cmd_patterns(args: argparse.Namespace) -> None:
    base = Path(args.repo).resolve() if args.repo else repo_root()
    all_clusters = clusters(base)
    if not all_clusters:
        print("No review findings recorded yet (.factory/history/*/reviews/ is empty).")
        return
    flagged = [c for c in all_clusters if c["count"] >= WATCH_AT]
    if not flagged:
        print(f"{len(all_clusters)} finding class(es), none recurring — healthy tail.")
        return
    for cluster in flagged:
        label = "RECURRING" if cluster["count"] >= RECURRING_AT else "watch"
        where = f" @ {cluster['area']}" if cluster["area"] else ""
        example = f' — e.g. "{cluster["examples"][0]}"' if cluster["examples"] else ""
        print(f"[{label} x{cluster['count']}] {cluster['category']}{where} "
              f"(tasks: {', '.join(cluster['tasks'])}){example}")
    if any(c["count"] >= RECURRING_AT for c in flagged):
        print(
            "\nA RECURRING class is a design signal, not a fix queue "
            "(WORKFLOW.md 'Recurring Findings'):\n"
            "  1. Write the invariant the area must satisfy -> ./forge decision new <slug>\n"
            "  2. CONSOLIDATE (self-contained churn): a refactor story on the roadmap that\n"
            "     audits every site against the invariant and pins it with tests, or\n"
            "  3. SPLIT OUT (entangled/cycle-sized): defer with a trigger — "
            "./forge defer add\n"
            "Distinguish it from a converging TAIL (distinct findings, trending down): "
            "a tail is healthy, keep going."
        )
