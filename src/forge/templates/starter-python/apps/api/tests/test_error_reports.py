"""HTTP error-report contracts.

Audit: each real crash or web report must produce one safe log; missing,
duplicate, or sensitive fields are credible failures. Existing HTTP tests cover
neither contract. These use real HTTP and Postgres without a test seam.
"""

import json
import subprocess
from collections.abc import Mapping
from typing import cast
from uuid import uuid4

import httpx
from test_api import compose_logs


def _run_psql(statement: str) -> None:
    subprocess.run(
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
            "-c",
            statement,
        ],
        cwd="../..",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=30,
    )


def _report_contexts(logs: str, error_id: str) -> list[Mapping[str, object]]:
    contexts: list[Mapping[str, object]] = []
    for line in logs.splitlines():
        if '"message":"Error report"' not in line:
            continue
        event = cast(Mapping[str, object], json.loads(line[line.index("{") :]))
        context = event.get("context")
        if isinstance(context, dict):
            report = cast(Mapping[str, object], context)
            if report.get("errorId") == error_id:
                contexts.append(report)
    return contexts


def test_an_api_crash_writes_one_error_report(client: httpx.Client) -> None:
    column = f"email_before_crash_{uuid4().hex}"
    _run_psql(f'ALTER TABLE account RENAME COLUMN email TO "{column}"')
    try:
        response = client.post(
            "/api/v1/auth/sign-up",
            json={
                "email": f"crash-{uuid4()}@example.test",
                "password": "correct-horse-battery-staple",
            },
        )
        assert response.status_code == 500, response.text
        body = response.json()
        error_id = body["error"]["errorId"]
        assert body["error"]["message"] == "Something went wrong. Try again."

        logs = compose_logs("api")
        contexts = _report_contexts(logs, error_id)
        assert len(contexts) == 1
        context = contexts[0]
        assert context["source"] == "api"
        assert context["name"] == "ProgrammingError"
        assert context["method"] == "POST"
        assert context["path"] == "/api/v1/auth/sign-up"
        assert context["status"] == 500
        assert "email_before_crash" not in logs
        assert "does not exist" not in logs
    finally:
        _run_psql(f'ALTER TABLE account RENAME COLUMN "{column}" TO email')


def test_accepts_a_public_web_error_report_and_logs_only_its_safe_fields(
    client: httpx.Client,
) -> None:
    path = "/projects?token=private-token#settings"
    invalid = client.post(
        "/api/v1/error-reports",
        json={"name": "TypeError", "path": "/projects", "token": "private-token"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "private-token" not in invalid.text

    response = client.post(
        "/api/v1/error-reports", json={"name": "TypeError", "path": path}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["success"] is True and body["error"] is None
    error_id = body["data"]["errorId"]

    logs = compose_logs("api")
    contexts = _report_contexts(logs, error_id)
    assert len(contexts) == 1
    assert contexts[0] == {
        "errorId": error_id,
        "source": "web",
        "name": "TypeError",
        "path": "/projects",
    }
    assert "private-token" not in logs
