"""Change history contracts at the running API boundary."""

import csv
import io
import re
from datetime import datetime, timedelta
from typing import cast
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session
from test_api import credentials, sign_up
from test_invites import invite

from app.core import AccountPrincipal
from app.history.models import ChangeRecord
from app.history.service import HistoryService


class _RecordingSession:
    def __init__(self) -> None:
        self.records: list[ChangeRecord] = []

    def add(self, record: ChangeRecord) -> None:
        self.records.append(record)


def test_history_records_the_agent_that_acts_for_a_person() -> None:
    # Audit: this owns the service mapping from a person-signed agent principal to the stored
    # history value, including the empty case. HTTP history tests cannot supply such a principal;
    # HistoryService already accepts the caller's session, so a recording stub needs no seam.
    session = _RecordingSession()
    service = HistoryService(cast(Session, session))
    organisation_id = uuid4()
    service.record(
        AccountPrincipal(
            uuid4(),
            "person@example.test",
            organisation_id,
            "admin",
            "the assistant",
        ),
        "project.created",
        "Created a project",
    )
    service.record(
        AccountPrincipal(uuid4(), "other@example.test", organisation_id, "admin"),
        "project.created",
        "Created another project",
    )

    assert [record.via_agent for record in session.records] == [
        "the assistant",
        None,
    ]


def test_an_invite_and_a_role_change_write_change_history(
    client: httpx.Client,
) -> None:
    # Audit: this protects the public history DTO, newest-first action order, organisation
    # isolation, and admin-only access for the list and export. A missing history write or an
    # unscoped/unguarded endpoint breaks it. Invite and role tests cover those actions without
    # history, and the React API suite cannot prove the Python API contract. It uses real HTTP
    # and Postgres, with the existing logged test invite link only to create a member; no
    # production test seam is needed.
    admin, csrf = sign_up(client)
    invited = credentials()
    token = invite(client, csrf, invited["email"])

    with httpx.Client(base_url=client.base_url, timeout=15) as member:
        joined = member.post(
            "/api/v1/auth/accept-invite",
            json={**invited, "token": token},
        )
        assert joined.status_code == 201, joined.text
        for path in ("/api/v1/history", "/api/v1/history/export"):
            denied = member.get(path)
            assert denied.status_code == 403, denied.text
            assert denied.json()["error"]["code"] == "ADMIN_ONLY"

    changed = client.patch(
        f"/api/v1/members/{joined.json()['data']['id']}",
        headers={"x-csrf-token": csrf},
        json={"role": "admin"},
    )
    assert changed.status_code == 200, changed.text

    response = client.get("/api/v1/history")
    assert response.status_code == 200, response.text
    entries = response.json()["data"]
    assert len(entries) == 2
    assert [entry["summary"] for entry in entries] == [
        f"Changed {invited['email']} from member to admin",
        f"Invited {invited['email']}",
    ]
    for entry in entries:
        assert set(entry) == {"id", "actorEmail", "summary", "createdAtUtc"}
        assert isinstance(entry["id"], str) and entry["id"]
        assert entry["actorEmail"] == admin["email"]
        timestamp = datetime.fromisoformat(entry["createdAtUtc"])
        assert timestamp.tzinfo is not None
        assert timestamp.utcoffset() == timedelta(0)
    assert datetime.fromisoformat(entries[0]["createdAtUtc"]) >= datetime.fromisoformat(
        entries[1]["createdAtUtc"]
    )

    with httpx.Client(base_url=client.base_url, timeout=15) as other_organisation:
        sign_up(other_organisation)
        empty = other_organisation.get("/api/v1/history")
        assert empty.status_code == 200, empty.text
        assert empty.json()["data"] == []
        empty_export = other_organisation.get("/api/v1/history/export")
        assert empty_export.status_code == 200, empty_export.text
        assert empty_export.text == "When (UTC),Who,What\r\n"

    with httpx.Client(base_url=client.base_url, timeout=15) as anonymous:
        for path in ("/api/v1/history", "/api/v1/history/export"):
            denied = anonymous.get(path)
            assert denied.status_code == 401, denied.text
            assert denied.json()["error"]["code"] == "UNAUTHENTICATED"


def test_change_history_exports_as_csv(client: httpx.Client) -> None:
    # Audit: this protects the 100-row list limit, the complete newest-first CSV, and its UTC
    # header and timestamps. Truncating the export or making it follow the list limit would lose
    # older actions. Existing project and member export tests do not exercise history retention;
    # the React contract cannot establish the Python API result. All 101 actions enter through
    # HTTP against Postgres, and no production test seam or mail-log read is needed.
    admin, csrf = sign_up(client)
    emails = [credentials()["email"] for _ in range(101)]
    for email in emails:
        invited = client.post(
            "/api/v1/invites",
            headers={"x-csrf-token": csrf},
            json={"email": email},
        )
        assert invited.status_code == 201, invited.text

    history = client.get("/api/v1/history")
    assert history.status_code == 200, history.text
    assert len(history.json()["data"]) == 100
    assert history.json()["data"][0]["summary"] == f"Invited {emails[100]}"
    assert history.json()["data"][99]["summary"] == f"Invited {emails[1]}"

    response = client.get("/api/v1/history/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert (
        response.headers["content-disposition"] == 'attachment; filename="history.csv"'
    )
    rows = list(csv.reader(io.StringIO(response.text)))
    assert len(rows) == 102
    assert rows[0] == ["When (UTC)", "Who", "What"]
    date_time = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")
    assert all(date_time.fullmatch(row[0]) for row in rows[1:])
    assert [(row[1], row[2]) for row in rows[1:]] == [
        (admin["email"], f"Invited {email}") for email in reversed(emails)
    ]
