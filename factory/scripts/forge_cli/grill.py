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
        artifact,
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


# Two cold reads without a recordable pass means the grill is no longer
# converging on the artifact. Round one finds the seam errors, round two
# checks the fold; every round past that on the stories measured bought only
# residue an implementer hits anyway (one ran to eleven and asked for help,
# one to twenty-six, one to forty over six hours; a task grill's third round
# returned locks, a locale and a bounded key). Past two, the human is brought
# in or the residue is folded and the work starts.
ROUNDS_BEFORE_ESCALATING = 2


def _rounds_since_last_pass(base: Path, ledger_id: str, gate: str,
                            task_id: str) -> int:
    """Cold reads released for this gate since its last recorded pass.

    From the delegation ledger, which carries a row per launch with its pid —
    a count of runs that actually happened. Distinct launch ids, because one
    launch appends several rows as it starts, runs and finishes.
    """
    try:
        from factory_lib import (
            evidence_path, load_json, run_state_path,
        )
        from grill_gates import get_gate

        story = load_json(run_state_path(base), default={}).get("issue_key", "")
        record = load_json(
            evidence_path(base, story if get_gate(gate).story_scoped else "",
                          get_gate(gate).evidence_name(task_id)), default={})
        since = str(record.get("recorded_at") or "")
        return sum(
            row.get("launch_status") != "failed"
            for row in _latest_launch_rows(base, ledger_id, since)
        )
    except (Exception, SystemExit):
        # SystemExit is NOT an Exception: load_delegations calls fail() on a
        # malformed ledger. Never let the counter refuse a grill it cannot
        # count — a missed cap costs a round, a false cap costs the story.
        return 0


def _refuse_past_the_cap(base: Path, ledger_id: str, gate: str,
                         task_id: str) -> None:
    rounds = _rounds_since_last_pass(base, ledger_id, gate, task_id)
    if rounds < ROUNDS_BEFORE_ESCALATING:
        return
    try:
        from forge_cli.signal import open_escalation
        if open_escalation(base):
            return  # the human has been brought in; carry on
    except (Exception, SystemExit):
        return

    fail(
        f"{rounds} cold reads on --gate {gate} without a recorded pass.\n\n"
        "  This is no longer a grilling problem. Past a handful of rounds the "
        "reader has stopped converging on the artifact and started circling "
        "something nobody has decided, and another round cannot settle that — "
        "stories that kept going reached eleven, twenty-six and forty rounds, "
        "the last costing six hours.\n\n"
        "  Resolve repository-answerable findings from repository facts. If "
        "an unresolved material choice remains, take only that choice to the "
        "human, say what you recommend, and record what they decide:\n"
        "    ./forge signal escalate --missing-decision \"<what nobody has "
        "decided>\" --checked \"contract,plan,constitution,decisions,lessons\"\n"
        "  Grilling continues after that. Recording a pass resets the count."
    )


def _artifact_digest(artifact: str) -> str:
    """Digest the exact bytes the reader was shown.

    Gate-agnostic on purpose: every gate resolves its artifact to text through
    the gate table, so hashing that text works for all six without a per-gate
    digest rule to drift out of sync.
    """
    import hashlib
    return hashlib.sha256(artifact.encode("utf-8")).hexdigest()


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


def _refuse_a_second_cold_read(base: Path, ledger_id: str, gate: str,
                               task_id: str, reread: str) -> None:
    """One unconstrained cold read per recorded pass.

    The second read is the one that diverges: it has no memory of what the
    first found, so it returns a different frontier and the grill never ends.
    Amending the artifact is exactly when a second read feels necessary and
    exactly when it is wrong: the amendment answers the findings, so a reader
    that never saw them will not check it, it will look for new ones.

    This is not a wall. The coordinator resolves repository-answerable
    findings, escalates only an unresolved material choice, amends the artifact
    once, and records the pass against the AMENDED version -- one read, then
    save. A reread stays available as a CHOICE with a reason, for when
    the answers changed the artifact's SHAPE rather than its details; the
    reason is ledgered, and the five-read cap still backstops it.
    """
    if reread:
        return
    try:
        since = _last_pass_at(base, gate, task_id)
        story = load_json(run_state_path(base), default={}).get("issue_key", "") \
            if get_gate(gate).story_scoped else ""
        cold = [row for row in _latest_launch_rows(
            base, ledger_id, since, story=story)
                if row.get("launch_status") != "failed"]
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
        "  If their answers changed the artifact's SHAPE rather than its "
        "details, say so and read again:\n"
        f"    ./forge grill run --gate {gate}"
        f"{' --task ' + task_id if task_id else ''} "
        "--reread \"<what changed shape>\""
    )


def cmd_grill_run(args: argparse.Namespace) -> None:
    from .delegate import launch_companion, mode_run_config

    base = Path(args.repo).resolve() if args.repo else repo_root()
    gate = args.gate
    task_id = (args.task or "").strip()
    # Keyed apart from real task ids so a grill row can never be mistaken for
    # a task's delegation, and so concurrent grills of different gates do not
    # collide in the ledger.
    ledger_id = f"grill-{gate}" + (f"-{task_id}" if task_id else "")
    # Before composing anything: a capped run should not pay for a brief, and
    # a missing artifact should not report itself ahead of the real problem.
    _refuse_past_the_cap(base, ledger_id, gate, task_id)
    # One unconstrained read per recorded pass. Amending the artifact is when
    # a second read feels necessary and exactly when it diverges.
    _refuse_a_second_cold_read(base, ledger_id, gate, task_id,
                               (getattr(args, "reread", "") or "").strip())

    label, artifact = _artifact_text(
        base, gate, task_id, (getattr(args, "file", "") or "").strip())
    text = _compose_brief(base, gate, label, artifact, task_id)
    path = base / ".factory" / f"grill-brief-{gate}" \
        f"{'-' + task_id if task_id else ''}.md"
    model, effort, _bound = mode_run_config(base, "grill")

    launch_companion(
        base,
        task_id=ledger_id,
        text=text,
        path=path,
        task_sha256_value=_artifact_digest(artifact),
        model=model,
        effort=effort,
        write=False,          # a cold read never writes, and never authorises
        story=load_json(run_state_path(base), default={}).get("issue_key", ""),
        print_only=bool(args.print_only),
    )
    if args.print_only:
        return
    print(
        "NEXT: resolve repository-answerable findings from repository facts. "
        "Escalate only an unresolved material choice through the host's "
        "synchronous question tool, amend the artifact once, then record the pass:\n"
        "  python3 factory/scripts/record_grill_from_json.py "
        f"--gate {gate}"
        f"{' --task ' + task_id if task_id else ''} --input <json>\n"
        "This is the whole grill. Do not cold-read again: a second read "
        "returns a different frontier, not a shorter one.")
