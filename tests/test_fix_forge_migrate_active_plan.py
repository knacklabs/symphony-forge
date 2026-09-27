"""A pending old Forge stage must not become a finished migrated story."""

import json

import pytest

from test_migrate import _copied_client, _land

STORY = "forge-migrate-marks-an-active-plan-finis"


@pytest.mark.parametrize(("old", "key", "title", "part"), [
    ("SIGNIN-1", "SIGNIN-1", "Shoppers stay signed in", "| T1 | Longer sessions |"),
    ("tidy-up", "TIDY-UP", "The shop code is easy to change",
     "| T2 | Remove the old helpers |"),
])
def test_1_pending_part_gets_replan_draft_and_is_named_in_dry_run(
        repo, tmp_path, monkeypatch, old, key, title, part):
    _copied_client(repo, tmp_path, monkeypatch)
    if key == "SIGNIN-1":
        repo.write(".factory/stages.json", json.dumps({"stages": [
            {"id": "SIGNIN-1-T1", "status": "pending"}]}))
        _land(repo, "Record unfinished sign-in stage")

    dry = repo.forge("migrate", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert f"{title} ({key}): not carried over" in dry.stdout
    assert f".forge-migrate/replan/{key}.md" in dry.stdout
    assert "Parts not done yet:" in dry.stdout
    assert part in dry.stdout
    assert f"{key}): its approval on main carries over" not in dry.stdout

    moved = repo.forge("migrate")
    assert moved.returncode == 0, moved.stderr
    assert repo.git("show", f"forge/migrate-v1:.forge-migrate/replan/{key}.md").startswith(
        f"# {title}")
    assert repo.git("ls-tree", "-r", "--name-only", "forge/migrate-v1", f"plans/{key}.md") == ""
