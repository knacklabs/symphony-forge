"""A copied-in client's finished task stays finished despite another story's stage."""

import json

import pytest

from test_migrate import _copied_client, _land
from test_setup import _fresh_client

STORY = "skipped-workers"


@pytest.mark.parametrize("path", [
    ".factory/stages.json",
    ".factory/stories/SIGNIN-1/stages.json",
])
def test_5_migration_filters_stage_records_by_story(repo, tmp_path, monkeypatch, path):
    # Migration applies to clients adopted on the copied-in release, represented by
    # plain text fixtures; a fresh installed-v1 repo has no copied-in layout to move.
    _copied_client(repo, tmp_path, monkeypatch)
    repo.write(path, json.dumps({"stages": [
        {"story": "SIGNIN-1", "id": "SIGNIN-1-T1", "status": "done"},
        {"story": "OTHER-1", "id": "SIGNIN-1-T1", "status": "pending"},
    ]}))
    _land(repo, "Record stages from different stories")

    dry = repo.forge("migrate", "--dry-run")
    assert dry.returncode == 0, dry.stderr
    assert ("Shoppers stay signed in (SIGNIN-1): its approval on main carries over, and "
            "it is finished: every part was done before the move.") in dry.stdout
    moved = repo.forge("migrate")
    assert moved.returncode == 0, moved.stderr
    assert repo.git("show", "forge/migrate-v1:plans/SIGNIN-1.md").startswith(
        "# Shoppers stay signed in")
    assert repo.git("ls-tree", "-r", "--name-only", "forge/migrate-v1",
                    ".forge-migrate/replan/SIGNIN-1.md") == ""
    after = repo.forge("next", cwd=tmp_path / "repo-forge-migrate-v1")
    assert after.returncode == 0, after.stderr
    assert "Shoppers stay signed in" not in after.stdout


def test_6_new_client_needs_no_copied_in_migration(repo, gh, tmp_path):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stderr
    before = (repo.git("rev-parse", "HEAD", cwd=client),
              repo.git("status", "--porcelain", cwd=client),
              repo.git("for-each-ref", cwd=client))
    migrated = repo.forge("migrate", cwd=client)
    assert migrated.returncode == 1, migrated.stdout
    assert "has no copied-in factory/ layout to move" in migrated.stderr
    assert migrated.stderr.endswith("Next: forge next\n")
    assert (repo.git("rev-parse", "HEAD", cwd=client),
            repo.git("status", "--porcelain", cwd=client),
            repo.git("for-each-ref", cwd=client)) == before
