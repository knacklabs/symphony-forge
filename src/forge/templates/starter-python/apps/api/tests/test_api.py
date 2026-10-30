"""HTTP contracts against the running app and its fresh Postgres database.

Audit: these cases own the same API contracts as the React starter's HTTP suite.
They catch broken sessions, CRUD, account permissions, validation, CSRF and reset
mail handling in the Python implementation. Forge's init and packaging tests
cannot exercise those behaviors. All data enters through HTTP, without a
test-only production seam or database fixtures.
"""

import json
import re
import subprocess
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx


def test_the_api_container_runs_as_a_user_that_is_not_root() -> None:
    # Audit: check the running image's user, not just its Dockerfile declaration.
    # A root runtime user can pass the HTTP cases; no production seam is needed.
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose.test.yml",
            "exec",
            "-T",
            "api",
            "id",
            "-u",
        ],
        cwd="../..",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip().isdigit(), result.stdout
    assert result.stdout.strip() != "0", result.stdout


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


# Audit: real HTTP and compose stdout own request completion logs. Missing or
# duplicate lines, raw paths, query leaks and early refusals regress this.
# Existing response tests do not inspect request logs; no production seam.
def test_each_api_request_writes_one_log_line_without_its_query_string(
    client: httpx.Client,
) -> None:
    words = [str(uuid4()) for _ in range(3)]
    expected: list[tuple[str, str, str | None, int]] = []

    def send(
        method: str, path: str, route: str | None, status: int, **headers: str
    ) -> None:
        correlation_id = str(uuid4())
        response = client.request(
            method, path, headers={"x-correlation-id": correlation_id, **headers}
        )
        assert response.status_code == status, response.text
        expected.append((correlation_id, method, route, status))

    send("GET", f"/api/v1/projects?search={words[0]}", "/api/v1/projects", 401)
    send("GET", f"/api/v1/projects/{uuid4()}", "/api/v1/projects/{project_id}", 401)
    send("GET", f"/api/v1/missing-{words[1]}", None, 404)
    sign_up(client)
    send("GET", f"/api/v1/auth/me?search={words[2]}", "/api/v1/auth/me", 200)
    send(
        "OPTIONS",
        "/api/v1/projects",
        None,
        204,
        Origin=str(client.base_url).rstrip("/"),
        **{"Access-Control-Request-Method": "POST"},
    )
    send("POST", "/api/v1/projects", None, 403, Origin="https://foreign.example")
    health_id, web_id = str(uuid4()), str(uuid4())
    assert (
        client.get("/health", headers={"x-correlation-id": health_id}).status_code
        == 200
    )
    assert client.get("/", headers={"x-correlation-id": web_id}).status_code == 200

    logs = compose_logs("api")
    events = [
        json.loads(line[line.index("{") :]) for line in logs.splitlines() if "{" in line
    ]
    for correlation_id, method, route, status in expected:
        matches = [
            event
            for event in events
            if event.get("message") == "API request"
            and event.get("correlationId") == correlation_id
        ]
        assert len(matches) == 1, matches
        event = matches[0]
        assert event["level"] == "info"
        duration = event["context"]["durationMs"]
        assert type(duration) is int and duration >= 0
        assert event["context"] == {
            "method": method,
            "route": route,
            "status": status,
            "durationMs": duration,
        }
    assert not any(
        event.get("correlationId") in {health_id, web_id} for event in events
    )
    assert all(word not in logs for word in words)


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


def test_projects_export_as_csv(client: httpx.Client) -> None:
    _, csrf = sign_up(client)
    for name in ('Plan, "draft"', "=1+1", "Deleted project"):
        created = client.post(
            "/api/v1/projects",
            json={"name": name, "status": "active"},
            headers={"x-csrf-token": csrf},
        )
        assert created.status_code == 201, created.text
    deleted = created.json()["data"]["id"]
    removed = client.delete(
        f"/api/v1/projects/{deleted}", headers={"x-csrf-token": csrf}
    )
    assert removed.status_code == 200, removed.text

    response = client.get("/api/v1/projects/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert (
        response.headers["content-disposition"] == 'attachment; filename="projects.csv"'
    )
    date_time = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}"
    lines = response.text.split("\r\n")
    assert len(lines) == 4, response.text
    assert lines[0] == "Name,Status,Created (UTC),Updated (UTC)"
    # Newest first, whatever order the screen sorts by.
    assert re.fullmatch(rf"'=1\+1,active,{date_time},{date_time}", lines[1])
    assert re.fullmatch(rf'"Plan, ""draft""",active,{date_time},{date_time}', lines[2])
    assert lines[3] == ""
    assert "Deleted project" not in response.text

    with httpx.Client(base_url=client.base_url, timeout=15) as other:
        sign_up(other)
        assert other.get("/api/v1/projects/export").text == (
            "Name,Status,Created (UTC),Updated (UTC)\r\n"
        )
    with httpx.Client(base_url=client.base_url, timeout=15) as anonymous:
        assert anonymous.get("/api/v1/projects/export").status_code == 401
