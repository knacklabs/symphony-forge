"""A pending old Forge stage must not become a finished migrated story."""

import json

from test_migrate import _copied_client, _land

STORY = "forge-migrate-marks-an-active-plan-finis"


def test_1_pending_part_gets_replan_draft_and_is_named_in_dry_run(repo, tmp_path, monkeypatch):
    _copied_client(repo, tmp_path, monkeypatch)
    repo.write(".factory/stages.json", json.dumps({"stages": [
        {"id": "SIGNIN-1-T1", "status": "pending"}]}))
    _land(repo, "Record unfinished sign-in stage")

    dry = repo.forge("migrate", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert "Shoppers stay signed in (SIGNIN-1): not carried over" in dry.stdout
    assert ".forge-migrate/replan/SIGNIN-1.md" in dry.stdout
    assert "Parts not done yet:" in dry.stdout
    assert "| T1 | Longer sessions |" in dry.stdout
    assert "SIGNIN-1): its approval on main carries over, and it is finished" not in dry.stdout

    moved = repo.forge("migrate")
    assert moved.returncode == 0, moved.stderr
    assert repo.git("show", "forge/migrate-v1:.forge-migrate/replan/SIGNIN-1.md").startswith(
        "# Shoppers stay signed in")
    assert repo.git("ls-tree", "-r", "--name-only", "forge/migrate-v1", "plans/SIGNIN-1.md") == ""
