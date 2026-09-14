from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_gates import HARNESS, git, repo, run  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import upgrade  # noqa: E402


def _upgrade(target: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HARNESS / "factory/scripts/forge.py"),
         "upgrade", "--target", str(target), *extra],
        cwd=HARNESS, capture_output=True, text=True,
    )


def _legacy_round(target: Path) -> Path:
    path = target / ".factory" / "grill-rounds" / "old.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"questions":[]}\n', encoding="utf-8")
    return path


def test_lean_migration_refuses_dirty_checkout_before_writing(repo: Path):
    legacy = _legacy_round(repo)
    before = legacy.read_bytes()
    result = _upgrade(repo)
    assert result.returncode != 0
    assert "no --force bypass" in result.stdout
    assert legacy.read_bytes() == before
    assert not (repo / ".factory/migrations/lean-workflow-v2.json").exists()


def test_lean_migration_force_cannot_bypass_dirty_tree_refusal(repo: Path):
    legacy = _legacy_round(repo)
    result = _upgrade(repo, "--force")
    assert result.returncode != 0 and "no --force bypass" in result.stdout
    assert legacy.exists()


def test_lean_migration_independent_raw_walk_covers_each_candidate_exactly_once(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    path = _legacy_round(repo)
    primary = upgrade.lean_primary_inventory(repo)
    raw = upgrade.lean_raw_inventory(repo)
    assert primary == raw
    assert [entry["path"] for entry in raw].count(
        path.relative_to(repo).as_posix()) == 1
    monkeypatch.setattr(upgrade, "lean_raw_inventory", lambda _target: [])
    with pytest.raises(SystemExit):
        upgrade.preflight_lean_migration(repo)


def test_lean_migration_inventories_hashes_temp_validates_publishes_and_reads_back(
        repo: Path):
    legacy = _legacy_round(repo)
    git(repo, "add", legacy.relative_to(repo).as_posix())
    git(repo, "commit", "-q", "-m", "legacy lean input")
    result = _upgrade(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not legacy.exists()
    manifest = json.loads((repo / ".factory/migrations/lean-workflow-v2.json").read_text())
    assert manifest["version"] == "lean-workflow-v2"
    assert len(manifest["input_inventory_digest"]) == 64
    assert len(manifest["installed_runtime_digest"]) == 64
    assert manifest["entries"][0]["family"] == "grill-round"


def test_lean_migration_refuses_malformed_mixed_partial_conflicting_or_linked_inputs(
        repo: Path, capsys: pytest.CaptureFixture[str]):
    malformed = _legacy_round(repo)
    malformed.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        upgrade.preflight_lean_migration(repo)
    assert "malformed grill-round" in capsys.readouterr().out
    malformed.unlink()

    reviews = repo / ".factory/stories/S1/tasks/T1/reviews"
    reviews.mkdir(parents=True)
    (reviews.parent / "pr-ready.json").write_text(
        '{"commit":"sealed"}\n', encoding="utf-8")
    (reviews / "quality.json").write_text(
        '{"branch_diff_digest":"a"}\n', encoding="utf-8")
    migration = {
        "entries": upgrade.lean_primary_inventory(repo),
        "input_inventory_digest": "a" * 64,
    }
    with pytest.raises(SystemExit):
        upgrade._fixed_review_candidates(repo, migration)
    assert "partial" in capsys.readouterr().out
    for lens, digest in zip(upgrade.LEAN_LENSES, ("a", "b", "c")):
        (reviews / f"{lens}.json").write_text(
            json.dumps({"branch_diff_digest": digest}) + "\n", encoding="utf-8")
    migration["entries"] = upgrade.lean_primary_inventory(repo)
    with pytest.raises(SystemExit):
        upgrade._fixed_review_candidates(repo, migration)
    assert "conflicting" in capsys.readouterr().out

    external = repo.parent / "external"
    external.mkdir()
    linked = repo / ".factory" / "linked"
    linked.symlink_to(external, target_is_directory=True)
    with pytest.raises(SystemExit):
        upgrade.lean_raw_inventory(repo)


def test_lean_migration_is_idempotent_for_byte_identical_retry_and_refuses_unequal_partial_retry(
        repo: Path):
    legacy = _legacy_round(repo)
    git(repo, "add", legacy.relative_to(repo).as_posix())
    git(repo, "commit", "-q", "-m", "legacy")
    first = _upgrade(repo)
    assert first.returncode == 0, first.stdout + first.stderr
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "lean migration")
    second = _upgrade(repo)
    assert second.returncode == 0, second.stdout + second.stderr
    _legacy_round(repo)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "unequal partial")
    third = _upgrade(repo)
    assert third.returncode != 0 and "unequal partial" in third.stdout


def test_lean_migration_forces_fresh_review_for_active_old_proof_and_migrates_only_exact_sealed_proof(
        repo: Path):
    root = repo / ".factory/stories/S1/tasks/T1/reviews"
    root.mkdir(parents=True, exist_ok=True)
    for lens in upgrade.LEAN_LENSES:
        (root / f"{lens}.json").write_text("{}", encoding="utf-8")
    migration = {
        "entries": upgrade.lean_primary_inventory(repo),
        "input_inventory_digest": "a" * 64,
    }
    # No pr-ready marker: active old fixed files cannot be promoted.
    assert upgrade._fixed_review_candidates(repo, migration) == []
    marker = root.parent / "pr-ready.json"
    marker.write_text('{"commit":"sealed"}', encoding="utf-8")
    with pytest.raises(SystemExit):
        upgrade._fixed_review_candidates(repo, migration)


def test_normal_runtime_refuses_lean_removed_formats_with_upgrade_guidance(repo: Path):
    code, output = run(
        repo, "record_grill_from_json.py", "--gate", "requirements",
        stdin=json.dumps({
            "generated_by": "griller", "gate": "requirements", "verdict": "pass",
            "gaps": [], "contradictions": [], "resolutions": [], "rounds": [],
        }),
    )
    assert code != 0
    assert "invalid choice" in output or "run forge upgrade" in output.lower()
