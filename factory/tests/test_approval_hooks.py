from __future__ import annotations

import difflib
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from test_gates import (  # noqa: F401
    HARNESS, ensure_story, git, intake, load_factory_lib, plan_draft,
    record_grill, repo, run, save_plan, sign_off, story_state,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import approval, upgrade  # noqa: E402
from forge_cli.decisions import active_decision_ids  # noqa: E402


def _event(candidate: approval.ApprovalCandidate, runtime: str = "claude") -> dict:
    common = {
        "session_id": f"session-{uuid.uuid4().hex}",
        "tool_use_id": f"event-{uuid.uuid4().hex}",
    }
    if runtime == "claude":
        return {**common, "tool_name": "ExitPlanMode",
                "tool_input": {"plan": candidate.path.read_text(encoding="utf-8")},
                "tool_response": {"status": "success"}}
    question_id = f"approve_plan_{candidate.digest}"
    question = "Approve this plan?"
    return {
        **common,
        "tool_name": "request_user_input",
        "tool_input": {"questions": [{
            "id": question_id, "header": "Approve plan", "question": question,
            "options": [
                {"label": "Approve plan"},
                {"label": "Request changes"},
                {"label": "Stop"},
            ],
        }]},
        "tool_response": {
            "answers": {question_id: {"answers": ["Approve plan"]}},
        },
    }


def _artifact_delta(before: str, after: str) -> list[dict]:
    old = before.splitlines(keepends=True)
    new = after.splitlines(keepends=True)
    return [{
        "cold_start": left_start, "cold_end": left_end,
        "cold": "".join(old[left_start:left_end]),
        "final_start": right_start, "final_end": right_end,
        "final": "".join(new[right_start:right_end]),
    } for tag, left_start, left_end, right_start, right_end
        in difflib.SequenceMatcher(
            a=old, b=new, autojunk=False,
        ).get_opcodes() if tag != "equal"]


def _story_candidate(repo: Path, story: str = "APPROVE-1") -> approval.ApprovalCandidate:
    lib = load_factory_lib(repo)
    plan = repo / "plans" / "active" / f"{story}-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("---\nstatus: awaiting-approval\n---\n\n# Plan\n", encoding="utf-8")
    lib.dump_json(lib.run_state_path(repo), {
        "issue_key": story, "story": story,
        "plan_status": "awaiting-approval",
        "plan_file": plan.relative_to(repo).as_posix(),
    })
    digest = lib.plan_digest_without_assumptions(plan)
    lib.dump_json(
        lib.evidence_path(
            repo, story, "grills/plan.json", for_write=True,
        ),
        {
            "verdict": "pass", "commit": lib.head_sha(repo),
            "issue": story, "input_sha256": digest,
            "cold_input_sha256": digest,
            "final_artifact_sha256": digest,
            "finding_dispositions": [],
        },
    )
    candidate = approval._story_candidate(repo)
    assert candidate is not None
    return candidate


def _task_candidate(repo: Path, monkeypatch: pytest.MonkeyPatch):
    story = _story_candidate(repo)
    approval.record_native_approval(repo, _event(story), runtime="claude")
    lib = load_factory_lib(repo)
    task = {"id": "T1"}
    monkeypatch.setattr(
        approval, "task_frontier_state", lambda _base: ("await-approval", task),
    )
    plan = lib.evidence_path(
        repo, story.story, "task-plans/T1.md", for_write=True,
    )
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# Task plan\n", encoding="utf-8")
    digest = lib.plan_digest_without_assumptions(plan)
    grill = lib.evidence_path(
        repo, story.story, "grills/tasks/T1.json", for_write=True,
    )
    lib.dump_json(grill, {
        "verdict": "pass", "task_plan_sha256": digest,
        "cold_input_sha256": digest, "final_artifact_sha256": digest,
        "finding_dispositions": [],
    })
    lib.dump_json(lib.protected_decomposition_state_path(repo), {
        "plan_sha256": story.digest, "tasks": [task],
    })
    candidates = approval.eligible_candidates(repo)
    assert len(candidates) == 1 and candidates[0].kind == "task"
    return candidates[0]


def _add_worktree(repo: Path, path: Path) -> Path:
    git(repo, "worktree", "add", "--detach", str(path), "HEAD")
    return path


def test_plan_save_refuses_split_issue_and_story_keys_without_mutation(
        repo: Path, tmp_path: Path):
    sign_off(repo)
    intake(repo, "ISSUE-I", "Invoices")
    ensure_story(repo, "ISSUE-I", "Invoices")
    ensure_story(repo, "STORY-S", "Roadmap story")
    draft = tmp_path / "distinct-identities.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    code, output = record_grill(repo, "plan", digest_of=draft)
    assert code == 0, output
    state_path = load_factory_lib(repo).run_state_path(repo)
    state_before = state_path.read_bytes()

    code, output = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--issue", "ISSUE-I", "--story", "STORY-S",
    )
    assert code != 0 and "--story must match --issue" in output, output
    assert state_path.read_bytes() == state_before
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["issue_key"] == "ISSUE-I"
    assert state.get("plan_status") != "awaiting-approval"
    assert not list((repo / "plans" / "active").glob("*.md"))
    assert approval.eligible_candidates(repo) == []

    # The default story remains the issue key and can still be saved normally.
    code, output = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--issue", "ISSUE-I",
    )
    assert code == 0, output
    candidates = approval.eligible_candidates(repo)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.story == "ISSUE-I"

    lib = load_factory_lib(repo)
    grill = json.loads(
        lib.evidence_path(repo, "ISSUE-I", "grills/plan.json").read_text()
    )
    assert grill["issue"] == "ISSUE-I"
    record = approval.record_native_approval(
        repo, _event(candidate), runtime="claude",
    )
    assert record["story"] == "ISSUE-I"
    assert json.loads(
        lib.evidence_path(repo, "ISSUE-I", "plan-approval.json").read_text()
    )["story"] == "ISSUE-I"
    state = json.loads(lib.run_state_path(repo).read_text())
    assert state["issue_key"] == "ISSUE-I"
    assert state["story"] == "ISSUE-I"
    assert lib.require_approved_plan_digest(repo) == candidate.digest


def test_plan_save_refuses_inline_list_frontmatter_and_accepts_canonical_form(
        repo: Path, tmp_path: Path):
    sign_off(repo)
    code, output = intake(repo)
    assert code == 0, output
    draft = tmp_path / "frontmatter-plan.md"
    canonical = plan_draft(repo)
    frontmatter, body = canonical.split("\n---\n", 1)
    decision_lines = [
        line for line in frontmatter.splitlines() if line.startswith("  - ")
    ]
    inline_field = "decisions_reviewed: [" + ", ".join(
        line[4:] for line in decision_lines
    ) + "]"
    inline_frontmatter = frontmatter.replace(
        "decisions_reviewed:\n" + "\n".join(decision_lines), inline_field,
    )
    draft.write_text(inline_frontmatter + "\n---\n" + body, encoding="utf-8")
    active_dir = repo / "plans" / "active"
    active_dir_existed = active_dir.exists()
    state_path = load_factory_lib(repo).run_state_path(repo)
    state_before = state_path.read_bytes()
    code, output = record_grill(repo, "plan", digest_of=draft)
    assert code == 0, output

    code, output = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--story", "ENG-1",
    )
    assert code != 0 and "canonical" in output, output
    assert state_path.read_bytes() == state_before
    assert active_dir.exists() is active_dir_existed
    assert not list(active_dir.glob("*.md"))
    assert approval.eligible_candidates(repo) == []

    draft.write_text(canonical, encoding="utf-8")
    code, output = record_grill(repo, "plan", digest_of=draft)
    assert code == 0, output
    code, output = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--story", "ENG-1",
    )
    assert code == 0, output
    assert len(approval.eligible_candidates(repo)) == 1
    saved = next((repo / "plans" / "active").glob("ENG-1-*.md"))
    saved_text = saved.read_text(encoding="utf-8")
    assert saved_text == body
    assert not saved_text.startswith("---\n")
    metadata = json.loads(
        (repo / ".factory" / "stories" / "ENG-1" / "plan-meta.json").read_text()
    )
    assert metadata["decisions_reviewed"] == active_decision_ids(repo)


def test_plan_resave_replaces_only_unapproved_story_plan(repo: Path, tmp_path: Path):
    sign_off(repo)
    code, output = intake(repo)
    assert code == 0, output
    draft = tmp_path / "resaved-plan.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    code, output = record_grill(repo, "plan", digest_of=draft)
    assert code == 0, output
    code, output = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--title", "First title",
    )
    assert code == 0, output
    first = repo / "plans" / "active" / "ENG-1-first-title.md"
    assert first.is_file()

    code, output = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--title", "Updated title",
    )
    assert code == 0, output
    updated = repo / "plans" / "active" / "ENG-1-updated-title.md"
    assert not first.exists()
    assert list((repo / "plans" / "active").glob("ENG-1-*.md")) == [updated]

    candidate = approval.eligible_candidates(repo)[0]
    approved_bytes = updated.read_bytes()
    approval.record_native_approval(repo, _event(candidate), runtime="claude")
    code, output = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--title", "Third title",
    )
    assert code != 0
    assert ("an approved plan exists at plans/active/ENG-1-updated-title.md; "
            "amend it rather than saving a new title") in output
    assert updated.read_bytes() == approved_bytes
    assert list((repo / "plans" / "active").glob("ENG-1-*.md")) == [updated]


