from __future__ import annotations

import argparse
import hashlib
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
    path.write_text(json.dumps({
        "generated_by": "claude-code:plan-mode", "questions": [],
        "at": "2026-01-01T00:00:00+00:00", "session_id": "session-1",
    }) + "\n", encoding="utf-8")
    return path


def _legacy_grill(gate: str) -> dict:
    value = {
        "generated_by": "griller", "gate": gate, "verdict": "pass",
        "gaps": [], "contradictions": [], "resolutions": [],
    }
    if gate == "task":
        value["rounds"] = []
    return value


def _fixed_lens(
        task: str = "T1",
        delta: str = hashlib.sha256(b"").hexdigest(),
) -> dict:
    return {
        "generated_by": "autoreview", "task_id": task, "score": 10,
        "summary": "clean legacy lens", "blocking_findings": [],
        "non_blocking_findings": [], "branch_diff_digest": delta,
        "recommendation": "approve",
    }


def test_lean_migration_refuses_dirty_checkout_before_writing(repo: Path):
    legacy = _legacy_round(repo)
    before = legacy.read_bytes()
    result = _upgrade(repo)
    assert result.returncode != 0
    assert "no --force bypass" in result.stdout
    assert legacy.read_bytes() == before
    assert not (repo / ".factory/migrations/lean-workflow-v2.json").exists()


def test_lean_migration_refuses_failed_clean_tree_probe_before_writing(
        repo: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]):
    sentinel = repo / "AGENTS.md"
    before = sentinel.read_bytes()

    def failed_status(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 2, "", "index unreadable")

    monkeypatch.setattr(upgrade.subprocess, "run", failed_status)
    with pytest.raises(SystemExit):
        upgrade.cmd_upgrade(argparse.Namespace(target=str(repo), force=False))
    assert "could not verify" in capsys.readouterr().out
    assert sentinel.read_bytes() == before
    assert not (repo / ".factory/migrations/lean-workflow-v2.json").exists()


def test_lean_migration_force_cannot_bypass_dirty_tree_refusal(repo: Path):
    legacy = _legacy_round(repo)
    result = _upgrade(repo, "--force")
    assert result.returncode != 0 and "no --force bypass" in result.stdout
    assert legacy.exists()


