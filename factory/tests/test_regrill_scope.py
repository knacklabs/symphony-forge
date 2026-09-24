"""What actually forces a re-grill, and what must never.

Its own module — test_gates.py is one 690-test file where every added branch
collides with every other.

Measured cost of the old rule on one story: eighteen grill rounds. The grill
bound the WHOLE task contract plus the whole product tree, so resolving a grill
finding — which is done by editing the contract — invalidated the grill that
found it, and committing the implementation invalidated it again. Neither loop
can converge. Raising a review-budget ceiling from 38 files to 58, pure
bookkeeping, cost a full adversarial round.
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import json
import sys
from pathlib import Path

import pytest

from test_gates import HARNESS, git, load_factory_lib, repo, run  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from factory_lib import (  # noqa: E402
    GROUNDING_CONTRACT_FIELDS, IN_STAGE_GROUNDING_FIELDS,
    MEASUREMENT_CONTRACT_FIELDS,
)


TASK = {
    "id": "T1",
    "title": "core slice",
    "epic_id": "E1",
    "objective": "Build the slice.",
    "acceptance_criteria": ["the slice runs green"],
    "plan_contracts": [{"id": "C1", "statement": "the slice runs green",
                        "source": "plans/active/TEST-1-test-plan.md#ac"}],
    "write_scope": ["src/"],
    "required_tests": [{"id": "t1", "path": "a.spec.ts", "command": "run"}],
    "verify_commands": ["npm test"],
    "user_facing": False,
    "review_budget": {"max_changed_files": 38, "max_changed_lines": 2000,
                      "reason": "foundation"},
    "reviewer_focus": "watch the boundaries",
}


def _seed(repo: Path):
    """A minimal repo where grounding_digest can be derived."""
    lib = load_factory_lib(repo)
    control = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "forge"
    control.mkdir(parents=True, exist_ok=True)
    plan = repo / "plans" / "active" / "TEST-1-test-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# Plan\n\nThe approved story plan.\n", encoding="utf-8")
    lib.dump_json(control / "run.json",
                  {"issue_key": "TEST-1", "plan_file": "plans/active/TEST-1-test-plan.md"})
    lib.dump_json(control / "decomposition.json",
                  {"plan_file": "plans/active/TEST-1-test-plan.md", "tasks": [TASK]})
    return lib


def _seed_pre_stage_grill(repo: Path, task: dict) -> str:
    """Reproduce the opaque pre-Lean grill carried by the dogfood stage."""
    lib = load_factory_lib(repo)
    stage = lib.task_stage_record(repo, task["id"])
    path = lib.evidence_path(
        repo, "ENG-1", f"grills/tasks/{task['id']}.json", for_write=True,
    )
    grill = lib.load_json(path, default={})
    grill["input_sha256"] = lib.grounding_digest(
        repo, task, treeish=stage["base_sha"], in_stage=False,
    )
    lib.dump_json(path, grill)
    return grill["input_sha256"]


def _fake_companion_env(tmp_path: Path) -> dict[str, str]:
    from test_gates import _fake_psutil_module, fake_companion_env  # noqa: E402

    return {
        **fake_companion_env(tmp_path),
        "PYTHONPATH": str(_fake_psutil_module(tmp_path)),
    }


def _start_stage_with_contract_frame(
        repo: Path, tmp_path: Path, task: dict, monkeypatch,
        *, launch: bool = True) -> None:
    """Keep these regressions on the current plan-plus-contract task frame."""
    import test_gates

    seed = test_gates._seed_cold_launch

    def seed_current(repo, gate, digest, task_id="", *, findings=None,
                     artifact_text=None, artifact_file="",
                     include_artifact_frame=True):
        if gate == "task":
            from forge_cli.grill import _artifact_digest, _review_artifact_text
            from grill_gates import get_gate

            _label, plan = get_gate(gate).locate(repo, task_id, "")
            artifact_text = _review_artifact_text(
                repo, gate, task_id, plan,
            )
            digest = _artifact_digest(artifact_text)
        return seed(
            repo, gate, digest, task_id, findings=findings,
            artifact_text=artifact_text,
            artifact_file=artifact_file,
            include_artifact_frame=include_artifact_frame,
        )

    monkeypatch.setattr(test_gates, "_seed_cold_launch", seed_current)
    test_gates.start_stage(repo, tmp_path, task, launch=launch)


def test_task_cold_read_requires_reason_for_second_read(
        repo: Path, tmp_path: Path, capsys, monkeypatch):
    from types import SimpleNamespace

    from test_gates import DECOMP, STAGE_TASK, run
    from forge_cli import delegate
    from forge_cli.delegate import load_delegations
    from forge_cli.grill import cmd_grill_run
    from factory_lib import evidence_path, load_json, run_state_path

    _start_stage_with_contract_frame(repo, tmp_path, STAGE_TASK, monkeypatch)

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    monkeypatch.setattr(
        delegate, "now_iso", lambda: "2099-01-01T00:00:00+00:00",
    )
    args = SimpleNamespace(
        repo=str(repo), gate="task", task="T1", print_only=False,
        file="", context_file="", fresh=False, reason="",
    )
    cmd_grill_run(args)
    assert "host-native spawn_agent" in capsys.readouterr().out

    story = load_json(run_state_path(repo), default={}).get("issue_key", "")
    task_plan = evidence_path(
        repo, story, "task-plans/T1.md", for_write=True,
    )
    task_plan.write_text(
        task_plan.read_text(encoding="utf-8") + "\nPlan-only amendment.\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        cmd_grill_run(args)
    refusal = capsys.readouterr().out
    assert "already been cold-read" in refusal
    assert "--fresh --reason" in refusal

    amended = {
        **STAGE_TASK,
        "acceptance_criteria": ["the slice runs green", "and audits"],
        "plan_contracts": STAGE_TASK["plan_contracts"] + [{
            "id": "C2", "statement": "and audits",
            "source": "plans/active/TEST-1-test-plan.md#acceptance-criteria",
        }],
    }
    code, out = run(
        repo, "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [amended]}),
    )
    assert code == 0, out

    with pytest.raises(SystemExit):
        cmd_grill_run(args)
    refusal = capsys.readouterr().out
    assert "already been cold-read" in refusal
    assert "contract changed" not in refusal

    args.fresh = True
    args.reason = "Owner approved a new cold read after contract review."
    cmd_grill_run(args)
    output = capsys.readouterr().out
    assert "host-native spawn_agent" in output
    launches = [
        row for row in load_delegations(repo)
        if row.get("task") == "grill-task-T1"
        and row.get("launch_status") == "prepared"
    ]
    assert len(launches) == 2
    assert launches[0]["brief_sha256"] != launches[1]["brief_sha256"]
    assert launches[1]["reason"] == args.reason

    args.fresh = False
    args.reason = ""
    with pytest.raises(SystemExit):
        cmd_grill_run(args)
    blocked = capsys.readouterr().out
    assert "already been cold-read" in blocked
    assert "contract changed" not in blocked


@pytest.mark.parametrize("change", ["contract", "plan", "both"])
def test_task_contract_change_records_against_existing_read(
        repo: Path, tmp_path: Path, monkeypatch, change: str):
    from types import SimpleNamespace

    from test_gates import (
        DECOMP, STAGE_TASK, run, story_state, task_grill_payload,
    )
    from forge_cli import delegate
    from forge_cli.delegate import load_delegations
    from forge_cli.grill import (
        _artifact_digest, _cold_artifact_from_brief, _review_artifact_text,
        cmd_grill_run,
    )
    from grill_gates import get_gate

    _start_stage_with_contract_frame(repo, tmp_path, STAGE_TASK, monkeypatch)
    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    monkeypatch.setattr(
        delegate, "now_iso", lambda: "2099-01-01T00:00:00+00:00",
    )
    cmd_grill_run(SimpleNamespace(
        repo=str(repo), gate="task", task="T1", print_only=False,
        file="", context_file="", fresh=False, reason="",
    ))

    launch = next(row for row in load_delegations(repo)
                  if row.get("task") == "grill-task-T1"
                  and row.get("launch_status") == "prepared")
    brief = repo / launch["brief_path"]
    cold_artifact = _cold_artifact_from_brief(
        brief.read_bytes(), launch["task_sha256"],
    )
    assert cold_artifact is not None and "The contract as recorded" in cold_artifact

    contract_changed = change in ("contract", "both")
    plan_changed = change in ("plan", "both")
    amended = STAGE_TASK
    if contract_changed:
        amended = {
            **STAGE_TASK,
            "acceptance_criteria": ["the slice runs green", "and audits"],
            "plan_contracts": STAGE_TASK["plan_contracts"] + [{
                "id": "C2", "statement": "and audits",
                "source": "plans/active/TEST-1-test-plan.md#acceptance-criteria",
            }],
        }
        code, out = run(
            repo, "record_decomposition_from_json.py",
            stdin=json.dumps({**DECOMP, "tasks": [amended]}),
        )
        assert code == 0, out
    task_plan = story_state(repo) / "task-plans" / "T1.md"
    if plan_changed:
        task_plan.write_text(
            task_plan.read_text(encoding="utf-8") + "\nApproved audit amendment.\n",
            encoding="utf-8",
        )
    _, current_plan = get_gate("task").locate(repo, "T1", "")
    final_artifact = _review_artifact_text(repo, "task", "T1", current_plan)
    cold_lines = cold_artifact.splitlines(keepends=True)
    final_lines = final_artifact.splitlines(keepends=True)
    delta = [
        {
            "cold_start": left_start, "cold_end": left_end,
            "cold": "".join(cold_lines[left_start:left_end]),
            "final_start": right_start, "final_end": right_end,
            "final": "".join(final_lines[right_start:right_end]),
        }
        for tag, left_start, left_end, right_start, right_end
        in difflib.SequenceMatcher(
            a=cold_lines, b=final_lines, autojunk=False,
        ).get_opcodes()
        if tag != "equal"
    ]
    decision = (
        "Owner decision: add the audit acceptance criterion."
        if contract_changed else "Owner decision: add the approved plan note."
    )
    payload = {
        **task_grill_payload(amended),
        "finding_dispositions": [{
            "finding": decision, "resolution": "Applied as requested.",
            "source": decision,
        }],
        "amendments": [{
            "delta_index": index, "findings": [decision],
            "change": "Applied the approved task contract or plan text edit.",
            "reason": "Owner decision recorded before the edit.",
            "source": decision,
        } for index in range(len(delta))],
        "artifact_delta": delta,
    }
    cold_result = tmp_path / "cold-result.json"
    cold_result.write_text(
        json.dumps({"gaps": [], "contradictions": []}), encoding="utf-8",
    )
    code, out = run(
        repo, "record_grill_from_json.py", "--gate", "task", "--task", "T1",
        "--cold-result", str(cold_result), "--preparation-id", launch["launch_id"],
        stdin=json.dumps(payload),
    )
    assert code == 0, out
    recorded = json.loads(
        (story_state(repo) / "grills" / "tasks" / "T1.json").read_text(),
    )
    assert recorded["preparation_id"] == launch["launch_id"]
    assert recorded["cold_input_sha256"] == _artifact_digest(cold_artifact)
    assert recorded["final_artifact_sha256"] == _artifact_digest(final_artifact)
    assert recorded["artifact_delta"] == delta


def test_latest_of_three_successful_cold_reads_is_selected(
        repo: Path, monkeypatch):
    from forge_cli import delegate, grill

    _seed(repo)
    rows = [
        {
            "task": "grill-task-T1", "story": "TEST-1",
            "launch_id": f"launch-{index}", "at": f"2099-01-01T00:00:0{index}Z",
            "launch_status": "prepared", "transport": "host-native",
        }
        for index in range(1, 4)
    ]
    monkeypatch.setattr(delegate, "load_delegations", lambda _base: rows)

    selected = grill._latest_cold_launch_rows(
        repo, "grill-task-T1", "task",
    )

    assert len(selected) == 1
    assert selected[0]["launch_id"] == "launch-3"


# --------------------------------------------------------------- bookkeeping
@pytest.mark.parametrize("field,value", [
    ("review_budget", {"max_changed_files": 999, "max_changed_lines": 9,
                       "reason": "raised after measuring"}),
    ("reviewer_focus", "a completely rewritten focus"),
    ("title", "renamed"),
    ("epic_id", "E9"),
])
def test_bookkeeping_never_forces_a_regrill(repo: Path, field, value):
    """The signal that interrupted the human to raise a file count.

    A review budget is a stop on runaway scope, not a statement about what the
    task must do. Binding the grill to it meant the human's own instruction —
    "raise it and do not stop again" — was itself a stop.
    """
    lib = _seed(repo)
    before = lib.grounding_digest(repo, TASK, in_stage=True)
    after = lib.grounding_digest(repo, {**TASK, field: value}, in_stage=True)
    assert before == after, f"changing {field} forced a re-grill"


# --------------------------------------------------------------- substantive
@pytest.mark.parametrize("field,value", [
    ("objective", "Build something else entirely."),
    ("acceptance_criteria", ["a different bar for done"]),
    ("plan_contracts", [{"id": "C9", "statement": "different", "source": "x"}]),
    ("write_scope", ["src/", "apps/api/src/NEW.ts"]),
    ("required_tests", [{"id": "t2", "path": "b.spec.ts", "command": "run"}]),
    ("verify_commands", ["npm run other"]),
    ("user_facing", True),
])
def test_changing_what_the_work_is_forces_a_regrill(repo: Path, field, value):
    # BEFORE the stage opens every substantive field is what was authorised,
    # and the grill that read the old version does not speak to the new one.
    lib = _seed(repo)
    before = lib.grounding_digest(repo, TASK, in_stage=False)
    after = lib.grounding_digest(repo, {**TASK, field: value}, in_stage=False)
    assert before != after, f"changing {field} did NOT force a re-grill"
    # ONCE the stage is open, scope/tests/verify are MEASUREMENT fields:
    # `stage done` measures the diff and runs the tests, so a cold read of
    # them adds nothing and re-grilling on them cost T2 a 21-minute round, a
    # plan rewrite and a human re-approval for zero code change.
    before = lib.grounding_digest(repo, TASK, in_stage=True)
    after = lib.grounding_digest(repo, {**TASK, field: value}, in_stage=True)
    if field in MEASUREMENT_CONTRACT_FIELDS:
        assert before == after, f"changing {field} in-stage re-grilled"
    else:
        assert before != after, f"changing {field} in-stage did NOT re-grill"


def test_every_substantive_field_is_actually_bound(repo: Path):
    # A field named in the tuple but absent from the payload would be silently
    # unbound — the shape of the original defect.
    lib = _seed(repo)
    base = lib.grounding_digest(repo, TASK, in_stage=False)
    for field in GROUNDING_CONTRACT_FIELDS:
        mutated = {**TASK, field: ["mutated-sentinel"]}
        assert lib.grounding_digest(repo, mutated, in_stage=False) != base, field
    base = lib.grounding_digest(repo, TASK, in_stage=True)
    for field in IN_STAGE_GROUNDING_FIELDS:
        mutated = {**TASK, field: ["mutated-sentinel"]}
        assert lib.grounding_digest(repo, mutated, in_stage=True) != base, field


def test_a_grill_recorded_under_the_old_in_stage_rule_still_matches(repo: Path):
    """Migration without a launch: an in-stage grill fingerprinted with all
    seven fields is accepted while those fields have not moved -- it says
    exactly what a new record would say."""
    lib = _seed(repo)
    legacy = lib.grounding_digest(repo, TASK, in_stage=True,
                                  fields=GROUNDING_CONTRACT_FIELDS)
    assert legacy != lib.grounding_digest(repo, TASK, in_stage=True)
    assert lib.grounding_matches(repo, TASK, legacy, in_stage=True)
    # Not a hole: a legacy record for a changed criterion is still stale.
    moved = {**TASK, "acceptance_criteria": ["something else"]}
    assert not lib.grounding_matches(repo, moved, legacy, in_stage=True)


# -------------------------------------------------------------- product tree
def test_the_work_does_not_invalidate_its_own_authorisation(repo: Path):
    """The circularity, stated as a test.

    delegate refuses without a fresh grill; committing the implementation moved
    the tree; the tree was part of the grill's binding. So the only way to fix
    delivered code was blocked by having delivered it.
    """
    lib = _seed(repo)
    before = lib.grounding_digest(repo, TASK, in_stage=True)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "implementation.ts").write_text(
        "export const built = true;\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit",
        "-m", "the implementation lands")
    assert lib.grounding_digest(repo, TASK, in_stage=True) == before, (
        "committing the implementation still stales the grill")


def test_before_the_stage_opens_the_tree_still_counts(repo: Path):
    # The other half. A plan is grilled against a codebase; if that codebase
    # moves BEFORE the work is authorised, the grill read something else.
    lib = _seed(repo)
    before = lib.grounding_digest(repo, TASK, in_stage=False)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "elsewhere.ts").write_text("export const x = 1;\n",
                                               encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit",
        "-m", "unrelated work lands first")
    assert lib.grounding_digest(repo, TASK, in_stage=False) != before


def test_in_stage_is_decided_by_the_stage_not_the_caller(repo: Path):
    # Four call sites asked this question three different ways; the read-only
    # one never asked it at all, so the board and `forge next` reported STALE
    # for delivered work and kept routing it back to the grill.
    lib = _seed(repo)
    control = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "forge"
    lib.dump_json(control / "stages.json", {"stages": [
        {"id": "T1", "status": "pending"}]})
    assert lib.task_in_stage(repo, "T1") is False
    for status in ("active", "done"):
        lib.dump_json(control / "stages.json", {"stages": [
            {"id": "T1", "status": status}]})
        assert lib.task_in_stage(repo, "T1") is True, status


# ------------------------------------------------------------- compatibility
def test_a_grill_recorded_by_older_tooling_still_verifies(repo: Path):
    """An unchanged in-flight task keeps the exact Decision 0066 bridge."""
    lib = _seed(repo)
    legacy = lib.legacy_grounding_digest(repo, TASK)
    assert lib.grounding_matches(repo, TASK, legacy, in_stage=True)
    assert not lib.grounding_matches(repo, TASK, "not-a-digest", in_stage=True)
    moved = {**TASK, "write_scope": ["src/", "src/extra.ts"]}
    assert not lib.grounding_matches(repo, moved, legacy, in_stage=True)


def test_a_missing_digest_is_never_treated_as_a_match(repo: Path):
    lib = _seed(repo)
    for empty in ("", None):
        assert not lib.grounding_matches(repo, TASK, empty, in_stage=True)


def test_opening_the_stage_does_not_stale_the_grill_that_authorised_it(repo: Path):
    """The transition, which is the normal order of events.

    grill -> approve -> stage start. The grill is stamped while the stage is
    still pending, so the product tree IS part of its binding. If the checker
    simply stopped counting the tree once the stage opened, the act of opening
    the stage would stale every grill — the opposite of the bug being fixed,
    at the worst possible moment. The stage pins that same tree as its
    baseline, so measuring against the baseline reproduces what was recorded.
    """
    lib = _seed(repo)
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit",
        "-m", "the tree the grill was recorded against")
    head = git(repo, "rev-parse", "HEAD")

    # Recorded BEFORE the stage opened: tree included.
    recorded = lib.grounding_digest(repo, TASK, in_stage=False)

    control = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "forge"
    control.mkdir(parents=True, exist_ok=True)
    lib.dump_json(control / "stages.json", {"stages": [
        {"id": "T1", "status": "active", "base_sha": head}]})

    assert lib.grounding_matches(repo, TASK, recorded, in_stage=True), (
        "opening the stage staled the grill that authorised it")

    # And the gate still bites on a real contract change afterwards.
    moved = {**TASK, "write_scope": ["src/", "src/unplanned.ts"]}
    assert not lib.grounding_matches(repo, moved, recorded, in_stage=True)


def test_a_second_delegate_after_committing_needs_no_new_grill(
        repo: Path, tmp_path, monkeypatch):
    """The loop, replayed end to end with the real commands.

    From the story's own handover: "committing the code stales the gate that
    authorises fixing the code. Every fix cycle therefore costs a grill round."
    Twenty rounds. This is that cycle: grill, approve, open the stage, deliver
    the implementation, then go back for the fix round — which is where the
    harness used to demand a fresh grill before it would let anyone write.
    """
    from test_gates import DECOMP, STAGE_TASK  # noqa: E402

    (repo / "src").mkdir()
    (repo / "src" / "existing.ts").write_text(
        "export const existing = true;\n", encoding="utf-8")
    git(repo, "add", "src/existing.ts")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit",
        "-m", "seed immutable source ownership")
    _start_stage_with_contract_frame(repo, tmp_path, STAGE_TASK, monkeypatch)
    original_grill = _seed_pre_stage_grill(repo, STAGE_TASK)

    # A worker signal reveals one more mechanically measured path. The
    # recorder proves the original grill + launch before carrying the unchanged
    # semantic authorization across the wider measurement contract.
    widened = {**STAGE_TASK, "write_scope": ["src/", "billing/"]}
    code, out = run(
        repo,
        "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [widened]}),
    )
    assert code == 0, out
    lib = load_factory_lib(repo)
    grill = lib.load_json(
        lib.evidence_path(repo, "ENG-1", "grills/tasks/T1.json"), default={},
    )
    assert grill["input_sha256"] == original_grill
    # An identical re-record rebuilds the stage skeleton but must not drop the
    # receipt that carries authorization across the measurement amendment.
    code, out = run(
        repo,
        "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [widened]}),
    )
    assert code == 0, out
    assert len(lib.task_stage_record(repo, "T1")["measurement_continuity"]) == 1

    # Codex delivers, and the delivery is committed — the step that used to
    # stale the gate.
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "delivered.ts").write_text(
        "export const implementation = true;\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit",
        "-m", "WF-1 T1: the implementation lands")

    # The fix round. No re-grill or re-approval; a real narrowed launch proves
    # the retry receives only its proper subset of the now-approved scope.
    code, out = run(repo, "forge.py", "delegate", "T1", "--scope", "src/",
                    env=_fake_companion_env(tmp_path))
    assert code == 0, (
        "delegate still demands a fresh grill after the implementation was "
        f"committed — the loop is intact:\n{out}")
    from forge_cli.delegate import load_delegations  # noqa: E402
    succeeded = [
        row for row in load_delegations(repo)
        if row.get("task") == "T1" and row.get("launch_status") == "succeeded"
    ]
    assert len({row["launch_id"] for row in succeeded}) == 2
    assert succeeded[-1]["write_scope"] == ["src/"]

    # Stage close rewrites task_sha256 to the final measured contract. The same
    # immutable receipt must keep completed-task readiness grounded.
    from forge_cli.stages import load_stages, write_stages  # noqa: E402
    stages = load_stages(repo)
    stages["stages"][0]["status"] = "done"
    stages["stages"][0]["task_sha256"] = lib.task_digest(widened)
    write_stages(repo, stages)
    assert lib.require_ready_task(
        repo, "T1", allow_completed=True, require_approval=False,
    )["id"] == "T1"

    # The receipt is authority, so a forged field must close the gate again.
    stages = load_stages(repo)
    stages["stages"][0]["measurement_continuity"][0][
        "semantic_grounding_sha256"
    ] = "0" * 64
    write_stages(repo, stages)
    with pytest.raises(SystemExit, match="stage-baseline"):
        lib.require_ready_task(
            repo, "T1", allow_completed=True, require_approval=False,
        )


def test_native_preparation_rebinds_after_brief_changes(
        repo: Path, tmp_path, monkeypatch, capsys):
    from test_gates import STAGE_TASK  # noqa: E402
    from forge_cli.delegate import brief_path, launch_companion  # noqa: E402
    from forge_cli.stages import _require_successful_launch  # noqa: E402

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    # This fixture is not a trusted Codex checkout, and the readiness probe
    # shells out to the real `codex` CLI -- absent in CI, and bound to the
    # harness rather than this temp repo locally. The gate has its own
    # regression coverage in test_native_setup.py.
    from forge_cli import doctor
    monkeypatch.setattr(
        doctor, "codex_hook_readiness", lambda _base: (True, "fixture-ready"),
    )
    _start_stage_with_contract_frame(
        repo, tmp_path, STAGE_TASK, monkeypatch, launch=False,
    )
    lib = load_factory_lib(repo)
    stage = lib.task_stage_record(repo, "T1")
    path = brief_path(repo, "T1")
    common = dict(
        task_id="T1", path=path,
        task_sha256_value=lib.task_digest(STAGE_TASK), model="ignored",
        effort="ignored", write=True, story="ENG-1",
        stage_started_at=stage["started_at"], task_metadata=STAGE_TASK,
    )
    launch_companion(
        repo, text="# current native brief\n",
        write_scope=STAGE_TASK["write_scope"], **common,
    )
    assert _require_successful_launch(repo, "T1", stage, STAGE_TASK) == ""

    # Native preparation is a current contract binding, not a process receipt:
    # changing the canonical brief invalidates it until Forge prepares again.
    path.write_text(path.read_text(encoding="utf-8") + "stale\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        _require_successful_launch(repo, "T1", stage, STAGE_TASK)
    assert "host-native preparation" in capsys.readouterr().out

    launch_companion(
        repo, text="# refreshed native brief\n",
        write_scope=STAGE_TASK["write_scope"], **common,
    )
    assert _require_successful_launch(repo, "T1", stage, STAGE_TASK) == ""
    latest = json.loads(
        (Path(git(repo, "rev-parse", "--absolute-git-dir")) /
         "forge" / "delegations.jsonl").read_text().splitlines()[-1]
    )
    assert latest["transport"] == "host-native"
    assert latest["launch_status"] == "prepared"
    assert latest["argv"] == []
    for forbidden in ("pid", "process_token", "session_id", "output_path"):
        assert forbidden not in latest


def test_host_native_preparation_anchors_measurement_amendment(
        repo: Path, tmp_path, monkeypatch, capsys):
    from test_gates import DECOMP, STAGE_TASK  # noqa: E402
    from forge_cli.delegate import brief_path, launch_companion, load_delegations  # noqa: E402

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    from forge_cli import doctor
    monkeypatch.setattr(
        doctor, "codex_hook_readiness", lambda _base: (True, "fixture-ready"),
    )
    _start_stage_with_contract_frame(
        repo, tmp_path, STAGE_TASK, monkeypatch, launch=False,
    )
    lib = load_factory_lib(repo)
    stage = lib.task_stage_record(repo, "T1")
    launch_companion(
        repo, task_id="T1", path=brief_path(repo, "T1"),
        task_sha256_value=lib.task_digest(STAGE_TASK),
        model="ignored", effort="ignored", write=True,
        write_scope=STAGE_TASK["write_scope"], story="ENG-1",
        stage_started_at=stage["started_at"], task_metadata=STAGE_TASK,
        text="# current native brief\n",
    )
    prepared = next(
        row for row in reversed(load_delegations(repo))
        if row.get("task") == "T1"
    )
    widened = {**STAGE_TASK, "write_scope": ["src/", "billing/"]}

    code, out = run(
        repo, "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [widened]}),
        env={"FORGE_COORDINATOR": "codex"},
    )

    assert code == 0, out
    assert lib.task_stage_record(repo, "T1")["measurement_continuity"][0][
        "launch_id"
    ] == prepared["launch_id"]
    grill = lib.load_json(lib.evidence_path(
        repo, "ENG-1", "grills/tasks/T1.json",
    ), default={})
    assert lib._measurement_continuity_matches(repo, widened, grill)

    # A later preparation must not replace the one named by the receipt.
    launch_companion(
        repo, task_id="T1", path=brief_path(repo, "T1"),
        task_sha256_value=lib.task_digest(widened),
        model="ignored", effort="ignored", write=True,
        write_scope=widened["write_scope"], story="ENG-1",
        stage_started_at=stage["started_at"], task_metadata=widened,
        text="# later native brief\n",
    )
    assert lib._measurement_continuity_matches(repo, widened, grill)


def test_measurement_amendment_without_a_bound_launch_writes_nothing(
        repo: Path, tmp_path, monkeypatch):
    from test_gates import DECOMP, STAGE_TASK  # noqa: E402

    _start_stage_with_contract_frame(
        repo, tmp_path, STAGE_TASK, monkeypatch, launch=False,
    )
    _seed_pre_stage_grill(repo, STAGE_TASK)
    lib = load_factory_lib(repo)
    protected = lib.protected_decomposition_state_path(repo)
    tracked = lib.decomposition_state_path(repo)
    before = (protected.read_bytes(), tracked.read_bytes())
    widened = {**STAGE_TASK, "write_scope": ["src/", "billing/"]}

    code, out = run(
        repo,
        "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [widened]}),
    )

    assert code != 0 and "exact successful write launch" in out, out
    assert (protected.read_bytes(), tracked.read_bytes()) == before


@pytest.mark.parametrize("corruption", ["missing", "invalid-bytes"])
def test_measurement_continuity_never_replaces_native_task_approval_authority(
        repo: Path, tmp_path: Path, corruption: str, monkeypatch):
    from test_gates import DECOMP, STAGE_TASK  # noqa: E402

    _start_stage_with_contract_frame(repo, tmp_path, STAGE_TASK, monkeypatch)
    _seed_pre_stage_grill(repo, STAGE_TASK)
    widened = {**STAGE_TASK, "write_scope": ["src/", "billing/"]}
    code, out = run(
        repo, "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [widened]}),
    )
    assert code == 0, out
    lib = load_factory_lib(repo)
    grill_path = lib.evidence_path(
        repo, "ENG-1", "grills/tasks/T1.json",
    )
    grill = lib.load_json(grill_path, default={})
    assert lib._measurement_continuity_matches(repo, widened, grill)
    replays = [
        path for path in grill_path.parents[2].glob("approval-events/*.json")
        if json.loads(path.read_text()).get("task") == "T1"
    ]
    assert replays
    if corruption == "missing":
        for replay in replays:
            replay.unlink()
    else:
        for replay in replays:
            replay.write_bytes(b"\xff")

    digest = lib.plan_digest_without_assumptions(
        lib.evidence_path(repo, "ENG-1", "task-plans/T1.md"),
    )
    assert not lib._task_plan_approval_matches_digest(
        repo, widened, grill, digest,
    )
    with pytest.raises(SystemExit, match="approval"):
        lib.require_ready_task(repo, "T1")


def test_story_plan_reapproval_rebinds_an_active_task_without_restarting_it(
        repo: Path, tmp_path, monkeypatch):
    from test_gates import (  # noqa: E402
        DECOMP, STAGE_TASK, native_claude_approval,
        post_hook, run_state, story_state,
    )

    _start_stage_with_contract_frame(repo, tmp_path, STAGE_TASK, monkeypatch)
    _seed_pre_stage_grill(repo, STAGE_TASK)
    widened = {**STAGE_TASK, "write_scope": ["src/", "billing/"]}
    code, out = run(
        repo, "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [widened]}),
    )
    assert code == 0, out
    lib = load_factory_lib(repo)
    stage_before = lib.task_stage_record(repo, "T1")
    receipts_before = copy.deepcopy(stage_before["measurement_continuity"])
    stable_before = {
        field: copy.deepcopy(stage_before.get(field))
        for field in ("started_at", "base_sha", "dirty_at_start", "task_sha256")
    }
    grill_path = story_state(repo) / "grills" / "tasks" / "T1.json"
    grill_before = grill_path.read_bytes()
    task_plan = story_state(repo) / "task-plans" / "T1.md"
    task_plan_before = task_plan.read_bytes()
    approval_events = story_state(repo) / "approval-events"
    task_approval_events_before = sorted(
        path.read_bytes() for path in approval_events.glob("*.json")
        if json.loads(path.read_text()).get("task") == "T1"
    )
    from forge_cli.delegate import load_delegations  # noqa: E402
    task_cold_launches_before = [
        row for row in load_delegations(repo)
        if row.get("task") == "grill-task-T1"
    ]

    state = run_state(repo)
    plan = repo / state["plan_file"]
    original_story_digest = state["approved_plan_sha256"]
    plan.write_text(
        plan.read_text(encoding="utf-8") + "\nApproved story amendment.\n",
        encoding="utf-8",
    )
    amended_story_digest = lib.plan_digest_without_assumptions(plan)
    code, out = run(repo, "forge.py", "next")
    assert code == 0 and "awaiting amended-plan approval" in out, out
    code, out = post_hook(repo, native_claude_approval(repo))
    assert code == 0, out
    assert run_state(repo)["approved_plan_sha256"] == amended_story_digest
    approval_record = json.loads(
        (story_state(repo) / "plan-approval.json").read_text()
    )
    assert approval_record["previous_approved_plan_sha256"] \
        == original_story_digest
    assert approval_record["approved_plan_sha256"] == amended_story_digest

    # Reapproval alone is not permission to continue: the protected
    # decomposition must first publish the new story binding.
    code, out = run(
        repo, "forge.py", "delegate", "T1",
        env=_fake_companion_env(tmp_path),
    )
    assert code != 0 and "task grill is STALE" in out, out

    code, out = run(
        repo, "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [widened]}),
    )
    assert code == 0, out
    state = run_state(repo)
    assert state["decomposition_plan_sha256"] == amended_story_digest
    assert grill_path.read_bytes() == grill_before
    assert task_plan.read_bytes() == task_plan_before
    assert sorted(
        path.read_bytes() for path in approval_events.glob("*.json")
        if json.loads(path.read_text()).get("task") == "T1"
    ) == task_approval_events_before
    assert [
        row for row in load_delegations(repo)
        if row.get("task") == "grill-task-T1"
    ] == task_cold_launches_before

    stage_after = lib.task_stage_record(repo, "T1")
    assert stage_after["measurement_continuity"] == receipts_before
    assert {
        field: stage_after.get(field) for field in stable_before
    } == stable_before
    assert lib.task_grill_grounding_matches(repo, widened, json.loads(
        grill_path.read_text()
    ))

    widened_again = {**widened, "write_scope": ["src/", "billing/", "ops/"]}
    code, out = run(
        repo, "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [widened_again]}),
    )
    assert code == 0, out
    receipts = lib.task_stage_record(repo, "T1")["measurement_continuity"]
    assert len(receipts) == 2
    assert {row["story_plan_sha256"] for row in receipts} == {
        original_story_digest,
    }
    assert lib.task_grill_grounding_matches(repo, widened_again, json.loads(
        grill_path.read_text()
    ))

    code, out = run(
        repo, "forge.py", "delegate", "T1",
        env=_fake_companion_env(tmp_path),
    )
    assert code == 0, out

    from forge_cli.stages import load_stages, write_stages  # noqa: E402
    stages = load_stages(repo)
    stages["stages"][0]["measurement_continuity"][0][
        "semantic_grounding_sha256"
    ] = "0" * 64
    write_stages(repo, stages)
    code, out = run(
        repo, "forge.py", "delegate", "T1",
        env=_fake_companion_env(tmp_path),
    )
    assert code != 0 and "task grill is STALE" in out, out


def test_story_plan_reapproval_preserves_an_active_task_without_receipts(
        repo: Path, tmp_path, monkeypatch):
    from test_gates import (  # noqa: E402
        DECOMP, STAGE_TASK, native_claude_approval,
        post_hook, run_state, story_state,
    )

    _start_stage_with_contract_frame(repo, tmp_path, STAGE_TASK, monkeypatch)
    lib = load_factory_lib(repo)
    stage_before = copy.deepcopy(lib.task_stage_record(repo, "T1"))
    assert not stage_before.get("measurement_continuity")
    grill_path = story_state(repo) / "grills" / "tasks" / "T1.json"
    grill_before = grill_path.read_bytes()
    original_story_digest = run_state(repo)["approved_plan_sha256"]
    plan = repo / run_state(repo)["plan_file"]
    plan.write_text(
        plan.read_text(encoding="utf-8") + "\nApproved story amendment.\n",
        encoding="utf-8",
    )

    code, out = post_hook(repo, native_claude_approval(repo))
    assert code == 0, out
    first_amended_digest = run_state(repo)["approved_plan_sha256"]
    code, out = run(
        repo, "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [STAGE_TASK]}),
    )
    assert code == 0, out
    assert grill_path.read_bytes() == grill_before
    assert lib.task_stage_record(repo, "T1") == stage_before

    code, out = run(
        repo, "forge.py", "delegate", "T1",
        env=_fake_companion_env(tmp_path),
    )
    assert code == 0, out

    plan.write_text(
        plan.read_text(encoding="utf-8") + "\nSecond approved amendment.\n",
        encoding="utf-8",
    )
    code, out = post_hook(repo, native_claude_approval(repo))
    assert code == 0, out
    second_amended_digest = run_state(repo)["approved_plan_sha256"]
    code, out = run(
        repo, "record_decomposition_from_json.py",
        stdin=json.dumps({**DECOMP, "tasks": [STAGE_TASK]}),
    )
    assert code == 0, out
    assert lib.approved_story_plan_predecessors(repo, second_amended_digest) == (
        first_amended_digest, original_story_digest,
    )
    assert grill_path.read_bytes() == grill_before
    assert lib.task_stage_record(repo, "T1") == stage_before
    code, out = run(
        repo, "forge.py", "delegate", "T1",
        env=_fake_companion_env(tmp_path),
    )
    assert code == 0, out

    task_plan = story_state(repo) / "task-plans" / "T1.md"
    task_plan.write_text(
        task_plan.read_text(encoding="utf-8") + "\nChanged task meaning.\n",
        encoding="utf-8",
    )
    code, out = run(
        repo, "forge.py", "delegate", "T1",
        env=_fake_companion_env(tmp_path),
    )
    assert code != 0 and "Task plan approval required" in out, out


def test_approved_task_plan_amendment_does_not_mask_changed_grounding(
        repo: Path, tmp_path, monkeypatch):
    from test_gates import (  # noqa: E402
        STAGE_TASK, native_claude_approval, post_hook, story_state,
    )

    _start_stage_with_contract_frame(
        repo, tmp_path, STAGE_TASK, monkeypatch, launch=False,
    )
    lib = load_factory_lib(repo)
    task_plan = story_state(repo) / "task-plans" / "T1.md"
    task_plan.write_text(
        task_plan.read_text(encoding="utf-8") + "\nApproved amendment.\n",
        encoding="utf-8",
    )
    code, out = post_hook(repo, native_claude_approval(repo))
    assert code == 0, out

    grill = lib.load_json(
        story_state(repo) / "grills" / "tasks" / "T1.json", default={},
    )
    assert lib._task_plan_amendment_preserves_cold_proof(
        repo, STAGE_TASK, grill,
    )
    lib.require_task_grill(repo, "T1", STAGE_TASK)

    changed_grounding = (
        ("objective", "Build a different feature."),
        ("acceptance_criteria", ["a different acceptance bar"]),
        ("plan_contracts", [{"id": "C2", "statement": "different", "source": "x"}]),
        ("user_facing", True),
    )
    for field, value in changed_grounding:
        with pytest.raises(SystemExit, match="task grill is STALE"):
            lib.require_task_grill(repo, "T1", {**STAGE_TASK, field: value})


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"cold_input_sha256": "not-a-digest"}, "malformed cold proof"),
        ({"final_artifact_sha256": "F" * 64}, "malformed cold proof"),
        ({"finding_dispositions": {}}, "malformed cold proof"),
        ({"amendments": []}, "malformed amendment bridge"),
        ({"artifact_delta": "not-a-list"}, "malformed amendment bridge"),
        ({"amendments": [{
            "delta_index": 0, "findings": [{}], "change": "change",
            "reason": "reason", "source": "source",
        }]}, "malformed amendment bridge"),
        ({"amendments": [{
            "delta_index": 1, "findings": ["cold finding"], "change": "change",
            "reason": "reason", "source": "source",
        }]}, "malformed amendment bridge"),
    ],
)
def test_require_task_grill_rejects_malformed_cold_proof(
        repo: Path, monkeypatch: pytest.MonkeyPatch, changes: dict, message: str):
    lib = _seed(repo)
    path = lib.evidence_path(
        repo, "TEST-1", "grills/tasks/T1.json", for_write=True,
    )
    lib.dump_json(path, {
        "verdict": "pass", "commit": "base",
        "cold_input_sha256": "a" * 64,
        "final_artifact_sha256": "b" * 64,
        "finding_dispositions": [{
            "finding": "cold finding", "resolution": "resolved", "source": "test",
        }],
        "amendments": [{
            "delta_index": 0, "findings": ["cold finding"],
            "change": "change", "reason": "reason", "source": "source",
        }],
        "artifact_delta": [{
            "cold_start": 0, "cold_end": 1, "cold": "old\n",
            "final_start": 0, "final_end": 1, "final": "new\n",
        }],
        **changes,
    })
    monkeypatch.setattr(
        lib, "task_grill_grounding_matches", lambda *_args, **_kwargs: True,
    )

    with pytest.raises(SystemExit, match=message):
        lib.require_task_grill(repo, "T1", TASK)


def test_story_plan_predecessors_fail_closed_on_malformed_sibling_event(
        repo: Path):
    lib = _seed(repo)
    current_plan = repo / "plans" / "active" / "TEST-1-test-plan.md"
    current_digest = lib.plan_digest_without_assumptions(current_plan)
    previous_digest = "a" * 64
    lib.dump_json(lib.run_state_path(repo), {
        "story": "TEST-1", "issue_key": "TEST-1",
        "plan_file": "plans/active/TEST-1-test-plan.md",
        "plan_status": "approved", "approved_plan_sha256": current_digest,
    })
    record = {
        "runtime": "claude", "approved_by": "human-via-Claude",
        "plan_kind": "story", "story": "TEST-1", "task": "",
        "approved_plan_sha256": current_digest,
        "approved_at": "2026-09-16T00:00:00+00:00",
        "session_id": "session-current", "event_id": "event-current",
        "previous_approved_plan_sha256": previous_digest,
    }
    approval = lib.evidence_path(
        repo, "TEST-1", "plan-approval.json", for_write=True,
    )
    lib.dump_json(approval, record)
    events = approval.parent / "approval-events"
    events.mkdir(parents=True, exist_ok=True)

    def replay_path(value: dict) -> Path:
        key = hashlib.sha256(
            f"{value['runtime']}\0{value['session_id']}\0"
            f"{value['event_id']}".encode("utf-8")
        ).hexdigest()
        return events / f"{key}.json"

    lib.dump_json(replay_path(record), record)
    previous = {
        **record,
        "approved_plan_sha256": previous_digest,
        "approved_at": "2026-09-15T00:00:00+00:00",
        "session_id": "session-previous", "event_id": "event-previous",
        "previous_approved_plan_sha256": "",
    }
    lib.dump_json(replay_path(previous), previous)
    malformed = events / "bad.json"
    malformed.write_bytes(b"{not-json\n")
    before = {path.name: path.read_bytes() for path in events.glob("*.json")}

    with pytest.raises(SystemExit, match="approval event bad.json"):
        lib.approved_story_plan_predecessors(repo, current_digest)
    assert {path.name: path.read_bytes() for path in events.glob("*.json")} == before


def test_a_contract_change_still_stops_the_next_delegate(
        repo: Path, tmp_path, monkeypatch):
    # The other half: the gate must still refuse when what was authorised
    # actually changed, or the fix has simply removed the gate.
    from test_gates import STAGE_TASK  # noqa: E402
    from factory_lib import (  # noqa: E402
        dump_json, load_json, protected_decomposition_state_path,
    )

    _start_stage_with_contract_frame(
        repo, tmp_path, STAGE_TASK, monkeypatch, launch=False,
    )

    path = protected_decomposition_state_path(repo)
    decomposition = load_json(path, default={})
    for task in decomposition.get("tasks", []):
        if task.get("id") == "T1":
            task["write_scope"] = list(task.get("write_scope") or []) + ["apps/"]
    dump_json(path, decomposition)

    code, out = run(repo, "forge.py", "delegate", "T1",
                    env=_fake_companion_env(tmp_path))
    assert code != 0, f"a widened write scope no longer stops delegate:\n{out}"
    assert "STALE" in out or "grill" in out.lower()


def _prepare_file_cold_read(
        repo: Path, gate: str, artifact_file: Path, monkeypatch) -> dict:
    from types import SimpleNamespace

    from factory_lib import grill_key_suffix
    from forge_cli import codex_status
    from forge_cli.delegate import load_delegations
    from forge_cli.grill import cmd_grill_run

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    monkeypatch.setattr(codex_status, "dead_launches", lambda _base: [])
    args = SimpleNamespace(
        repo=str(repo), gate=gate, task="", file=str(artifact_file),
        context_file="", print_only=False, fresh=False, reason="",
    )
    cmd_grill_run(args)
    key = f"grill-{gate}-{grill_key_suffix(gate, artifact=artifact_file, root=repo)}"
    return next(
        row for row in reversed(load_delegations(repo))
        if row.get("task") == key and row.get("launch_status") == "prepared"
    )


def _record_prepared_file(
        repo: Path, gate: str, artifact_file: Path, launch: dict,
        tmp_path: Path) -> dict:
    from factory_lib import grill_evidence_name

    result = tmp_path / f"{gate}-{artifact_file.stem}-cold-result.json"
    result.write_text(json.dumps({"gaps": [], "contradictions": []}),
                      encoding="utf-8")
    payload = {
        "generated_by": "griller", "gate": gate, "verdict": "pass",
        "gaps": [], "contradictions": [], "resolutions": [],
        "finding_dispositions": [],
    }
    code, out = run(
        repo, "record_grill_from_json.py", "--gate", gate,
        "--input-digest", str(artifact_file), "--cold-result", str(result),
        "--preparation-id", launch["launch_id"], stdin=json.dumps(payload),
    )
    assert code == 0, out
    return json.loads(
        (repo / ".factory" / grill_evidence_name(
            gate, artifact=artifact_file, root=repo,
        ))
        .read_text(encoding="utf-8"),
    )


def test_two_specs_record_against_their_own_cold_reads(
        repo: Path, tmp_path: Path, monkeypatch):
    from factory_lib import grill_key_suffix, sha256_of
    from forge_cli.delegate import load_delegations

    specs = repo / "docs" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    alpha = specs / "alpha.md"
    beta = specs / "beta.md"
    alpha.write_text("# Alpha\n\nAlpha capability.\n", encoding="utf-8")
    beta.write_text("# Beta\n\nBeta capability.\n", encoding="utf-8")

    alpha_launch = _prepare_file_cold_read(repo, "spec", alpha, monkeypatch)
    beta_launch = _prepare_file_cold_read(repo, "spec", beta, monkeypatch)
    alpha_record = _record_prepared_file(
        repo, "spec", alpha, alpha_launch, tmp_path,
    )
    beta_record = _record_prepared_file(
        repo, "spec", beta, beta_launch, tmp_path,
    )

    assert alpha_record["preparation_id"] == alpha_launch["launch_id"]
    assert beta_record["preparation_id"] == beta_launch["launch_id"]
    assert alpha_record["input_sha256"] == sha256_of(alpha)
    assert beta_record["input_sha256"] == sha256_of(beta)
    assert alpha_record["input_sha256"] != beta_record["input_sha256"]
    assert {row["task"] for row in load_delegations(repo)
            if row.get("launch_status") == "prepared"} >= {
                f"grill-spec-{grill_key_suffix('spec', artifact=alpha, root=repo)}",
                f"grill-spec-{grill_key_suffix('spec', artifact=beta, root=repo)}",
            }


def test_second_read_of_same_spec_needs_fresh_reason(
        repo: Path, monkeypatch, capsys):
    from types import SimpleNamespace

    from factory_lib import grill_key_suffix
    from forge_cli.delegate import load_delegations
    from forge_cli.grill import cmd_grill_run

    specs = repo / "docs" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    spec = specs / "repeat.md"
    spec.write_text("# Repeat\n", encoding="utf-8")
    _prepare_file_cold_read(repo, "spec", spec, monkeypatch)

    with pytest.raises(SystemExit):
        cmd_grill_run(SimpleNamespace(
            repo=str(repo), gate="spec", task="", file=str(spec),
            context_file="", print_only=False, fresh=False, reason="",
        ))

    assert "already been cold-read" in capsys.readouterr().out
    assert sum(row.get("task") == f"grill-spec-{grill_key_suffix('spec', artifact=spec, root=repo)}"
               and row.get("launch_status") == "prepared"
               for row in load_delegations(repo)) == 1


def test_epics_file_cold_read_records_under_its_artifact_key(
        repo: Path, tmp_path: Path, monkeypatch):
    from factory_lib import grill_key_suffix, sha256_of

    artifact = tmp_path / "roadmap-input.json"
    artifact.write_text('{"epics": []}\n', encoding="utf-8")
    launch = _prepare_file_cold_read(repo, "epics", artifact, monkeypatch)
    record = _record_prepared_file(repo, "epics", artifact, launch, tmp_path)

    suffix = grill_key_suffix("epics", artifact=artifact, root=repo)
    assert launch["task"] == f"grill-epics-{suffix}"
    assert launch["brief_path"] == \
        f".factory/grill-brief-epics-{suffix}.md"
    assert record["preparation_id"] == launch["launch_id"]
    assert record["input_sha256"] == sha256_of(artifact)


def test_outside_epics_artifact_key_records_and_reads_pass(
        repo: Path, tmp_path: Path, monkeypatch):
    from factory_lib import grill_key_suffix, require_grill, sha256_of

    artifact = tmp_path / "roadmap-input.json"
    artifact.write_text('{"epics": []}\n', encoding="utf-8")
    path_hash = hashlib.sha256(
        artifact.resolve().as_posix().encode("utf-8")
    ).hexdigest()[:16]
    expected = f"{artifact.stem}-{path_hash}"

    def cross_drive_relpath(*_args, **_kwargs):
        raise ValueError("path is on a different drive")

    with monkeypatch.context() as patch:
        patch.setattr("os.path.relpath", cross_drive_relpath)
        assert grill_key_suffix("epics", artifact=artifact, root=repo) == expected
        assert grill_key_suffix("epics", artifact=artifact, root=repo) == expected

    launch = _prepare_file_cold_read(repo, "epics", artifact, monkeypatch)
    record = _record_prepared_file(repo, "epics", artifact, launch, tmp_path)
    assert launch["task"] == f"grill-epics-{expected}"
    assert record["input_sha256"] == sha256_of(artifact)
    require_grill(repo, "epics", (), expect_digest_of=artifact)


def test_same_named_epics_files_keep_separate_grill_passes(
        repo: Path, tmp_path: Path, monkeypatch):
    from factory_lib import (
        grill_evidence_name, require_grill, sha256_of,
    )

    first = repo / "docs" / "first" / "roadmap-input.json"
    second = repo / "docs" / "second" / "roadmap-input.json"
    for path, text in ((first, '{"epics": []}\n'),
                       (second, '{"epics": [{"id": "E2"}]}\n')):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    first_launch = _prepare_file_cold_read(repo, "epics", first, monkeypatch)
    second_launch = _prepare_file_cold_read(repo, "epics", second, monkeypatch)
    first_pass = _record_prepared_file(
        repo, "epics", first, first_launch, tmp_path,
    )
    second_pass = _record_prepared_file(
        repo, "epics", second, second_launch, tmp_path,
    )

    assert first_launch["task"] != second_launch["task"]
    assert first_launch["brief_path"] != second_launch["brief_path"]
    assert grill_evidence_name("epics", artifact=first, root=repo) != \
        grill_evidence_name("epics", artifact=second, root=repo)
    assert first_pass["input_sha256"] == sha256_of(first)
    assert second_pass["input_sha256"] == sha256_of(second)
    require_grill(repo, "epics", (), expect_digest_of=first)
    require_grill(repo, "epics", (), expect_digest_of=second)


def test_spec_confirmation_does_not_use_another_specs_pass(repo: Path):
    from types import SimpleNamespace

    from factory_lib import (
        dump_json, evidence_path, grill_evidence_name, sha256_of,
    )
    from forge_cli.specs import cmd_confirm

    specs = repo / "docs" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    alpha = specs / "alpha.md"
    beta = specs / "beta.md"
    alpha.write_text(
        "---\nslug: alpha\ntitle: Alpha\nstatus: draft\n---\n\n"
        "# Alpha\n\n## Why\n\nAlpha is needed.\n\n"
        "## Behaviour\n\nAlpha works.\n\n"
        "## Acceptance criteria\n\n- Alpha works.\n",
        encoding="utf-8",
    )
    beta.write_text(
        "---\nslug: beta\ntitle: Beta\nstatus: draft\n---\n\n"
        "# Beta\n\n## Why\n\nBeta is needed.\n\n"
        "## Behaviour\n\nBeta works.\n\n"
        "## Acceptance criteria\n\n- Beta works.\n",
        encoding="utf-8",
    )
    beta_pass = {
        "verdict": "pass", "commit": "test", "input_sha256": sha256_of(beta),
        "cold_input_sha256": "a" * 64, "final_artifact_sha256": "b" * 64,
        "finding_dispositions": [],
    }
    dump_json(evidence_path(
        repo, None, grill_evidence_name("spec", artifact=beta, root=repo),
        for_write=True,
    ), beta_pass)

    with pytest.raises(SystemExit, match="Handover grill required first"):
        cmd_confirm(SimpleNamespace(repo=str(repo), slug="alpha"))


def test_legacy_spec_grill_fallback_is_bound_to_its_input(repo: Path):
    from factory_lib import (
        dump_json, evidence_path, head_sha, require_grill, sha256_of,
    )

    specs = repo / "docs" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    alpha = specs / "alpha.md"
    beta = specs / "beta.md"
    alpha.write_text("# Alpha\n", encoding="utf-8")
    beta.write_text("# Beta\n", encoding="utf-8")
    dump_json(evidence_path(
        repo, None, "grills/spec.json", for_write=True,
    ), {
        "verdict": "pass", "commit": head_sha(repo),
        "input_sha256": sha256_of(alpha),
        "cold_input_sha256": "a" * 64, "final_artifact_sha256": "b" * 64,
        "finding_dispositions": [],
    })

    require_grill(repo, "spec", (), expect_digest_of=alpha)
    with pytest.raises(SystemExit, match="Handover grill required first"):
        require_grill(repo, "spec", (), expect_digest_of=beta)


def test_legacy_epics_grill_fallback_is_bound_to_its_input(repo: Path):
    from factory_lib import (
        dump_json, evidence_path, head_sha, require_grill, sha256_of,
    )

    first = repo / "docs" / "first" / "roadmap-input.json"
    second = repo / "docs" / "second" / "roadmap-input.json"
    for path, text in ((first, '{"epics": []}\n'),
                       (second, '{"epics": [{"id": "E2"}]}\n')):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    dump_json(evidence_path(
        repo, None, "grills/epics.json", for_write=True,
    ), {
        "verdict": "pass", "commit": head_sha(repo),
        "input_sha256": sha256_of(first),
        "cold_input_sha256": "a" * 64, "final_artifact_sha256": "b" * 64,
        "finding_dispositions": [],
    })

    require_grill(repo, "epics", (), expect_digest_of=first)
    with pytest.raises(SystemExit, match="Handover grill required first"):
        require_grill(repo, "epics", (), expect_digest_of=second)