def test_brief_plan_saves_body_only_and_claude_approves_exact_text(
        repo: Path, tmp_path: Path):
    sign_off(repo)
    code, output = intake(repo)
    assert code == 0, output
    brief = (
        "## What and why\n\nPeople need a clear invoice workflow.\n\n"
        "## What changes for you\n\nInvoices are easier to review.\n\n"
        "## Done when\n\nA user can create and review an invoice.\n\n"
        "## Risks\n\nExisting records must remain readable.\n\n"
        "## Technical approach\n\nUse the existing invoice service.\n\n"
        "## Task decomposition\n\nImplement the user flow and its checks.\n\n"
        "## Verify plan\n\nRun the focused invoice checks.\n"
    )
    draft = tmp_path / "brief-plan.md"
    draft.write_text(brief, encoding="utf-8")
    code, output = record_grill(repo, "plan", digest_of=draft)
    assert code == 0, output
    code, output = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--story", "ENG-1",
    )
    assert code == 0, output
    saved = next((repo / "plans" / "active").glob("ENG-1-*.md"))
    exact_text = saved.read_text(encoding="utf-8")
    assert exact_text == brief
    assert "---" not in exact_text
    metadata_path = repo / ".factory" / "stories" / "ENG-1" / "plan-meta.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert set(metadata) == {
        "issue", "story", "title", "status", "saved", "plan_file",
        "decisions_in_force",
    }
    assert metadata["decisions_in_force"] == active_decision_ids(repo)
    assert "decisions_reviewed" not in metadata
    candidate = approval.eligible_candidates(repo)[0]
    event = _event(candidate)
    assert event["tool_input"]["plan"] == exact_text
    record = approval.record_native_approval(repo, event, runtime="claude")
    assert record["approved_plan_sha256"] == candidate.digest
    assert saved.read_text(encoding="utf-8") == exact_text
    assert json.loads(metadata_path.read_text(encoding="utf-8"))["status"] == "approved"
    assert json.loads(load_factory_lib(repo).run_state_path(repo).read_text())["plan_status"] == "approved"


def test_brief_plan_refuses_decision_accepted_after_its_grill(repo: Path, tmp_path: Path):
    sign_off(repo)
    code, output = intake(repo)
    assert code == 0, output
    brief = (
        "## What and why\n\nPeople need a clear invoice workflow.\n\n"
        "## What changes for you\n\nInvoices are easier to review.\n\n"
        "## Done when\n\nA user can create and review an invoice.\n\n"
        "## Risks\n\nExisting records must remain readable.\n\n"
        "## Technical approach\n\nUse the existing invoice service.\n\n"
        "## Task decomposition\n\nImplement the user flow and its checks.\n\n"
        "## Verify plan\n\nRun the focused invoice checks.\n"
    )
    draft = tmp_path / "brief-plan.md"
    draft.write_text(brief, encoding="utf-8")
    code, output = record_grill(repo, "plan", digest_of=draft)
    assert code == 0, output
    code, output = run(repo, "forge.py", "decision", "new", "after-grill",
                       "--repo", str(repo))
    assert code == 0, output
    code, output = run(repo, "forge.py", "decision", "accept", "after-grill",
                       "--by", "PM", "--repo", str(repo))
    assert code == 0, output

    code, output = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--story", "ENG-1",
    )

    assert code != 0
    assert "a decision was accepted after the plan grill; re-grill" in output
    assert not list((repo / "plans" / "active").glob("*.md"))


def test_body_only_plan_approval_uses_matching_run_state(repo: Path):
    candidate = _story_candidate(repo)
    body = "# Brief plan\n\nApproved exact body.\n"
    candidate.path.write_text(body, encoding="utf-8")
    lib = load_factory_lib(repo)
    digest = lib.plan_digest_without_assumptions(candidate.path)
    grill_path = lib.evidence_path(repo, candidate.story, "grills/plan.json")
    grill = json.loads(grill_path.read_text(encoding="utf-8"))
    grill["input_sha256"] = digest
    lib.dump_json(grill_path, grill)
    metadata_path = repo / ".factory" / "stories" / candidate.story / "plan-meta.json"
    metadata_path.unlink(missing_ok=True)

    candidate = approval._story_candidate(repo)
    assert candidate is not None
    approval.record_native_approval(repo, _event(candidate), runtime="claude")

    assert candidate.path.read_text(encoding="utf-8") == body
    assert not metadata_path.exists()
    assert json.loads(lib.run_state_path(repo).read_text())["plan_status"] == "approved"


@pytest.mark.parametrize("body", ["{not json\n", "[]\n"])
def test_native_approval_malformed_run_state_is_a_controlled_refusal(
        repo: Path, body: str):
    lib = load_factory_lib(repo)
    path = lib.run_state_path(repo)
    path.write_text(body, encoding="utf-8")
    with pytest.raises(approval.ApprovalRefused, match="run state"):
        approval.eligible_candidates(repo)


def test_awaiting_story_edit_is_ineligible_until_its_plan_grill_matches(
        repo: Path):
    candidate = _story_candidate(repo)
    grill = candidate.evidence.parent / "grills" / "plan.json"
    original_grill = grill.read_bytes()
    candidate.path.write_text(
        candidate.path.read_text(encoding="utf-8") + "\nEdited before approval.\n",
        encoding="utf-8",
    )

    assert approval._story_candidate(repo) is None
    assert grill.read_bytes() == original_grill


def test_recorder_accepts_amended_cold_draft_before_story_plan_save(
        repo: Path, tmp_path: Path):
    from test_gates import _seed_cold_launch

    sign_off(repo)
    code, out = intake(repo)
    assert code == 0, out
    draft = tmp_path / "cold-plan.md"
    cold = plan_draft(repo)
    draft.write_text(cold, encoding="utf-8")
    finding = "State the repository fact needed by the plan."
    _seed_cold_launch(
        repo, "plan", hashlib.sha256(cold.encode()).hexdigest(),
        artifact_text=cold,
        findings={"gaps": [finding], "contradictions": []},
    )
    final = cold + "\nResolved repository fact.\n"
    draft.write_text(final, encoding="utf-8")
    payload = {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [finding], "contradictions": [],
        "resolutions": ["Added the repository fact."],
        "finding_dispositions": [{
            "finding": finding,
            "resolution": "Added the repository fact.",
            "source": "factory/scripts/record_grill_from_json.py",
        }],
        "amendments": [{
            "delta_index": 0, "findings": [finding],
            "change": "Added the repository fact.",
            "reason": "Closes the cold-read finding.",
            "source": "factory/scripts/record_grill_from_json.py",
        }],
        "artifact_delta": _artifact_delta(cold, final),
    }
    code, out = run(
        repo, "record_grill_from_json.py", "--gate", "plan",
        "--input-digest", str(draft), stdin=json.dumps(payload),
    )
    assert code == 0, out
    grill_path = repo / ".factory" / "stories" / "ENG-1" / "grills" / "plan.json"
    grill = json.loads(grill_path.read_text(encoding="utf-8"))
    assert grill["input_sha256"] == load_factory_lib(repo).plan_digest_without_assumptions(
        draft,
    )
    assert grill["cold_input_sha256"] == hashlib.sha256(cold.encode()).hexdigest()
    assert grill["final_artifact_sha256"] == hashlib.sha256(
        final.encode(),
    ).hexdigest()

    code, out = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--story", "ENG-1",
    )
    assert code == 0 and "awaiting-approval" in out, out
    candidate = approval._story_candidate(repo)
    assert candidate is not None
    record = approval.record_native_approval(
        repo, _event(candidate), runtime="claude",
    )
    assert record["approved_plan_sha256"] == candidate.digest


