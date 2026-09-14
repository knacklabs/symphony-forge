#!/usr/bin/env python3
"""Record a handover grill (.factory/grills/<gate>.json).

A grill is the adversarial gap/contradiction interrogation run BEFORE a
handover gate (factory/prompts/griller.md): `signoff` protects the client->PM
gate, `epics` protects the PM->EM gate. The downstream gate scripts
(record_signoff.py, forge roadmap import) refuse without a fresh, passing
grill — recording a verdict here is what makes "we checked for gaps" a fact
instead of a claim. A `blocked` verdict is recordable (it is the audit trail
of what blocked) but never satisfies a gate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from factory_lib import (
    plan_digest_without_assumptions,
    dump_json, evidence_path, git_control_dir, grounding_digest, head_sha,
    load_json, now_iso, protected_decomposition_state_path, read_stdin_utf8,
    repo_root, run_state_path, sha256_of,
    task_frontier_state, task_stage_record, validate_payload,
)
from grill_gates import gate_names, get_gate

VERDICTS = {"pass", "blocked"}
TASK_DECISIONS = {"keep", "split", "block"}


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _cold_launch_digest(root: Path, gate: str, task_id: str) -> str:
    from forge_cli.delegate import load_delegations
    label = f"grill-{gate}" + (f"-{task_id}" if task_id else "")
    story = load_json(run_state_path(root), default={}).get("issue_key", "")
    spec = get_gate(gate)
    previous = load_json(
        evidence_path(root, story if spec.story_scoped else "",
                      spec.evidence_name(task_id)), default={},
    )
    since = str(previous.get("recorded_at") or "")
    latest: dict[str, dict] = {}
    for row in load_delegations(root):
        if (row.get("task") == label
                and (not spec.story_scoped or row.get("story") == story)
                and str(row.get("at") or "") > since
                and isinstance(row.get("launch_id"), str)):
            latest[row["launch_id"]] = row
    completed = [row for row in latest.values()
                 if row.get("launch_status") == "succeeded"]
    if len(completed) != 1:
        raise SystemExit(
            f"{gate} grill requires exactly one successful independent cold-read "
            f"launch since its last pass; found {len(completed)}"
        )
    digest = completed[0].get("task_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise SystemExit(f"{gate} cold-read launch has no exact input digest")
    return digest


def _validate_dispositions(payload: dict, cold: str, final: str) -> None:
    findings = [*payload.get("gaps", []), *payload.get("contradictions", [])]
    dispositions = payload.get("finding_dispositions")
    if not isinstance(dispositions, list) or len(dispositions) != len(findings):
        raise SystemExit(
            "grill finding_dispositions must map every cold-read finding exactly once"
        )
    for finding, disposition in zip(findings, dispositions):
        if (not isinstance(disposition, dict)
                or disposition.get("finding") != finding
                or any(not _non_empty_string(disposition.get(field))
                       for field in ("resolution", "source"))):
            raise SystemExit(
                "grill finding_dispositions must be ordered one-to-one objects "
                "with exact finding, resolution, and source"
            )
    amendments = payload.get("amendments", [])
    if not isinstance(amendments, list):
        raise SystemExit("grill amendments must be a list")
    for entry in amendments:
        if (not isinstance(entry, dict)
                or any(not _non_empty_string(entry.get(field))
                       for field in ("change", "reason", "source"))):
            raise SystemExit(
                "grill amendments require non-empty change, reason, and source"
            )
    if cold != final and not amendments:
        raise SystemExit(
            "the final artifact differs from the cold-read input; every change "
            "requires an explained amendment bridge"
        )
    payload["cold_input_sha256"] = cold
    payload["final_artifact_sha256"] = final


def _validate_task_grill(root: Path, payload: dict, task_id: str) -> dict:
    required = {
        "inspected_refs": list,
        "current_flow": str,
        "criteria_map": dict,
        "decision": str,
        "new_abstractions": list,
        "finding_dispositions": list,
    }
    for field, expected in required.items():
        if field not in payload:
            raise SystemExit(f"task grill missing required proof field {field!r}")
        if not isinstance(payload[field], expected):
            raise SystemExit(
                f"task grill proof field {field!r} must be {expected.__name__}"
            )

    if not payload["inspected_refs"]:
        raise SystemExit("task grill inspected_refs must name at least one working-tree path")
    for ref in payload["inspected_refs"]:
        if not _non_empty_string(ref):
            raise SystemExit("task grill inspected_refs entries must be non-empty strings")
        path_text = ref
        candidate = (root / path_text).resolve()
        if not candidate.exists() and ":" in path_text:
            path_text = path_text.rsplit(":", 1)[0]
            candidate = (root / path_text).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            raise SystemExit(f"task grill inspected ref escapes the working tree: {ref!r}")
        if not candidate.exists():
            raise SystemExit(f"task grill inspected ref path does not exist: {path_text!r}")

    if not payload["current_flow"].strip():
        raise SystemExit("task grill current_flow must not be empty")
    if payload["decision"] not in TASK_DECISIONS:
        raise SystemExit("task grill decision must be one of: keep, split, block")
    if payload["verdict"] == "pass" and payload["decision"] != "keep":
        raise SystemExit("task grill verdict 'pass' requires decision 'keep'")
    if any(not _non_empty_string(item) for item in payload["new_abstractions"]):
        raise SystemExit("task grill new_abstractions entries must be non-empty strings")
    if any(not _non_empty_string(gap) for gap in payload["gaps"]):
        raise SystemExit("task grill gaps entries must be non-empty strings")

    frontier = task_frontier_state(root)
    stage = next(
        (s for s in load_json(
            git_control_dir(root) / "stages.json", default={}
        ).get("stages", []) if s.get("id") == task_id),
        {},
    )
    # The frontier task grills before it starts; but an ACTIVE or DONE task may
    # be legitimately RE-grilled — a re-decomposition or a post-approval plan
    # edit stales its grill, and by then the frontier has moved past it. Accept
    # the target task itself in that case (validated against ITS OWN contract,
    # mirroring the seal check), and refuse only a task that is neither the
    # frontier nor active/done.
    if frontier is not None and frontier[1].get("id") == task_id:
        target = frontier[1]
    elif stage.get("status") in ("active", "done"):
        target = next(
            (t for t in load_json(
                protected_decomposition_state_path(root), default={}
            ).get("tasks", []) if t.get("id") == task_id),
            None,
        )
        if target is None:
            raise SystemExit(
                f"task grill target {task_id} is not in the protected decomposition"
            )
    else:
        frontier_id = frontier[1].get("id") if frontier else "none"
        raise SystemExit(
            f"task grill must cover the frontier task ({frontier_id}) or an "
            f"active/done task; {task_id} is neither"
        )
    criteria = target.get("acceptance_criteria") or []
    if set(payload["criteria_map"]) != set(criteria):
        missing = sorted(set(criteria) - set(payload["criteria_map"]))
        extra = sorted(set(payload["criteria_map"]) - set(criteria))
        raise SystemExit(
            "task grill criteria_map must cover every task acceptance "
            f"criterion exactly (missing={missing}, extra={extra})"
        )
    if any(not _non_empty_string(value) for value in payload["criteria_map"].values()):
        raise SystemExit("task grill criteria_map values must be non-empty strings")
    plan_contracts = target.get("plan_contracts")
    if not isinstance(plan_contracts, list) or not plan_contracts:
        raise SystemExit(
            "task grill requires the task's plan_contracts whose statements "
            "match criteria_map keys"
        )
    contract_statements = {
        contract.get("statement")
        for contract in plan_contracts
        if isinstance(contract, dict)
    }
    if contract_statements != set(payload["criteria_map"]):
        missing = sorted(set(payload["criteria_map"]) - contract_statements)
        extra = sorted(contract_statements - set(payload["criteria_map"]))
        raise SystemExit(
            "task grill criteria_map keys must equal protected plan_contracts "
            f"statements (missing={missing}, extra={extra})"
        )

    if payload["decision"] == "block":
        packet = payload.get("escalation_packet")
        packet_fields = {
            "issue", "evidence", "recommendation", "alternatives", "rollback",
        }
        if (
            not isinstance(packet, dict)
            or set(packet) != packet_fields
            or any(not _non_empty_string(packet[field]) for field in packet_fields)
        ):
            raise SystemExit(
                "task grill decision 'block' requires escalation_packet with exactly "
                "these non-empty string fields: issue, evidence, recommendation, "
                "alternatives, rollback"
            )
    return target


if any(
    arg == "--task-digest" or arg.startswith("--task-digest=")
    for arg in sys.argv[1:]
):
    raise SystemExit(
        "--task-digest is no longer accepted; the digest is derived from the "
        "protected contract, approved plan, and product tree"
    )

parser = argparse.ArgumentParser(description="Record a handover/plan grill from structured JSON")
parser.add_argument("--gate", required=True, choices=gate_names())
parser.add_argument("--input", help="Path to grill JSON. If omitted, read from stdin.")
parser.add_argument("--input-digest", dest="input_digest",
                    help="Path to the artifact this grill interrogated (roadmap input for "
                         "--gate spec/epics, the plan draft for --gate plan); its sha256 binds "
                         "the grill to THAT version. Required for epics and plan gates.")
parser.add_argument("--task", help="Task id for --gate task.")
args = parser.parse_args()

if args.input:
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
else:
    raw = read_stdin_utf8().strip()
    if not raw:
        raise SystemExit("Expected JSON on stdin or via --input")
    payload = json.loads(raw)

root = repo_root()
validate_payload(root, "grill", payload)
if payload.get("gate") != args.gate:
    raise SystemExit(f"payload gate {payload.get('gate')!r} does not match --gate {args.gate}")
if payload.get("verdict") not in VERDICTS:
    raise SystemExit(f"verdict must be one of {', '.join(sorted(VERDICTS))}")
# Parked findings count: an entry explicitly carried in open_items is a
# documented non-blocking park, not an unresolved blocker.
parked = len(payload.get("open_items") or [])
unresolved = (len(payload["gaps"]) + len(payload["contradictions"])
              - len(payload["resolutions"]) - parked)
if payload["verdict"] == "pass" and unresolved > 0:
    raise SystemExit(
        f"verdict 'pass' with {unresolved} unresolved finding(s) — every gap/contradiction "
        "needs a resolution (doc edit or decision record), an explicit open_items park, "
        "or the verdict is 'blocked'."
    )
if args.gate in ("spec", "epics", "plan"):
    if not args.input_digest:
        raise SystemExit(
            f"--gate {args.gate} requires --input-digest <artifact>: the grill must be "
            "bound to the exact spec / roadmap input / plan draft it interrogated."
        )
    digest_target = Path(args.input_digest).expanduser()
    if not digest_target.is_file():
        raise SystemExit(f"--input-digest {digest_target} not found")
    payload["input_sha256"] = (
        plan_digest_without_assumptions(digest_target)
        if args.gate == "plan" else sha256_of(digest_target)
    )
if args.gate == "task":
    if not args.task:
        raise SystemExit("--gate task requires --task <id>")
    if Path(args.task).name != args.task or args.task in (".", ".."):
        raise SystemExit("--task must be a single task id, not a path")
    if payload.get("task_id") and payload["task_id"] != args.task:
        raise SystemExit(
            f"payload task_id {payload['task_id']!r} does not match --task {args.task!r}"
        )
    issue = load_json(run_state_path(root), default={}).get("issue_key", "")
    task_plan = evidence_path(root, issue, f"task-plans/{args.task}.md")
    if not task_plan.is_file():
        raise SystemExit(
            f"task grill requires a saved task plan first: run `./forge task plan "
            f"save {args.task} --from <path>`"
        )
    task = _validate_task_grill(root, payload, args.task)
    for field in (
        "approved_task_plan_sha256", "approved_by", "approved_at",
        "approval_runtime", "approval_session_id", "approval_event_id",
    ):
        payload.pop(field, None)
    payload["task_id"] = args.task
    # Ground on the SAME treeish the seal (require_ready_task) uses: a DONE
    # task's grill seals against its stage baseline, so grounding the record on
    # the moving working tree would read perpetually stale and the re-grill of an
    # approved/completed task could never be seen fresh. A frontier/active task
    # still grounds on the working tree ("").
    #
    # The stage is resolved from the TASK'S OWN WORKTREE, not from whichever
    # control directory this process happens to sit in. Both copies exist and
    # drift: a task closed in its worktree still reads `active` in the main
    # repo, so recording the grill from there ground it on the working tree
    # while the seal -- run in the worktree -- checked the baseline. Same task,
    # same code, two answers, and a passing grill that could never verify.
    _stage = task_stage_record(root, args.task)
    if _stage.get("status") == "done":
        from forge_cli.stages import stage_baseline
        from factory_lib import task_state_root
        # The baseline ref lives with the stage that recorded it.
        _treeish = stage_baseline(task_state_root(root, args.task), _stage)
        _basis = "stage-baseline"
    else:
        _treeish = ""
        _basis = "working-tree"
    _in_stage = _stage.get("status") in ("active", "done")
    payload["input_sha256"] = grounding_digest(
        root, task, treeish=_treeish, in_stage=_in_stage)
    # Say what this attestation was grounded on. A digest alone can only ever
    # report "stale"; naming the basis lets the seal say WHY it disagrees and
    # which command fixes it.
    payload["grounding_basis"] = _basis
    payload["grounding_treeish"] = _treeish
    payload["task_plan_sha256"] = plan_digest_without_assumptions(task_plan)
if args.gate == "plan":
    # Plan grills are per task: stamp the active issue so a stale grill from
    # a previous task can never satisfy this one's plan save.
    issue = load_json(run_state_path(root), default={}).get("issue_key", "")
    if not issue:
        raise SystemExit("no active task (.factory/run.json issue_key) — run intake first")
    if payload.get("issue") and payload["issue"] != issue:
        raise SystemExit(
            f"payload issue {payload['issue']!r} does not match the active task {issue!r}"
        )
    payload["issue"] = issue
payload["recorded_at"] = now_iso()
payload["commit"] = head_sha(root)
active_story = load_json(run_state_path(root), default={}).get("issue_key", "")
_gate = get_gate(args.gate)
if args.gate == "task":
    final_digest = sha256_of(task_plan)
else:
    _label, artifact = _gate.locate(root, args.task or "", args.input_digest or "")
    from forge_cli.grill import _artifact_digest
    final_digest = _artifact_digest(artifact)
_validate_dispositions(
    payload,
    _cold_launch_digest(root, args.gate, args.task or ""),
    final_digest,
)


story = active_story if _gate.story_scoped else ""
name = _gate.evidence_name(args.task or "")
dest = evidence_path(root, story, name, for_write=True)
dump_json(dest, payload)
print(f"Recorded {args.gate} grill: {payload['verdict']} "
      f"({len(payload['gaps'])} gap(s), {len(payload['contradictions'])} contradiction(s), "
      f"{len(payload['resolutions'])} resolution(s))")
