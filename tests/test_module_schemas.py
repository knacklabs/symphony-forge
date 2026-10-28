"""Both new client starters keep each module's tables in its own Postgres schema."""
from pathlib import Path

import pytest

from test_setup import _fresh_client
from test_close import CLEAN, GREEN, env  # noqa: F401 (fixture)
from test_score_notes import _client_repo as setup_client
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

STORY = "FORGE-LIBS-1"


def _review_reports_a_foreign_key_between_business_module_schemas(env, tmp_path, adopted):
    # Audit: close must send the schema rule to the reviewer on both adoption paths.
    # A lost rule or exception would silently change review instructions. The live schema
    # case below checks the starter database, not prompt delivery. Only external edges are
    # stubbed; this tests delivery, not a model's judgement, and needs no production seam.
    setup_client(env, tmp_path, adopted)
    env.checks(GREEN)
    item, _ = env.start(
        "module-link", "fix/module-link", ".factory/fixes/module-link.json",
        {"kind": "fix", "why": "Link business modules",
         "done_when": "The module link follows the schema rule"},
        {"link.sql": 'ALTER TABLE projects."Project" ADD COLUMN "historyId" uuid '
                     'REFERENCES history."History"(id);\n'},
    )
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert (
        "In an app with a database, report a foreign key that this change adds between two "
        "business-module Postgres schemas as a P1 finding titled `Module foreign key: <the link>`. "
        "A link between business modules stores an indexed id without a foreign key and is "
        "checked through the other module's public service. Links within a module and links "
        "to core keep their foreign key. A foreign key the default branch already has is not "
        "a finding; existing apps keep their tables and schemas."
    ) in " ".join(env.prompt().split())


def _starter_keeps_each_module_tables_in_its_own_schema(
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


@pytest.mark.parametrize(
    ("scenario", "value"),
    [
        pytest.param("review", False, id="review-new-client"),
        pytest.param("review", True, id="review-adopted-v1.2.2"),
        pytest.param("schema", "react", marks=(pytest.mark.platform, pytest.mark.timeout(1800)),
                     id="react"),
        pytest.param("schema", "python", marks=(pytest.mark.platform, pytest.mark.timeout(1800)),
                     id="python"),
    ],
)
def test_4_each_module_keeps_its_tables_in_its_own_schema(
    request, tmp_path, tmp_path_factory, scenario, value,
):
    # Audit: one owner covers Done when 4 at both boundaries: starter delivery and review guidance.
    # The scenarios share the criterion but keep their separate init/schema and close/review paths.
    if scenario == "review":
        _review_reports_a_foreign_key_between_business_module_schemas(
            request.getfixturevalue("env"), tmp_path, value,
        )
    else:
        _starter_keeps_each_module_tables_in_its_own_schema(
            request.getfixturevalue("repo"), request.getfixturevalue("gh"),
            tmp_path, tmp_path_factory, value,
        )