def test_native_approval_revalidates_candidate_before_first_mutation(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    candidate = _story_candidate(repo)
    event = _event(candidate)
    calls = 0

    def changing_candidates(_base: Path):
        nonlocal calls
        calls += 1
        return [candidate] if calls == 1 else []

    monkeypatch.setattr(approval, "eligible_candidates", changing_candidates)
    with pytest.raises(approval.ApprovalRefused, match="changed before publication"):
        approval.record_native_approval(repo, event, runtime="claude")
    assert not (candidate.evidence.parent / "approval-events").exists()
    assert "status: awaiting-approval" in candidate.path.read_text(encoding="utf-8")


def test_phase_refuses_approved_status_without_native_approval_authority(
        repo: Path):
    from forge_cli.phase import (
        _approved_plan_authority_state, _approved_plan_changed,
    )

    candidate = _story_candidate(repo)
    approval.record_native_approval(repo, _event(candidate), runtime="claude")
    lib = load_factory_lib(repo)
    state = json.loads(lib.run_state_path(repo).read_text(encoding="utf-8"))
    assert _approved_plan_changed(repo, state) is False
    authority_bytes = candidate.evidence.read_bytes()
    candidate.evidence.unlink()
    assert _approved_plan_changed(repo, state) is False
    assert _approved_plan_authority_state(repo, state) == "repair"
    lib.dump_json(candidate.evidence, {
        "approved_plan_sha256": candidate.digest,
        "issue": candidate.story, "story": candidate.story,
        "approver": "Legacy Human",
        "at": "2026-01-01T00:00:00+00:00",
    })
    assert _approved_plan_authority_state(repo, state) == "upgrade"
    candidate.evidence.write_bytes(authority_bytes)
    candidate.path.write_text(
        candidate.path.read_text(encoding="utf-8") + "\nChanged bytes.\n",
        encoding="utf-8",
    )
    assert _approved_plan_authority_state(repo, state) == "changed"


def test_legacy_exact_plan_approval_is_reachable_and_upgrade_preflight_allows_it(
        repo: Path):
    candidate = _story_candidate(repo)
    lib = load_factory_lib(repo)
    candidate.path.write_text(
        candidate.path.read_text(encoding="utf-8").replace(
            "status: awaiting-approval", "status: approved", 1,
        ),
        encoding="utf-8",
    )
    state_path = lib.run_state_path(repo)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(plan_status="approved", approved_plan_sha256=candidate.digest)
    lib.dump_json(state_path, state)
    lib.dump_json(candidate.evidence, {
        "approved_plan_sha256": candidate.digest,
        "issue": candidate.story, "story": candidate.story,
        "approver": "Legacy Human", "at": "2026-01-01T00:00:00+00:00",
    })
    plan_grill = repo / ".factory" / "grills" / "plan.json"
    lib.dump_json(plan_grill, {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [], "contradictions": [], "resolutions": [],
    })
    recovered = approval.eligible_candidates(repo)
    assert recovered == [candidate]
    before = {
        path: path.read_bytes() if path.exists() else None
        for path in (candidate.path, candidate.evidence, state_path, plan_grill)
    }
    migration = upgrade.preflight_lean_migration(repo)
    assert migration is not None
    assert any(
        entry.get("family") == "manual-plan-approval"
        and entry.get("classification") == "eligible"
        and entry.get("path") == candidate.evidence.relative_to(repo).as_posix()
        for entry in migration.get("entries") or []
    )
    assert {
        path: path.read_bytes() if path.exists() else None
        for path in before
    } == before

    approval.record_native_approval(repo, _event(recovered[0]), runtime="claude")
    assert approval.eligible_candidates(repo) == []


def _completed_deleted_plan_approval_fixture(repo: Path):
    sign_off(repo)
    intake(repo)
    candidate = _story_candidate(repo)
    lib = load_factory_lib(repo)
    legacy = {
        "approved_plan_sha256": candidate.digest,
        "issue": candidate.story, "story": candidate.story,
        "approver": "Legacy Human", "at": "2026-01-01T00:00:00+00:00",
    }
    lib.dump_json(candidate.evidence, legacy)
    lib.dump_json(repo / ".factory" / "grills" / "plan.json", {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [], "contradictions": [], "resolutions": [],
    })
    migration = upgrade.preflight_lean_migration(repo)
    assert migration is not None
    upgrade.apply_lean_migration(repo, migration)
    assert not candidate.evidence.exists()
    state = json.loads(lib.run_state_path(repo).read_text(encoding="utf-8"))
    state.update(plan_status="approved", approved_plan_sha256=candidate.digest)
    lib.dump_json(lib.run_state_path(repo), state)
    return candidate, repo / ".factory" / "migrations" / "lean-workflow-v2.json"


def test_completed_deleted_plan_approval_manifest_offers_one_native_candidate(
        repo: Path):
    candidate, _manifest = _completed_deleted_plan_approval_fixture(repo)

    recovered = approval.eligible_candidates(repo)
    assert len(recovered) == 1
    assert recovered[0].kind == "story"
    code, output = run(repo, "forge.py", "next")
    assert code == 0, output
    assert "native Plan Mode" in output
    approval.record_native_approval(
        repo, _event(recovered[0], "codex"), runtime="codex",
    )
    assert approval.eligible_candidates(repo) == []


@pytest.mark.parametrize("mutation", ["missing", "tampered", "wrong-path", "digest"])
def test_completed_deleted_plan_approval_refuses_incomplete_manifest_lineage(
        repo: Path, mutation: str):
    _candidate, manifest_path = _completed_deleted_plan_approval_fixture(repo)
    if mutation == "missing":
        manifest_path.unlink()
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = next(
            row for row in manifest["entries"]
            if row.get("family") == "manual-plan-approval"
        )
        if mutation == "tampered":
            manifest["completed_at"] = ""
        elif mutation == "wrong-path":
            entry["path"] = "plans/active/not-the-approved-plan.json"
        else:
            entry["sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert approval.eligible_candidates(repo) == []


def test_completed_deleted_plan_approval_searches_authenticated_prior_completion(
        repo: Path, monkeypatch):
    """A later supported supplement keeps the deleted approval in prior data."""
    from test_upgrade_lean_workflow import _history_fixed_review, _sealed_fixed_review

    sign_off(repo)
    intake(repo)
    _sealed_fixed_review(repo)
    candidate = _story_candidate(repo)
    lib = load_factory_lib(repo)
    lib.dump_json(candidate.evidence, {
        "approved_plan_sha256": candidate.digest,
        "issue": candidate.story, "story": candidate.story,
        "approver": "Legacy Human", "at": "2026-01-01T00:00:00+00:00",
    })
    lib.dump_json(repo / ".factory" / "grills" / "plan.json", {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [], "contradictions": [], "resolutions": [],
    })
    empty_digest = upgrade._inventory_digest([])
    manifest = repo / ".factory" / "migrations" / "lean-workflow-v2.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({
        "generated_by": "upgrade", "version": "lean-workflow-v2",
        "input_inventory_digest": empty_digest, "output_digest": empty_digest,
        "installed_runtime_digest": (
            "bb4b6c05b41897447063959fc782e9ca4c2e00f9b219559314b725485b91b2e8"
        ),
        "entries": [], "recorded_at": "2026-09-14T05:48:01+00:00",
        "completed_at": "2026-09-14T05:48:01+00:00",
    }) + "\n", encoding="utf-8")

    first = upgrade.preflight_lean_migration(repo)
    assert first is not None
    upgrade.apply_lean_migration(repo, first)
    supplement = manifest.with_name(upgrade.LEAN_MIGRATION_SUPPLEMENT)
    prior = json.loads(supplement.read_text(encoding="utf-8"))
    assert any(entry.get("family") == "manual-plan-approval"
               for entry in prior["entries"])

    state = json.loads(lib.run_state_path(repo).read_text(encoding="utf-8"))
    state.update(plan_status="approved", approved_plan_sha256=candidate.digest)
    lib.dump_json(lib.run_state_path(repo), state)
    _history_fixed_review(repo)
    import factory_lib
    monkeypatch.setattr(factory_lib, "product_delta_digest", lambda *_args: "f" * 64)
    extension = upgrade.preflight_lean_migration(repo)
    assert extension is not None
    upgrade.apply_lean_migration(repo, extension)
    completed = json.loads(supplement.read_text(encoding="utf-8"))
    assert completed["prior_completion"] == prior
    assert any(entry.get("family") == "manual-plan-approval"
               for entry in completed["prior_completion"]["entries"])
    assert approval.eligible_candidates(repo) == [candidate]


def test_public_upgrade_retry_after_native_reapproval_does_not_keep_legacy_gate(
        repo: Path):
    sign_off(repo)
    intake(repo)
    candidate = _story_candidate(repo)
    lib = load_factory_lib(repo)
    candidate.path.write_text(
        candidate.path.read_text(encoding="utf-8").replace(
            "status: awaiting-approval", "status: approved", 1,
        ),
        encoding="utf-8",
    )
    state_path = lib.run_state_path(repo)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(plan_status="approved", approved_plan_sha256=candidate.digest)
    lib.dump_json(state_path, state)
    lib.dump_json(candidate.evidence, {
        "approved_plan_sha256": candidate.digest,
        "issue": candidate.story, "story": candidate.story,
        "approver": "Legacy Human", "at": "2026-01-01T00:00:00+00:00",
    })
    lib.dump_json(repo / ".factory" / "grills" / "plan.json", {
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [], "contradictions": [], "resolutions": [],
    })

    def public_upgrade():
        return subprocess.run(
            [sys.executable, str(HARNESS / "factory/scripts/forge.py"),
             "upgrade", "--target", str(repo)],
            cwd=HARNESS, capture_output=True, text=True,
        )

    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "legacy approval recovery fixture")
    first = public_upgrade()
    code, output = first.returncode, first.stdout + first.stderr
    assert code == 0, output
    assert (
        f"re-approve {candidate.path.relative_to(repo)} in native Plan Mode after upgrade"
        in output
    )

    assert approval.eligible_candidates(repo) == [candidate]
    code, output = run(repo, "forge.py", "next")
    assert code == 0, output
    assert "native Plan Mode" in output
    approval.record_native_approval(repo, _event(candidate), runtime="claude")
    assert approval.eligible_candidates(repo) == []


