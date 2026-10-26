"""New apps start on Postgres 18 with the three day-one extensions."""
import re
from pathlib import Path

import pytest

from test_setup import _fresh_client
from test_starter_tree import LIVE, STARTER, _require_cases, live_run

pytest_plugins = ("test_python_starter",)

STORY = "FORGE-DATABASE-1"
MIGRATIONS = {
    "react": Path("apps/api/prisma/migrations/20261026000000_extensions/migration.sql"),
    "python": Path("apps/api/migrations/versions/0006_extensions.py"),
}


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("kind", ("react", "python"))
def test_2_starters_run_postgres_18_with_three_extensions(
    repo, gh, tmp_path, tmp_path_factory, request, kind,
):
    # Audit: init must deliver the database config and extension migration unchanged.
    # An old image, wrong data mount or omitted migration breaks that setup contract.
    # Existing starter tests do not own the database version or extension availability.
    # The live cases separately prove migration execution and preload against real Postgres;
    # both checks use existing command and Docker boundaries, with no production test seam.
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", kind)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    source = STARTER if kind == "react" else STARTER.parent / "starter-python"
    compose = (client / "compose.test.yml").read_text(encoding="utf-8")
    assert re.search(r"image: postgres:18\.\d+-alpine\s", compose), compose
    assert 'command: ["postgres", "-c", "shared_preload_libraries=pg_stat_statements"]' in compose
    assert "tmpfs: /var/lib/postgresql\n" in compose
    for relative in (Path("compose.test.yml"), MIGRATIONS[kind]):
        assert (client / relative).read_bytes() == (source / relative).read_bytes(), relative

    if LIVE:
        if kind == "python":
            result = request.getfixturevalue("live_python_starter")
            case = "test_the_database_runs_postgres_18_with_the_day_one_extensions"
        else:
            result = live_run(tmp_path_factory)
            case = "the database runs Postgres 18 with the day-one extensions"
        _require_cases(result["api"], (case,))


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("kind", ("react", "python"))
def test_3_new_rows_get_time_ordered_ids_and_updated_times(
    repo, gh, tmp_path, tmp_path_factory, request, kind,
):
    # Audit: init must copy the id migration and database-generated schema defaults.
    # Omitting either leaves new apps with random ids or no direct-SQL update clock.
    # test_2 owns extensions, not ids; the live API/SQL case owns runtime behavior
    # and schema drift. These use existing entry points, with no production seam.
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", kind)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    if kind == "python":
        source = STARTER.parent / "starter-python"
        migration = Path("apps/api/migrations/versions/0007_ids_and_updated_at.py")
        assert (client / migration).read_bytes() == (source / migration).read_bytes()
        models = list((client / "apps/api/app").glob("*/models.py"))
        assert models
        for model in models:
            text = model.read_text(encoding="utf-8")
            assert "uuid4" not in text, model
            for field in re.findall(r"^\s*id: Mapped\[UUID\] = (.+)$", text, re.MULTILINE):
                assert 'server_default=text("uuidv7()")' in field, model
        for service in (client / "apps/api/app").glob("*/service.py"):
            assert "uuid4()" not in service.read_text(encoding="utf-8"), service
        if LIVE:
            result = request.getfixturevalue("live_python_starter")
            _require_cases(result["api"], (
                "test_a_new_row_gets_a_time_ordered_id_and_an_update_sets_its_last_changed_time",
            ))
        return
    migration = Path("apps/api/prisma/migrations/20261026000100_ids_and_updated_at/migration.sql")
    assert (client / migration).read_bytes() == (STARTER / migration).read_bytes()
    schemas = list((client / "apps/api/prisma/schema").glob("*.prisma"))
    assert schemas
    for schema in schemas:
        text = schema.read_text(encoding="utf-8")
        assert "@default(uuid())" not in text, schema
        for field in re.findall(r"^\s*id\s+String\s+(.+)$", text, re.MULTILINE):
            assert '@default(dbgenerated("uuidv7()"))' in field, schema

    if LIVE:
        result = live_run(tmp_path_factory)
        _require_cases(result["api"], (
            "a new row gets a time-ordered id and an update sets its last-changed time",
        ))
