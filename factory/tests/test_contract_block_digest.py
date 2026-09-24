"""A rendered contract block must not stale the approval it is excluded from.

`render_task_contract_block` appends a harness-generated block to the task plan
and the block itself tells the reader it is "excluded from the plan's approval
and grill digests, so a re-render never stales either".

It was not excluded. `strip_derived_sections` substitutes a newline for the
block, and the block is appended after one, so stripping left one MORE trailing
newline than the file carried before the block existed. `plan_body_digest`
hashed that one byte, so the first render changed the digest and `task approve`
refused with "the plan CHANGED after <name> approved it" against authored text
that was byte-identical. It fires at the last gate before a PR, and the message
sends the reader hunting for a content change that never happened.
"""
from __future__ import annotations

import hashlib
import json

from test_gates import (  # noqa: I001 — puts factory/scripts on sys.path
    STAGE_TASK, intake, plan_draft, plan_digest_without_assumptions,
    record_grill, record_skeleton_then_frontier,
    record_task_grill, repo, run, save_plan, sign_off, story_state,
)
from factory_lib import (  # noqa: E402
    CONTRACT_BLOCK_END, CONTRACT_BLOCK_START, plan_body_digest,
    refresh_task_plan_contract, run_state_path, strip_derived_sections,
)

__all__ = ["repo"]

PLAN = """---
issue: STORY-1
story: STORY-1
decisions_reviewed: []
---

# STORY-1-T1 — a task

## Problem

Something needs doing.
"""

BLOCK = f"""
{CONTRACT_BLOCK_START}
## Contract (recorded)

Rendered by the harness from the recorded decomposition.

**Acceptance criteria**

- stale acceptance criteria

**Write scope**

- stale/scope.py
{CONTRACT_BLOCK_END}
"""


def test_rendering_the_contract_block_does_not_change_the_plan_digest(repo):
    path = repo / "plan.md"
    path.write_text(PLAN, encoding="utf-8")
    before = plan_body_digest(path)

    path.write_text(PLAN + BLOCK, encoding="utf-8")

    assert plan_body_digest(path) == before


def test_re_rendering_a_changed_contract_block_still_does_not_change_it(repo):
    """A scope widening re-renders the block; approval must survive that."""
    path = repo / "plan.md"
    path.write_text(PLAN + BLOCK, encoding="utf-8")
    before = plan_body_digest(path)

    wider = BLOCK.replace("Rendered by the harness", "Rendered, now with 19 files")
    path.write_text(PLAN + wider, encoding="utf-8")

    assert plan_body_digest(path) == before


def test_an_authored_edit_still_changes_the_digest(repo):
    """The exclusion must not swallow a real change to the authored body."""
    path = repo / "plan.md"
    path.write_text(PLAN + BLOCK, encoding="utf-8")
    before = plan_body_digest(path)

    path.write_text(PLAN.replace("Something needs doing.", "Something else.") + BLOCK,
                    encoding="utf-8")

    assert plan_body_digest(path) != before


def test_refresh_removes_existing_contract_without_changing_approval_digest(repo):
    state_path = run_state_path(repo)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["issue_key"] = "STORY-1"
    state["story"] = "STORY-1"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    path = repo / ".factory" / "stories" / "STORY-1" / "task-plans" / "T1.md"
    path.parent.mkdir(parents=True)
    path.write_text(PLAN + BLOCK, encoding="utf-8")
    before = plan_body_digest(path)

    assert refresh_task_plan_contract(
        repo, "T1", {"id": "T1", "acceptance_criteria": ["new criteria"]},
    )

    refreshed = path.read_text(encoding="utf-8")
    assert "forge:contract" not in refreshed
    assert "stale acceptance criteria" not in refreshed
    assert "stale/scope.py" not in refreshed
    assert plan_body_digest(path) == before


def test_forge_next_codex_approval_question_keeps_digest_in_id(repo, tmp_path):
    sign_off(repo)
    intake(repo)
    plan = tmp_path / "codex-next-plan.md"
    plan.write_text(plan_draft(repo))
    record_grill(repo, "plan", digest_of=plan)
    code, out = run(repo, "forge.py", "plan", "save", "--from", str(plan),
                    "--story", "ENG-1")
    assert code == 0 and "awaiting-approval" in out, out

    active = next((repo / "plans" / "active").glob("ENG-1-*.md"))
    digest = plan_digest_without_assumptions(active)
    code, out = run(repo, "forge.py", "next", env={"FORGE_COORDINATOR": "codex"})

    assert code == 0, out
    assert 'question="Approve this plan?"' in out
    assert f'id="approve_plan_{digest}"' in out
    assert f'question="Approve exact plan digest {digest}?"' not in out


def test_task_plan_save_strips_contract_block_and_preserves_legacy_metadata(
        repo, tmp_path):
    sign_off(repo)
    intake(repo)
    save_plan(repo, tmp_path)
    record_skeleton_then_frontier(repo, [STAGE_TASK])
    source = tmp_path / "T1-plan.md"
    body = (
        "# T1 plan\n\n### Workflow\n\nA -> B.\n"
        "\n### Manual Verification\n\n1. Run it.\n" + BLOCK
    )
    source.write_text(body, encoding="utf-8")
    approval_digest = plan_body_digest(source)

    code, out = run(repo, "forge.py", "task", "plan", "save", "T1",
                    "--from", str(source))
    assert code == 0, out
    destination = story_state(repo) / "task-plans" / "T1.md"
    meta = story_state(repo) / "task-plans" / "T1.meta.json"
    assert destination.read_bytes() == strip_derived_sections(body.encode("utf-8"))
    saved = destination.read_text(encoding="utf-8")
    assert "forge:contract" not in saved
    assert "stale acceptance criteria" not in saved
    assert "stale/scope.py" not in saved
    assert plan_body_digest(destination) == approval_digest
    assert not meta.exists()

    legacy_body = (
        "# T1 plan\n\n## Workflow\n\nA -> B.\n\n"
        "## Manual Verification\n\n1. Run it.\n"
    )
    source.write_text(
        "---\nlegacy_owner: Test Human\nlabels:\n  - old\n  - task\n---\n"
        + legacy_body,
        encoding="utf-8",
    )
    code, out = run(repo, "forge.py", "task", "plan", "save", "T1",
                    "--from", str(source))
    assert code == 0, out
    assert destination.read_text(encoding="utf-8") == legacy_body
    assert json.loads(meta.read_text(encoding="utf-8")) == {
        "legacy_owner": "Test Human", "labels": ["old", "task"],
    }

    source.write_text(legacy_body, encoding="utf-8")
    code, out = run(repo, "forge.py", "task", "plan", "save", "T1",
                    "--from", str(source))
    assert code == 0, out
    assert not meta.exists()