def test_legacy_plan_approval_requires_exact_issue_and_story_binding(repo: Path):
    candidate = _story_candidate(repo)
    lib = load_factory_lib(repo)
    candidate.path.write_text(
        candidate.path.read_text(encoding="utf-8").replace(
            "status: awaiting-approval", "status: approved", 1,
        ),
        encoding="utf-8",
    )
    state_path = lib.run_state_path(repo)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(plan_status="approved", approved_plan_sha256=candidate.digest)
    lib.dump_json(state_path, state)
    lib.dump_json(candidate.evidence, {
        "approved_plan_sha256": candidate.digest,
        "issue": "OTHER-ISSUE", "story": candidate.story,
        "approver": "Legacy Human", "at": "2026-01-01T00:00:00+00:00",
    })
    assert approval.eligible_candidates(repo) == []


@pytest.mark.parametrize("body", [b"\xff", b"[]\n"])
def test_forge_next_routes_malformed_plan_approval_to_authority_repair(
        repo: Path, tmp_path: Path, body: bytes):
    sign_off(repo)
    intake(repo)
    code, out = save_plan(repo, tmp_path)
    assert code == 0, out
    (story_state(repo) / "plan-approval.json").write_bytes(body)
    code, out = run(repo, "forge.py", "next")
    assert code == 0, out
    assert "planning authority repair required" in out


def test_story_approval_refuses_unknown_runtime_even_with_matching_replay(
        repo: Path):
    candidate = _story_candidate(repo)
    record = approval.record_native_approval(
        repo, _event(candidate), runtime="claude",
    )
    lib = load_factory_lib(repo)
    old_replay = next(
        path for path in candidate.evidence.parent.glob(
            "approval-events/*.json")
        if json.loads(path.read_text()).get("event_id") == record["event_id"]
    )
    forged = dict(record)
    forged["runtime"] = "unknown"
    forged.pop("approved_by")
    replay_key = hashlib.sha256(
        f"unknown\0{record['session_id']}\0{record['event_id']}".encode()
    ).hexdigest()
    old_replay.unlink()
    replay = old_replay.parent / f"{replay_key}.json"
    lib.dump_json(replay, forged)
    lib.dump_json(candidate.evidence, forged)
    assert not lib._native_story_approval_recorded(repo, candidate.story, forged)
    forged.pop("runtime")
    replay.unlink()
    replay_key = hashlib.sha256(
        f"None\0{record['session_id']}\0{record['event_id']}".encode()
    ).hexdigest()
    replay = old_replay.parent / f"{replay_key}.json"
    lib.dump_json(replay, forged)
    lib.dump_json(candidate.evidence, forged)
    assert not lib._native_story_approval_recorded(repo, candidate.story, forged)

    for runtime in ("claude", "codex"):
        control = _story_candidate(repo, story=f"CONTROL-{runtime}")
        stored = approval.record_native_approval(
            repo, _event(control, runtime), runtime=runtime,
        )
        assert lib._native_story_approval_recorded(
            repo, control.story, stored,
        )


def test_approved_story_edit_is_the_only_candidate_and_rebinds_atomically(
        repo: Path):
    candidate = _story_candidate(repo)
    original = approval.record_native_approval(
        repo, _event(candidate), runtime="claude",
    )
    candidate.path.write_text(
        candidate.path.read_text(encoding="utf-8") + "\nApproved amendment.\n",
        encoding="utf-8",
    )
    lib = load_factory_lib(repo)
    amended_digest = lib.plan_digest_without_assumptions(candidate.path)
    candidates = approval.eligible_candidates(repo)
    assert [(row.kind, row.digest) for row in candidates] == [
        ("story", amended_digest),
    ]
    protected = lib.protected_decomposition_state_path(repo)
    authority_before = (
        candidate.path.read_bytes(),
        candidate.evidence.read_bytes(),
        lib.run_state_path(repo).read_bytes(),
        protected.read_bytes() if protected.is_file() else None,
        sorted(
            path.read_bytes()
            for path in (candidate.evidence.parent / "approval-events").glob("*.json")
        ),
    )

    stale = _event(candidates[0])
    stale["tool_input"] = {"plan": "# stale plan\n"}
    with pytest.raises(approval.ApprovalRefused, match="found 0 matching candidates"):
        approval.record_native_approval(repo, stale, runtime="claude")
    cancelled = {**_event(candidates[0]), "cancelled": True}
    with pytest.raises(approval.ApprovalRefused, match="unsuccessful"):
        approval.record_native_approval(repo, cancelled, runtime="claude")
    assert (
        candidate.path.read_bytes(),
        candidate.evidence.read_bytes(),
        lib.run_state_path(repo).read_bytes(),
        protected.read_bytes() if protected.is_file() else None,
        sorted(
            path.read_bytes()
            for path in (candidate.evidence.parent / "approval-events").glob("*.json")
        ),
    ) == authority_before
    state = json.loads(lib.run_state_path(repo).read_text())
    assert state["approved_plan_sha256"] == original["approved_plan_sha256"]

    amended = approval.record_native_approval(
        repo, _event(candidates[0]), runtime="claude",
    )
    state = json.loads(lib.run_state_path(repo).read_text())
    assert amended["approved_plan_sha256"] == amended_digest
    assert amended["previous_approved_plan_sha256"] \
        == original["approved_plan_sha256"]
    assert state["approved_plan_sha256"] == amended_digest
    assert "status: approved" in candidate.path.read_text(encoding="utf-8")
    assert json.loads(candidate.evidence.read_text())["approved_plan_sha256"] \
        == amended_digest
    assert lib.approved_story_plan_predecessors(repo, amended_digest) == (
        original["approved_plan_sha256"],
    )

    replay = next(
        path for path in (candidate.evidence.parent / "approval-events").glob("*.json")
        if json.loads(path.read_text()) == amended
    )
    replay_bytes = replay.read_bytes()
    replay.write_text(json.dumps({**amended, "story": "OTHER"}))
    assert lib.approved_story_plan_predecessors(repo, amended_digest) == ()
    replay.write_bytes(replay_bytes)
    approval_bytes = candidate.evidence.read_bytes()
    candidate.evidence.write_text("[]\n", encoding="utf-8")
    assert lib.approved_story_plan_predecessors(repo, amended_digest) == ()
    candidate.evidence.write_bytes(approval_bytes)
    replay.write_text("[]\n", encoding="utf-8")
    assert lib.approved_story_plan_predecessors(repo, amended_digest) == ()
    replay.write_bytes(replay_bytes)
    predecessor = next(
        path for path in (candidate.evidence.parent / "approval-events").glob("*.json")
        if json.loads(path.read_text()).get("event_id") == original["event_id"]
    )
    predecessor_bytes = predecessor.read_bytes()
    predecessor.unlink()
    assert lib.approved_story_plan_predecessors(repo, amended_digest) == ()
    predecessor.write_bytes(predecessor_bytes)
    assert lib.approved_story_plan_predecessors(repo, amended_digest) == (
        original["approved_plan_sha256"],
    )


