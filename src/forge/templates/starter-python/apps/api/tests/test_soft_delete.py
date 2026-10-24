"""The database's hard-delete rule is exercised through the running API and Postgres."""

import subprocess
from uuid import uuid4

import httpx


def create_project(client: httpx.Client) -> tuple[str, str]:
    account = {
        "email": f"starter-{uuid4()}@example.test",
        "password": "correct-horse-battery-staple",
    }
    sign_up = client.post("/api/v1/auth/sign-up", json=account)
    assert sign_up.status_code == 201, sign_up.text
    csrf = sign_up.cookies["starter_csrf"]
    created = client.post(
        "/api/v1/projects",
        headers={"x-csrf-token": csrf},
        json={"name": "Protected project", "status": "active"},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"], csrf


def psql(sql: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose.test.yml",
            "exec",
            "-T",
            "database",
            "psql",
            "-U",
            "postgres",
            "-d",
            "starter_test",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ],
        cwd="../..",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )


def test_the_database_refuses_a_hard_delete_of_a_project(
    client: httpx.Client,
) -> None:
    project_id, csrf = create_project(client)

    hard_delete = psql(f"DELETE FROM project WHERE id = '{project_id}'")
    assert hard_delete.returncode != 0
    assert "are soft deleted" in hard_delete.stdout + hard_delete.stderr
    retained_by_api = client.get(f"/api/v1/projects/{project_id}")
    assert retained_by_api.status_code == 200, retained_by_api.text

    soft_delete = client.delete(
        f"/api/v1/projects/{project_id}", headers={"x-csrf-token": csrf}
    )
    assert soft_delete.status_code == 200, soft_delete.text
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
    retained_in_database = psql(
        "SELECT CASE WHEN EXISTS (SELECT 1 FROM project "
        f"WHERE id = '{project_id}' AND deleted_at_utc IS NOT NULL) "
        "THEN 'retained' ELSE 'missing' END"
    )
    assert retained_in_database.returncode == 0, retained_in_database.stderr
    assert "retained" in retained_in_database.stdout
