"""The grill release goes through the ledgered launcher.

In its own module on purpose. test_gates.py is one 680-test file, so every
branch that adds a test lands in the same region and re-conflicts whenever
another merges first — three times over for this change alone. Separate files
do not collide, and the resolution stops being a keep-both merge that can
silently duplicate a definition (Python shadows a repeated `def` without
complaint).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pytest

from test_gates import HARNESS, git, load_factory_lib, repo, run  # noqa: F401


def test_grill_runs_through_the_ledgered_launcher_read_only(repo, tmp_path):
    # The grill was the one Codex release the harness could not see: a
    # delegation records a pid and a review does too, so a launcher killed
    # uncatchably stays detectable — but a grill went out through the plugin
    # directly and nothing on the forge side knew it had started. It is also
    # the release the coordinator is told to WATCH every round.
    sys.path.insert(0, str(repo / "factory" / "scripts"))
    from forge_cli.grill import _artifact_text, _compose_brief  # noqa: E402

    lib = load_factory_lib(repo)
    control = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "forge"
    control.mkdir(parents=True, exist_ok=True)
    lib.dump_json(control / "run.json", {"issue_key": "ENG-1"})
    plan = lib.evidence_path(repo, "ENG-1", "task-plans/T1.md", for_write=True)
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text("# T1\n\nAdd the invoice endpoint.\n", encoding="utf-8")

    label, artifact = _artifact_text(repo, "task", "T1")
    brief = _compose_brief(repo, "task", label, artifact)
    # The reader has no memory of the session that wrote it, so the artifact
    # must travel IN the brief.
    assert "Add the invoice endpoint." in brief
    assert "You did NOT write what follows" in brief
    assert "READ-ONLY" in brief
    # Recording stays with the coordinating session: only it produces the
    # AskUserQuestion ledger entries the recorder matches against.
    assert "Do not record a gate" in brief

    # The model pin lives in harness.yaml beside every other pin, not in code.
    from forge_cli.delegate import mode_run_config  # noqa: E402
    model, effort, _ = mode_run_config(repo, "grill")
    assert (model, effort) == ("gpt-6-sol", "high")

    # A gate whose artifact is absent refuses, naming the command that makes it.
    code, out = run(repo, "forge.py", "grill", "run", "--gate", "task")
    assert code != 0 and "--task" in out
    # The plan gate points at the DRAFT, not at a saved plan: plan save refuses
    # without a passing grill, so a plan on disk is the fallback and an
    # unsaved draft is the normal case. Demanding the saved copy made the one
    # gate that worked work at the wrong moment.
    code, out = run(repo, "forge.py", "grill", "run", "--gate", "plan")
    assert code != 0 and "--file" in out


def test_griller_contract_names_the_ledgered_release(repo):
    # Guidance and mechanism must agree: if the contract still told the reader
    # to release through the plugin, the ledger would stay empty and the
    # watcher would keep its blind spot.
    contract = (HARNESS / "factory" / "prompts" / "griller.md").read_text(
        encoding="utf-8")
    assert "./forge grill run --gate" in contract
    assert "/codex:rescue" not in contract
    assert "read-only" in contract and "task close" in contract


def test_grill_skill_section_inlines_the_technique_not_the_pointer(repo):
    # What doctor installs as `grill-me` is a stub whose whole body is "Call
    # the Skill tool with 'grilling'". Naming it would hand a Codex reader a
    # pointer to a skill its runtime may not have, so the technique is inlined
    # — the same reason delegate inlines ponytail rather than trusting an
    # install to be present.
    sys.path.insert(0, str(repo / "factory" / "scripts"))
    from forge_cli.grill import _grill_skill_section  # noqa: E402

    section = _grill_skill_section()
    assert "Call the Skill tool" not in section, (
        "the stub is a pointer, not technique — it must never be inlined")
    assert "Interrogation technique" in section


def _seed_native_plan_grill(repo: Path, tmp_path: Path, monkeypatch, capsys,
                            *, print_only: bool = False):
    """Prepare one real native plan grill and return its bound descriptor."""
    from forge_cli import delegate, grill

    lib = load_factory_lib(repo)
    control = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "forge"
    control.mkdir(parents=True, exist_ok=True)
    lib.dump_json(control / "run.json", {"issue_key": "ENG-1"})
    draft = tmp_path / "draft.md"
    draft.write_text("# Plan\n\nShip the bounded change.\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_COORDINATOR", "codex")

    real_popen = delegate.subprocess.Popen

    def no_nested_codex(argv, *args, **kwargs):
        if argv and Path(str(argv[0])).name.lower().startswith("codex"):
            pytest.fail("native grill launched nested codex")
        return real_popen(argv, *args, **kwargs)

    monkeypatch.setattr(delegate.subprocess, "Popen", no_nested_codex)
    grill.cmd_grill_run(argparse.Namespace(
        repo=str(repo), gate="plan", task="", file=str(draft),
        context_file="", print_only=print_only,
    ))
    emitted = capsys.readouterr().out
    rows = []
    for line in emitted.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    assert len(rows) == 1, "native grill must emit exactly one dispatch descriptor"
    descriptor = next(row for row in rows if "response_schema" in row)
    return draft, descriptor, emitted


def test_native_grill_print_only_emits_one_complete_unrecorded_preview(
        repo, tmp_path, monkeypatch, capsys):
    from forge_cli.delegate import load_delegations

    _draft, descriptor, _emitted = _seed_native_plan_grill(
        repo, tmp_path, monkeypatch, capsys, print_only=True)

    assert descriptor["agent_type"] == "griller"
    assert descriptor["response_schema"]["required"] == [
        "gaps", "contradictions"]
    assert "Return JSON only" in descriptor["message"]
    assert "preparation_id" not in descriptor
    assert load_delegations(repo) == []


def test_print_only_reprints_an_undispatched_native_preparation_without_a_new_row(
        repo, tmp_path, monkeypatch, capsys):
    from forge_cli.delegate import load_delegations

    _draft, prepared, _ = _seed_native_plan_grill(
        repo, tmp_path, monkeypatch, capsys,
    )
    rows = load_delegations(repo)
    _draft, preview, _ = _seed_native_plan_grill(
        repo, tmp_path, monkeypatch, capsys, print_only=True,
    )

    assert preview["preparation_id"] == prepared["preparation_id"]
    assert preview["task_name"] == prepared["task_name"]
    assert load_delegations(repo) == rows
    # Recovery is the print-only re-show; a second real preparation is still
    # the second cold read the one-read rule refuses.
    with pytest.raises(SystemExit):
        _seed_native_plan_grill(repo, tmp_path, monkeypatch, capsys)
    assert load_delegations(repo) == rows


def test_print_only_refuses_changed_prepared_input_without_overwriting_brief(
        repo, tmp_path, monkeypatch, capsys):
    from forge_cli import grill

    draft, prepared, _ = _seed_native_plan_grill(
        repo, tmp_path, monkeypatch, capsys,
    )
    brief_path = repo / prepared["brief_path"]
    prepared_brief = brief_path.read_bytes()
    draft.write_text(
        draft.read_text(encoding="utf-8") + "\nChanged after preparation.\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        grill.cmd_grill_run(argparse.Namespace(
            repo=str(repo), gate="plan", task="", file=str(draft),
            context_file="", print_only=True,
        ))

    assert brief_path.read_bytes() == prepared_brief


def test_native_grill_prepares_one_self_contained_griller_descriptor(
        repo, tmp_path, monkeypatch, capsys):
    draft, descriptor, emitted = _seed_native_plan_grill(
        repo, tmp_path, monkeypatch, capsys)

    assert descriptor["action"] == "spawn_agent"
    assert "followup_action" not in descriptor
    assert descriptor["agent_type"] == "griller"
    assert descriptor["repo"] == str(repo)
    assert descriptor["story"] == "ENG-1"
    assert descriptor["gate"] == "plan"
    assert descriptor["target_task"] == ""
    assert descriptor["preparation_id"]
    assert descriptor["brief_sha256"] == hashlib.sha256(
        (repo / descriptor["brief_path"]).read_bytes()).hexdigest()
    from forge_cli.grill import _artifact_digest, _artifact_text
    assert descriptor["cold_input_sha256"] == _artifact_digest(
        _artifact_text(repo, "plan", "", str(draft))[1])
    assert descriptor["response_schema"]["required"] == [
        "gaps", "contradictions"]
    assert descriptor["response_schema"]["additionalProperties"] is False
    assert "Return JSON only" in descriptor["message"]
    assert descriptor["preparation_id"] in descriptor["message"]
    assert "_cold_" in descriptor["task_name"]
    assert "Do not reuse an existing task with followup_task" in descriptor[
        "dispatch_guidance"]
    assert "spawn_agent tool." in emitted
    assert "or followup_task" not in emitted
    assert not ({"pid", "process_token", "session_id", "model", "effort"}
                & descriptor.keys())


def _record_native_plan_grill(repo: Path, draft: Path, descriptor: dict,
                              tmp_path: Path, *, preparation_id: str | None = None):
    result = tmp_path / "cold-result.json"
    result.write_text(json.dumps({"gaps": [], "contradictions": []}) + "\n",
                      encoding="utf-8")
    payload = tmp_path / "grill-record.json"
    payload.write_text(json.dumps({
        "generated_by": "griller", "gate": "plan", "verdict": "pass",
        "gaps": [], "contradictions": [], "resolutions": [],
        "finding_dispositions": [],
    }) + "\n", encoding="utf-8")
    return run(
        repo, "record_grill_from_json.py", "--gate", "plan",
        "--input-digest", str(draft), "--input", str(payload),
        "--cold-result", str(result), "--preparation-id",
        preparation_id or descriptor["preparation_id"],
    ), result


def test_native_grill_records_exact_returned_json_with_preparation_binding(
        repo, tmp_path, monkeypatch, capsys):
    draft, descriptor, _emitted = _seed_native_plan_grill(
        repo, tmp_path, monkeypatch, capsys)
    (code, out), result = _record_native_plan_grill(
        repo, draft, descriptor, tmp_path)

    assert code == 0, out
    lib = load_factory_lib(repo)
    record = json.loads(lib.evidence_path(
        repo, "ENG-1", "grills/plan.json").read_text(encoding="utf-8"))
    assert record["transport"] == "host-native"
    assert record["preparation_id"] == descriptor["preparation_id"]
    assert record["cold_input_sha256"] == descriptor["cold_input_sha256"]
    assert record["result_sha256"] == hashlib.sha256(result.read_bytes()).hexdigest()


def test_native_grill_refuses_wrong_preparation_id(
        repo, tmp_path, monkeypatch, capsys):
    draft, descriptor, _emitted = _seed_native_plan_grill(
        repo, tmp_path, monkeypatch, capsys)
    (code, out), _result = _record_native_plan_grill(
        repo, draft, descriptor, tmp_path, preparation_id="wrong-preparation")

    assert code != 0
    assert "preparation id is invalid" in out


@pytest.mark.parametrize("tamper", ["digest", "pid"])
def test_native_grill_refuses_tampered_preparation(
        repo, tmp_path, monkeypatch, capsys, tamper):
    from forge_cli.delegate import delegations_path

    draft, descriptor, _emitted = _seed_native_plan_grill(
        repo, tmp_path, monkeypatch, capsys)
    ledger = delegations_path(repo)
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    prepared = next(row for row in rows
                    if row.get("launch_id") == descriptor["preparation_id"])
    if tamper == "digest":
        prepared["task_sha256"] = "0" * 64
    else:
        prepared["pid"] = 12345
    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows),
                      encoding="utf-8")

    (code, out), _result = _record_native_plan_grill(
        repo, draft, descriptor, tmp_path)
    assert code != 0
    assert ("input digest is invalid" in out if tamper == "digest"
            else "carries process claims" in out)
