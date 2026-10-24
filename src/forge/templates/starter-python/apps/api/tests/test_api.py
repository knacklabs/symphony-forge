"""HTTP contracts against the running app and its fresh Postgres database.

Audit: these cases own the same API contracts as the React starter's HTTP suite.
They catch broken sessions, CRUD, account permissions, validation, CSRF and reset
mail handling in the Python implementation. Forge's init and packaging tests
cannot exercise those behaviors. All data enters through HTTP, without a
test-only production seam or database fixtures.
"""

import json
import subprocess
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx


def credentials() -> dict[str, str]:
    return {
        "email": f"starter-{uuid4()}@example.test",
        "password": "correct-horse-battery-staple",
    }


def sign_up(client: httpx.Client) -> tuple[dict[str, str], str]:
    account = credentials()
    response = client.post("/api/v1/auth/sign-up", json=account)
    assert response.status_code == 201, response.text
    return account, response.cookies["starter_csrf"]


def compose_logs(service: str) -> str:
    return subprocess.run(
        ["docker", "compose", "-f", "compose.test.yml", "logs", "--no-color", service],
        cwd="../..",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    ).stdout


def latest_reset_token() -> str:
    for line in reversed(compose_logs("api").splitlines()):
        if '"resetUrl"' in line:
            event = json.loads(line[line.index("{") :])
            reset_url = event["context"]["resetUrl"]
            assert isinstance(reset_url, str)
            return parse_qs(urlsplit(reset_url).query)["token"][0]
    raise AssertionError("The test mail provider did not log a reset link.")


def test_signs_up_signs_in_and_signs_out_with_a_server_session(
    client: httpx.Client,
) -> None:
    account = credentials()
    response = client.post("/api/v1/auth/sign-up", json=account)
    assert response.status_code == 201, response.text
    assert response.json()["data"]["email"] == account["email"]
    assert response.json()["success"] is True
    assert response.json()["error"] is None
    session_cookie = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith("starter_session=")
    )
    assert "httponly" in session_cookie.lower()
    assert "samesite=lax" in session_cookie.lower()
    assert client.get("/api/v1/auth/me").json()["data"]["email"] == account["email"]
    signed_out = client.post(
        "/api/v1/auth/sign-out",
        headers={"x-csrf-token": response.cookies["starter_csrf"]},
    )
    assert signed_out.status_code == 200, signed_out.text
    assert client.get("/api/v1/auth/me").status_code == 401
    signed_in = client.post("/api/v1/auth/sign-in", json=account)
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["data"]["email"] == account["email"]
    assert client.get("/api/v1/auth/me").status_code == 200