def test_task_approval_waits_for_story_approval_and_decomposition_rebinding(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    story = _story_candidate(repo)
    approval.record_native_approval(repo, _event(story), runtime="claude")
    lib = load_factory_lib(repo)
    task = {"id": "T1"}
    monkeypatch.setattr(
        approval, "task_frontier_state", lambda _base: ("await-approval", task),
    )
    task_plan = lib.evidence_path(
        repo, "APPROVE-1", "task-plans/T1.md", for_write=True,
    )
    task_plan.parent.mkdir(parents=True, exist_ok=True)
    task_plan.write_text("# Task plan\n", encoding="utf-8")
    task_digest = lib.plan_digest_without_assumptions(task_plan)
    task_grill = lib.evidence_path(
        repo, "APPROVE-1", "grills/tasks/T1.json", for_write=True,
    )
    lib.dump_json(task_grill, {
        "verdict": "pass", "task_plan_sha256": task_digest,
        "cold_input_sha256": task_digest,
        "final_artifact_sha256": task_digest,
        "finding_dispositions": [],
    })
    decomposition = lib.protected_decomposition_state_path(repo)
    decomposition.unlink(missing_ok=True)

    assert approval._task_candidate(repo) is None
    story_digest = lib.plan_digest_without_assumptions(story.path)
    lib.dump_json(decomposition, {
        "plan_sha256": story_digest, "tasks": [task],
    })
    assert approval._task_candidate(repo) is not None

    story.path.write_text(
        story.path.read_text(encoding="utf-8") + "\nAnother amendment.\n",
        encoding="utf-8",
    )
    assert approval._task_candidate(repo) is None
    assert [row.kind for row in approval.eligible_candidates(repo)] == ["story"]


def test_task_approval_requires_exact_approval_frontier(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    story = _story_candidate(repo)
    approval.record_native_approval(repo, _event(story), runtime="claude")
    lib = load_factory_lib(repo)
    task = {"id": "T1"}
    task_plan = lib.evidence_path(
        repo, "APPROVE-1", "task-plans/T1.md", for_write=True,
    )
    task_plan.parent.mkdir(parents=True, exist_ok=True)
    task_plan.write_text("# Task plan\n", encoding="utf-8")
    task_digest = lib.plan_digest_without_assumptions(task_plan)
    task_grill = lib.evidence_path(
        repo, "APPROVE-1", "grills/tasks/T1.json", for_write=True,
    )
    lib.dump_json(task_grill, {
        "verdict": "pass", "task_plan_sha256": task_digest,
        "cold_input_sha256": task_digest,
        "final_artifact_sha256": task_digest,
        "finding_dispositions": [],
    })
    lib.dump_json(lib.protected_decomposition_state_path(repo), {
        "plan_sha256": story.digest, "tasks": [task],
    })
    before = task_grill.read_bytes()

    for action in ("grill", "author-task-plan", "stage-start", "delegate"):
        monkeypatch.setattr(
            approval, "task_frontier_state", lambda _base, value=action: (value, task),
        )
        assert approval._task_candidate(repo) is None
        assert task_grill.read_bytes() == before


def test_native_approval_refuses_zero_multiple_candidates_replay_and_missing_identity(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [])
    with pytest.raises(approval.ApprovalRefused, match="found 0"):
        approval.record_native_approval(repo, _event(candidate), runtime="claude")

    monkeypatch.setattr(
        approval, "eligible_candidates", lambda _base: [candidate, candidate])
    with pytest.raises(approval.ApprovalRefused, match="found 2"):
        approval.record_native_approval(repo, _event(candidate), runtime="claude")

    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    missing = _event(candidate)
    missing.pop("tool_use_id")
    with pytest.raises(approval.ApprovalRefused, match="stable session and event"):
        approval.record_native_approval(repo, missing, runtime="claude")

    event = _event(candidate)
    approval.record_native_approval(repo, event, runtime="claude")
    with pytest.raises(approval.ApprovalRefused, match="already consumed"):
        approval.record_native_approval(repo, event, runtime="claude")


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_native_approval_from_main_checkout_records_in_matching_task_worktree(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        runtime: str):
    task_worktree = _add_worktree(repo, tmp_path / "task-worktree")
    candidate = _task_candidate(task_worktree, monkeypatch)
    primary_candidate = _story_candidate(repo)
    assert approval.eligible_candidates(repo) == [primary_candidate]
    assert primary_candidate.digest != candidate.digest
    primary_before = (
        primary_candidate.path.read_bytes(),
        load_factory_lib(repo).run_state_path(repo).read_bytes(),
    )

    recorded_in: list[str] = []
    record = approval.record_native_approval(
        repo, _event(candidate, runtime), runtime=runtime,
        recorded_in=recorded_in,
    )

    assert record["plan_kind"] == "task"
    assert recorded_in == [str(task_worktree.resolve())]
    stored = json.loads(candidate.evidence.read_text(encoding="utf-8"))
    assert stored["approved_task_plan_sha256"] == candidate.digest
    assert (
        primary_candidate.path.read_bytes(),
        load_factory_lib(repo).run_state_path(repo).read_bytes(),
    ) == primary_before
    assert not primary_candidate.evidence.exists()
    assert not (repo / ".factory" / "stories" / candidate.story
                / "grills" / "tasks" / f"{candidate.task}.json").exists()


def test_native_approval_refuses_event_consumed_in_another_worktree(
        repo: Path, tmp_path: Path):
    first_root = _add_worktree(repo, tmp_path / "first-worktree")
    first = _story_candidate(first_root)
    event = _event(first)
    approval.record_native_approval(first_root, event, runtime="claude")
    tombstone = next((first.evidence.parent / "approval-events").glob("*.json"))

    second_root = _add_worktree(repo, tmp_path / "second-worktree")
    second = _story_candidate(second_root)
    assert second.digest == first.digest
    second_lib = load_factory_lib(second_root)
    state_path = second_lib.run_state_path(second_root)
    events_dir = second_root / ".factory" / "events"
    before = (
        second.path.read_bytes(), state_path.read_bytes(),
        second.evidence.read_bytes() if second.evidence.exists() else None,
        {path.name: path.read_bytes() for path in events_dir.glob("*.json")},
    )

    with pytest.raises(approval.ApprovalRefused, match="already consumed"):
        approval.record_native_approval(repo, event, runtime="claude")

    assert (
        second.path.read_bytes(), state_path.read_bytes(),
        second.evidence.read_bytes() if second.evidence.exists() else None,
        {path.name: path.read_bytes() for path in events_dir.glob("*.json")},
    ) == before
    assert not (second.evidence.parent / "approval-events").exists()
    assert tombstone.is_file()


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_native_approval_hooks_report_routed_worktree(
        repo: Path, tmp_path: Path, runtime: str):
    target = _add_worktree(repo, tmp_path / "approval-worktree")
    candidate = _story_candidate(target)

    code, output = run(
        repo, "forge.py", "hook", "post_tool_use",
        stdin=json.dumps(_event(candidate, runtime)),
    )

    context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
    assert code == 0 and "recorded native story plan approval" in context
    assert str(target.resolve()) in context
    assert candidate.evidence.is_file()


def test_native_approval_refuses_when_no_worktree_has_an_eligible_candidate(
        repo: Path):
    candidate = _story_candidate(repo)
    lib = load_factory_lib(repo)
    state_path = lib.run_state_path(repo)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["plan_status"] = "planning"
    lib.dump_json(state_path, state)
    before = (candidate.path.read_bytes(), state_path.read_bytes())

    with pytest.raises(approval.ApprovalRefused, match="found 0 matching") as refused:
        approval.record_native_approval(repo, _event(candidate), runtime="claude")

    assert str(repo.resolve()) in str(refused.value)
    assert (candidate.path.read_bytes(), state_path.read_bytes()) == before
    assert not candidate.evidence.exists()


def test_native_approval_refuses_two_matching_registered_worktrees(
        repo: Path, tmp_path: Path):
    first_root = _add_worktree(repo, tmp_path / "first-worktree")
    first = _story_candidate(first_root)
    second_root = _add_worktree(repo, tmp_path / "second-worktree")
    second = _story_candidate(second_root)
    assert first.digest == second.digest

    with pytest.raises(approval.ApprovalRefused, match="found 2 matching") as refused:
        approval.record_native_approval(repo, _event(first), runtime="claude")

    message = str(refused.value)
    assert str(first_root.resolve()) in message
    assert str(second_root.resolve()) in message
    assert not first.evidence.exists() and not second.evidence.exists()


def test_native_approval_refuses_same_digest_in_current_and_registered_worktree(
        repo: Path, tmp_path: Path):
    current = _story_candidate(repo)
    worktree = _add_worktree(repo, tmp_path / "matching-worktree")
    matching = _story_candidate(worktree)
    assert current.digest == matching.digest
    before = (
        current.path.read_bytes(), current.evidence.exists(),
        matching.path.read_bytes(), matching.evidence.exists(),
    )

    with pytest.raises(
            approval.ApprovalRefused,
            match="found 2 matching candidates") as refused:
        approval.record_native_approval(repo, _event(current), runtime="claude")

    message = str(refused.value)
    assert str(repo.resolve()) in message
    assert str(worktree.resolve()) in message
    assert current.digest in message
    assert (
        current.path.read_bytes(), current.evidence.exists(),
        matching.path.read_bytes(), matching.evidence.exists(),
    ) == before


def test_native_approval_refuses_digest_missing_from_registered_worktrees(
        repo: Path, tmp_path: Path):
    target = _add_worktree(repo, tmp_path / "candidate-worktree")
    candidate = _story_candidate(target)
    event = _event(candidate)
    event["tool_input"]["plan"] += "\nDifferent displayed plan.\n"
    grill = candidate.evidence.parent / "grills" / "plan.json"
    before = (candidate.path.read_bytes(), grill.read_bytes())

    with pytest.raises(approval.ApprovalRefused, match="found 0 matching") as refused:
        approval.record_native_approval(repo, event, runtime="claude")

    message = str(refused.value)
    assert str(target.resolve()) in message
    assert candidate.digest in message
    assert (candidate.path.read_bytes(), grill.read_bytes()) == before


def test_claude_approval_refusal_reports_uncommitted_decision(repo: Path):
    candidate = _story_candidate(repo)
    decision = repo / "docs" / "decisions" / "decision-uncommitted.md"
    decision.parent.mkdir(parents=True, exist_ok=True)
    decision.write_text("# Pending decision\n", encoding="utf-8")

    with pytest.raises(approval.ApprovalRefused) as refused:
        approval.record_native_approval(
            repo, _event(candidate), runtime="claude",
        )

    message = str(refused.value)
    assert decision.relative_to(repo).as_posix() in message
    assert "commit it, then run `forge grill run --gate plan` again" in message.lower()


def test_codex_approval_refuses_non_list_options_without_raising_type_error(repo):
    candidate = _story_candidate(repo)
    event = _event(candidate, "codex")
    event["tool_input"]["questions"][0]["options"] = None

    with pytest.raises(approval.ApprovalRefused, match="unsupported or unsuccessful"):
        approval.record_native_approval(repo, event, runtime="codex")

    assert not candidate.evidence.exists()


@pytest.mark.parametrize("status", ["", "pending", "unknown", "rejected"])
def test_claude_approval_requires_affirmative_success_without_mutation(
        repo: Path, status: str):
    candidate = _story_candidate(repo)
    event = _event(candidate)
    event["tool_response"]["status"] = status
    lib = load_factory_lib(repo)
    before = (candidate.path.read_bytes(), lib.run_state_path(repo).read_bytes())

    with pytest.raises(approval.ApprovalRefused, match="unsuccessful"):
        approval.record_native_approval(repo, event, runtime="claude")

    assert (candidate.path.read_bytes(), lib.run_state_path(repo).read_bytes()) == before
    assert not candidate.evidence.exists()


@pytest.mark.parametrize("status", ["success", "succeeded", "completed"])
def test_claude_approval_accepts_supported_success_statuses(repo: Path, status: str):
    candidate = _story_candidate(repo)
    event = _event(candidate)
    event["tool_response"]["status"] = status

    record = approval.record_native_approval(repo, event, runtime="claude")

    assert record["approved_plan_sha256"] == candidate.digest


def test_claude_approval_hook_reports_refusal_and_recording(repo: Path):
    candidate = _story_candidate(repo)
    event = _event(candidate)
    event["tool_response"]["status"] = "cancelled"

    code, out = run(repo, "forge.py", "hook", "post_tool_use", stdin=json.dumps(event))
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert code == 0 and "did NOT record" in context and "unsuccessful" in context
    assert not candidate.evidence.exists()

    event["tool_response"]["status"] = "success"
    code, out = run(repo, "forge.py", "hook", "post_tool_use", stdin=json.dumps(event))
    context = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert code == 0 and f"recorded native story plan approval {candidate.digest}" in context


def test_codex_approval_hook_reports_refusal(repo: Path):
    candidate = _story_candidate(repo)
    event = _event(candidate, "codex")
    event["tool_input"]["questions"][0]["question"] = "Review this plan?"

    code, out = run(repo, "forge.py", "hook", "post_tool_use", stdin=json.dumps(event))

    output = json.loads(out)
    assert code == 0
    assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "Forge did NOT record this plan approval" in context
    assert "unsupported" in context
    assert not candidate.evidence.exists()


def test_codex_ordinary_question_hook_is_silent(repo: Path):
    event = {
        "tool_name": "request_user_input",
        "tool_input": {"questions": [{
            "id": "clarify_environment", "header": "Environment",
            "question": "Which environment should I use?", "options": [],
        }]},
        "tool_response": {"answers": {}},
    }

    code, output = run(
        repo, "forge.py", "hook", "post_tool_use", stdin=json.dumps(event),
    )

    assert code == 0
    assert output == ""


def test_plan_save_and_awaiting_phase_show_codex_approval_identity(
        repo: Path, tmp_path: Path):
    sign_off(repo)
    code, output = intake(repo)
    assert code == 0, output
    draft = tmp_path / "codex-plan.md"
    draft.write_text(plan_draft(repo), encoding="utf-8")
    code, output = record_grill(repo, "plan", digest_of=draft)
    assert code == 0, output
    code, output = run(
        repo, "forge.py", "plan", "save", "--from", str(draft),
        "--story", "ENG-1",
    )
    assert code == 0, output
    candidates = approval.eligible_candidates(repo)
    assert len(candidates) == 1
    digest = candidates[0].digest
    question_id = f"approve_plan_{digest}"
    question = "Approve this plan?"
    assert f"Semantic digest: {digest}" in output
    assert question_id in output
    assert 'header="Approve plan"' in output
    assert f'question="{question}"' in output
    assert "Approve exact plan digest" not in output

    code, output = run(repo, "forge.py", "next")
    assert code == 0, output
    assert f'id="{question_id}"' in output
    assert 'header="Approve plan"' in output
    assert 'question="Approve this plan?"' in output


@pytest.mark.parametrize("plan_file", ["", "plans/active/missing-plan.md"])
def test_awaiting_approval_next_handles_missing_plan_file(repo: Path, plan_file: str):
    sign_off(repo)
    code, output = intake(repo)
    assert code == 0, output
    lib = load_factory_lib(repo)
    state_path = lib.run_state_path(repo)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(plan_status="awaiting-approval", plan_file=plan_file)
    lib.dump_json(state_path, state)

    code, output = run(repo, "forge.py", "next")

    assert code == 0, output
    assert "saved plan file" in output
    assert "is missing" in output


def test_claude_no_argument_exit_plan_mode_approves_from_response(repo: Path):
    candidate = _story_candidate(repo)
    event = _event(candidate)
    plan = event["tool_input"].pop("plan")
    event["tool_response"] = {"plan": plan, "isAgent": False, "filePath": "/x/plan.md"}

    record = approval.record_native_approval(repo, event, runtime="claude")

    assert record["approved_plan_sha256"] == candidate.digest


@pytest.mark.parametrize("location", ["scoped", "archived", "legacy"])
def test_native_approval_refuses_cross_story_host_event_replay_without_mutation(
        repo: Path, location: str):
    if location != "legacy":
        (repo / ".factory" / "stories" / "APPROVE-1").mkdir(parents=True)
    first = _story_candidate(repo)
    event = _event(first)
    approval.record_native_approval(repo, event, runtime="claude")
    lib = load_factory_lib(repo)
    tombstone = next((first.evidence.parent / "approval-events").glob("*.json"))
    destination = tombstone
    if location in {"archived", "legacy"}:
        destination = (repo / ".factory" / "history" / first.story / "approval-events"
                       if location == "archived" else repo / ".factory" / "approval-events") / tombstone.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        tombstone.rename(destination)
    (repo / ".factory" / "stories" / "APPROVE-2").mkdir(parents=True)
    second = _story_candidate(repo, "APPROVE-2")
    assert second.digest == first.digest
    event["tool_input"]["plan"] = second.path.read_text(encoding="utf-8")
    before = (second.path.read_bytes(), lib.run_state_path(repo).read_bytes(),
              second.evidence.read_bytes() if second.evidence.exists() else None)
    with pytest.raises(approval.ApprovalRefused, match="already consumed"):
        approval.record_native_approval(repo, event, runtime="claude")
    assert (second.path.read_bytes(), lib.run_state_path(repo).read_bytes(),
            second.evidence.read_bytes() if second.evidence.exists() else None) == before
    assert not (repo / ".factory" / "stories" / second.story / "approval-events").exists()
    assert destination.is_file()


@pytest.mark.parametrize("runtime", ["claude", "codex"])
def test_native_approval_records_human_via_runtime_identity_without_display_name(
        repo: Path, monkeypatch: pytest.MonkeyPatch, runtime: str):
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    event = _event(candidate, runtime)
    event["runtime"] = "codex" if runtime == "claude" else "claude"
    with pytest.raises(approval.ApprovalRefused, match="contradicts its adapter"):
        approval.record_native_approval(repo, event, runtime=runtime)
    assert not candidate.evidence.exists()
    event.pop("runtime")
    record = approval.record_native_approval(repo, event, runtime=runtime)
    assert record["approved_by"] == f"human-via-{runtime.capitalize()}"
    assert record["session_id"] == event["session_id"]
    assert record["event_id"] == event["tool_use_id"]
    assert "name" not in record


def test_codex_approval_uses_question_id_and_requires_displayed_digest(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    question_id = f"approve_plan_{candidate.digest}"
    malformed_answers = [
        {question_id: "Approve plan"},
        {question_id: {}},
        {question_id: {"answers": []}},
        {question_id: {"answers": ["Approve plan", "Approve plan"]}},
        {question_id: {"answers": [1]}},
        {question_id: {"answers": ["Request changes"]}},
        {"wrong-question-id": {"answers": ["Approve plan"]}},
    ]
    for answers in malformed_answers:
        event = _event(candidate, "codex")
        event["tool_response"]["answers"] = answers
        with pytest.raises(approval.ApprovalRefused, match="unsupported"):
            approval.record_native_approval(repo, event, runtime="codex")

    event = _event(candidate, "codex")
    assert approval._codex_approved(event) == candidate.digest
    event["tool_input"]["questions"][0]["question"] = (
        f"Approve exact plan digest {candidate.digest}?"
    )
    assert approval._codex_approved(event) == candidate.digest

    stale_digest = "0" * 64
    stale_id = f"approve_plan_{stale_digest}"
    event = _event(candidate, "codex")
    event["tool_input"]["questions"][0].update({
        "id": stale_id,
        "question": f"Approve exact plan digest {stale_digest}?",
    })
    event["tool_response"]["answers"] = {
        stale_id: {"answers": ["Approve plan"]},
    }
    with pytest.raises(approval.ApprovalRefused, match="found 0 matching candidates"):
        approval.record_native_approval(repo, event, runtime="codex")


@pytest.mark.parametrize("status", ["pending", "unknown", "rejected"])
def test_codex_approval_refuses_noncompleted_explicit_status_without_mutation(
        repo: Path, status: str):
    candidate = _story_candidate(repo)
    event = _event(candidate, "codex")
    event["tool_response"]["status"] = status
    lib = load_factory_lib(repo)
    before = (candidate.path.read_bytes(), lib.run_state_path(repo).read_bytes())

    with pytest.raises(approval.ApprovalRefused, match="unsuccessful"):
        approval.record_native_approval(repo, event, runtime="codex")

    assert (candidate.path.read_bytes(), lib.run_state_path(repo).read_bytes()) == before
    assert not candidate.evidence.exists()


@pytest.mark.parametrize("status", [None, "success", "succeeded", "completed"])
def test_codex_approval_accepts_missing_or_completed_status(
        repo: Path, status: str | None):
    candidate = _story_candidate(repo)
    event = _event(candidate, "codex")
    if status is not None:
        event["tool_response"]["status"] = status

    record = approval.record_native_approval(repo, event, runtime="codex")

    assert record["approved_plan_sha256"] == candidate.digest


def test_native_approval_reuses_existing_story_and_task_approval_storage(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    story = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [story])
    record = approval.record_native_approval(repo, _event(story), runtime="claude")
    assert json.loads(story.evidence.read_text())["approved_plan_sha256"] == record[
        "approved_plan_sha256"]

    plan = repo / ".factory" / "task.md"
    plan.write_text("# task\n", encoding="utf-8")
    grill = repo / ".factory" / "task-grill.json"
    grill.write_text('{"verdict":"pass"}\n', encoding="utf-8")
    task = approval.ApprovalCandidate(
        "task", "APPROVE-1", "T1", plan,
        load_factory_lib(repo).plan_digest_without_assumptions(plan), grill,
    )
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [task])
    task_record = approval.record_native_approval(
        repo, _event(task, "codex"), runtime="codex")
    stored = json.loads(grill.read_text())
    assert stored["approved_task_plan_sha256"] == task_record["approved_plan_sha256"]
    assert stored["approval_event_id"] == task_record["event_id"]
    lib = load_factory_lib(repo)
    task_row = {"id": "T1"}
    assert lib._task_plan_approval_matches_digest(
        repo, task_row, stored, task.digest)

    replay = next(
        path for path in (story.evidence.parent / "approval-events").glob("*.json")
        if json.loads(path.read_text()).get("task") == "T1"
    )
    replay_bytes = replay.read_bytes()
    replay.unlink()
    assert not lib._task_plan_approval_matches_digest(
        repo, task_row, stored, task.digest)
    replay.write_text("{not json\n", encoding="utf-8")
    assert not lib._task_plan_approval_matches_digest(
        repo, task_row, stored, task.digest)
    replay.write_bytes(b"\xff")
    assert not lib._task_plan_approval_matches_digest(
        repo, task_row, stored, task.digest)
    replay.write_bytes(replay_bytes)
    legacy = {
        "approved_task_plan_sha256": task.digest,
        "approved_by": "Legacy Human",
        "approved_at": "2026-01-01T00:00:00+00:00",
        "task_plan_sha256": task.digest,
    }
    assert not lib._task_plan_approval_matches_digest(
        repo, task_row, legacy, task.digest)


def test_native_task_approval_preserves_exact_grill_artifact_digest(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    lib = load_factory_lib(repo)
    plan = repo / ".factory" / "task.md"
    plan.write_text("---\nstatus: approved\n---\n\n# task\n", encoding="utf-8")
    exact_digest = hashlib.sha256(plan.read_bytes()).hexdigest()
    semantic_digest = lib.plan_digest_without_assumptions(plan)
    assert exact_digest != semantic_digest

    grill = repo / ".factory" / "task-grill.json"
    lib.dump_json(grill, {"verdict": "pass", "final_artifact_sha256": exact_digest})
    candidate = approval.ApprovalCandidate(
        "task", "APPROVE-1", "T1", plan, semantic_digest, grill,
    )
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])

    record = approval.record_native_approval(
        repo, _event(candidate, "codex"), runtime="codex",
    )

    stored = json.loads(grill.read_text(encoding="utf-8"))
    assert stored["final_artifact_sha256"] == exact_digest
    assert stored["approved_task_plan_sha256"] == semantic_digest
    assert record["approved_plan_sha256"] == semantic_digest


def _recorded_lean_bootstrap_actor(lib, root: Path, runtime: str = "codex") -> str:
    story = lib._LEAN_SELF_BOOTSTRAP_STORY
    actor = {"claude": "human-via-Claude", "codex": "human-via-Codex"}[runtime]
    story_plan = root / "plans" / "active" / "lean-bootstrap.md"
    story_plan.parent.mkdir(parents=True, exist_ok=True)
    story_plan.write_text(
        f"# Story\n\n{lib._LEAN_SELF_BOOTSTRAP_CLAUSE}.\n",
        encoding="utf-8",
    )
    digest = lib.plan_digest_without_assumptions(story_plan)
    state = lib.load_json(lib.run_state_path(root), default={})
    state.update({
        "issue_key": story,
        "story": story,
        "plan_file": story_plan.relative_to(root).as_posix(),
        "plan_status": "approved",
        "approved_plan_sha256": digest,
    })
    lib.dump_json(lib.run_state_path(root), state)
    session = "bootstrap-approval-session"
    event = "bootstrap-approval-event"
    approval_record = {
        "approved_plan_sha256": digest,
        "approved_by": actor,
        "approved_at": "2026-09-18T12:00:00+00:00",
        "runtime": runtime,
        "session_id": session,
        "event_id": event,
        "plan_kind": "story",
        "story": story,
        "task": "",
    }
    event_key = hashlib.sha256(
        f"{runtime}\0{session}\0{event}".encode("utf-8")
    ).hexdigest()
    for relative, payload in (
        ("plan-approval.json", approval_record),
        (f"approval-events/{event_key}.json", approval_record),
    ):
        path = lib.evidence_path(root, story, relative, for_write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        lib.dump_json(path, payload)
    return actor


def _lean_bootstrap_grill(lib, actor: str) -> dict:
    digest = lib._LEAN_SELF_BOOTSTRAP_DIGEST
    return {
        "generated_by": "griller",
        "gate": "task",
        "verdict": "pass",
        "issue": lib._LEAN_SELF_BOOTSTRAP_STORY,
        "task_id": lib._LEAN_SELF_BOOTSTRAP_TASK,
        "final_artifact_sha256": lib._LEAN_SELF_BOOTSTRAP_FINAL_ARTIFACT_SHA256,
        "approved_task_plan_sha256": digest,
        "approved_by": actor,
        "approved_at": "2026-09-18T12:00:00+00:00",
    }


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("story", "OTHER"),
        ("task", "OTHER"),
        ("digest", "0" * 64),
        ("approved_by", "Other Human"),
        ("approved_at", "not-a-time"),
        ("approval_runtime", "claude"),
    ],
)
def test_lean_self_bootstrap_compatibility_is_exact(
        repo: Path, monkeypatch: pytest.MonkeyPatch, change: str, value: str):
    lib = load_factory_lib(repo)
    actor = _recorded_lean_bootstrap_actor(lib, repo)
    grill = _lean_bootstrap_grill(lib, actor)
    task = {"id": lib._LEAN_SELF_BOOTSTRAP_TASK}
    story = lib._LEAN_SELF_BOOTSTRAP_STORY
    digest = lib._LEAN_SELF_BOOTSTRAP_DIGEST
    if change == "story":
        story = value
    elif change == "task":
        task["id"] = value
    elif change == "digest":
        digest = value
    else:
        grill[change] = value
    monkeypatch.setattr(lib, "_active_story_key", lambda _root: story)
    monkeypatch.setattr(
        lib, "task_grill_grounding_matches",
        lambda _root, _task, _grill: True,
    )

    accepted = lib._lean_self_bootstrap_task_grill(repo, task, grill, digest)

    assert accepted is (change not in {
        "story", "task", "digest", "approved_by", "approved_at",
        "approval_runtime",
    })


