#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import shlex
from pathlib import Path, PurePosixPath

from factory_lib import (
    decomposition_state_path, dump_json, evidence_path, gate, grounding_digest,
    grounding_matches, head_sha,
    load_json, now_iso, plan_digest_without_assumptions,
    protected_decomposition_state_path, repo_root, require_approved_plan_digest,
    run_state_path,
    read_stdin_utf8, validate_payload,
    ready_task_ids,
    IN_STAGE_GROUNDING_FIELDS, MEASUREMENT_CONTRACT_FIELDS, measurement_contract,
    approved_story_plan_predecessors, refresh_task_plan_contract,
    story_plan_digest, task_grill_grounding_matches, task_plan_binding_digest,
    validated_measurement_launch,
)
from forge_cli.doctor import unrunnable_reason
from forge_cli.stages import review_budget

parser = argparse.ArgumentParser(description="Record decomposition from structured JSON")
parser.add_argument("--input", help="Path to decomposition JSON. If omitted, read from stdin.")
args = parser.parse_args()

if args.input:
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
else:
    raw = read_stdin_utf8().strip()
    if not raw:
        raise SystemExit("Expected JSON on stdin or via --input")
    payload = json.loads(raw)

root = repo_root()
state = gate(root, signoff=True, approved_plan=True)

# Provenance belongs to repository state, not to the agent recording the task
# graph. The one agent-supplied provenance value that matters is its view of
# the plan digest: if present, it must still describe the active plan.
project = state.get("project")
story = state.get("story")
plan_file = state.get("plan_file")
# OPTIONAL, unlike story and plan_file. `project` is written by `forge init`
# at scaffold time and carried forward by intake, so a repo that adopted the
# harness rather than being scaffolded by it — this one included — has never
# had the field. Requiring provenance nobody can supply refuses the harness's
# own repo, and the field is optional in the schema for the same reason.
# Absent or null is a legacy repo that never ran `forge init`; anything else
# non-string is a broken run.json and must REFUSE rather than be recorded as
# "no project". Third instance of this shape in this file — erasing a value to
# make it validate is how false provenance gets written.
if project is None:
    project = ""
elif not isinstance(project, str):
    raise SystemExit(
        f"decomposition provenance: .factory/run.json has a non-string project "
        f"({type(project).__name__}); it must be a string, absent, or null"
    )
else:
    project = project.strip()
if not isinstance(story, str) or not story.strip():
    raise SystemExit("decomposition provenance: .factory/run.json has no story")
if not isinstance(plan_file, str) or not plan_file.strip():
    raise SystemExit("decomposition provenance: .factory/run.json has no plan_file")
plan_path = root / plan_file
if not plan_path.is_file():
    raise SystemExit(
        f"decomposition provenance: active plan {plan_file!r} is not readable"
    )
plan_sha256 = plan_digest_without_assumptions(plan_path)
approved_sha256 = require_approved_plan_digest(root)
# The digest the recorder can actually VOUCH for: it reads the active plan
# itself, so the stamp is true at record time without asking the producer to
# hash a file. A supplied digest is still compared — a producer that knows
# which plan it decomposed must not disagree with the one that is active.
# Requiring it would not buy the guarantee it appears to: the real failure is
# the plan being edited AFTER this artifact is recorded, which no record-time
# check can see. `stage start` compares the stamp against the plan then.
supplied_plan_sha256 = payload.get("plan_sha256")
if supplied_plan_sha256 is not None and supplied_plan_sha256 != plan_sha256:
    raise SystemExit(
        "decomposition plan_sha256 does not match the active plan file "
        f"{plan_file!r} — this task graph was built from a different plan"
    )
roadmap = load_json(root / "plans" / "roadmap.json", default={})
roadmap_story = next(
    (
        item for item in roadmap.get("items") or []
        if isinstance(item, dict) and item.get("key") == story
    ),
    None,
)
if roadmap_story is None:
    raise SystemExit(
        f"decomposition provenance: story {story!r} is not in plans/roadmap.json"
    )
