"""Module schema ownership through the running API and Postgres."""

import subprocess

import httpx
import pytest
from test_api import sign_up
from test_soft_delete import psql

EXPECTED_TABLE_SCHEMAS = (
    "core.account",
    "core.invite",
    "core.membership",
    "core.organisation",
    "core.password_reset_token",
    "core.session",
    "history.change_record",
    "projects.project",
)


@pytest.mark.parametrize(
    "expected_table_schemas",
    [
        pytest.param(
            EXPECTED_TABLE_SCHEMAS,
            id="each module keeps its tables in its own schema",
        )
    ],
)
def test_each_module_keeps_its_tables_in_its_own_schema(
    client: httpx.Client, expected_table_schemas: tuple[str, ...]
) -> None:
    # Audit: a migration that leaves a table in public breaks schema ownership, while a
    # cross-schema foreign key couples business modules. Existing API CRUD tests do not check
    # either database rule. This test uses HTTP and the migrated Postgres database directly.
    _, csrf = sign_up(client)
    created = client.post(
        "/api/v1/projects",
        headers={"x-csrf-token": csrf},
        json={"name": "Schema-owned project", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["data"]["id"]
    read = client.get(f"/api/v1/projects/{project_id}")
    assert read.status_code == 200, read.text
    assert read.json()["data"]["id"] == project_id

    tables = psql(
        "SELECT string_agg(table_schema || '.' || table_name, ',' "
        "ORDER BY table_schema, table_name) FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE' "
        "AND table_schema NOT IN ('pg_catalog', 'information_schema') "
        "AND table_name <> 'alembic_version'"
    )
    assert tables.returncode == 0, tables.stderr
    assert ",".join(expected_table_schemas) in [
        line.strip() for line in tables.stdout.splitlines()
    ]

    foreign_keys = psql(
        "SELECT CASE WHEN EXISTS (SELECT 1 FROM pg_constraint AS c "
        "JOIN pg_class AS source_table ON source_table.oid = c.conrelid "
        "JOIN pg_namespace AS source_schema ON source_schema.oid = source_table.relnamespace "
        "JOIN pg_class AS target_table ON target_table.oid = c.confrelid "
        "JOIN pg_namespace AS target_schema ON target_schema.oid = target_table.relnamespace "
        "WHERE c.contype = 'f' AND source_schema.nspname IN ('history', 'projects') "
        "AND target_schema.nspname IN ('history', 'projects') "
        "AND source_schema.nspname <> target_schema.nspname) "
        "THEN 'cross-schema foreign key found' ELSE 'no cross-schema foreign keys' END"
    )
    assert foreign_keys.returncode == 0, foreign_keys.stderr
    assert "no cross-schema foreign keys" in foreign_keys.stdout

    drift = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose.test.yml",
            "exec",
            "-T",
            "api",
            "uv",
            "run",
            "--no-sync",
            "alembic",
            "check",
        ],
        cwd="../..",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert drift.returncode == 0, drift.stdout + drift.stderr
