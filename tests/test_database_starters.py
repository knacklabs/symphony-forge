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