def test_lean_migration_independent_raw_walk_covers_each_candidate_exactly_once(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    path = _legacy_round(repo)
    excluded = path.parent / "README.txt"
    excluded.write_text("project note\n", encoding="utf-8")
    primary = upgrade.lean_primary_inventory(repo)
    raw = upgrade.lean_raw_inventory(repo)
    assert primary == raw
    assert [entry["path"] for entry in raw].count(
        path.relative_to(repo).as_posix()) == 1
    excluded_row = next(
        row for row in raw if row["path"] == excluded.relative_to(repo).as_posix())
    assert excluded_row["classification"] == "excluded"
    assert excluded_row["reason"] == "current-or-project-owned"
    monkeypatch.setattr(upgrade, "lean_raw_inventory", lambda _target: [])
    with pytest.raises(SystemExit):
        upgrade.preflight_lean_migration(repo)


def test_lean_raw_inventory_does_not_reuse_primary_classifiers_or_identities(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    eligible = _legacy_round(repo)
    excluded = eligible.parent / "README.txt"
    excluded.write_text("project note\n", encoding="utf-8")
    tasks = repo / ".factory/grills/tasks"
    tasks.mkdir(parents=True)
    invalid = repo / ".factory/grills/requirements.json"
    invalid.write_text('{"gate":"requirements"}\n', encoding="utf-8")
    fixed = repo / ".factory/stories/S1/tasks/T1/reviews/quality.json"
    fixed.parent.mkdir(parents=True)
    fixed.write_text(json.dumps(_fixed_lens()) + "\n", encoding="utf-8")

    def primary_only(*_args, **_kwargs):
        raise AssertionError("raw inventory reused a primary-pass classifier")

    for name in (
            "_lean_family", "_legacy_json_shape_reason", "_entry_identity",
            "_classify_fixed_review_coverage"):
        monkeypatch.setattr(upgrade, name, primary_only)

    rows = upgrade.lean_raw_inventory(repo)
    by_path = {row["path"]: row for row in rows}
    assert by_path[eligible.relative_to(repo).as_posix()]["classification"] == "eligible"
    assert by_path[excluded.relative_to(repo).as_posix()]["classification"] == "excluded"
    assert by_path[invalid.relative_to(repo).as_posix()]["classification"] == "invalid"
    assert by_path[fixed.relative_to(repo).as_posix()]["reason"] == (
        "incomplete fixed review is display-only")
    assert by_path[tasks.relative_to(repo).as_posix()]["source_paths"] == [
        tasks.relative_to(repo).as_posix()]
    assert all(row["reason"] and row["source_paths"] for row in rows)
    assert all(path == Path(path).as_posix()
               for row in rows for path in row["source_paths"])


def test_lean_migration_independent_inventories_cover_every_declared_family(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    def write(relative: str, content: str) -> Path:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    profile = b"retired profile\n"
    monkeypatch.setitem(
        upgrade.RETIRED_FORGE_PROFILE_HASHES, "retired.toml",
        hashlib.sha256(profile).hexdigest())
    path = repo / ".codex/agents/retired.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(profile)
    write(".codex/config.toml", "codex_hooks = true\n")
    write(".factory/grill-rounds/old.json", json.dumps({
        "generated_by": "claude-code:plan-mode", "questions": [],
        "at": "2026-01-01T00:00:00+00:00", "session_id": "s",
    }))
    write(".factory/grills/requirements.json",
          json.dumps(_legacy_grill("requirements")))
    write(".factory/grills/plan.json", json.dumps(_legacy_grill("plan")))
    write(".factory/grills/tasks/T1.json", json.dumps(_legacy_grill("task")))
    write(".factory/plan-approval.json", json.dumps({
        "approved_plan_sha256": "a" * 64, "issue": "S1", "story": "S1",
        "approver": "human", "at": "2026-01-01T00:00:00+00:00",
    }))
    write(".factory/plan-mode/old.json", json.dumps({
        "generated_by": "claude-code:plan-mode", "path": "/tmp/plan.md",
        "sha256": "a" * 64, "sha256_body": "b" * 64,
        "at": "2026-01-01T00:00:00+00:00", "session_id": "s",
    }))
    write(".factory/stories/S1/tasks/T1/reviews/quality.json",
          json.dumps(_fixed_lens()))
    write(".factory/stories/S1/stages/T1.json",
          json.dumps({"local_review_stamp": {
              "stage_id": "T1", "base_sha": "a" * 40,
              "delta_id": "b" * 64,
              "recorded_at": "2026-01-01T00:00:00+00:00",
              "generated_by": "autoreview",
          }}))

    primary = upgrade.lean_primary_inventory(repo)
    raw = upgrade.lean_raw_inventory(repo)
    assert primary == raw
    assert {entry["family"] for entry in primary if entry["family"]} == {
        "old-hook-flag", "retired-forge-profile", "grill-round",
        "requirements-grill", "old-plan-grill", "old-task-grill",
        "manual-plan-approval", "plan-mode-marker", "fixed-review-lens",
        "legacy-stage-stamp",
    }
    fixed = next(row for row in primary if row["family"] == "fixed-review-lens")
    assert fixed["classification"] == "excluded"
    assert fixed["reason"] == "incomplete fixed review is display-only"


@pytest.mark.parametrize(("relative", "value", "family"), [
    (".factory/grill-rounds/old.json", {"questions": []}, "grill-round"),
    (".factory/grills/requirements.json", {"gate": "requirements"},
     "requirements-grill"),
    (".factory/grills/plan.json", {"gate": "plan"}, "old-plan-grill"),
    (".factory/grills/tasks/T1.json", {"rounds": []}, "old-task-grill"),
    (".factory/plan-approval.json", {"approver": "human"},
     "manual-plan-approval"),
    (".factory/plan-mode/old.json", {"generated_by": "old"},
     "plan-mode-marker"),
    (".factory/stories/S1/tasks/T1/reviews/quality.json",
     {"generated_by": "autoreview", "task_id": "T1"}, "fixed-review-lens"),
    (".factory/stories/S1/stages/T1.json",
     {"local_review_stamp": "old"}, "legacy-stage-stamp"),
])
def test_lean_migration_refuses_family_specific_malformed_objects(
        repo: Path, relative: str, value: dict, family: str,
        capsys: pytest.CaptureFixture[str]):
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    before = path.read_bytes()

    primary = upgrade.lean_primary_inventory(repo)
    raw = upgrade.lean_raw_inventory(repo)
    assert primary == raw
    row = next(entry for entry in primary if entry["path"] == relative)
    assert row["family"] == family
    assert row["classification"] == "invalid"
    with pytest.raises(SystemExit):
        upgrade.preflight_lean_migration(repo)
    assert "invalid" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_lean_migration_inventories_ignore_paths_outside_declared_legacy_roots(
        repo: Path):
    history = repo / ".factory/history/S1/grill-rounds/old.json"
    history.parent.mkdir(parents=True)
    history.write_text('{"questions":[]}\n', encoding="utf-8")
    live = repo / ".factory/unexpected/grill-rounds/old.json"
    live.parent.mkdir(parents=True)
    live.write_text('{"questions":[]}\n', encoding="utf-8")

    primary = upgrade.lean_primary_inventory(repo)
    raw = upgrade.lean_raw_inventory(repo)
    history_rel = history.relative_to(repo).as_posix()
    live_rel = live.relative_to(repo).as_posix()
    assert history_rel not in {entry["path"] for entry in primary}
    assert history_rel not in {entry["path"] for entry in raw}
    assert live_rel not in {entry["path"] for entry in primary}
    assert live_rel not in {entry["path"] for entry in raw}
    assert primary == raw
    assert not [entry for entry in upgrade.preflight_lean_migration(repo)["entries"]
                if entry["classification"] == "eligible"]


def test_lean_migration_excludes_and_preserves_current_family_objects(repo: Path):
    fixtures = {
        ".factory/grills/plan.json": {
            **_legacy_grill("plan"), "cold_input_sha256": "a" * 64,
        },
        ".factory/plan-approval.json": {
            "runtime": "codex", "approved_plan_sha256": "a" * 64,
        },
        ".factory/stories/S1/stages/T1.json": {
            "local_review_stamp": {"reviewed_meaning": "a" * 64},
        },
    }
    before = {}
    for relative, value in fixtures.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        before[relative] = path.read_bytes()

    primary = upgrade.lean_primary_inventory(repo)
    assert primary == upgrade.lean_raw_inventory(repo)
    rows = {row["path"]: row for row in primary if row["path"] in fixtures}
    assert set(rows) == set(fixtures)
    assert all(row["classification"] == "excluded" and row["preserve"]
               for row in rows.values())
    migration = upgrade.preflight_lean_migration(repo)
    assert migration is not None
    upgrade.apply_lean_migration(repo, migration)
    assert {relative: (repo / relative).read_bytes() for relative in fixtures} == before


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
    assert any(entry["family"] == "grill-round"
               and entry["classification"] == "eligible"
               for entry in manifest["entries"])


def test_lean_migration_refuses_malformed_mixed_partial_conflicting_or_linked_inputs(
        repo: Path, capsys: pytest.CaptureFixture[str]):
    malformed = _legacy_round(repo)
    malformed.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        upgrade.preflight_lean_migration(repo)
    assert "invalid grill-round" in capsys.readouterr().out
    malformed.unlink()

    malformed.touch()
    primary = upgrade.lean_primary_inventory(repo)
    raw = upgrade.lean_raw_inventory(repo)
    assert primary == raw
    row = next(entry for entry in primary if entry["path"].endswith("old.json"))
    assert row["classification"] == "invalid"
    assert row["reason"] == "zero-byte legacy artifact"
    malformed.unlink()

    reviews = repo / ".factory/stories/S1/tasks/T1/reviews"
    reviews.mkdir(parents=True)
    (reviews.parent / "pr-ready.json").write_text(
        '{"commit":"sealed"}\n', encoding="utf-8")
    (reviews / "quality.json").write_text(
        json.dumps(_fixed_lens()) + "\n", encoding="utf-8")
    migration = {
        "entries": upgrade.lean_primary_inventory(repo),
        "input_inventory_digest": "a" * 64,
    }
    assert upgrade._fixed_review_candidates(repo, migration) == []
    for lens, digest in zip(upgrade.LEAN_LENSES, ("a", "b", "c")):
        (reviews / f"{lens}.json").write_text(
            json.dumps(_fixed_lens(delta=digest * 64)) + "\n", encoding="utf-8")
    migration["entries"] = upgrade.lean_primary_inventory(repo)
    with pytest.raises(SystemExit):
        upgrade._fixed_review_candidates(repo, migration)
    assert "conflicting" in capsys.readouterr().out

    external = repo.parent / "external"
    external.mkdir()
    unrelated = repo / ".factory" / "temporary-link"
    unrelated.symlink_to(external, target_is_directory=True)
    assert upgrade.lean_primary_inventory(repo) == upgrade.lean_raw_inventory(repo)

    unrelated.unlink()
    linked = repo / ".factory" / "plan-mode"
    linked.symlink_to(external, target_is_directory=True)
    with pytest.raises(SystemExit):
        upgrade.lean_primary_inventory(repo)
    with pytest.raises(SystemExit):
        upgrade.lean_raw_inventory(repo)
    linked.unlink()

    external_file = repo.parent / "external-plan-approval.json"
    external_file.write_text("{}\n", encoding="utf-8")
    candidate = repo / ".factory" / "plan-approval.json"
    candidate.symlink_to(external_file)
    with pytest.raises(SystemExit):
        upgrade.lean_primary_inventory(repo)
    with pytest.raises(SystemExit):
        upgrade.lean_raw_inventory(repo)
    candidate.unlink()

    migrations = repo / ".factory" / "migrations"
    migrations.symlink_to(external, target_is_directory=True)
    with pytest.raises(SystemExit):
        upgrade.preflight_lean_migration(repo)
    assert "linked or reparse" in capsys.readouterr().out


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


def test_lean_migration_resumes_durable_manifest_before_input_deletion(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    legacy = _legacy_round(repo)
    migration = upgrade.preflight_lean_migration(repo)
    assert migration is not None
    original_unlink = Path.unlink

    def interrupted_unlink(path: Path, *args, **kwargs):
        if path == legacy:
            raise OSError("simulated interruption")
        return original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", interrupted_unlink)
        with pytest.raises(OSError, match="simulated interruption"):
            upgrade.apply_lean_migration(repo, migration)
    manifest = repo / ".factory/migrations/lean-workflow-v2.json"
    assert manifest.is_file()
    assert "completed_at" not in json.loads(manifest.read_text())

    resumed = upgrade.preflight_lean_migration(repo)
    assert resumed is not None and resumed["resume"] is True
    upgrade.apply_lean_migration(repo, resumed)
    assert not legacy.exists()
    assert "completed_at" in json.loads(manifest.read_text())


def test_completed_lean_manifest_allows_later_runtime_versions(repo: Path):
    legacy = _legacy_round(repo)
    git(repo, "add", legacy.relative_to(repo).as_posix())
    git(repo, "commit", "-q", "-m", "legacy")
    first = _upgrade(repo)
    assert first.returncode == 0, first.stdout + first.stderr
    runtime = repo / "factory/scripts/forge_cli/approval.py"
    runtime.write_text(runtime.read_text(encoding="utf-8") + "\n# later runtime\n",
                       encoding="utf-8")
    assert upgrade.preflight_lean_migration(repo) is None


def test_completed_lean_manifest_tracks_intentionally_preserved_fixed_proof(
        repo: Path):
    fixed = repo / ".factory/stories/S1/tasks/T1/reviews/quality.json"
    fixed.parent.mkdir(parents=True, exist_ok=True)
    fixed.write_text(json.dumps(_fixed_lens()), encoding="utf-8")
    migration = upgrade.preflight_lean_migration(repo)
    assert migration is not None
    row = next(entry for entry in migration["entries"]
               if entry["path"] == fixed.relative_to(repo).as_posix())
    assert row["classification"] == "excluded"
    assert row["source_paths"] == [fixed.relative_to(repo).as_posix()]
    before = fixed.read_bytes()
    upgrade.apply_lean_migration(repo, migration)
    assert fixed.read_bytes() == before
    assert upgrade.preflight_lean_migration(repo) is None


def test_lean_migration_refuses_tampered_completed_manifest_and_preflight_preserves_target(
        repo: Path):
    legacy = _legacy_round(repo)
    git(repo, "add", legacy.relative_to(repo).as_posix())
    git(repo, "commit", "-q", "-m", "legacy")
    first = _upgrade(repo)
    assert first.returncode == 0, first.stdout + first.stderr
    manifest = repo / ".factory/migrations/lean-workflow-v2.json"
    data = json.loads(manifest.read_text())
    data["output_digest"] = "0" * 64
    manifest.write_text(json.dumps(data), encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "tamper completed migration")
    retry = _upgrade(repo)
    assert retry.returncode != 0 and "tampered" in retry.stdout

    manifest.unlink()
    malformed = repo / ".factory/stories/S1/tasks/T1/reviews/quality.json"
    malformed.parent.mkdir(parents=True, exist_ok=True)
    malformed.write_text("{}", encoding="utf-8")
    runtime = repo / "factory/scripts/forge_cli/approval.py"
    runtime.write_text("# client sentinel\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "malformed fixed proof")
    before = runtime.read_bytes()
    refused = _upgrade(repo)
    assert refused.returncode != 0 and "invalid fixed-review-lens" in refused.stdout
    assert runtime.read_bytes() == before


def test_lean_migration_forces_fresh_review_for_active_old_proof_and_migrates_only_exact_sealed_proof(
        repo: Path):
    root = repo / ".factory/stories/S1/tasks/T1/reviews"
    root.mkdir(parents=True, exist_ok=True)
    for lens in upgrade.LEAN_LENSES:
        (root / f"{lens}.json").write_text(
            json.dumps(_fixed_lens()), encoding="utf-8")
    migration = {
        "entries": upgrade.lean_primary_inventory(repo),
        "input_inventory_digest": "a" * 64,
    }
    # No pr-ready marker: active old fixed files cannot be promoted.
    fixed_rows = [row for row in migration["entries"]
                  if row["family"] == "fixed-review-lens"]
    assert {row["classification"] for row in fixed_rows} == {"excluded"}
    assert {row["reason"] for row in fixed_rows} == {
        "active fixed review requires a fresh review",
    }
    before = {path.name: path.read_bytes() for path in root.glob("*.json")}
    assert upgrade._fixed_review_candidates(repo, migration) == []
    upgrade.apply_lean_migration(repo, {
        **migration, "review_candidates": [], "review_sentinels": [],
    })
    assert {path.name: path.read_bytes() for path in root.glob("*.json")} == before
    marker = root.parent / "pr-ready.json"
    marker.write_text('{"commit":"sealed"}', encoding="utf-8")
    migration = {
        "entries": upgrade.lean_primary_inventory(repo),
        "input_inventory_digest": "a" * 64,
    }
    with pytest.raises(SystemExit):
        upgrade._fixed_review_candidates(repo, migration)


def test_lean_migration_refuses_sealed_fixed_proof_with_wrong_product_delta(
        repo: Path, capsys: pytest.CaptureFixture[str]):
    base = git(repo, "rev-parse", "HEAD").strip()
    branch = git(repo, "branch", "--show-current").strip()
    reviews = repo / ".factory/stories/S1/tasks/T1/reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    for lens in upgrade.LEAN_LENSES:
        (reviews / f"{lens}.json").write_text(
            json.dumps(_fixed_lens(delta="a" * 64)), encoding="utf-8")
    (reviews.parent / "pr-ready.json").write_text(json.dumps({
        "task_id": "T1", "branch": branch, "base_main_sha": base,
        "commit": base, "sealed_at": "2026-09-15T00:00:00+00:00",
    }), encoding="utf-8")
    git(repo, "add", ".factory/stories")
    git(repo, "commit", "-q", "-m", "mismatched sealed fixed proof")

    with pytest.raises(SystemExit):
        upgrade.preflight_lean_migration(repo)
    assert "delta does not match its marker" in capsys.readouterr().out


def test_lean_migration_promotes_valid_task_and_story_scoped_sealed_fixed_proof(
        repo: Path):
    base = git(repo, "rev-parse", "HEAD").strip()
    branch = git(repo, "branch", "--show-current").strip()
    roots = {
        ("S1", "T1"): repo / ".factory/stories/S1/tasks/T1/reviews",
        ("S2", "T2"): repo / ".factory/stories/S2/reviews",
    }
    for (story, task), reviews in roots.items():
        reviews.mkdir(parents=True, exist_ok=True)
        for lens in upgrade.LEAN_LENSES:
            (reviews / f"{lens}.json").write_text(
                json.dumps(_fixed_lens(task)), encoding="utf-8")
        marker = repo / f".factory/stories/{story}/tasks/{task}/pr-ready.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({
            "task_id": task, "branch": branch, "base_main_sha": base,
            "commit": base, "sealed_at": "2026-09-15T00:00:00+00:00",
        }), encoding="utf-8")
    git(repo, "add", ".factory/stories")
    git(repo, "commit", "-q", "-m", "sealed fixed proof fixtures")

    migration = upgrade.preflight_lean_migration(repo)
    assert migration is not None
    fixed_rows = [row for row in migration["entries"]
                  if row["family"] == "fixed-review-lens"]
    assert fixed_rows and {row["classification"] for row in fixed_rows} == {"eligible"}
    assert all(row["story"] in {"S1", "S2"} and row["task_id"] in {"T1", "T2"}
               and len(row["source_paths"]) == 3
               and row["marker_identity"]["commit"] == base
               and len(row["marker_identity"]["sha256"]) == 64
               for row in fixed_rows)
    assert {(row[0]["story"], row[0]["task_id"])
            for row in migration["review_candidates"]} == {("S1", "T1"), ("S2", "T2")}
    retry_preflight = upgrade.preflight_lean_migration(repo)
    assert retry_preflight is not None
    assert retry_preflight["review_candidates"] == migration["review_candidates"]
    from factory_lib import publish_review_generation
    selected_before = {}
    for candidate, _sources in migration["review_candidates"]:
        candidate = {
            **candidate,
            "upgrade": {**candidate["upgrade"], "inventory_digest": "b" * 64},
        }
        publish_review_generation(
            repo, candidate["story"], candidate["task_id"], candidate)
        selected_path = (repo / ".factory/stories" / candidate["story"] / "tasks"
                         / candidate["task_id"] / "reviews" / "selected.json")
        selected_before[(candidate["story"], candidate["task_id"])] = \
            selected_path.read_bytes()
    interrupted_retry = upgrade.preflight_lean_migration(repo)
    assert interrupted_retry is not None
    assert interrupted_retry["review_candidates"] == []
    assert len(interrupted_retry["review_sentinels"]) == 2
    upgrade.apply_lean_migration(repo, interrupted_retry)
    for story, task in roots:
        selected_path = repo / f".factory/stories/{story}/tasks/{task}/reviews/selected.json"
        assert selected_path.read_bytes() == selected_before[(story, task)]
        selected = json.loads(selected_path.read_text())
        generation = json.loads((repo / f".factory/stories/{story}/tasks/{task}/reviews/generations/{selected['generation_id']}.json").read_text())
        assert generation["origin"] == "upgrade"
        assert generation["upgrade"]["sealed_commit"] == base
    assert not any((root / f"{lens}.json").exists()
                   for root in roots.values() for lens in upgrade.LEAN_LENSES)


def test_lean_migration_revalidates_inventory_before_each_pointer_commit(
        repo: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]):
    base = git(repo, "rev-parse", "HEAD").strip()
    branch = git(repo, "branch", "--show-current").strip()
    for story, task in (("S1", "T1"), ("S2", "T2")):
        reviews = repo / f".factory/stories/{story}/tasks/{task}/reviews"
        reviews.mkdir(parents=True, exist_ok=True)
        for lens in upgrade.LEAN_LENSES:
            (reviews / f"{lens}.json").write_text(
                json.dumps(_fixed_lens(task)), encoding="utf-8")
        marker = reviews.parent / "pr-ready.json"
        marker.write_text(json.dumps({
            "task_id": task, "branch": branch, "base_main_sha": base,
            "commit": base, "sealed_at": "2026-09-15T00:00:00+00:00",
        }), encoding="utf-8")
    git(repo, "add", ".factory/stories")
    git(repo, "commit", "-q", "-m", "two sealed fixed proof fixtures")
    migration = upgrade.preflight_lean_migration(repo)
    assert migration is not None

    import factory_lib
    replace_selection = factory_lib._replace_review_selection
    changed = False

    def replace_then_drift(root: Path, destination: Path, selection: dict):
        nonlocal changed
        replace_selection(root, destination, selection)
        if not changed:
            changed = True
            source = repo / ".factory/stories/S2/tasks/T2/reviews/quality.json"
            value = json.loads(source.read_text())
            value["summary"] = "changed after first pointer"
            source.write_text(json.dumps(value), encoding="utf-8")

    monkeypatch.setattr(factory_lib, "_replace_review_selection", replace_then_drift)
    with pytest.raises(SystemExit):
        upgrade.apply_lean_migration(repo, migration)
    assert "inventory changed" in capsys.readouterr().out
    assert (repo / ".factory/stories/S1/tasks/T1/reviews/selected.json").is_file()
    assert not (repo / ".factory/stories/S2/tasks/T2/reviews/selected.json").exists()


def test_lean_migration_refuses_mixed_canonical_and_fixed_review_proof(
        repo: Path, capsys: pytest.CaptureFixture[str]):
    base = git(repo, "rev-parse", "HEAD").strip()
    branch = git(repo, "branch", "--show-current").strip()
    reviews = repo / ".factory/stories/S1/tasks/T1/reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    for lens in upgrade.LEAN_LENSES:
        (reviews / f"{lens}.json").write_text(
            json.dumps(_fixed_lens()), encoding="utf-8")
    marker = reviews.parent / "pr-ready.json"
    marker.write_text(json.dumps({
        "task_id": "T1", "branch": branch, "base_main_sha": base,
        "commit": base, "sealed_at": "2026-09-15T00:00:00+00:00",
    }), encoding="utf-8")
    selected = reviews / "selected.json"
    selected.write_text(json.dumps({
        "format": "forge-review-selection/v1", "story": "S1",
        "task_id": "T1", "generation_id": "b" * 64,
        "generation_sha256": "c" * 64, "delta_id": "a" * 64,
        "selected_at": "2026-09-15T00:00:00+00:00",
    }), encoding="utf-8")
    git(repo, "add", ".factory/stories")
    git(repo, "commit", "-q", "-m", "mixed fixed and canonical proof")
    before = selected.read_bytes()

    with pytest.raises(SystemExit):
        upgrade.preflight_lean_migration(repo)
    assert "mixed canonical and fixed review proof" in capsys.readouterr().out
    assert selected.read_bytes() == before


def test_normal_runtime_refuses_lean_removed_formats_with_upgrade_guidance(repo: Path):
    code, output = run(
        repo, "record_grill_from_json.py", "--gate", "requirements",
        stdin=json.dumps({
            "generated_by": "griller", "gate": "requirements", "verdict": "pass",
            "gaps": [], "contradictions": [], "resolutions": [], "rounds": [],
        }),
    )
    assert code != 0
    assert "run forge upgrade" in output.lower()