# A legacy roadmap says "no epic" as a missing key or an explicit null; the
# decomposition says it as "". Refusing null would block recording for every
# pre-hierarchy story, which is the case this provenance has to survive — and
# PH-2's own backfilled roadmap writes null for stories it has not adopted yet.
# Only None becomes "". `or ""` also swallowed false, 0, {} and [], so the
# type check below could never reject them and provenance recorded "no epic"
# for a malformed roadmap — the same bug this file already had for
# `dependencies`, reintroduced three lines away.
epic = roadmap_story.get("epic")
epic = "" if epic is None else epic
if not isinstance(epic, str):
    raise SystemExit(
        f"decomposition provenance: roadmap story {story!r} has a non-string epic "
        f"({type(roadmap_story.get('epic')).__name__}); it must be a string, "
        "absent, or null"
    )
payload.update({
    "project": project,
    "story": story,
    "epic": epic,
    "plan_file": plan_file,
    "plan_sha256": approved_sha256,
})
validate_payload(root, "decomposition", payload)
tasks = payload.get("tasks") or []
if not tasks:
    raise SystemExit(
        "decomposition needs at least one leaf task — an empty task graph opens the "
        "implementation gates with nothing bounded to implement."
    )
OBJECTIVE_MAX = 2000
seen_task_ids: set[str] = set()
seen_contract_ids: set[str] = set()
for pos, task in enumerate(tasks, 1):
    if not isinstance(task, dict) or not isinstance(task.get("id"), str) \
            or not isinstance(task.get("title"), str) or not task["id"].strip():
        raise SystemExit(
            f"decomposition task {pos} must be an object with string 'id' and 'title' "
            "(plus write_scope/acceptance_criteria per the decomposer contract)."
        )
    task_id = task["id"]
    if task_id in seen_task_ids:
        raise SystemExit(f"decomposition task {task_id}: duplicate task id")
    # Default only when ABSENT. `or []` treated false, 0, "", {} and null as an
    # empty list for validation while the malformed value stayed in the payload,
    # so the artifact was recorded with a non-list `dependencies` that had
    # passed a list check.
    dependencies = task.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(dependency, str) and dependency.strip()
        for dependency in dependencies
    ):
        raise SystemExit(
            f"decomposition task {task_id}: dependencies must be a list of "
            "non-empty task ids"
        )
    for dependency in dependencies:
        if dependency not in seen_task_ids:
            raise SystemExit(
                f"decomposition task {task_id}: dependency {dependency!r} must "
                "name an earlier task; array order is the execution sequence."
            )
    seen_task_ids.add(task_id)
    try:
        review_budget(task)
    except ValueError as exc:
        raise SystemExit(
            f"decomposition task {task_id}: review_budget {exc}"
        ) from exc
    # The narrative fields were prompt-convention and silently droppable, so a
    # task could reach the board as an id and a title. They are the contract now.
    objective = task.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        raise SystemExit(
            f"decomposition task {task['id']}: 'objective' is required — one or two "
            "sentences of what this task changes and why, in a reader's language."
        )
    if len(objective) > OBJECTIVE_MAX:
        raise SystemExit(
            f"decomposition task {task['id']}: 'objective' is {len(objective)} chars "
            f"(max {OBJECTIVE_MAX}) — it is the summary a human reads, not the "
            "implementation transcript; put the detail in the plan."
        )
    plan_contracts = task.get("plan_contracts", [])
    if not isinstance(plan_contracts, list):
        raise SystemExit(
            f"decomposition task {task_id}: plan_contracts must be a list"
        )
    for contract_pos, contract in enumerate(plan_contracts, 1):
        if not isinstance(contract, dict) or set(contract) != {
                "id", "statement", "source"} or not all(
                    isinstance(contract.get(key), str) and contract[key].strip()
                    for key in ("id", "statement", "source")
                ):
            raise SystemExit(
                f"decomposition task {task_id}: plan_contracts entry "
                f"{contract_pos} needs exactly non-empty id, statement and "
                "source strings."
            )
        contract_id = contract["id"]
        if contract_id in seen_contract_ids:
            raise SystemExit(
                f"decomposition task {task_id}: plan_contracts entry "
                f"{contract_pos} has duplicate contract id {contract_id!r} "
                "across the decomposition"
            )
        seen_contract_ids.add(contract_id)
    for proof_pos, proof in enumerate(task.get("required_tests") or [], 1):
        if not isinstance(proof, dict):
            raise SystemExit(
                f"decomposition task {task['id']}: required_tests entry "
                f"{proof_pos} must be an object with id, path and command; "
                "opaque test names are not executable proof."
            )
        if set(proof) != {"id", "path", "command"} or not all(
            isinstance(proof.get(key), str) and proof[key].strip()
            for key in ("id", "path", "command")
        ):
            raise SystemExit(
                f"decomposition task {task['id']}: required_tests entry "
                f"{proof_pos} needs exactly non-empty id, path and command strings."
            )
        # Repo-relative paths are always posix (forward slashes), independent of
        # the host OS. Using os.path here validated with ntpath on Windows, which
        # rewrites "a/b/c" to "a\\b\\c" and rejected every valid path.
        rel = PurePosixPath(proof["path"])
        if (
            "\\" in proof["path"]
            or rel.is_absolute()
            or ".." in rel.parts
            or posixpath.normpath(proof["path"]) != proof["path"]
        ):
            raise SystemExit(
                f"decomposition task {task['id']}: required test path "
                f"{proof['path']!r} must be a normalized repo-relative path."
            )
        try:
            tokens = shlex.split(proof["command"])
        except ValueError as exc:
            raise SystemExit(
                f"decomposition task {task['id']}: required test command is not "
                f"parseable as argv ({exc})."
            )
        forbidden = {";", "&&", "||", "|", "&", ">", ">>", "<", "<<", "#"}
        if any(token in forbidden or token.startswith("#") for token in tokens):
            raise SystemExit(
                f"decomposition task {task['id']}: required test command must be "
                "one shell-free runner invocation, not a compound/commented command."
            )
        executable_pos = 0
        while (
            executable_pos < len(tokens)
            and "=" in tokens[executable_pos]
            and not tokens[executable_pos].startswith("=")
        ):
            executable_pos += 1
        executable = (
            Path(tokens[executable_pos]).name.lower()
            if executable_pos < len(tokens) else ""
        )
        if executable in {
            "sh", "bash", "zsh", "dash", "ksh", "fish", "csh", "tcsh",
            "pwsh", "powershell", "cmd", "cmd.exe", "env",
        }:
            raise SystemExit(
                f"decomposition task {task['id']}: required test command must "
                f"invoke the runner directly; shell/env wrapper {executable!r} "
                "is not shell-free."
            )
        if not any("{report}" in token for token in tokens):
            raise SystemExit(
                f"decomposition task {task['id']}: required test command "
                "must include a {report} placeholder for fresh JUnit proof."
            )
        if not any("{path}" in token for token in tokens):
            raise SystemExit(
                f"decomposition task {task['id']}: required test command "
                "must include a runner-native {path} placeholder."
            )
        if not any("{id}" in token for token in tokens):
            raise SystemExit(
                f"decomposition task {task['id']}: required test command "
                "must include a runner-native {id} placeholder."
            )
        reason = unrunnable_reason(proof["command"])
        if reason:
            raise SystemExit(
                f"decomposition task {task['id']}: required test command "
                f"{proof['command']!r} {reason}."
            )
    # `stage done` runs these. An entry that cannot execute is not a check, and
    # in practice it was prose ("package test script") nobody ever ran.
    for command in task.get("verify_commands") or []:
        reason = unrunnable_reason(str(command))
        if reason:
            raise SystemExit(
                f"decomposition task {task['id']}: verify_commands entry "
                f"{str(command)!r} {reason}. `forge stage done` executes every "
                "entry, so an unrunnable one is a gate that can never pass — "
                "write the command that proves this task, not a description of it."
            )
    criteria = task.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria or not all(
        isinstance(c, str) and c.strip() for c in criteria
    ):
        raise SystemExit(
            f"decomposition task {task['id']}: 'acceptance_criteria' must be a "
            "non-empty list of non-empty strings — a task nobody can check is done "
            "cannot be reviewed."
        )
