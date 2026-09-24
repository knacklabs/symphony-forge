"""The harness stops the human for the right things and nothing else.

Its own module — test_gates.py is one 690-test file where every added branch
collides with every other.

Measured over one project: 26 worker signals reached the human. 8 were the
sandbox refusing a dependency install, 6 were a review-budget ceiling, 5 were a
write_scope one file short of what the work mechanically implied, and 7 were
genuine design questions. Nineteen of twenty-six were mechanical, because the
guidance said "the orchestrator resolves the event" and never said which of
them it was allowed to resolve without asking.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from test_gates import (  # noqa: F401
    HARNESS, STAGE_TASK, git, intake, load_factory_lib, record_skeleton_then_frontier,
    native_claude_approval, post_hook, record_task_grill, repo, run, save_plan,
    sign_off, start_stage, story_state, write_in_scope, write_task_proof,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))


# ------------------------------------------------- a plan edited after approval
def test_an_edited_story_plan_routes_to_native_reapproval_without_a_cold_read(
        repo: Path, tmp_path):
    sign_off(repo)
    intake(repo)
    code, out = save_plan(repo, tmp_path)
    assert code == 0, out
    lib = load_factory_lib(repo)
    state = json.loads(lib.run_state_path(repo).read_text())
    plan = repo / state["plan_file"]
    grill = story_state(repo) / "grills" / "plan.json"
    original_grill = grill.read_bytes()
    plan.write_text(
        plan.read_text(encoding="utf-8") + "\nApproved amendment.\n",
        encoding="utf-8",
    )

    code, out = run(repo, "forge.py", "next")

    assert code == 0, out
    assert "PHASE: awaiting amended-plan approval" in out
    assert "Display its exact current bytes in native Plan Mode" in out
    assert "do not launch another plan cold read" in out
    assert "re-record the same decomposition" in out
    assert "keeps its existing cold proof and task approval" in out
    assert grill.read_bytes() == original_grill


def test_a_plan_edited_after_approval_cannot_reuse_stale_native_authority(
        repo: Path, tmp_path):
    """An old approval alone cannot authenticate a newly edited artifact."""
    sign_off(repo)
    intake(repo)
    save_plan(repo, tmp_path)
    record_skeleton_then_frontier(repo, [STAGE_TASK])
    code, out = record_task_grill(repo, STAGE_TASK, approve=False)
    assert code == 0, out
    code, out = post_hook(repo, native_claude_approval(repo))
    assert code == 0, out

    saved = story_state(repo) / "task-plans" / "T1.md"
    grill_path = story_state(repo) / "grills" / "tasks" / "T1.json"
    original_grill = json.loads(grill_path.read_text())
    preserved_cold_proof = {
        field: original_grill.get(field)
        for field in (
            "cold_input_sha256", "final_artifact_sha256",
            "finding_dispositions", "amendments",
        )
    }

    def task_approval_events():
        return [
            event
            for path in (story_state(repo) / "approval-events").glob("*.json")
            if (event := json.loads(path.read_text())).get("task") == "T1"
        ]

    saved.write_text(saved.read_text(encoding="utf-8") + "\nOne reworded line.\n",
                     encoding="utf-8")

    code, out = run(repo, "forge.py", "stage", "start", "T1", "--trunk")
    assert code != 0, out
    assert "Task plan approval required" in out
    lib = load_factory_lib(repo)
    assert not lib._task_plan_approval_matches_digest(
        repo, STAGE_TASK, original_grill,
        lib.plan_digest_without_assumptions(saved),
    )
    assert len(task_approval_events()) == 1
    assert {
        field: json.loads(grill_path.read_text()).get(field)
        for field in preserved_cold_proof
    } == preserved_cold_proof
    code, out = post_hook(repo, native_claude_approval(repo))
    assert code == 0, out
    code, out = run(repo, "forge.py", "stage", "start", "T1", "--trunk")
    assert code == 0, out
    updated = json.loads(grill_path.read_text())
    assert {
        field: updated.get(field) for field in preserved_cold_proof
    } == preserved_cold_proof
    amended_digest = lib.plan_digest_without_assumptions(saved)
    assert updated["approved_task_plan_sha256"] == amended_digest
    assert updated["previous_approved_task_plan_sha256"] \
        == original_grill["approved_task_plan_sha256"]
    assert len(task_approval_events()) == 2
    assert lib._task_plan_approval_matches_digest(
        repo, STAGE_TASK, updated, amended_digest,
    )


def test_an_unapproved_plan_edit_still_needs_a_regrill(repo: Path, tmp_path):
    # The other side: if nobody approved it yet, the grill genuinely has not
    # read this text, so the re-grill instruction is the correct one.
    sign_off(repo)
    intake(repo)
    save_plan(repo, tmp_path)
    record_skeleton_then_frontier(repo, [STAGE_TASK])
    code, out = record_task_grill(repo, STAGE_TASK, approve=False)
    assert code == 0, out

    saved = story_state(repo) / "task-plans" / "T1.md"
    saved.write_text(saved.read_text(encoding="utf-8") + "\nEdited pre-approval.\n",
                     encoding="utf-8")
    code, out = run(repo, "forge.py", "stage", "start", "T1", "--trunk")
    assert code != 0, out
    assert "STALE" in out and "record_grill_from_json.py" in out


# --------------------------------------------------- task start is not optional
def test_stage_start_refuses_when_task_start_was_skipped(repo: Path, tmp_path):
    """`forge next` already called this step "not optional". Now it is.

    require_task_worktree returns early when the run pointer has no task_id —
    exactly the state a skipped `task start` leaves — so every task-level guard
    silently stopped checking. One story ran its whole implementation on the
    trunk's tree, on a hand-made branch, with base_main_sha/branch/worktree all
    null.
    """
    sign_off(repo)
    intake(repo)
    save_plan(repo, tmp_path)
    record_skeleton_then_frontier(repo, [STAGE_TASK])
    code, out = record_task_grill(repo, STAGE_TASK, approve=False)
    assert code == 0, out
    code, out = post_hook(repo, native_claude_approval(repo))
    assert code == 0, out

    code, out = run(repo, "forge.py", "stage", "start", "T1")
    assert code != 0, f"stage opened without task start:\n{out}"
    assert "task start T1" in out
    # The refusal has to say what it costs, or it reads as bureaucracy.
    assert "worktree" in out.lower() and "base_main_sha" in out


def test_the_guard_names_the_command_and_where_to_run_it(repo: Path):
    sys.path.insert(0, str(repo / "factory" / "scripts"))
    from factory_lib import require_task_start_recorded  # noqa: E402

    try:
        require_task_start_recorded(repo, "T7")
    except SystemExit as exc:
        message = str(exc)
    else:
        raise AssertionError("a repo with no task start must refuse")
    assert "./forge task start T7" in message
    assert "INSIDE the worktree" in message


# ------------------------------------------------------- who answers a signal
def test_the_guidance_says_which_signals_to_answer_alone():
    """Guidance that says only "the orchestrator resolves it" produced 19
    unnecessary interruptions out of 26. The split has to be written down."""
    workflow = (HARNESS / "WORKFLOW.md").read_text(encoding="utf-8")
    for phrase in ("ANSWERS IT ITSELF", "review_budget", "write_scope",
                   "burden is on ESCALATING"):
        assert phrase in workflow, phrase
    # And it must still route real decisions to the human.
    assert "ESCALATES to the human" in workflow
    assert "options and the" in workflow


def test_forge_next_repeats_the_split_where_it_is_needed():
    # The human reads WORKFLOW.md once; the coordinator reads `forge next`
    # every time a signal is open.
    source = (HARNESS / "factory" / "scripts" / "forge_cli" / "phase.py"
              ).read_text(encoding="utf-8")
    step = source[source.index("OPEN worker signal(s)"):][:900]
    assert "ANSWER " in step and "YOURSELF" in step
    assert "Escalate ONLY" in step
    assert "recommendation" in step


def test_review_triage_is_the_frontier_and_blocks_only_real_write_launches(
        repo: Path, tmp_path):
    start_stage(repo, tmp_path, STAGE_TASK)
    write_in_scope(repo, "src/core.py", "version = 1\n")
    git(repo, "add", "src/core.py")
    git(repo, "commit", "-qm", "reviewed work")
    write_task_proof(repo, "T1", publish_review=True, review_blocked=True)

    from forge_cli.review import selected_generation
    generation = selected_generation(repo, "ENG-1", "T1")
    assert generation is not None

    code, out = run(repo, "forge.py", "next")
    assert code == 0, out
    assert "REVIEW TRIAGE for T1" in out
    assert generation["generation_id"] in out
    assert "1 of 1 actionable P0/P1 defect finding(s) untriaged" in out
    assert './forge review T1 --triage "<finding text>"' in out
    assert "Inspect them, then delegate the bounded fixes" not in out

    code, out = run(
        repo, "forge.py", "delegate", "T1",
        env={"FORGE_COORDINATOR": "codex"},
    )
    assert code != 0, out
    assert "write delegation refused" in out
    assert generation["generation_id"] in out
    assert './forge review T1 --triage "<finding text>"' in out

    code, out = run(
        repo, "forge.py", "delegate", "T1", "--print-only",
        env={"FORGE_COORDINATOR": "codex"},
    )
    assert code == 0, out
    assert "Write access: NO" in out and "not dispatched" in out


# ------------------------------------------------------- reachable escalation
def test_the_effort_escalation_harness_yaml_documents_is_reachable(repo: Path):
    """The delegated lead is pinned to Sol/medium; effort is not a CLI knob."""
    from forge_cli.delegate import pinned_run_config

    assert pinned_run_config(HARNESS) == ("gpt-6-sol", "medium")
    for args in (("--effort", "low"), ("--effort", "medium"),
                 ("--effort", "high"), ("--effort", "xhigh"),
                 ("--effort", "maximum"), ("--effort=medium",)):
        code, out = run(repo, "forge.py", "delegate", "T1", *args)
        assert code != 0 and "unrecognized arguments" in out, args


# ------------------------------------------- caught in planning, not later --
def test_a_required_test_outside_the_write_scope_is_refused(repo: Path, tmp_path):
    """Five of one story's interruptions were a scope discovered too late.

    The derivable part is checkable before approval: a required test names a
    path, and a task that may not write that path cannot produce that proof.
    """
    sys.path.insert(0, str(repo / "factory" / "scripts"))
    from factory_lib import required_tests_outside_scope  # noqa: E402

    inside = {"write_scope": ["src/"],
              "required_tests": [{"path": "src/core.spec.ts"}]}
    assert required_tests_outside_scope(inside) == []

    outside = {"write_scope": ["src/"],
               "required_tests": [{"path": "apps/api/test/e2e.spec.ts"}]}
    assert required_tests_outside_scope(outside) == ["apps/api/test/e2e.spec.ts"]

    # A scope entry naming the file exactly covers it.
    exact = {"write_scope": ["src/core.spec.ts"],
             "required_tests": [{"path": "src/core.spec.ts"}]}
    assert required_tests_outside_scope(exact) == []

    # A prefix must not match a sibling directory: "src" does not cover
    # "srcfoo/".
    sibling = {"write_scope": ["src"],
               "required_tests": [{"path": "srcfoo/a.spec.ts"}]}
    assert required_tests_outside_scope(sibling) == ["srcfoo/a.spec.ts"]


def test_the_task_grill_sees_the_lessons_in_force(repo: Path):
    """A cold reader that cannot see the constraints cannot fault a plan for
    ignoring them.

    Eight of one story's interruptions were an environment block that was
    already recorded as a lesson. The delegate brief carried them; the grill
    brief, which reads the plan BEFORE the work, did not.
    """
    sys.path.insert(0, str(repo / "factory" / "scripts"))
    from forge_cli.grill import _lessons_section  # noqa: E402

    # No task, no scope: silence rather than a list the reader learns to skip.
    assert _lessons_section(repo, "spec", "") == ""
    assert _lessons_section(repo, "task", "") == ""

    source = (HARNESS / "factory" / "scripts" / "forge_cli" / "grill.py"
              ).read_text(encoding="utf-8")
    assert "_lessons_section(base, gate, task_id)" in source, (
        "the brief must actually carry the section")
    assert "design AROUND these" in source


def test_the_audit_counts_interruptions_after_approval(repo: Path):
    # No gate catches everything, so a bad stop still reaches the human once.
    # What must not happen is it reaching them eighteen times unmeasured.
    sys.path.insert(0, str(repo / "factory" / "scripts"))
    from forge_cli.audit import interruptions_after_approval  # noqa: E402
    from forge_cli.signal import escalations_path  # noqa: E402
    import json as _json

    assert interruptions_after_approval(repo) == []

    path = escalations_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(
        _json.dumps({"id": str(n), "story": "WF-1", "spent": True,
                     "missing_decision": f"decision {n} nobody has made"}) + "\n"
        for n in range(4)), encoding="utf-8")

    problems = interruptions_after_approval(repo)
    assert problems and "WF-1 stopped for the human 4 time(s)" in problems[0]
    assert "approval to" in problems[0]
