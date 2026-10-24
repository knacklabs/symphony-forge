"""New apps protect projects in Postgres; upgrades leave existing app code alone."""
import json
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_python_starter import live_python_starter  # noqa: F401 - shared live stack fixture
from test_setup import _fresh_client
from test_starter_tree import LIVE, STARTER, _require_cases, live_run

STORY = "FORGE-DEFAULTS-1"
MIGRATIONS = {
    "react": Path("apps/api/prisma/migrations/20261025000300_soft_delete_only/migration.sql"),
    "python": Path("apps/api/migrations/versions/0002_soft_delete_only.py"),
}


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["react", "python", "earlier adopted"])
def test_4_the_database_refuses_to_remove_a_record_completely(
        repo, gh, tmp_path, starter, request):
    # Audit: init must ship the protection and its real HTTP/SQL case for each backend.
    # Missing migrations or omitted template files would leave new apps unprotected.
    # Existing format/init tests do not exercise a database DELETE; the live cases own it.
    # This uses Forge init/sync and the running starters, with no production test seam.
    if starter == "earlier adopted":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        old_migration = repo.path / "apps/api/prisma/migrations/initial/migration.sql"
        old_migration.parent.mkdir(parents=True)
        old_migration.write_text("CREATE TABLE client_record (id integer);\n", encoding="utf-8")
        before = {path.relative_to(repo.path): path.read_bytes()
                  for path in (repo.path / "apps").rglob("*") if path.is_file()}
        repo.git("checkout", "-b", "fix/check-soft-delete-upgrade")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        after = {path.relative_to(repo.path): path.read_bytes()
                 for path in (repo.path / "apps").rglob("*") if path.is_file()}
        assert after == before
        return

    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", starter)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    source = STARTER if starter == "react" else STARTER.parent / "starter-python"
    migration = MIGRATIONS[starter]
    assert (source / migration).is_file(), "the starter has no hard-delete protection migration"
    assert (client / migration).read_bytes() == (source / migration).read_bytes()
    case_file = Path("apps/api/test/soft-delete.e2e-spec.ts") if starter == "react" else Path(
        "apps/api/tests/test_soft_delete.py")
    assert (client / case_file).read_bytes() == (source / case_file).read_bytes()
    if LIVE:
        live = live_run(request.getfixturevalue("tmp_path_factory")) if starter == "react" else (
            request.getfixturevalue("live_python_starter"))
        case = "the database refuses a hard delete of a project" if starter == "react" else (
            "test_the_database_refuses_a_hard_delete_of_a_project")
        _require_cases(live["api"], (case,))
