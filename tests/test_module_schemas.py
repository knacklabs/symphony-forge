"""A new React starter moves each module's tables into its own Postgres schema."""
from pathlib import Path

import pytest

from test_setup import _fresh_client
from test_starter_tree import (
    LIVE,
    STARTER,
    _require_cases,
    live_python_run,
    live_run,
)


MIGRATION = Path(
    "apps/api/prisma/migrations/20261026000150_module_schemas/migration.sql"
)
PYTHON_STARTER = Path(__file__).resolve().parents[1] / "src/forge/templates/starter-python"
PYTHON_MIGRATION = Path("apps/api/migrations/versions/0008_module_schemas.py")


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("kind", ("react", "python"), ids=("react", "python"))
def test_4_each_module_keeps_its_tables_in_its_own_schema(
    repo, gh, tmp_path, tmp_path_factory, kind,
):
    # Audit: init must deliver each starter's schema migration to a new app. A missing or stale
    # migration leaves module tables in the shared schema. Existing starter database tests cover
    # extensions and IDs, not schema ownership. The live API run checks the migrated database and
    # schema drift; no production seam is needed.
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", kind)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    if kind == "react":
        assert (client / MIGRATION).read_bytes() == (STARTER / MIGRATION).read_bytes()
    else:
        assert (client / PYTHON_MIGRATION).read_bytes() == (PYTHON_STARTER / PYTHON_MIGRATION).read_bytes()

    if LIVE:
        result = live_run(tmp_path_factory) if kind == "react" else live_python_run(tmp_path_factory)
        _require_cases(result["api"], ("each module keeps its tables in its own schema",))
