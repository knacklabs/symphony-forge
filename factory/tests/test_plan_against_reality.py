"""Planning reads the system, and the harness says which skill it uses.

Its own module — test_gates.py is one 690-test file where every added branch
collides with every other.

One story's plan grill recorded twenty inspected refs. All twenty were
documents; none was app source. The plan then asserted what a type carries,
which enum values exist and which routes touch a binding — facts that live in
code, not in an architecture note. So the planner described the system as
DESIGNED while the cold reader checked the system as BUILT, and every gap
became a finding. Twenty-six rounds of them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from test_gates import HARNESS, git, load_factory_lib, post_hook, repo, run  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))


def _flat(text: str) -> str:
    """Collapse whitespace.

    These are hard-wrapped documents. A phrase assertion against raw text
    breaks the moment someone re-flows a paragraph, which is a false failure
    about formatting dressed as a failure about content.
    """
    return " ".join(text.split())


def test_implementer_prompt_keeps_reporting_commands_available():
    prompt = (HARNESS / "factory" / "prompts" / "implementer.md").read_text(
        encoding="utf-8")
    assert "Never run `forge` commands yourself" not in prompt
    assert "parent-owned lifecycle commands" in prompt
    for command in ("forge delegate", "forge next", "forge task close",
                    "forge.py plan assume", "forge.py signal raise",
                    "forge.py lesson add"):
        assert command in prompt


# --------------------------------------------------- reading is not blocked
def test_nothing_actually_prevents_reading_the_repo(repo: Path):
    """The rule was obeyed as a prohibition and ignored as an instruction.

    "Do NOT grep/read app code yourself — delegate instead" has two halves.
    Nothing enforces either: no hook denies Read, Grep or Glob, the
    permissions file is empty, and the planning lock blocks WRITES. So the
    half that removes knowledge is free and the half that restores it costs a
    launch. Only the free half happened.
    """
    hook = (HARNESS / "factory" / "scripts" / "pre_tool_use.py").read_text(
        encoding="utf-8")
    for tool in ('"Read"', '"Grep"', '"Glob"'):
        assert tool not in hook, (
            f"a read tool is now gated ({tool}) — planning would go blind")

    settings = json.loads(
        (HARNESS / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert not (settings.get("permissions") or {}).get("deny"), (
        "a deny rule would silently re-create the prohibition")


def test_the_contract_tells_the_planner_to_read_first(repo: Path):
    claude = (HARNESS / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "do NOT grep/read app code yourself" not in claude, (
        "the prohibition is back")
    # CLAUDE.md is capped at 40 lines by check_dual_runtime — it points, and
    # planner.md carries the rule. Assert the pointer here and the substance
    # there, or the cap and the test fight each other.
    assert "READ BEFORE YOU ASSERT" in claude
    assert "Delegate BREADTH" in claude

    planner = (HARNESS / "factory" / "prompts" / "planner.md").read_text(
        encoding="utf-8")
    flat = _flat(planner)
    assert "FIRST, READ THE SYSTEM YOU ARE PLANNING AGAINST" in flat
    # And it must say WHY docs are not enough, or it reads as a style note.
    assert "as designed" in flat and "what was built" in flat
    # The distinction that makes delegation safe: breadth yes, facts no.
    assert "a summary of a type is not the type" in flat.lower()


def test_forge_next_makes_reading_a_step_not_a_parenthesis(repo: Path):
    """It was mentioned three times, never as a step.

    `forge next` said "MANDATORY: plan per planner.md (... exploration via
    /codex:rescue read-only)" — the mandatory half was writing, and reading was
    an aside inside a bracket. The grill gets a step of its own; so should this.
    """
    source = (HARNESS / "factory" / "scripts" / "forge_cli" / "phase.py"
              ).read_text(encoding="utf-8")
    first = source.index("FIRST read the system this plan will assert about")
    then = source.index("THEN plan per factory/prompts/planner.md")
    assert first < then, "authoring must not come before reading"
    step = source[first:then]
    assert "types, enums, routes" in step
    assert "/codex:rescue" in step, "breadth still delegates"


def test_doctor_requires_the_skill_that_is_used(repo: Path):
    # Requiring the Codex mirror of an un-invocable stub sent anyone missing it
    # to fix something no reader can use.
    doctor = (HARNESS / "factory" / "scripts" / "forge_cli" / "doctor.py"
              ).read_text(encoding="utf-8")
    assert '"grilling skill (both runtimes)"' in doctor
    assert "(grill_me_codex / \"SKILL.md\").is_file()" not in doctor


# ------------------------------------------------- the unrecordable grill --
def test_lean_docs_match_single_cold_grill_runtime(repo: Path):
    recorder = (HARNESS / "factory" / "scripts" / "record_grill_from_json.py"
                ).read_text(encoding="utf-8")
    workflow = _flat((HARNESS / "WORKFLOW.md").read_text(encoding="utf-8"))
    quality = _flat((HARNESS / "docs/QUALITY.md").read_text(encoding="utf-8"))
    assert "finding_dispositions" in recorder
    assert "cold_input_sha256" in recorder and "final_artifact_sha256" in recorder
    assert "one independent cold" in workflow.lower()
    assert "one independent cold" in quality.lower()
    assert "frontier_empty" not in recorder and "grill-rounds" not in recorder


def test_lean_handoff_and_close_docs_match_runtime_ownership(repo: Path):
    getting_started = (HARNESS / "docs/getting-started.md").read_text(encoding="utf-8")
    architecture = (HARNESS / "docs/architecture/dual-coordinator-parity.md").read_text(
        encoding="utf-8")
    griller = (HARNESS / "factory/prompts/griller.md").read_text(encoding="utf-8")
    implementer = (HARNESS / "factory/prompts/implementer.md").read_text(encoding="utf-8")
    loop = (HARNESS / "docs/specs/accountable-engineering-loop.md").read_text(
        encoding="utf-8")

    assert "LOCAL autoreview" not in getting_started
    assert "branch autoreview" not in getting_started
    for current in ("task proof", "`forge task close`", "combined three-lens",
                    "delegate fixes and rerun close until clean", "task PR readiness"):
        assert current in getting_started
    lean, successors = architecture.split("## Successor ownership", 1)
    assert "first event bundle" not in lean.lower()
    assert "Portable also owns the event-family migration" in successors
    assert "`user_facing` is true exactly for tasks that change frontend or UI behavior" \
        in griller
    assert "every user-visible behavior" not in griller
    for text in (implementer, loop):
        flat = _flat(text)
        assert "every assigned requirement" in flat
        assert "actual focused" in flat
        assert "remains incomplete" in flat
        assert "three-lens review remains authoritative" in flat


# ------------------------------------------------------------- dead code ---
def test_the_plan_mode_marker_recording_is_gone(repo: Path):
    """Decision 0050 removed the gate; nothing has read a marker since.

    Keeping the write kept `permission_mode == "plan"` in the hook's dispatch,
    which reads as if plan mode were still load-bearing three decisions after
    it stopped being.
    """
    hook = (HARNESS / "factory" / "scripts" / "post_tool_use.py").read_text(
        encoding="utf-8")
    assert 'permission_mode") == "plan"' not in hook
    assert '"plan-mode"' not in hook

    assert 'tool == "AskUserQuestion"' not in hook
    assert '"grill-rounds"' not in hook
    assert 'tool == "ExitPlanMode"' in hook


def test_optional_questions_do_not_create_grill_authority(repo: Path):
    lib = load_factory_lib(repo)
    control = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "forge"
    control.mkdir(parents=True, exist_ok=True)
    lib.dump_json(control / "run.json", {"issue_key": "ENG-1"})

    code, out = post_hook(repo, {
        "tool_name": "AskUserQuestion",
        "tool_input": {"questions": [{
            "question": "Does GRN come from SAP?",
            "options": [{"label": "SAP"}, {"label": "MineOps"}],
        }]},
        "tool_response": {"answers": {"Does GRN come from SAP?": "SAP"}},
    })
    assert code == 0, out
    assert not lib.evidence_path(repo, "ENG-1", "grill-rounds").exists()


# ------------------------------------------------- the TASK plan, equally --
def test_the_task_plan_authoring_step_reads_first_too(repo: Path):
    """Both plans are written by the same session against the same codebase.

    Only the story plan got the read-first step at first. The task plan is the
    worse case: it names the exact files, types and routes the implementer
    writes against, so a fact taken from a drifted doc does not cost a grill
    round — it costs a worker paused mid-implementation against a contract
    asking for something that is not there.
    """
    source = (HARNESS / "factory" / "scripts" / "forge_cli" / "phase.py"
              ).read_text(encoding="utf-8")
    first = source.index("FIRST read what {task_id} will touch")
    then = source.index("THEN author the {task_id} plan")
    assert first < then, "authoring must not come before reading"

    step = source[first:then]
    assert "migrations" in step, "a task plan names migrations; they must be read"
    assert "permission codes" in step
    assert "/codex:rescue" in step, "breadth still delegates"
    # It must say what a wrong fact COSTS here, or it reads as the same
    # boilerplate as the story-plan step and gets skimmed.
    assert "paused mid-" in step


def test_the_planner_contract_covers_both_plans(repo: Path):
    # planner.md is the contract both authoring steps point at. If it reads as
    # story-only, the task-plan step points at a document that does not
    # obviously apply to it.
    planner = (HARNESS / "factory" / "prompts" / "planner.md").read_text(
        encoding="utf-8")
    flat = _flat(planner)
    assert "governs BOTH the story plan and each per-task plan" in flat
    assert "binds harder for a TASK plan" in flat


def test_both_authoring_steps_say_the_same_thing(repo: Path):
    """One rule, two places — they must not drift.

    This is the defect this whole PR exists to fix, applied to itself: the
    story step and the task step are the same instruction, and a change to one
    that misses the other re-creates the gap.
    """
    source = (HARNESS / "factory" / "scripts" / "forge_cli" / "phase.py"
              ).read_text(encoding="utf-8")
    story = source[source.index("FIRST read the system this plan will assert"):
                   source.index("THEN plan per factory/prompts/planner.md")]
    task = source[source.index("FIRST read what {task_id} will touch"):
                  source.index("THEN author the {task_id} plan")]
    for shared in ("Not the ", "architecture note", "/codex:rescue",
                   "look up specific facts yourself"):
        assert shared in story, f"story step lost: {shared!r}"
        assert shared in task, f"task step lost: {shared!r}"


def test_normal_review_docs_use_selected_generation_not_fixed_aspect_recorders(
    repo: Path,
):
    docs = [
        (HARNESS / "AGENTS.md").read_text(encoding="utf-8"),
        (HARNESS / "WORKFLOW.md").read_text(encoding="utf-8"),
        (HARNESS / "docs" / "getting-started.md").read_text(encoding="utf-8"),
        (HARNESS / "factory" / "skills" / "forge.md").read_text(encoding="utf-8"),
    ]
    assert "./forge task close <task-id>" in docs[0]
    assert "forge task close <id>" in docs[1]
    assert "forge task close" in docs[3]
    assert "./forge review <task-id>" in docs[2]
    getting_started = docs[2]
    assert "selected generation" in getting_started
    assert "record_review_from_json.py --aspect quality" not in getting_started
    assert "Lite diagnostics" in getting_started