def test_lean_self_bootstrap_actor_comes_from_current_story_approval(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    lib = load_factory_lib(repo)
    actor = _recorded_lean_bootstrap_actor(lib, repo)
    grill = _lean_bootstrap_grill(lib, actor)
    task = {"id": lib._LEAN_SELF_BOOTSTRAP_TASK}
    monkeypatch.setattr(
        lib, "task_grill_grounding_matches", lambda _root, _task, _grill: True,
    )

    assert lib._lean_self_bootstrap_task_grill(
        repo, task, grill, lib._LEAN_SELF_BOOTSTRAP_DIGEST,
    )

    grill["approved_by"] = "forged-grill-actor"
    assert not lib._lean_self_bootstrap_task_grill(
        repo, task, grill, lib._LEAN_SELF_BOOTSTRAP_DIGEST,
    )

    grill["approved_by"] = actor
    story_plan = repo / "plans" / "active" / "lean-bootstrap.md"
    original_plan = story_plan.read_bytes()
    story_plan.write_bytes(original_plan + b"\nchanged\n")
    assert not lib._lean_self_bootstrap_task_grill(
        repo, task, grill, lib._LEAN_SELF_BOOTSTRAP_DIGEST,
    )

    story_plan.write_bytes(original_plan)
    approval_path = lib.evidence_path(
        repo, lib._LEAN_SELF_BOOTSTRAP_STORY, "plan-approval.json",
    )
    approval_path.unlink()
    assert not lib._lean_self_bootstrap_task_grill(
        repo, task, grill, lib._LEAN_SELF_BOOTSTRAP_DIGEST,
    )


def test_lean_self_bootstrap_records_once_without_native_event_identity(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    lib = load_factory_lib(repo)
    story = lib._LEAN_SELF_BOOTSTRAP_STORY
    task_id = lib._LEAN_SELF_BOOTSTRAP_TASK
    digest = lib._LEAN_SELF_BOOTSTRAP_DIGEST
    actor = _recorded_lean_bootstrap_actor(lib, repo)
    story_digest = lib.require_approved_plan_digest(repo)
    task = {"id": task_id}
    decomposition = lib.protected_decomposition_state_path(repo)
    lib.dump_json(decomposition, {"plan_sha256": story_digest, "tasks": [task]})
    task_plan = lib.evidence_path(
        repo, story, f"task-plans/{task_id}.md", for_write=True,
    )
    task_plan.parent.mkdir(parents=True, exist_ok=True)
    task_plan.write_text("# exact Lean task plan\n", encoding="utf-8")
    grill_path = lib.evidence_path(
        repo, story, f"grills/tasks/{task_id}.json", for_write=True,
    )
    clean_grill = {
        "generated_by": "griller",
        "gate": "task",
        "verdict": "pass",
        "gaps": [],
        "contradictions": [],
        "resolutions": [],
        "finding_dispositions": [],
        "issue": story,
        "task_id": task_id,
        "final_artifact_sha256": lib._LEAN_SELF_BOOTSTRAP_FINAL_ARTIFACT_SHA256,
    }
    lib.dump_json(grill_path, clean_grill)
    monkeypatch.setattr(lib, "_active_story_key", lambda _root: story)
    monkeypatch.setattr(
        lib, "plan_digest_without_assumptions",
        lambda path: digest if path == task_plan else story_digest,
    )
    real_sha256 = hashlib.sha256
    monkeypatch.setattr(lib.hashlib, "sha256", lambda body=b"": (
        type("Digest", (), {
            "hexdigest": lambda self: lib._LEAN_SELF_BOOTSTRAP_FINAL_ARTIFACT_SHA256,
        })() if body == task_plan.read_bytes() else real_sha256(body)
    ))
    monkeypatch.setattr(
        lib, "require_task_grill",
        lambda _root, _task_id, _task, **_kwargs: clean_grill,
    )
    monkeypatch.setattr(
        lib, "task_grill_grounding_matches",
        lambda _root, _task, _grill: True,
    )

    recorded = lib.record_lean_self_bootstrap_approval(repo, task_id, actor)

    assert recorded["approved_task_plan_sha256"] == digest
    assert recorded["approved_by"] == actor
    assert recorded["approved_at"].endswith("+00:00")
    assert not any(field in recorded for field in (
        "approval_runtime", "approval_session_id", "approval_event_id",
    ))
    assert lib._task_plan_approval_matches_digest(
        repo, task, recorded, digest,
    )
    assert not list(
        (grill_path.parent.parent / "approval-events").glob("*.json")
    )
    with pytest.raises(SystemExit, match="already consumed"):
        lib.record_lean_self_bootstrap_approval(repo, task_id, actor)
    with pytest.raises(SystemExit, match="does not match"):
        lib.record_lean_self_bootstrap_approval(repo, task_id, "Other Human")


def test_story_approval_digest_requires_native_event_proof_without_backfill(
        repo: Path):
    candidate = _story_candidate(repo)
    lib = load_factory_lib(repo)
    state_path = lib.run_state_path(repo)
    state = json.loads(state_path.read_text())
    state.update(
        plan_status="approved", approved_plan_sha256=candidate.digest,
    )
    lib.dump_json(state_path, state)
    before = state_path.read_bytes()

    with pytest.raises(SystemExit, match="binding is missing"):
        lib.require_approved_plan_digest(repo)

    assert state_path.read_bytes() == before
    assert not candidate.evidence.exists()


@pytest.mark.parametrize("kind", ["absolute", "traversal", "symlink", "hardlink", "ancestor"])
def test_native_approval_refuses_unsafe_story_plan_without_external_write(repo, tmp_path, kind):
    import os
    candidate = _story_candidate(repo)
    event = _event(candidate)
    outside = tmp_path / "external-plan.md"
    original = candidate.path.read_bytes()
    outside.write_bytes(original)
    lib = load_factory_lib(repo)
    state_path = lib.run_state_path(repo)
    state = json.loads(state_path.read_text())
    if kind == "absolute":
        state["plan_file"] = str(outside)
    elif kind == "traversal":
        state["plan_file"] = os.path.relpath(outside, repo)
    elif kind == "ancestor":
        parent = repo / "linked-plans"
        parent.symlink_to(tmp_path, target_is_directory=True)
        state["plan_file"] = "linked-plans/external-plan.md"
    else:
        candidate.path.unlink()
        if kind == "symlink":
            candidate.path.symlink_to(outside)
        else:
            os.link(outside, candidate.path)
    lib.dump_json(state_path, state)
    before = state_path.read_bytes()
    with pytest.raises(approval.ApprovalRefused):
        approval.record_native_approval(repo, event, runtime="claude")
    assert outside.read_bytes() == original
    assert state_path.read_bytes() == before
    assert not candidate.evidence.exists()


def test_native_approval_refuses_lexically_traversing_destination(repo, tmp_path):
    outside = tmp_path / "approval.json"
    lexical_escape = repo / "plans" / ".." / ".." / tmp_path.name / outside.name

    with pytest.raises(approval.ApprovalRefused, match="contained and non-linked"):
        approval._require_safe_destination(repo, lexical_escape, required=False)
    assert not outside.exists()


def test_native_approval_rechecks_replaced_plan_before_publication(repo, tmp_path, monkeypatch):
    candidate = _story_candidate(repo)
    event = _event(candidate)
    outside = tmp_path / "external-plan.md"
    outside.write_bytes(candidate.path.read_bytes())
    before = outside.read_bytes()
    original_approve = approval._approve_story

    def replace_before_write(base, selected, record):
        selected.path.unlink()
        selected.path.symlink_to(outside)
        original_approve(base, selected, record)

    monkeypatch.setattr(approval, "_approve_story", replace_before_write)
    with pytest.raises(approval.ApprovalRefused, match="non-linked"):
        approval.record_native_approval(repo, event, runtime="claude")
    assert outside.read_bytes() == before
    assert not candidate.evidence.exists()
    assert len(list((candidate.evidence.parent / "approval-events").glob("*.json"))) == 1


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "ancestor", "replay-ancestor"])
def test_native_approval_refuses_unsafe_authority_and_replay_destinations(
        repo: Path, tmp_path: Path, kind: str, monkeypatch: pytest.MonkeyPatch):
    import os

    (repo / ".factory" / "stories" / "APPROVE-1").mkdir(parents=True)
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    event = _event(candidate)
    lib = load_factory_lib(repo)
    state_path = lib.run_state_path(repo)
    before = (candidate.path.read_bytes(), state_path.read_bytes())
    outside = tmp_path / "outside"
    outside.mkdir()
    external = outside / "authority.json"
    external.write_text('{"sentinel": true}\n', encoding="utf-8")

    if kind == "symlink":
        candidate.evidence.symlink_to(external)
    elif kind == "hardlink":
        os.link(external, candidate.evidence)
    elif kind == "ancestor":
        story_dir = candidate.evidence.parent
        backup = tmp_path / "story-backup"
        story_dir.rename(backup)
        story_dir.symlink_to(outside, target_is_directory=True)
    else:
        replay_dir = candidate.evidence.parent / "approval-events"
        replay_dir.symlink_to(outside, target_is_directory=True)

    with pytest.raises(approval.ApprovalRefused):
        approval.record_native_approval(repo, event, runtime="claude")

    assert (candidate.path.read_bytes(), state_path.read_bytes()) == before
    assert external.read_text(encoding="utf-8") == '{"sentinel": true}\n'


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_native_task_approval_refuses_unsafe_grill_destination(
        repo: Path, tmp_path: Path, kind: str, monkeypatch: pytest.MonkeyPatch):
    import os

    plan = repo / ".factory" / "task.md"
    plan.write_text("# task\n", encoding="utf-8")
    grill = repo / ".factory" / "task-grill.json"
    outside = tmp_path / "task-grill.json"
    outside.write_text('{"verdict":"pass"}\n', encoding="utf-8")
    if kind == "symlink":
        grill.symlink_to(outside)
    else:
        os.link(outside, grill)
    task = approval.ApprovalCandidate(
        "task", "APPROVE-1", "T1", plan,
        load_factory_lib(repo).plan_digest_without_assumptions(plan), grill,
    )
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [task])
    before = outside.read_bytes()

    with pytest.raises(approval.ApprovalRefused, match="destination"):
        approval.record_native_approval(
            repo, _event(task, "codex"), runtime="codex")

    assert outside.read_bytes() == before


def test_native_story_approval_refuses_unsafe_run_state_without_tombstone(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    candidate = _story_candidate(repo)
    monkeypatch.setattr(approval, "eligible_candidates", lambda _base: [candidate])
    lib = load_factory_lib(repo)
    state = lib.run_state_path(repo)
    saved = state.read_bytes()
    outside = tmp_path / "outside-run.json"
    outside.write_bytes(saved)
    state.unlink()
    state.symlink_to(outside)
    plan_before = candidate.path.read_bytes()

    with pytest.raises(approval.ApprovalRefused, match="destination"):
        approval.record_native_approval(
            repo, _event(candidate), runtime="claude")

    assert candidate.path.read_bytes() == plan_before
    assert outside.read_bytes() == saved
    assert not candidate.evidence.exists()
    assert not list(candidate.evidence.parent.glob("approval-events/*.json"))
