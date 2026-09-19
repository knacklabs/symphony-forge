"""The grill release goes through the ledgered launcher.

In its own module on purpose. test_gates.py is one 680-test file, so every
branch that adds a test lands in the same region and re-conflicts whenever
another merges first — three times over for this change alone. Separate files
do not collide, and the resolution stops being a keep-both merge that can
silently duplicate a definition (Python shadows a repeated `def` without
complaint).
"""
from __future__ import annotations

import sys

import pytest
from pathlib import Path

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
    assert (model, effort) == ("gpt-5.6-sol", "high")

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
    assert "read-only" in contract and "stage done" in contract


def test_grill_skill_section_is_matt_pococks_grilling_and_nothing_else(repo, monkeypatch):
    # The technique is the installed mattpocock/skills `grilling` (doctor --fix
    # puts it in both runtimes; CI installs it before the suite). `grill-me` is
    # a 164-byte pointer ("Call the Skill tool with 'grilling'") and is never
    # what the reader gets; without the skill the grill is refused, not improvised.
    sys.path.insert(0, str(repo / "factory" / "scripts"))
    import forge_cli.delegate as delegate
    from forge_cli.grill import _grill_skill_section  # noqa: E402

    section = _grill_skill_section()
    assert "Interrogation technique" in section
    assert "design tree" in section, "Matt Pocock's grilling technique"
    assert "Call the Skill tool" not in section
    monkeypatch.setattr(delegate, "_skill_text", lambda *_a, **_k: "")
    with pytest.raises(SystemExit):
        _grill_skill_section()


def test_every_write_launch_loads_ponytail_whatever_the_brief_says(repo, tmp_path, monkeypatch):
    """The launcher, not the brief's author, loads the skill: a bare brief
    still reaches the worker with ponytail as its first section, from the
    installed mattpocock/skills pack."""
    sys.path.insert(0, str(repo / "factory" / "scripts"))
    import forge_cli.delegate as delegate
    from forge_cli.delegate import brief_path, compose_brief, launch_companion

    monkeypatch.setenv("FORGE_COORDINATOR", "claude")
    monkeypatch.setattr(delegate, "companion_script", lambda: tmp_path / "companion.mjs")
    monkeypatch.setattr(delegate.shutil, "which", lambda _name: "node")
    path = brief_path(repo, "T1")
    launch_companion(repo, task_id="T1", text="# bare brief\n", path=path,
                     task_sha256_value="d" * 64, model="m", effort="medium",
                     write=True, print_only=True)
    saved = path.read_text(encoding="utf-8")
    preamble = saved.split("# bare brief")[0]
    assert "## ponytail skill -- loaded for this run" in preamble, saved[:300]
    assert "Stop at the first rung that holds" in preamble
    # A read-only launch (a grill) does not get it.
    launch_companion(repo, task_id="T1", text="# read only\n", path=path,
                     task_sha256_value="d" * 64, model="m", effort="medium",
                     write=False, print_only=True)
    assert "ponytail skill" not in path.read_text(encoding="utf-8")
    # The brief composer no longer carries its own copy: one source, the launcher.
    from test_gates import STAGE_TASK
    composed = compose_brief(repo, dict(STAGE_TASK), write=True, user_facing=False, story="ENG-1")
    assert "loaded for this run" not in composed and "LOAD and RUN" not in composed