def test_creates_lists_reads_updates_and_deletes_a_project(
    client: httpx.Client,
) -> None:
    _, csrf = sign_up(client)
    headers = {"x-csrf-token": csrf}
    created = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "First project", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["data"]["id"]
    listed = client.get("/api/v1/projects?page=1&limit=20&sortBy=name&sortOrder=asc")
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["items"] == [created.json()["data"]]
    assert listed.json()["data"]["pagination"] == {
        "page": 1,
        "limit": 20,
        "totalItems": 1,
        "totalPages": 1,
    }
    assert (
        client.get(f"/api/v1/projects/{project_id}").json()["data"]["id"] == project_id
    )
    updated = client.put(
        f"/api/v1/projects/{project_id}",
        headers=headers,
        json={"name": "Renamed project", "status": "archived"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["name"] == "Renamed project"
    assert updated.json()["data"]["status"] == "archived"
    deleted = client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"success": True, "data": None, "error": None}
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404


def test_account_isolation_returns_404_and_leaves_the_project_unchanged(
    client: httpx.Client,
) -> None:
    owner, csrf = sign_up(client)
    created = client.post(
        "/api/v1/projects",
        headers={"x-csrf-token": csrf},
        json={"name": "Private project", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["data"]["id"]
    _, other_csrf = sign_up(client)
    assert client.get("/api/v1/projects").json()["data"]["items"] == []
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
    assert (
        client.put(
            f"/api/v1/projects/{project_id}",
            headers={"x-csrf-token": other_csrf},
            json={"name": "Changed by another account", "status": "archived"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/projects/{project_id}", headers={"x-csrf-token": other_csrf}
        ).status_code
        == 404
    )
    assert client.post("/api/v1/auth/sign-in", json=owner).status_code == 200
    unchanged = client.get(f"/api/v1/projects/{project_id}")
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["data"]["name"] == "Private project"
    assert unchanged.json()["data"]["status"] == "active"


def test_forgot_password_gives_the_same_reply_for_known_and_unknown_addresses(
    client: httpx.Client,
) -> None:
    account, _ = sign_up(client)
    known = client.post(
        "/api/v1/auth/forgot-password", json={"email": account["email"]}
    )
    unknown = client.post(
        "/api/v1/auth/forgot-password", json={"email": credentials()["email"]}
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert known.json()["data"]["message"] == (
        "If an account exists, a reset link has been sent."
    )


def test_resets_a_password_once_and_signs_out_old_sessions(
    client: httpx.Client,
) -> None:
    account, _ = sign_up(client)
    response = client.post(
        "/api/v1/auth/forgot-password", json={"email": account["email"]}
    )
    assert response.status_code == 200, response.text
    token = latest_reset_token()
    new_password = "different-correct-horse-password"
    reset = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": new_password}
    )
    assert reset.status_code == 200, reset.text
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/sign-in", json=account).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/sign-in", json={**account, "password": new_password}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": account["password"]},
        ).status_code
        == 400
    )


def test_rejects_invalid_input_with_field_errors_in_the_envelope(
    client: httpx.Client,
) -> None:
    response = client.post(
        "/api/v1/auth/sign-up",
        json={"email": "not-an-email", "password": "short", "unexpected": True},
    )
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["success"] is False and body["data"] is None
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Check the fields and try again."
    assert body["error"]["errorId"]
    assert all(
        isinstance(error["field"], str) and isinstance(error["reason"], str)
        for error in body["error"]["details"]["fieldErrors"]
    )
    assert {error["field"] for error in body["error"]["details"]["fieldErrors"]} == {
        "email",
        "password",
        "unexpected",
    }


def test_rejects_a_whitespace_only_project_name(client: httpx.Client) -> None:
    _, csrf = sign_up(client)
    response = client.post(
        "/api/v1/projects",
        headers={"x-csrf-token": csrf},
        json={"name": "   ", "status": "active"},
    )
    assert response.status_code == 400, response.text
    assert any(
        field["field"] == "name"
        for field in response.json()["error"]["details"]["fieldErrors"]
    )


def test_requires_sign_in_and_csrf_before_project_changes(client: httpx.Client) -> None:
    response = client.get("/api/v1/projects")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    _, csrf = sign_up(client)
    project = {"name": "No token", "status": "active"}
    assert client.post("/api/v1/projects", json=project).status_code == 403
    response = client.post(
        "/api/v1/projects", json=project, headers={"x-csrf-token": csrf + "wrong"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_CHECK_FAILED"


def test_rejects_cross_origin_sign_in(client: httpx.Client) -> None:
    response = client.post(
        "/api/v1/auth/sign-up",
        json=credentials(),
        headers={"Origin": "https://attacker.example"},
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "CSRF_CHECK_FAILED"


def test_production_forgot_password_does_not_log_a_reset_link(
    production_client: httpx.Client,
) -> None:
    account, _ = sign_up(production_client)
    known = production_client.post(
        "/api/v1/auth/forgot-password", json={"email": account["email"]}
    )
    unknown = production_client.post(
        "/api/v1/auth/forgot-password", json={"email": credentials()["email"]}
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    token = "x" * 43
    page = production_client.get(f"/reset-password?token={token}")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    logs = compose_logs("production-api")
    assert "/reset-password" not in logs
    assert token not in logs
