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

import sys
from pathlib import Path

from test_gates import (  # noqa: F401
    HARNESS, STAGE_TASK, git, intake, load_factory_lib, record_skeleton_then_frontier,
    record_task_grill, repo, run, save_plan, sign_off, story_state,
    view_plan_on_board,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))


# ------------------------------------------------- a plan edited after approval
def test_a_plan_edited_after_approval_goes_to_the_human_not_the_grill(
        repo: Path, tmp_path):
    """The rule the human asked for: strict, but not another cold read.

    The grill already converged on this design and a human signed it off. When
    the words then change, another adversarial read is not what is missing —
    the human is, because they approved specific text and it is no longer that
    text. One reworded sentence used to cost a full grill round; worse, a real
    design change could be cleared by an agent re-grilling rather than by the
    person who approved the original.
    """
    sign_off(repo)
    intake(repo)
    save_plan(repo, tmp_path)
    record_skeleton_then_frontier(repo, [STAGE_TASK])
    code, out = record_task_grill(repo, STAGE_TASK, approve=False)
    assert code == 0, out
    view_plan_on_board(repo, "T1")
    code, out = run(repo, "forge.py", "task", "approve", "T1",
                    "--by", "Test Human")
    assert code == 0, out

    saved = story_state(repo) / "task-plans" / "T1.md"
    saved.write_text(saved.read_text(encoding="utf-8") + "\nOne reworded line.\n",
                     encoding="utf-8")

    code, out = run(repo, "forge.py", "task", "approve", "T1",
                    "--by", "Test Human")
    assert code != 0, out
    # It must name the human and say re-approval, not re-grill.
    assert "CHANGED after" in out and "Test Human" in out
    assert "does not need another grill" in out
    assert "re-grill" not in out.lower().replace("does not need another grill", "")


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
    view_plan_on_board(repo, "T1")
    code, out = run(repo, "forge.py", "task", "approve", "T1",
                    "--by", "Test Human")
    assert code != 0, out
    assert "Re-grill the current plan" in out


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
    view_plan_on_board(repo, "T1")
    code, out = run(repo, "forge.py", "task", "approve", "T1",
                    "--by", "Test Human")
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
