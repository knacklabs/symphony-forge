"""One task journal, written only through the harness and read by both
agents (decision 0080)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from test_gates import (  # noqa: F401
    HARNESS, STAGE_TASK, delegation_ledger, intake, repo, run,
    sign_off, start_stage, write_in_scope,
)
from forge_cli.delegate import brief_path  # noqa: E402

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import journal  # noqa: E402


def _story(repo: Path) -> str:
    sign_off(repo)
    intake(repo)
    return "ENG-1"


def test_entries_are_validated_numbered_and_rendered(repo):
    story = _story(repo)
    first = journal.append(repo, story, "T1", kind="note", by="coordinator",
                           title="Heartbeat every five minutes", body="Nandu said so in chat.")
    second = journal.append(repo, story, "T1", kind="proof", by="harness",
                            title="npx vitest run", body="9 passed", command="npx vitest run",
                            exit_code=0)
    assert first["id"] == "J-1" and second["id"] == "J-2"
    items = journal.entries(repo, story, "T1")
    assert [e["kind"] for e in items] == ["note", "proof"]
    assert journal.head_id(items) == "J-2"
    assert [e["id"] for e in journal.since(items, "J-1")] == ["J-2"]
    md = (repo / ".factory" / "stories" / story / "tasks" / "T1" / "journal.md").read_text(
        encoding="utf-8")
    assert "## J-1 · note · coordinator" in md and "Nandu said so in chat." in md
    assert "- command: npx vitest run" in md
    raw = (repo / ".factory" / "stories" / story / "tasks" / "T1" / "journal.jsonl").read_bytes()
    assert b"\r\n" not in raw


def test_kind_actor_and_required_fields_are_enforced(repo):
    story = _story(repo)
    with pytest.raises(SystemExit):
        journal.append(repo, story, "T1", kind="proof", by="coordinator",
                       title="x", command="c", exit_code=0)
    with pytest.raises(SystemExit):
        journal.append(repo, story, "T1", kind="refusal", by="coordinator",
                       title="lockfile claim", finding="F1")
    with pytest.raises(SystemExit):
        journal.append(repo, story, "T1", kind="note", by="nobody", title="x")
    with pytest.raises(SystemExit):
        journal.append(repo, story, "T1", kind="gossip", by="coordinator", title="x")
    assert journal.entries(repo, story, "T1") == []


def test_long_bodies_become_attachments_and_repeats_do_not_double(repo):
    story = _story(repo)
    body = "\n".join(f"line {n}" for n in range(2000))
    entry = journal.append(repo, story, "T1", kind="proof", by="harness",
                           title="long", body=body, command="c", exit_code=1)
    assert entry["truncated"] is True
    attachment = repo / entry["attachment"]
    assert attachment.read_text(encoding="utf-8") == body
    assert entry["body"].endswith("line 1999") and "line 1960" in entry["body"]
    again = journal.append(repo, story, "T1", kind="proof", by="harness",
                           title="long", body=body, command="c", exit_code=1)
    assert again["id"] == entry["id"]
    assert len(journal.entries(repo, story, "T1")) == 1


def test_acted_on_must_name_existing_entries(repo):
    story = _story(repo)
    journal.append(repo, story, "T1", kind="note", by="coordinator", title="n")
    with pytest.raises(SystemExit):
        journal.append(repo, story, "T1", kind="report", by="harness", title="r",
                       launch_id="launch-1", acted_on=["J-9"])
    entry = journal.append(repo, story, "T1", kind="report", by="harness", title="r",
                           launch_id="launch-1", acted_on=["J-1"])
    assert entry["acted_on"] == ["J-1"]


def test_standing_entries_keep_the_latest_contract_and_every_instruction(repo):
    story = _story(repo)
    journal.append(repo, story, "T1", kind="contract", by="harness", title="v1", body="a")
    journal.append(repo, story, "T1", kind="note", by="coordinator", title="keep", body="b")
    journal.append(repo, story, "T1", kind="proof", by="harness", title="p", command="c",
                   exit_code=0)
    journal.append(repo, story, "T1", kind="contract", by="harness", title="v2", body="c")
    kept = journal.standing(journal.entries(repo, story, "T1"))
    assert [e["title"] for e in kept] == ["v2", "keep"]


def test_cli_adds_shows_and_reports_status(repo):
    _story(repo)
    code, out = run(repo, "forge.py", "journal", "add", "T1", "--kind", "decision",
                    "--title", "Drop the connector CI", "--reason", "Nandu, chat 11:58",
                    "--by", "human")
    assert code == 0 and "J-1 decision recorded for T1" in out, out
    code, out = run(repo, "forge.py", "journal", "add", "T1", "--kind", "scope",
                    "--title", "shared test helper", "--path", "apps/api/test/database.ts",
                    "--reason", "the cleanup grace is what blocks the seal")
    assert code == 0 and "J-2 scope" in out, out
    code, out = run(repo, "forge.py", "journal", "show", "T1", "--kind", "decision")
    assert code == 0 and "Drop the connector CI" in out and "J-2" not in out, out
    code, out = run(repo, "forge.py", "journal", "status", "T1")
    assert code == 0 and "2 entries; head J-2" in out and "decision=1, scope=1" in out, out
    code, out = run(repo, "forge.py", "journal", "add", "T1", "--kind", "proof",
                    "--title", "x", "--command", "c", "--exit-code", "0")
    assert code != 0 and "coordinator entry cannot be of kind" in out, out


# ------------------------------------------------ the harness writes it (0080)


def test_stage_start_and_delegate_write_contract_launch_and_exit(repo, tmp_path):
    start_stage(repo, tmp_path, STAGE_TASK)
    items = journal.entries(repo, "ENG-1", "T1")
    kinds = [e["kind"] for e in items]
    assert kinds[0] == "contract" and "launch" in kinds and "exit" in kinds, kinds
    contract = items[0]
    assert "Objective: Build the core slice" in contract["body"]
    assert "stage_contract_proof.py" in contract["body"]
    launch = next(e for e in items if e["kind"] == "launch")
    assert launch["journal_head"] == "J-1", launch  # the contract was all it carried
    exit_entry = next(e for e in items if e["kind"] == "exit")
    assert exit_entry["launch_id"] == launch["launch_id"] and exit_entry["exit_code"] == 0
    ledger = [json.loads(line) for line in delegation_ledger(repo).read_text(
        encoding="utf-8").splitlines() if line.strip()]
    assert ledger[0]["journal_head"] == "J-1"
    brief = brief_path(repo, "T1").read_text(encoding="utf-8")
    assert "Task journal -- what the coordinator sees, you see" in brief
    assert "Standing instructions (apply regardless of age)" in brief
    assert "J-1 · contract · harness" in brief
    assert "acted on: J-..." in brief


def test_the_next_brief_carries_notes_and_everything_since_the_last_launch(repo, tmp_path):
    from forge_cli.delegate import compose_brief
    start_stage(repo, tmp_path, STAGE_TASK)
    code, out = run(repo, "forge.py", "journal", "add", "T1", "--kind", "note",
                    "--title", "Heartbeat every five minutes",
                    "--body", "Nandu decided it in chat; default 300, not 60.")
    assert code == 0, out
    task = dict(STAGE_TASK)
    brief = compose_brief(repo, task, write=True, user_facing=False, story="ENG-1")
    assert "Heartbeat every five minutes" in brief
    assert "Nandu decided it in chat" in brief
    head = next(e for e in journal.entries(repo, "ENG-1", "T1")
                if e["kind"] == "launch")["journal_head"]
    assert f"New since your last launch (after {head})" in brief
    assert "exited with code 0" in brief  # the worker's own earlier exit


def test_scope_amendments_and_signals_are_journaled(repo, tmp_path):
    start_stage(repo, tmp_path, STAGE_TASK)
    write_in_scope(repo, "billing/ledger.py")
    code, out = run(repo, "forge.py", "stage", "amend-scope", "T1",
                    "--reason", "the ledger row is part of this slice", "--by", "Nandu")
    assert code == 0, out
    code, out = run(repo, "forge.py", "signal", "raise", "--kind", "confusion",
                    "--message", "which ledger column is the key?", "--by", "implementer")
    assert code == 0, out
    signal_id = out.split("Signal ")[1].split()[0]
    code, out = run(repo, "forge.py", "signal", "resolve", signal_id,
                    "--notes", "ledger.id, see the plan")
    assert code == 0, out
    items = journal.entries(repo, "ENG-1", "T1")
    scope = next(e for e in items if e["kind"] == "scope")
    assert scope["paths"] == ["billing/ledger.py"]
    assert scope["reason"] == "the ledger row is part of this slice"
    raised = next(e for e in items if e["kind"] == "signal")
    assert raised["generated_by"] == "worker" and "ledger column" in raised["body"]
    resolved = next(e for e in items if e["kind"] == "signal-resolved")
    assert "ledger.id" in resolved["body"]


def test_a_path_declared_before_the_write_is_in_scope_for_the_brief_and_the_measurement(
        repo, tmp_path):
    from forge_cli.delegate import compose_brief
    start_stage(repo, tmp_path, STAGE_TASK)
    code, out = run(repo, "forge.py", "stage", "amend-scope", "T1",
                    "--path", "apps/api/test/database.ts",
                    "--reason", "the cleanup grace is what blocks the seal", "--by", "Nandu")
    assert code == 0 and "Declared T1 scope with 1 declared path(s)" in out, out
    scope = next(e for e in journal.entries(repo, "ENG-1", "T1") if e["kind"] == "scope")
    assert scope["title"].startswith("scope declared ahead") and scope["paths"] == [
        "apps/api/test/database.ts"]
    brief = compose_brief(repo, dict(STAGE_TASK), write=True, user_facing=False, story="ENG-1")
    section = brief.split("Write scope")[1].split("##")[0]
    assert "apps/api/test/database.ts" in section
    write_in_scope(repo, "apps/api/test/database.ts", "export const grace = 30_000;\n")
    from test_gates import stamp_and_commit
    stamp_and_commit(repo)
    code, out = run(repo, "forge.py", "stage", "done", "T1")
    assert code == 0, out
    assert "outside its declared write_scope" not in out, out


def test_forge_next_names_the_workers_last_exit_and_what_it_cited(repo, tmp_path):
    start_stage(repo, tmp_path, STAGE_TASK)
    code, out = run(repo, "forge.py", "next")
    assert code == 0, out
    assert "worker for T1 exited at" in out and "with code 0" in out, out
    assert "forge journal show T1 --since J-1" in out, out


def test_a_transient_sharing_violation_is_retried_not_refused(tmp_path, monkeypatch):
    """Windows: the host's file scanner holds a just-written state file for a
    moment; the next open fails with EACCES. The harness's own state reads
    retry for about two seconds instead of refusing a real close with
    "cannot read changed path"."""
    import factory_lib
    monkeypatch.setattr(factory_lib, "RETRY_SHARING_VIOLATIONS", True)
    monkeypatch.setattr(factory_lib, "_SHARING_RETRY_DELAYS", (0.0, 0.0, 0.0))
    calls = {"n": 0}

    def flaky_open():
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(13, "Permission denied")
        return "ok"

    assert factory_lib.retry_sharing_violation(flaky_open) == "ok" and calls["n"] == 3
    calls["n"] = -10  # never recovers: the error comes through unchanged
    with pytest.raises(PermissionError):
        factory_lib.retry_sharing_violation(flaky_open)
    monkeypatch.setattr(factory_lib, "RETRY_SHARING_VIOLATIONS", False)
    calls["n"] = 0
    with pytest.raises(PermissionError):
        factory_lib.retry_sharing_violation(flaky_open)
    assert calls["n"] == 1, "no retry outside Windows"


def test_upgrade_appends_the_journal_and_proof_pins_to_a_project_owned_harness_yaml(tmp_path):
    """harness.yaml is project-owned and never rewritten by upgrade. The
    journal schema pins five actors and the dual-runtime check requires each
    to be mentioned there, so a client taking 0080 failed that check until
    someone edited the file by hand (2026-09-21). Upgrade appends the pins."""
    from forge_cli.scaffold import ensure_harness_yaml_pins
    project = tmp_path / "client"
    project.mkdir()
    original = "version: 1\nsignoff_record: \"docs/decisions/0001.md\"\nlessons:\n  path: plans/lessons\n"
    (project / "harness.yaml").write_text(original, encoding="utf-8")
    assert ensure_harness_yaml_pins(project, HARNESS) == ["journal", "proof"]
    text = (project / "harness.yaml").read_text(encoding="utf-8")
    assert text.startswith(original.rstrip("\n")), "project content is kept, verbatim"
    for actor in ("harness", "coordinator", "worker", "reviewer", "human"):
        assert f'- "{actor}"' in text
    assert "min_free_memory_gb: 2" in text
    assert ensure_harness_yaml_pins(project, HARNESS) == [], "idempotent"
    # The harness's own manifest already carries both under evolution.journal
    # and proof:, so nothing is appended there.
    assert ensure_harness_yaml_pins(HARNESS, HARNESS) == []
