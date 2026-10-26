"""Live Postgres database contracts."""

import subprocess

import httpx

from test_api import credentials, sign_up
from test_soft_delete import psql


def test_the_starter_tables_follow_the_database_skill(client: httpx.Client) -> None:
    # Audit: API-created rows must retain the same HTTP contract while SQL rejects
    # invalid statuses, roles, names and upper-case sign-in/invite emails.
    # Native enums and varchar used to supply only part of this contract.
    # The init test owns delivery; this real Postgres test owns enforcement and
    # model/migration drift. Existing HTTP and CLI boundaries need no new seam.
    account, csrf = sign_up(client)
    headers = {"x-csrf-token": csrf}
    created = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Column rules", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["data"]["id"]
    invite_email = credentials()["email"]
    invited = client.post(
        "/api/v1/invites", headers=headers, json={"email": invite_email}
    )
    assert invited.status_code == 201, invited.text

    types = psql(
        "SELECT count(*) AS forbidden_types FROM information_schema.columns "
        "WHERE table_schema IN ('core', 'projects', 'history') "
        "AND table_name NOT IN ('alembic_version', '_prisma_migrations') "
        "AND data_type IN ('character varying', 'USER-DEFINED', "
        "'timestamp without time zone')"
    )
    assert types.returncode == 0, types.stderr
    counts = [
        line.strip() for line in types.stdout.splitlines() if line.strip().isdigit()
    ]
    assert counts == ["0"], types.stdout

    for sql, constraint in (
        (
            f"UPDATE projects.project SET status = 'paused' WHERE id = '{project_id}'",
            "project_status_allowed",
        ),
        (
            "UPDATE core.membership SET role = 'owner' WHERE account_id = "
            f"(SELECT id FROM core.account WHERE email = '{account['email']}')",
            "membership_role_allowed",
        ),
        (
            f"UPDATE projects.project SET name = '' WHERE id = '{project_id}'",
            "project_name_length",
        ),
        (
            "UPDATE projects.project SET name = repeat('x', 121) "
            f"WHERE id = '{project_id}'",
            "project_name_length",
        ),
        (
            "UPDATE core.account SET email = upper(email) "
            f"WHERE email = '{account['email']}'",
            "account_email_lower",
        ),
        (
            "UPDATE core.invite SET email = upper(email) "
            f"WHERE email = '{invite_email}'",
            "invite_email_lower",
        ),
    ):
        rejected = psql(sql)
        assert rejected.returncode != 0, rejected.stdout
        assert constraint in rejected.stderr, rejected.stderr

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


def test_the_database_runs_postgres_18_with_the_day_one_extensions() -> None:
    version = psql("SHOW server_version_num")
    assert version.returncode == 0, version.stderr
    version_number = next(
        (
            int(line.strip())
            for line in version.stdout.splitlines()
            if line.strip().isdigit()
        ),
        None,
    )
    assert version_number is not None and version_number >= 180000, version.stdout

    extensions = psql(
        "SELECT string_agg(extname::text, ',' ORDER BY extname) FROM pg_extension "
        "WHERE extname IN ('btree_gin', 'pg_stat_statements', 'pg_trgm')"
    )
    assert extensions.returncode == 0, extensions.stderr
    assert "btree_gin,pg_stat_statements,pg_trgm" in extensions.stdout

    statistics = psql("SELECT count(*) FROM pg_stat_statements")
    assert statistics.returncode == 0, statistics.stderr


def test_a_new_row_gets_a_time_ordered_id_and_an_update_sets_its_last_changed_time(
    client: httpx.Client,
) -> None:
    # Audit: real API writes must use UUIDv7 on every table, and SQL updates must
    # advance the database clock. Random service ids or a missing default/trigger
    # break this contract. Init checks only delivery, not running database behavior.
    # Existing HTTP/psql boundaries need no production test seam.
    account, csrf = sign_up(client)
    headers = {"x-csrf-token": csrf}
    created = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Time-ordered project", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["data"]["id"]
    invited = client.post(
        "/api/v1/invites", headers=headers, json={"email": credentials()["email"]}
    )
    assert invited.status_code == 201, invited.text
    reset = client.post(
        "/api/v1/auth/forgot-password", json={"email": account["email"]}
    )
    assert reset.status_code == 200, reset.text

    tables = (
        "account",
        "session",
        "password_reset_token",
        "organisation",
        "membership",
        "invite",
        "project",
        "change_record",
    )
    for table in tables:
        schema = (
            "projects"
            if table == "project"
            else "history"
            if table == "change_record"
            else "core"
        )
        versions = psql(
            "SELECT CASE WHEN count(*) > 0 AND "
            "count(*) FILTER (WHERE uuid_extract_version(id) IS DISTINCT FROM 7) = 0 "
            f"THEN 'all-v7' ELSE 'invalid-ids' END FROM {schema}.{table}"
        )
        assert versions.returncode == 0, versions.stderr
        assert "all-v7" in versions.stdout, (table, versions.stdout)
        default = psql(
            "SELECT column_default FROM information_schema.columns "
            f"WHERE table_schema = '{schema}' AND table_name = '{table}' "
            "AND column_name = 'id'"
        )
        assert default.returncode == 0, default.stderr
        assert "uuidv7()" in default.stdout, (table, default.stdout)

    # No clock manipulation or delay: this update is a later transaction.
    updated = psql(
        "WITH previous AS MATERIALIZED ("
        f"SELECT id, updated_at_utc FROM projects.project WHERE id = '{project_id}') "
        "UPDATE projects.project SET name = 'Changed through SQL' FROM previous "
        "WHERE project.id = previous.id RETURNING CASE "
        "WHEN project.updated_at_utc > previous.updated_at_utc "
        "THEN 'advanced' ELSE 'unchanged' END"
    )
    assert updated.returncode == 0, updated.stderr
    assert "advanced" in updated.stdout, updated.stdout
    assert "unchanged" not in updated.stdout, updated.stdout