from forge_cli.delegate import delegation_exclusion  # noqa: E402
from forge_cli.stages import (  # noqa: E402
    authoritative_stages_path, clear_story_authority, load_stages, task_digest,
    write_skeleton, write_stages,
)


def _full_contract_digest(task: dict) -> str:
    """Hash every recorded task field; stage measurement stays four-field."""
    canonical = json.dumps(task, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _task_graph(tasks: list[dict]) -> list[tuple[str, tuple[str, ...]]]:
    return [
        (task["id"], tuple(task.get("dependencies", [])))
        for task in tasks
    ]


def _measurement_receipt(
    root: Path,
    story: str,
    stage: dict,
    source: dict,
    target: dict,
    grill: dict,
) -> dict:
    """Build a continuity receipt after every original binding re-validates."""
    task_id = str(target.get("id") or "")
    task_plan_sha256 = task_plan_binding_digest(root, task_id, grill)
    current_story_plan_sha256 = story_plan_digest(root)
    receipts = stage.get("measurement_continuity")
    story_plan_sha256 = current_story_plan_sha256
    if isinstance(receipts, list) and receipts:
        predecessor = receipts[0].get("story_plan_sha256")
        permitted = {
            current_story_plan_sha256,
            *approved_story_plan_predecessors(root, current_story_plan_sha256),
        }
        if predecessor not in permitted:
            raise SystemExit(
                f"decomposition task {task_id}: measurement continuity is not "
                "bound to the current or an approved predecessor story plan; "
                "no decomposition state was written"
            )
        story_plan_sha256 = predecessor
    semantic = grounding_digest(
        root, target, in_stage=True, _plan_sha256=story_plan_sha256,
    )
    if (
        not task_plan_sha256
        or not story_plan_sha256
        or semantic != grounding_digest(
            root, source, in_stage=True, _plan_sha256=story_plan_sha256,
        )
    ):
        raise SystemExit(
            f"decomposition task {task_id}: cannot preserve the task grill across "
            "this measurement amendment because its approved story or task plan "
            "binding changed; no decomposition state was written"
        )
    if isinstance(receipts, list) and receipts:
        launch_id = receipts[0].get("launch_id")
        origin_measurement = receipts[0].get("from_measurement")
        origin_sha256 = stage.get("task_sha256")
        launch_task = {**target, **origin_measurement} \
            if isinstance(origin_measurement, dict) else source
    else:
        launch_id = ""
        origin_measurement = measurement_contract(source)
        origin_sha256 = task_digest(source)
        launch_task = source
    launch = validated_measurement_launch(
        root,
        launch_task,
        stage,
        str(origin_sha256 or ""),
        origin_measurement,
        str(launch_id or ""),
    )
    if launch is None:
        raise SystemExit(
            f"decomposition task {task_id}: an active-stage measurement amendment "
            "needs the exact successful write launch that the original task grill "
            "authorized; the launch is missing, failed, ambiguous, or no longer "
            "bound to this stage. No decomposition state was written"
        )
    return {
        "generated_by": "record_decomposition_from_json",
        "recorded_at": now_iso(),
        "story": story,
        "task_id": task_id,
        "stage_started_at": stage.get("started_at"),
        "stage_base_sha": stage.get("base_sha"),
        "source_grill_input_sha256": grill.get("input_sha256"),
        "story_plan_sha256": story_plan_sha256,
        "task_plan_sha256": task_plan_sha256,
        "semantic_grounding_sha256": semantic,
        "from_task_sha256": task_digest(source),
        "to_task_sha256": task_digest(target),
        "from_measurement": measurement_contract(source),
        "to_measurement": measurement_contract(target),
        "launch_id": launch.get("launch_id"),
    }


def _bootstrap_measurement_source(
    root: Path, stage: dict, target: dict, grill: dict,
) -> dict | None:
    """Recover a missed receipt from the exact stage-bound launch scope."""
    from forge_cli.delegate import current_delegation

    task_id = str(target.get("id") or "")
    original_sha256 = str(stage.get("task_sha256") or "")
    launch = current_delegation(
        root,
        task_id,
        stage_started_at=str(stage.get("started_at") or ""),
        task_sha256=original_sha256,
        ignore_lock=True,
    )
    scope = launch.get("write_scope") if launch else None
    if not isinstance(scope, list) or not all(isinstance(path, str) for path in scope):
        return None
    source = {**target, "write_scope": scope}
    if (
        task_digest(source) != original_sha256
        or not grounding_matches(
            root, source, grill.get("input_sha256"), in_stage=True,
        )
    ):
        return None
    return source

# Stage transitions and decomposition publication share one protected state
# lock. A re-record may amend an active task, but never rewrite the contract a
# completed stage already attested or race that stage's done transition.
with delegation_exclusion(
        root, "stages", kind="stage-state", namespace="state"):
    state = gate(root, signoff=True, approved_plan=True)
    current_tasks = {
        task.get("id"): task for task in tasks if isinstance(task, dict)
    }
    protected_decomposition = protected_decomposition_state_path(root)
    protected_stages = authoritative_stages_path(root)
    # Story-scope the protected authority the way load_stages already does:
    # leftover git-local state from a PREVIOUS story (its ship-time clear never
    # ran) must not freeze the NEW story's task graph to the old prefix. Only
    # same-story state participates in the freeze; anything else is the
    # documented shipped/orphaned-story case and is cleared idempotently.
    stale_story = load_json(protected_decomposition, default={}).get("story")
    stale_stages_issue = load_json(protected_stages, default={}).get("issue")
    if ((protected_decomposition.exists() and stale_story != story)
            or (protected_stages.exists()
                and stale_stages_issue not in (None, story))):
        removed = clear_story_authority(root)
        print(
            "Cleared stale protected authority from previous story "
            f"{stale_story or stale_stages_issue!r}: {', '.join(removed)}"
        )
    first_recording = (
        not protected_decomposition.exists() and not protected_stages.exists()
    )
    prior_decomposition = load_json(
        protected_decomposition, default={})
    reapproval_predecessors = approved_story_plan_predecessors(
        root, approved_sha256,
    )
    reapproval_rebind = bool(
        prior_decomposition.get("plan_sha256") in reapproval_predecessors
    )
    prior_tasks = {
        task.get("id"): task
        for task in prior_decomposition.get("tasks") or []
        if isinstance(task, dict)
    }
    stages_data = load_stages(root)
    stage_statuses = {
        stage.get("id"): stage.get("status")
        for stage in stages_data.get("stages") or []
        if isinstance(stage, dict)
    }
    frontier_index = next(
        (
            index for index, task in enumerate(tasks)
            if stage_statuses.get(task.get("id")) != "done"
        ),
        None,
    )
    execution_fields = (
        "write_scope", "required_tests", "verify_commands", "reviewer_focus",
        "plan_contracts", "review_budget",
    )
    if first_recording:
        for task in tasks:
            for field in execution_fields:
                if field in task:
                    raise SystemExit(
                        f"decomposition task {task['id']}: initial recording must "
                        f"be fully skeletal and must not declare {field}; re-record "
                        "frontier execution detail after the skeleton is protected."
                    )
    if not first_recording:
        prior_task_list = [
            task for task in prior_decomposition.get("tasks") or []
            if isinstance(task, dict)
        ]
        graph_changed = _task_graph(tasks) != _task_graph(prior_task_list)
        done_task_ids = {
            task_id for task_id, status in stage_statuses.items()
            if status == "done"
        }
        prior_done_tasks = [
            task for task in prior_task_list
            if task.get("id") in done_task_ids
        ]
        current_done_tasks = [
            task for task in tasks
            if task.get("id") in done_task_ids
        ]
        done_graph_unchanged = (
            len(prior_done_tasks) == len(done_task_ids)
            and len(current_done_tasks) == len(done_task_ids)
            and _task_graph(prior_done_tasks) == _task_graph(current_done_tasks)
        )
        graph_reapproved = (
            prior_decomposition.get("plan_sha256") != approved_sha256
            and prior_decomposition.get("plan_sha256") in reapproval_predecessors
            and (supplied_plan_sha256 == approved_sha256
                 or (supplied_plan_sha256 is None and load_json(
                     evidence_path(root, story, "plan-approval.json"), default={},
                 ).get("carried_forward_reason")))
        )
        # A changed graph needs native reapproval or a delivery-preserving
        # carried approval. Completed tasks keep IDs, order, and dependencies.
        if graph_changed and not (graph_reapproved and done_graph_unchanged):
            raise SystemExit(
                "decomposition task graph is frozen after approval: task ids, "
                "order, dependencies, and task count cannot change; amend and "
                "reapprove the story plan before recording a new graph."
            )
    if frontier_index is not None:
        # Execution detail is authored just-in-time: a pending task may carry it
        # only once every dependency is done (a task without explicit
        # dependencies follows its predecessor) — DAG order, not list order
        # (symphony-forge #145).
        done_ids = {
            task_id for task_id, status in stage_statuses.items()
            if status == "done"
        }
        ready_ids = set(ready_task_ids(tasks, done_ids))
        for task in tasks[frontier_index:]:
            if stage_statuses.get(task.get("id")) == "done":
                continue
            if task.get("id") in ready_ids:
                continue
            for field in execution_fields:
                if field in task:
                    raise SystemExit(
                        f"decomposition task {task['id']}: pending non-frontier "
                        f"task must not declare {field}; author execution detail "
                        "when the task reaches the frontier (its dependencies "
                        "are done)."
                    )
    backfilled_stage_digest = False
    stages_dirty = False
    changed_active: list[tuple[str, bool]] = []
    for stage in stages_data.get("stages") or []:
        if stage.get("status") not in {"active", "done"}:
            continue
        task_id = stage.get("id")
        new = current_tasks.get(task_id)
        if new is None:
            raise SystemExit(
                f"decomposition task {task_id}: an {stage.get('status')} stage "
                "cannot be removed or renamed; finish it or record it incomplete "
                "before changing the task list."
            )
        if stage.get("status") == "active":
            # Amending an active (in-flight) task's contract is allowed. What
            # that stales depends on WHICH fields moved: the grounding fields
            # (what the work is) stale the grill and the approval; the
            # measurement fields (scope, tests, verify) stale nothing -- they
            # are enforced by `stage done` measuring and running them. The
            # review stamp is never touched here: it binds to the product
            # diff, and a contract edit changes no product byte.
            prior = prior_tasks.get(task_id)
            if prior is not None and _full_contract_digest(prior) != _full_contract_digest(new):
                grounding_moved = any(
                    prior.get(field) != new.get(field)
                    for field in IN_STAGE_GROUNDING_FIELDS)
                measurement_moved = any(
                    prior.get(field) != new.get(field)
                    for field in MEASUREMENT_CONTRACT_FIELDS)
                changed_active.append(
                    (task_id, bool(stage.get("local_review_stamp")),
                     grounding_moved, measurement_moved))
            continue
        if stage.get("status") == "done":
            prior = prior_tasks.get(task_id)
            if (
                prior is None
                or _full_contract_digest(prior) != _full_contract_digest(new)
            ):
                raise SystemExit(
                    f"decomposition task {task_id}: a completed stage's full "
                    "contract cannot be changed or removed; add a new follow-up "
                    "task instead."
                )
            recorded_digest = stage.get("task_sha256")
            new_digest = task_digest(new)
            if not recorded_digest:
                if prior is None or task_digest(prior) != new_digest:
                    raise SystemExit(
                        f"decomposition task {task_id}: a completed stage's "
                        "legacy contract cannot be changed or removed; add a "
                        "new follow-up task instead."
                    )
                stage["task_sha256"] = new_digest
                backfilled_stage_digest = True
            elif new_digest == (stage.get("contract_changed") or {}).get("to"):
                # The stage RECORDS that its contract moved and that it closed
                # after the move (decision 0023). Its task_sha256 kept the start
                # digest, which made every completed stage permanently
                # un-re-recordable. Trust the evidence beside it and self-heal.
                stage["task_sha256"] = new_digest
                backfilled_stage_digest = True
            elif new_digest != recorded_digest:
                raise SystemExit(
                    f"decomposition task {task_id}: a completed stage's contract "
                    "cannot be changed or removed; add a new follow-up task instead."
                )
    # A pre-stage grill includes measurement fields so it can authorize stage
    # start. Once the stage is active those fields are enforced mechanically.
    # Preserve that transition as a protected receipt before publishing an
    # amended measurement contract; never rewrite the original grill evidence.
    for stage in stages_data.get("stages") or []:
        if stage.get("status") != "active":
            continue
        task_id = stage.get("id")
        target = current_tasks.get(task_id)
        prior = prior_tasks.get(task_id)
        if target is None or prior is None:
            continue
        grounding_moved = any(
            prior.get(field) != target.get(field)
            for field in IN_STAGE_GROUNDING_FIELDS
        )
        if grounding_moved:
            continue
        grill = load_json(
            evidence_path(root, story, f"grills/tasks/{task_id}.json"),
            default={},
        )
        if not grill or task_grill_grounding_matches(
            root,
            target,
            grill,
            allow_unbound_story_reapproval=reapproval_rebind,
        ):
            continue
        source = (
            prior if task_grill_grounding_matches(
                root,
                prior,
                grill,
                allow_unbound_story_reapproval=reapproval_rebind,
            )
            else _bootstrap_measurement_source(root, stage, target, grill)
        )
        if source is None:
            raise SystemExit(
                f"decomposition task {task_id}: cannot prove continuity from the "
                "original task grill to this active-stage measurement contract; "
                "no decomposition state was written"
            )
        receipt = _measurement_receipt(root, story, stage, source, target, grill)
        receipts = stage.setdefault("measurement_continuity", [])
        if not isinstance(receipts, list):
            raise SystemExit(
                f"decomposition task {task_id}: protected measurement continuity "
                "state is malformed; no decomposition state was written"
            )
        receipts.append(receipt)
        stages_dirty = True
    if backfilled_stage_digest:
        write_stages(root, stages_data)
    # The saved task plans carry a rendered copy of their contract. Re-render
    # so the copy can never lag the record it is rendered from.
    for task_id, new in current_tasks.items():
        try:
            refresh_task_plan_contract(root, task_id, new)
        except Exception:
            pass
    for task_id, was_reviewed, grounding_moved, measurement_moved in changed_active:
        if grounding_moved:
            print(
                f"\nNOTE: {task_id} execution contract changed in what the work IS "
                "(objective, acceptance criteria, plan contracts or user_facing). "
                "Its task grill and plan approval are now STALE and do NOT carry "
                "to the amended plan.\n"
                "Re-grill and re-approve BEFORE the next delegate or stage close:\n"
                f"  python3 factory/scripts/record_grill_from_json.py --gate task --task {task_id}\n"
                "  display the exact amended plan in native Plan Mode and consume its approval\n"
                "The review stamp, if any, stands: it binds to the product diff, "
                "which this did not change.\n"
            )
        elif measurement_moved:
            print(
                f"\nNOTE: {task_id} contract changed only in how the work is MEASURED "
                "(write scope, required tests or verify commands). Recorded; "
                "nothing to re-grill or re-approve -- `stage done` measures and "
                "runs these. The review stamp and the delegate launch stand.\n"
            )
        if was_reviewed and grounding_moved:
            print(
                f"WARNING: {task_id} was already implemented/reviewed. Approving the amended "
                "plan now post-dates the work — approval is meant to precede implementation. "
                "For a substantive scope change prefer a follow-up task rather than re-approving "
                "completed work.\n"
            )
    payload["commit"] = head_sha(root)
    dump_json(protected_decomposition_state_path(root), payload)
    dump_json(decomposition_state_path(root, for_write=True), payload)
    # The decomposition is immutable evidence; the stage tracker is its mutable
    # execution twin (decision 0007) — pr_ready refuses while stages are open.
    write_skeleton(root, state.get("issue_key", ""), tasks)
    receipts_by_task = {
        row.get("id"): row.get("measurement_continuity")
        for row in stages_data.get("stages") or []
        if row.get("measurement_continuity")
    }
    if receipts_by_task:
        # write_skeleton preserves seal fields but deliberately rebuilds each
        # row. Restore existing and newly validated receipts after that rebuild,
        # while retaining any pending-tail graph changes it created.
        refreshed_stages = load_stages(root)
        for row in refreshed_stages.get("stages") or []:
            if row.get("id") in receipts_by_task:
                row["measurement_continuity"] = receipts_by_task[row.get("id")]
        write_stages(root, refreshed_stages)
    state["decomposition_status"] = "recorded"
    state["decomposition_plan_sha256"] = approved_sha256
    state["updated_at"] = now_iso()
    dump_json(run_state_path(root), state)
    from forge_cli.events import append_event  # noqa: E402
    append_event(root, "decomposed", actor="docs-decomposer",
                 story=state.get("issue_key", ""), detail=f"{len(tasks)} task(s)")
print(f"Recorded decomposition: {len(tasks)} stage(s) -> .factory/stages.json")
