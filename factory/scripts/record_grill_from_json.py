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
import difflib
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
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


def _cold_launch_terminal(
    root: Path, gate: str, task_id: str,
) -> tuple[dict, list[str], dict | None]:
    """Select one launch and validate its immutable lifecycle and argv."""
    from forge_cli.delegate import argv_digest, load_delegations
    label = f"grill-{gate}" + (f"-{task_id}" if task_id else "")
    story = load_json(run_state_path(root), default={}).get("issue_key", "")
    spec = get_gate(gate)
    previous = load_json(
        evidence_path(root, story if spec.story_scoped else "",
                      spec.evidence_name(task_id)), default={},
    )
    since = str(previous.get("recorded_at") or "")
    previous_launch_id = previous.get("launch_id")
    scoped_rows = [
        row for row in load_delegations(root)
        if row.get("task") == label
        and (not spec.story_scoped or row.get("story") == story)
    ]
    new_rows = [
        row for row in scoped_rows
        if (str(row.get("at") or "") > since
            or (isinstance(previous_launch_id, str)
                and str(row.get("at") or "") == since
                and isinstance(row.get("launch_id"), str)
                and row.get("launch_id") != previous_launch_id))
    ]
    launches: dict[str, list[dict]] = {}
    for row in new_rows:
        if isinstance(row.get("launch_id"), str):
            launches.setdefault(row["launch_id"], []).append(row)
    bridge_previous = None
    if new_rows:
        completed = [rows for rows in launches.values()
                     if rows[-1].get("launch_status") == "succeeded"]
    else:
        previous_digest = previous.get("cold_input_sha256")
        if (gate != "plan"
                or previous.get("verdict") != "pass"
                or previous.get("transport") == "host-native"
                or not isinstance(previous_digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", previous_digest)):
            completed = []
        else:
            old_launches: dict[str, list[dict]] = {}
            for row in scoped_rows:
                if (row.get("task_sha256") == previous_digest
                        and isinstance(row.get("launch_id"), str)):
                    old_launches.setdefault(row["launch_id"], []).append(row)
            completed = [rows for rows in old_launches.values()
                         if rows[-1].get("launch_status") == "succeeded"]
            if previous_launch_id is not None:
                completed = [rows for rows in completed
                             if rows[0].get("launch_id") == previous_launch_id]
            elif completed:
                completed = [max(
                    enumerate(completed),
                    key=lambda item: (str(item[1][-1].get("at") or ""), item[0]),
                )[1]]
            bridge_previous = previous
    if len(completed) != 1:
        raise SystemExit(
            f"{gate} grill requires exactly one successful independent cold-read "
            f"launch since its last pass; found {len(completed)}"
        )
    rows = completed[0]
    terminal = rows[-1]
    immutable = (
        "task", "story", "brief_sha256", "prompt_sha256", "task_sha256",
        "write", "model",
        "effort", "argv", "argv_sha256", "transport", "brief_path",
        "output_path", "stderr_path", "context",
    )
    if (len(rows) != 3
            or [row.get("launch_status") for row in rows]
            != ["starting", "running", "succeeded"]
            or any(any(row.get(field) != rows[0].get(field) for field in immutable)
                   for row in rows[1:])
            or any(rows[1].get(field) != terminal.get(field)
                   for field in ("pid", "pgid", "pid_started"))
            or terminal.get("write") is not False
            or terminal.get("exit_code") != 0
            or not isinstance(terminal.get("pid"), int)
            or not isinstance(terminal.get("pgid"), int)
            or not _non_empty_string(terminal.get("pid_started"))):
        raise SystemExit(f"{gate} cold-read launch lifecycle is not authentic")
    argv = terminal.get("argv")
    if (not isinstance(argv, list) or not argv
            or any(not isinstance(token, str) for token in argv)
            or terminal.get("argv_sha256") != argv_digest(argv)):
        raise SystemExit(f"{gate} cold-read launch argv identity is invalid")
    return terminal, argv, bridge_previous


def _cold_launch_brief(
    root: Path, gate: str, task_id: str, terminal: dict,
) -> tuple[Path, bytes, str]:
    """Validate the exact brief bytes and optional context identity."""
    brief = root / ".factory" / (
        f"grill-brief-{gate}" + (f"-{task_id}" if task_id else "") + ".md"
    )
    try:
        brief_bytes = brief.read_bytes()
    except OSError:
        brief_bytes = b""
    if (terminal.get("brief_path") != brief.relative_to(root).as_posix()
            or not brief_bytes
            or terminal.get("brief_sha256")
            != hashlib.sha256(brief_bytes).hexdigest()):
        raise SystemExit(f"{gate} cold-read launch brief identity is invalid")
    context = terminal.get("context")
    context_opaque = ""
    if context is not None:
        if (not isinstance(context, dict)
                or set(context) != {"supplied", "bytes", "snapshot_id"}
                or context.get("supplied") is not True
                or type(context.get("bytes")) is not int
                or context["bytes"] < 0
                or not isinstance(context.get("snapshot_id"), str)):
            raise SystemExit(f"{gate} cold-read context identity is invalid")
        context_opaque = context["snapshot_id"].removeprefix("context-")
        if not re.fullmatch(
                r"[0-9a-f]{32}(?:[0-9a-f]{32})?", context_opaque):
            raise SystemExit(f"{gate} cold-read context identity is invalid")
        if len(context_opaque) == 64 and not re.fullmatch(
                r"[0-9a-f]{64}", str(terminal.get("prompt_sha256") or "")):
            raise SystemExit(f"{gate} cold-read prompt identity is invalid")
    return brief, brief_bytes, context_opaque


def _cold_result_bytes(terminal: dict, gate: str) -> tuple[Path, bytes]:
    """Read the authenticated result once without following links."""
    output_text = terminal.get("output_path")
    if not _non_empty_string(output_text):
        raise SystemExit(f"{gate} cold-read launch has no durable result identity")
    output = Path(output_text)
    try:
        info = output.lstat()
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1):
            raise SystemExit(f"{gate} cold-read result identity is invalid")
        descriptor = os.open(output, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                    or not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1):
                raise SystemExit(f"{gate} cold-read result identity is invalid")
            result = stream.read()
    except OSError:
        raise SystemExit(f"{gate} cold-read result is unavailable")
    if (not result or terminal.get("output_sha256")
            != hashlib.sha256(result).hexdigest()):
        raise SystemExit(f"{gate} cold-read result does not match its terminal output hash")
    return output, result


def _cold_finding_text(
    root: Path, gate: str, terminal: dict, argv: list[str], brief: Path,
    context_opaque: str, output: Path, result: bytes,
) -> str:
    """Validate native or companion transport and return exact finding text."""
    if terminal.get("transport") == "native":
        from forge_cli.codex_runtime import native_argv_valid, scan_native_result
        native_result = scan_native_result(output, data=result)
        if (not _non_empty_string(terminal.get("session_id"))
                or terminal.get("session_id") != native_result.session_id
                or native_result.error
                or not native_result.message
                or not native_argv_valid(terminal, root, [])):
            raise SystemExit(f"{gate} native cold-read has no session identity")
        return native_result.message
    else:
        companion = terminal.get("companion_path")
        base_argv = [
            argv[0], companion, "task", "--json", "--cwd", str(root),
            "--model", terminal.get("model"), "--effort", terminal.get("effort"),
        ]
        expected = []
        if not context_opaque:
            expected = [base_argv + ["--prompt-file", prompt] for prompt in (
                str(brief), brief.relative_to(root).as_posix(),
            )]
        elif len(context_opaque) == 64:
            expected = [base_argv]
        else:
            historical = (Path(tempfile.gettempdir()).resolve()
                          / f"forge-context-{context_opaque}" / "brief.md")
            expected = [base_argv + ["--prompt-file", str(historical)]]
        if (terminal.get("transport") is not None
                or not _non_empty_string(companion)
                or Path(argv[0]).stem.lower() != "node"
                or argv not in expected):
            raise SystemExit(f"{gate} cold-read transport identity is invalid")
        try:
            wrapper = json.loads(result.decode("utf-8"))
        except UnicodeDecodeError:
            raise SystemExit(f"{gate} cold-read findings are not UTF-8")
        except json.JSONDecodeError:
            raise SystemExit(f"{gate} cold-read result is not JSON")
        if (not isinstance(wrapper, dict)
                or wrapper.get("status") != 0
                or not _non_empty_string(wrapper.get("threadId"))
                or not _non_empty_string(wrapper.get("rawOutput"))):
            raise SystemExit(f"{gate} cold-read result has invalid companion shape")
        return wrapper["rawOutput"]


def _cold_findings(gate: str, finding_text: str) -> dict:
    """Validate the cold reader's intentionally small result schema."""
    try:
        findings = json.loads(finding_text)
    except json.JSONDecodeError:
        raise SystemExit(f"{gate} cold-read findings are not JSON")
    if (not isinstance(findings, dict)
            or set(findings) != {"gaps", "contradictions"}
            or any(not isinstance(findings[field], list)
                   or any(not _non_empty_string(item)
                          for item in findings[field])
                   for field in ("gaps", "contradictions"))):
        raise SystemExit(f"{gate} cold-read findings have invalid shape")
    return findings


def _cold_launch_result(
    root: Path, gate: str, task_id: str,
) -> tuple[str, dict, str | None, dict | None, str]:
    terminal, argv, bridge_previous = _cold_launch_terminal(root, gate, task_id)
    brief, brief_bytes, context_opaque = _cold_launch_brief(
        root, gate, task_id, terminal,
    )
    output, result = _cold_result_bytes(terminal, gate)
    finding_text = _cold_finding_text(
        root, gate, terminal, argv, brief, context_opaque, output, result,
    )
    findings = _cold_findings(gate, finding_text)
    digest = terminal.get("task_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SystemExit(f"{gate} cold-read launch has no exact input digest")
    from forge_cli.grill import _cold_artifact_from_brief
    try:
        cold_artifact = _cold_artifact_from_brief(brief_bytes, digest)
    except UnicodeDecodeError:
        raise SystemExit(f"{gate} cold-read brief artifact is not UTF-8")
    if (cold_artifact is not None
            and hashlib.sha256(cold_artifact.encode("utf-8")).hexdigest() != digest):
        raise SystemExit(f"{gate} cold-read brief artifact does not match its input digest")
    return digest, findings, cold_artifact, bridge_previous, terminal["launch_id"]


def _regular_utf8_bytes(path: Path, gate: str) -> tuple[bytes, str]:
    """Read a native handoff result without accepting links or byte drift."""
    try:
        info = path.lstat()
        if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1):
            raise SystemExit(f"{gate} host-native cold result is not a regular file")
        identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if ((opened.st_dev, opened.st_ino, opened.st_size,
                 opened.st_mtime_ns) != identity
                    or not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1):
                raise SystemExit(f"{gate} host-native cold result identity changed")
            data = stream.read()
            after = os.fstat(stream.fileno())
            current = path.lstat()
            if ((after.st_dev, after.st_ino, after.st_size,
                 after.st_mtime_ns) != identity
                    or (current.st_dev, current.st_ino, current.st_size,
                        current.st_mtime_ns) != identity
                    or stat.S_ISLNK(current.st_mode)
                    or not stat.S_ISREG(current.st_mode)
                    or current.st_nlink != 1):
                raise SystemExit(f"{gate} host-native cold result changed while read")
    except OSError:
        raise SystemExit(f"{gate} host-native cold result is unavailable")
    if not data:
        raise SystemExit(f"{gate} host-native cold result is empty")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise SystemExit(f"{gate} host-native cold result is not UTF-8")
    return data, text


def _native_cold_launch_result(
    root: Path, gate: str, task_id: str, result_path: Path,
    preparation_id: str,
) -> tuple[str, dict, str | None, str, dict | None]:
    """Admit one process-free host-native griller preparation and its result."""
    from forge_cli.delegate import argv_digest, load_delegations
    from forge_cli.grill import _cold_artifact_from_brief

    if not re.fullmatch(r"launch-[0-9a-f]{32}", preparation_id):
        raise SystemExit(f"{gate} host-native preparation id is invalid")
    label = f"grill-{gate}" + (f"-{task_id}" if task_id else "")
    story = load_json(run_state_path(root), default={}).get("issue_key", "")
    spec = get_gate(gate)
    previous = load_json(
        evidence_path(root, story if spec.story_scoped else "",
                      spec.evidence_name(task_id)), default={},
    )
    since = str(previous.get("recorded_at") or "")
    scoped_rows = [row for row in load_delegations(root)
                   if row.get("task") == label
                   and (not spec.story_scoped or row.get("story") == story)]
    new_rows = [row for row in scoped_rows
                if str(row.get("at") or "") > since]
    bridge_previous = None
    if new_rows:
        rows = [row for row in new_rows
                if row.get("launch_id") == preparation_id]
    else:
        previous_digest = previous.get("cold_input_sha256")
        if (gate == "plan"
                and previous.get("verdict") == "pass"
                and previous.get("transport") == "host-native"
                and previous.get("preparation_id") == preparation_id
                and isinstance(previous_digest, str)
                and re.fullmatch(r"[0-9a-f]{64}", previous_digest)):
            rows = [row for row in scoped_rows
                    if row.get("launch_id") == preparation_id]
            bridge_previous = previous
        else:
            rows = []
    if len(rows) != 1:
        raise SystemExit(
            f"{gate} grill requires exactly one matching host-native prepared "
            f"row; found {len(rows)}"
        )
    prepared = rows[0]
    forbidden_fragments = (
        "pid", "session", "token", "output", "process", "stderr",
        "companion", "exit_code",
    )
    forbidden = [key for key in prepared
                 if any(fragment in key.lower()
                        for fragment in forbidden_fragments)]
    if forbidden:
        raise SystemExit(
            f"{gate} host-native preparation carries process claims: "
            + ", ".join(sorted(forbidden))
        )
    argv = prepared.get("argv")
    if (prepared.get("launch_status") != "prepared"
            or prepared.get("transport") != "host-native"
            or str(prepared.get("story") or "") != str(story or "")
            or prepared.get("write") is not False
            or prepared.get("agent_type") != "griller"
            or argv != []
            or prepared.get("argv_sha256") != argv_digest([])
            or prepared.get("model") != ""
            or prepared.get("effort") != ""):
        raise SystemExit(f"{gate} host-native cold-read preparation is invalid")
    if (bridge_previous is not None
            and prepared.get("task_sha256")
            != bridge_previous.get("cold_input_sha256")):
        raise SystemExit(f"{gate} host-native bridge input does not match the previous pass")

    brief = root / ".factory" / (
        f"grill-brief-{gate}" + (f"-{task_id}" if task_id else "") + ".md"
    )
    try:
        brief_bytes = brief.read_bytes()
    except OSError:
        brief_bytes = b""
    digest = prepared.get("task_sha256")
    if (prepared.get("brief_path") != brief.relative_to(root).as_posix()
            or not brief_bytes
            or prepared.get("brief_sha256")
            != hashlib.sha256(brief_bytes).hexdigest()
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise SystemExit(f"{gate} host-native cold-read brief identity is invalid")
    try:
        cold_artifact = _cold_artifact_from_brief(brief_bytes, digest)
    except UnicodeDecodeError:
        raise SystemExit(f"{gate} host-native cold-read artifact is not UTF-8")
    if cold_artifact is None:
        raise SystemExit(f"{gate} host-native cold-read input digest is invalid")

    result_bytes, finding_text = _regular_utf8_bytes(result_path, gate)
    findings = _cold_findings(gate, finding_text)
    return (digest, findings, cold_artifact,
            hashlib.sha256(result_bytes).hexdigest(), bridge_previous)


def _validate_bridge_findings(previous: dict | None, payload: dict, gate: str) -> None:
    if (previous is not None
            and any(payload.get(field) != previous.get(field)
                    for field in ("gaps", "contradictions"))):
        raise SystemExit(f"{gate} bridge findings must match the previous pass")


def _artifact_delta(cold: str, final: str) -> list[dict]:
    """Return exact changed line spans; equal content is intentionally omitted."""
    cold_lines = cold.splitlines(keepends=True)
    final_lines = final.splitlines(keepends=True)
    return [
        {
            "cold_start": left_start,
            "cold_end": left_end,
            "cold": "".join(cold_lines[left_start:left_end]),
            "final_start": right_start,
            "final_end": right_end,
            "final": "".join(final_lines[right_start:right_end]),
        }
        for tag, left_start, left_end, right_start, right_end
        in difflib.SequenceMatcher(a=cold_lines, b=final_lines, autojunk=False).get_opcodes()
        if tag != "equal"
    ]


def _validate_dispositions(
    payload: dict, cold: str, final: str, cold_findings: dict,
    cold_artifact: str | None, final_artifact: str,
) -> None:
    if any(payload.get(field) != cold_findings[field]
           for field in ("gaps", "contradictions")):
        raise SystemExit("grill findings must match the authenticated cold-read result")
    findings = [*cold_findings["gaps"], *cold_findings["contradictions"]]
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
    disposition_findings = {entry["finding"] for entry in dispositions}
    indexes = []
    for entry in amendments:
        if (not isinstance(entry, dict)
                or any(not _non_empty_string(entry.get(field))
                       for field in ("change", "reason", "source"))):
            raise SystemExit(
                "grill amendments require non-empty change, reason, and source"
            )
        bound = entry.get("findings")
        if (not isinstance(bound, list) or not bound
                or len(set(bound)) != len(bound)
                or any(finding not in disposition_findings for finding in bound)):
            raise SystemExit(
                "every grill amendment must bind non-duplicate exact cold finding "
                "dispositions"
            )
        if type(entry.get("delta_index")) is not int:
            raise SystemExit("every grill amendment requires an integer delta_index")
        indexes.append(entry["delta_index"])
    if cold_artifact is None:
        raise SystemExit("the authenticated cold brief does not contain its exact artifact")
    delta = _artifact_delta(
        cold_artifact, final_artifact,
    )
    if payload.get("artifact_delta", []) != delta:
        raise SystemExit("grill artifact_delta must exactly match the cold-to-final bytes")
    if cold != final and (not amendments or sorted(indexes) != list(range(len(delta)))):
        raise SystemExit(
            "the final artifact differs from the cold-read input; every delta "
            "requires exactly one finding-bound amendment"
        )
    if cold == final and (amendments or delta or indexes):
        raise SystemExit("an unchanged artifact cannot carry an amendment bridge")
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

if any(
    (arg == "--gate" and index + 1 < len(sys.argv) and sys.argv[index + 1] == "requirements")
    or arg == "--gate=requirements"
    for index, arg in enumerate(sys.argv[1:], 1)
):
    raise SystemExit(
        "requirements grill is a Lean-removed format; run forge upgrade"
    )

parser = argparse.ArgumentParser(description="Record a handover/plan grill from structured JSON")
parser.add_argument("--gate", required=True, choices=gate_names())
parser.add_argument("--input", help="Path to grill JSON. If omitted, read from stdin.")
parser.add_argument("--input-digest", dest="input_digest",
                    help="Path to the artifact this grill interrogated (roadmap input for "
                         "--gate spec/epics, the plan draft for --gate plan); its sha256 binds "
                         "the grill to THAT version. Required for epics and plan gates.")
parser.add_argument("--task", help="Task id for --gate task.")
parser.add_argument(
    "--cold-result",
    help="Regular UTF-8 file containing a host-native griller's JSON-only result.",
)
parser.add_argument(
    "--preparation-id",
    help="Host-native preparation_id printed by `forge grill run`.",
)
args = parser.parse_args()

if bool(args.cold_result) != bool(args.preparation_id):
    raise SystemExit(
        "--cold-result and --preparation-id are required together for a "
        "host-native grill result"
    )

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
_label, artifact = _gate.locate(root, args.task or "", args.input_digest or "")
from forge_cli.grill import _artifact_digest
final_digest = _artifact_digest(artifact)
if args.cold_result:
    (_cold_digest, _cold_findings, _cold_artifact,
     _result_sha256, _bridge_previous) = \
        _native_cold_launch_result(
            root, args.gate, args.task or "",
            Path(args.cold_result).expanduser(), args.preparation_id,
        )
    payload["transport"] = "host-native"
    payload["preparation_id"] = args.preparation_id
    payload["result_sha256"] = _result_sha256
else:
    (_cold_digest, _cold_findings, _cold_artifact,
     _bridge_previous, _launch_id) = _cold_launch_result(
        root, args.gate, args.task or "",
    )
    payload["launch_id"] = _launch_id
_validate_bridge_findings(_bridge_previous, payload, args.gate)
if (_bridge_previous is not None
        and final_digest == _bridge_previous.get("final_artifact_sha256")):
    raise SystemExit(
        f"{args.gate} amendment bridge cannot reuse an unchanged final artifact"
    )
_validate_dispositions(
    payload, _cold_digest, final_digest, _cold_findings,
    _cold_artifact, artifact,
)


story = active_story if _gate.story_scoped else ""
name = _gate.evidence_name(args.task or "")
dest = evidence_path(root, story, name, for_write=True)
dump_json(dest, payload)
print(f"Recorded {args.gate} grill: {payload['verdict']} "
      f"({len(payload['gaps'])} gap(s), {len(payload['contradictions'])} contradiction(s), "
      f"{len(payload['resolutions'])} resolution(s))")
