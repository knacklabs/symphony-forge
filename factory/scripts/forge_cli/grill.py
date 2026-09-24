"""forge grill run — release the read-only cold reader through the ledger.

Grills were the one Codex release the harness could not see. A delegation
records a pid and a review now does too, so a launcher killed uncatchably is
still detectable afterwards; a grill went out through the plugin directly, so
nothing on the forge side knew it had ever started. That is backwards: the
grill is the release the coordinator is told to WATCH every single round.

Releasing it through `launch_companion` — the same launcher a delegation uses —
gives it the same treatment for free: the pid and process create-time are
ledgered before the wait, the process tree is reaped on exit, the argv is
pinned, and `forge codex status` reports it dead if its launcher was killed.

It stays READ-ONLY. `write=False` means no delegation lock is taken and the
row can never satisfy `stage done`, which matches on a write launch bound to a
task contract. The cold read returns findings; recording the gate remains the
coordinator's job through the ledger-matched recorder, exactly as before.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from pathlib import Path

from factory_lib import load_json, repo_root, run_state_path
from grill_gates import get_gate

from .common import fail

def _artifact_text(base: Path, gate: str, task_id: str,
                   file_arg: str = "") -> tuple[str, str]:
    """Ask the gate table where this gate's artifact lives.

    This used to be a hand-written if-chain that knew two of the six gates;
    the other four failed with "no artifact resolver yet" and sent the
    coordinator around the ledgered launcher, which is where the pid that
    makes a dead grill detectable gets recorded. A missing lookup silently
    cost liveness detection in an unrelated subsystem.
    """
    return get_gate(gate).locate(base, task_id, file_arg)


def _grill_skill_section() -> str:
    """The grill technique, INLINED rather than named.

    Naming a skill only works if the reader's runtime resolves it. `grill-me`
    is a 164-byte STUB whose body is "Call the Skill tool with 'grilling'",
    carrying `disable-model-invocation: true` — so no model invokes it, and a
    reader told to would find a redirect it may not follow. `doctor` mirrors
    the real `grilling` into ~/.codex/skills as well, so the technique IS
    reachable there; inlining is the belt to that braces, for a machine where
    `doctor --fix` has not run.

    `_skill_text` already looks in BOTH runtimes' skill directories, which is
    what lets the Claude-side text travel to Codex inside the brief. Prefer the
    real skill, accept grill-me only when it is not merely the stub, and carry
    a written floor when neither is installed — the same reason delegate
    inlines ponytail instead of trusting a per-machine install.
    """
    from .delegate import _skill_text

    for name in ("grilling", "grill-me"):
        text = _skill_text(name)
        # The stub points at a tool the reader may not have; it is not technique.
        if text and "Call the Skill tool" not in text:
            return ("## Interrogation technique\n\n"
                    "Run the interrogation this way. The harness contract above "
                    "is the floor; this is the technique.\n\n" + text)
    return ("## Interrogation technique\n\n"
            "No grill skill is installed (`./forge doctor --fix` installs it). "
            "Interrogate to the harness contract above: one line of questioning "
            "at a time, press each answer until it is concrete and checkable, "
            "and surface every place the artifact leaves the reader to guess.")


def _lessons_section(base: Path, gate: str, task_id: str) -> str:
    """Lessons in force for the paths this task may touch.

    Task-gate only: it is the one gate whose artifact names a write scope, and
    a lesson list unrelated to the work would be noise the reader learns to
    skip.
    """
    if gate != "task" or not task_id:
        return ""
    try:
        from factory_lib import (
            load_json, protected_decomposition_state_path,
        )
        from .lessons import relevant_lessons
        tasks = load_json(protected_decomposition_state_path(base),
                          default={}).get("tasks", [])
        task = next((t for t in tasks if t.get("id") == task_id), None)
        from .stages import effective_scope
        scope = effective_scope(base, task_id, [
            str(entry) for entry in (task or {}).get("write_scope") or []])
        lessons = relevant_lessons(base, scope) if scope else []
    except Exception:
        return ""
    if not lessons:
        return ""
    lines = ["## Lessons already in force for these paths", "",
             "The plan must design AROUND these. A plan that ignores one is "
             "not merely unlucky later — it is wrong now, and saying so is "
             "part of this read.", ""]
    lines += [f"- {entry.get('lesson', '')}" for entry in lessons]
    return "\n".join(lines) + "\n"


def _contract_section(base: Path, gate: str, task_id: str) -> str:
    """The recorded contract, rendered for the cold reader -- for a task gate.

    The reader used to see only the task plan, and the plan carried its own
    hand-written copy of the criteria and the file list. The two drifted;
    five of T2's six "blockers" were that drift. Now the reader is handed the
    contract itself, with every measured scope amendment, so a path added
    with `amend-scope` is a declared path here too -- the stage measure, the
    delegate brief and this brief read one scope.
    """
    if gate != "task" or not task_id:
        return ""
    try:
        from factory_lib import (
            load_json, protected_decomposition_state_path,
            render_task_contract_block,
        )
        from .stages import scope_amendments_path
        tasks = load_json(protected_decomposition_state_path(base),
                          default={}).get("tasks", [])
        task = next((t for t in tasks if t.get("id") == task_id), None)
        if not task:
            return ""
        amendments = (load_json(scope_amendments_path(base), default={})
                      .get("tasks", {}).get(task_id))
        block = render_task_contract_block(
            task, amendments if isinstance(amendments, dict) else None)
    except Exception:
        return ""
    body = "\n".join(
        line for line in block.splitlines()
        if not line.startswith("<!--")).strip()
    return ("## The contract as recorded (authoritative over any copy in the plan)\n\n"
            + body + "\n")


def _compose_brief(base: Path, gate: str, label: str, artifact: str,
                   task_id: str = "") -> str:
    contract = base / "factory" / "prompts" / "griller.md"
    contract_text = (contract.read_text(encoding="utf-8")
                     if contract.is_file() else "")
    skill_section = _grill_skill_section()
    return "\n".join([
        f"# Cold-read grill — gate: {gate} — {label}",
        "",
        "You did NOT write what follows. Read it cold, as an adversary trying "
        "to break the handover, never as its author defending it. You are "
        "READ-ONLY: return findings, change nothing.",
        "This is the ONE independent cold read for this gate. Return the "
        "complete finding set in this pass.",
        "",
        skill_section,
        "",
        "## Harness grill contract",
        "",
        contract_text,
        "",
        _lessons_section(base, gate, task_id),
        _contract_section(base, gate, task_id),
        f"## The artifact under interrogation ({label})",
        "",
        _cold_artifact_frame(artifact),
        "",
        "## What to return",
        "",
        "Return one JSON object with exactly two arrays: gaps and "
        "contradictions. Each entry is a non-empty finding string. Put "
        "unstated assumptions and anything a reader would have to guess in "
        "gaps. Return every finding in reading order, with no prose or "
        "Markdown fence. Do not record a gate — the coordinating session "
        "records it.",
        "",
    ])


def _artifact_digest(artifact: str) -> str:
    """Digest the exact bytes the reader was shown.

    Gate-agnostic on purpose: every gate resolves its artifact to text through
    the gate table, so hashing that text works for all six without a per-gate
    digest rule to drift out of sync.
    """
    import hashlib
    return hashlib.sha256(artifact.encode("utf-8")).hexdigest()


def _cold_artifact_frame(artifact: str) -> str:
    """Frame exact artifact bytes independently of Markdown headings/newlines."""
    size = len(artifact.encode("utf-8"))
    return (
        f"<!-- forge:cold-artifact sha256={_artifact_digest(artifact)} "
        f"bytes={size} -->\n{artifact}"
    )


def _cold_artifact_from_brief(brief: bytes, digest: str) -> str | None:
    """Recover one exact digest-bound artifact frame from authenticated bytes."""
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None
    frame = re.compile(
        rb"<!-- forge:cold-artifact sha256=" + digest.encode("ascii")
        + rb" bytes=([0-9]+) -->\n"
    )
    matches = list(frame.finditer(brief))
    if len(matches) != 1:
        return None
    start = matches[0].end()
    end = start + int(matches[0].group(1))
    if end > len(brief) or not brief[end:].startswith(b"\n\n## What to return\n"):
        return None
    artifact = brief[start:end].decode("utf-8")
    return artifact if _artifact_digest(artifact) == digest else None


def _launch_rows(
    base: Path, ledger_id: str, since: str, *, story: str = "",
) -> list[dict]:
    """Ledger rows for one grill key, newest last, after `since`."""
    from .delegate import load_delegations
    return sorted(
        (row for row in load_delegations(base)
         if row.get("task") == ledger_id
         and (not story or row.get("story") == story)
         and str(row.get("at") or "") > since),
        key=lambda row: str(row.get("at") or ""),
    )


def _latest_launch_rows(
    base: Path, ledger_id: str, since: str, *, story: str = "",
) -> list[dict]:
    """Latest ledger row for each launch after `since`."""
    latest: dict[str, dict] = {}
    for row in _launch_rows(base, ledger_id, since, story=story):
        if launch_id := row.get("launch_id"):
            latest[launch_id] = row
    return list(latest.values())


def _last_pass_at(base: Path, gate: str, task_id: str) -> str:
    """When this gate last recorded a pass. Empty if never."""
    from factory_lib import evidence_path, load_json, run_state_path
    from grill_gates import get_gate
    story = load_json(run_state_path(base), default={}).get("issue_key", "")
    record = load_json(
        evidence_path(base, story if get_gate(gate).story_scoped else "",
                      get_gate(gate).evidence_name(task_id)), default={})
    return str(record.get("recorded_at") or "")


def _task_contract_sha256(base: Path, task_id: str) -> str:
    """Fingerprint the protected task contract without its plan text."""
    from factory_lib import (
        GROUNDING_CONTRACT_FIELDS, load_json,
        protected_decomposition_state_path,
    )

    tasks = load_json(protected_decomposition_state_path(base),
                      default={}).get("tasks", [])
    task = next((entry for entry in tasks if entry.get("id") == task_id), None)
    if not task:
        return ""
    contract = {field: task.get(field) for field in GROUNDING_CONTRACT_FIELDS}
    payload = json.dumps(contract, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _refuse_a_second_cold_read(base: Path, ledger_id: str, gate: str,
                               task_id: str, brief_sha256: str = "",
                               input_sha256: str = "",
                               contract_sha256: str = "") -> None:
    """Allow one cold launch per recorded pass for the current input."""
    try:
        since = _last_pass_at(base, gate, task_id)
        story = load_json(run_state_path(base), default={}).get("issue_key", "") \
            if get_gate(gate).story_scoped else ""
        from .codex_status import dead_launches
        dead = {row.get("launch_id") for row in dead_launches(base)}
        cold = [row for row in _latest_launch_rows(
            base, ledger_id, since, story=story)
                if (row.get("launch_status") == "succeeded"
                    or (row.get("launch_status") == "prepared"
                        and row.get("transport") == "host-native")
                    or (row.get("launch_status") in {"starting", "running"}
                        and row.get("launch_id") not in dead))]
        stale = []
        current = []
        for row in cold:
            if gate == "task":
                recorded = row.get("cold_contract_sha256")
                if "cold_contract_sha256" in row:
                    identities = [(recorded, contract_sha256)]
                else:
                    identities = [(row.get("brief_sha256"), brief_sha256)]
            else:
                identities = [
                    (row.get("brief_sha256"), brief_sha256),
                    (row.get("task_sha256"), input_sha256),
                ]
            comparable = [
                (recorded, expected)
                for recorded, expected in identities
                if (isinstance(recorded, str)
                    and re.fullmatch(r"[0-9a-f]{64}", recorded)
                    and expected)
            ]
            if comparable and any(recorded != expected
                                  for recorded, expected in comparable):
                stale.append(row)
            else:
                current.append(row)
        if stale and not current:
            if gate == "task":
                print("the task's contract changed since its last cold read; "
                      "a fresh read is allowed")
            else:
                print("the grill input changed since its last cold read; "
                      "a fresh read is allowed")
        cold = current
        if not cold:
            return
    except (Exception, SystemExit):
        # A ledger this cannot read must not refuse a first grill.
        return

    fail(
        f"--gate {gate} has already been cold-read since its last recorded "
        f"pass.\n\n"
        "  A second unconstrained read is how the grill stops converging: it "
        "does not know what the first read found, so it returns a DIFFERENT "
        "frontier, and the artifact you amended to close round one becomes "
        "round two's input. Stories that kept re-reading reached eleven, "
        "twenty-six and forty rounds.\n\n"
        "  One read is the whole grill. Resolve repository-answerable findings "
        "from repository facts. Escalate only an unresolved material choice, "
        "then amend the artifact once and record the pass against the amended "
        "version:\n"
        "    python3 factory/scripts/record_grill_from_json.py "
        f"--gate {gate}"
        f"{' --task ' + task_id if task_id else ''} --input <json>\n\n"
        "  The successful cold launch remains authoritative until the pass is "
        "recorded. Failed launches do not consume it."
    )


def cmd_grill_run(args: argparse.Namespace) -> None:
    from .delegate import (
        _cleanup_private_context, _windows_current_sid, launch_companion,
        delegation_exclusion, mode_run_config, secure_context_snapshot,
    )

    base = Path(args.repo).resolve() if args.repo else repo_root()
    gate = args.gate
    task_id = (args.task or "").strip()
    # Keyed apart from real task ids so a grill row can never be mistaken for
    # a task's delegation, and so concurrent grills of different gates do not
    # collide in the ledger.
    ledger_id = f"grill-{gate}" + (f"-{task_id}" if task_id else "")
    with delegation_exclusion(
            base, ledger_id, kind="grill-cold-read", namespace="grill"):
        # Hold the exact gate/task key across admission and launch so a second
        # process cannot pass the repeat-read check before the first row lands.
        contract_sha256 = (_task_contract_sha256(base, task_id)
                           if gate == "task" else "")
        label, artifact = _artifact_text(
            base, gate, task_id, (getattr(args, "file", "") or "").strip())
        text = _compose_brief(base, gate, label, artifact, task_id)
        if not args.print_only:
            _refuse_a_second_cold_read(
                base, ledger_id, gate, task_id,
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
                _artifact_digest(artifact),
                contract_sha256,
            )
        path = base / ".factory" / f"grill-brief-{gate}" \
            f"{'-' + task_id if task_id else ''}.md"
        model, effort, _bound = mode_run_config(base, "grill")
        context_text = ""
        context_metadata = None
        context_snapshot = None
        context_identity = None
        story = load_json(run_state_path(base), default={}).get("issue_key", "")
        prepared_for_preview = None
        if args.print_only:
            since = _last_pass_at(base, gate, task_id)
            prepared_for_preview = next((row for row in reversed(
                _latest_launch_rows(base, ledger_id, since, story=story))
                if row.get("transport") == "host-native"
                and row.get("launch_status") == "prepared"), None)
        if prepared_for_preview and (
                prepared_for_preview.get("brief_sha256")
                != hashlib.sha256(text.encode("utf-8")).hexdigest()
                or prepared_for_preview.get("task_sha256")
                != _artifact_digest(artifact)):
            fail("prepared cold-read input changed; the recorded preparation cannot be reused")
        native_task_name = str(
            (prepared_for_preview or {}).get("task_name")
            or f"{ledger_id}-cold-{uuid.uuid4().hex[:12]}"
        )
        if context_file := (getattr(args, "context_file", "") or "").strip():
            (context_text, context_metadata, context_snapshot,
             context_identity) = secure_context_snapshot(
                 Path(context_file), base=base,
             )
        result = None
        try:
            result = launch_companion(
                base,
                task_id=ledger_id,
                text=text,
                path=path,
                task_sha256_value=_artifact_digest(artifact),
                model=model,
                effort=effort,
                write=False,      # cold reads never write or authorize writes
                story=story,
                print_only=bool(args.print_only),
                context_text=context_text,
                context_metadata=context_metadata,
                context_snapshot=context_snapshot,
                context_snapshot_identity=context_identity,
                context_source_path=context_file,
                native_task_name=native_task_name,
                cold_contract_sha256=contract_sha256,
                emit_descriptor=False,
            )
        finally:
            if context_snapshot is not None and context_snapshot.exists():
                _cleanup_private_context(
                    context_snapshot, context_identity,
                    _windows_current_sid()
                    if __import__("os").name == "nt" else "",
                )
    preparation_id = ""
    if isinstance(result, dict) and result.get("action") == "spawn_agent":
        # `launch_companion` deliberately exposes one uniform descriptor for
        # implementation and read-only work. A grill needs a stronger handoff:
        # its result is later admitted by preparation id, so print one complete
        # griller descriptor containing every value the host and recorder need.
        story = load_json(run_state_path(base), default={}).get("issue_key", "")
        if args.print_only:
            brief_sha256 = __import__("hashlib").sha256(
                path.read_bytes()).hexdigest()
            cold_input_sha256 = _artifact_digest(artifact)
            if prepared_for_preview:
                if (prepared_for_preview.get("brief_sha256") != brief_sha256
                        or prepared_for_preview.get("task_sha256") != cold_input_sha256):
                    fail("prepared cold-read input changed; the recorded preparation cannot be reused")
                preparation_id = str(prepared_for_preview.get("launch_id") or "")
                if not preparation_id:
                    fail("prepared host-native grill has no preparation id")
                saved_context = prepared_for_preview.get("context_file")
                if context_file:
                    source = Path(context_file).expanduser()
                    if not source.is_absolute():
                        source = base / source
                    expected_context = saved_context if isinstance(saved_context, dict) else {}
                    if (expected_context.get("source_path") != str(source.absolute())
                            or expected_context.get("bytes") != context_metadata.get("bytes")
                            or expected_context.get("sha256") != context_identity[3]):
                        fail("prepared cold-read context changed; the recorded preparation cannot be reused")
                if saved_context:
                    result["context_file"] = saved_context
        else:
            rows = [row for row in _launch_rows(base, ledger_id, "", story=story)
                    if row.get("transport") == "host-native"
                    and row.get("launch_status") == "prepared"]
            if not rows:
                fail("host-native grill preparation was not recorded")
            prepared = rows[-1]
            preparation_id = str(prepared.get("launch_id") or "")
            if not preparation_id:
                fail("host-native grill preparation has no preparation id")
            brief_sha256 = prepared.get("brief_sha256")
            cold_input_sha256 = prepared.get("task_sha256")
        response_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["gaps", "contradictions"],
            "properties": {
                "gaps": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
                "contradictions": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
            },
        }
        result.update({
            "repo": str(base),
            "story": story,
            "gate": gate,
            "target_task": task_id,
            "brief_sha256": brief_sha256,
            "cold_input_sha256": cold_input_sha256,
            "response_schema": response_schema,
        })
        if preparation_id:
            result["preparation_id"] = preparation_id
        context = result.get("context_file")
        context_instruction = ""
        if isinstance(context, dict):
            context_instruction = (
                " Supplemental context: path="
                f"{context.get('source_path')} bytes={context.get('bytes')} "
                f"sha256={context.get('sha256')}. Read it only when both the "
                "byte count and SHA-256 still match."
            )
        result["message"] = (
            f"Act as the griller role. Repository: {base}. Story: {story or '(none)'}. "
            f"Gate: {gate}. Task: {task_id or '(none)'}. Read only {result['brief_path']} "
            f"whose SHA-256 is {brief_sha256}; the framed cold input "
            f"SHA-256 is {cold_input_sha256}. Change no files. Return JSON "
            "only, exactly matching response_schema, with every finding in reading "
            f"order.{context_instruction}"
            + (f" Preparation id: {preparation_id}." if preparation_id else "")
        )
        result["dispatch_guidance"] = (
            f"Use the host's spawn_agent tool with task_name "
            f"{result.get('task_name')!r} for this fresh cold read. Do not "
            "reuse an existing task with followup_task."
        )
        # A cold reader is a fresh host task.  The implementation worker may
        # use followup_task, but carrying that action on this descriptor lets
        # callers accidentally reuse the reader that is meant to be
        # independent.
        result.pop("followup_action", None)
        print(__import__("json").dumps(result, sort_keys=True))
        if args.print_only:
            return
        print(
            "NEXT: dispatch the printed descriptor with the host's spawn_agent "
            "tool. Save "
            "the agent's JSON-only response as a regular UTF-8 file. After the "
            "reader returns, resolve its findings and record the grill pass."
        )
    elif args.print_only:
        return
    native_args = (
        f" --cold-result <result.json> --preparation-id {preparation_id}"
        if preparation_id else ""
    )
    print(
        "NEXT: resolve repository-answerable findings from repository facts. "
        "Escalate only an unresolved material choice through the host's "
        "synchronous question tool, amend the artifact once, then record the pass:\n"
        "  python3 factory/scripts/record_grill_from_json.py "
        f"--gate {gate}"
        f"{' --task ' + task_id if task_id else ''} --input <json>"
        f"{native_args}\n"
        "This is the whole grill. Do not cold-read again: a second read "
        "returns a different frontier, not a shorter one.")
