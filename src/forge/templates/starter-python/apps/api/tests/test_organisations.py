"""Organisation membership and project scope at the HTTP boundary."""

import re

import httpx
from test_api import credentials, sign_up


def test_organisation_isolation_returns_404_and_leaves_the_project_unchanged(
    client: httpx.Client,
) -> None:
    # Audit: a tenant-scoping regression can expose or mutate another organisation's project.
    # Existing project tests cover one account only; this real HTTP path also checks the list and
    # export queries, with no test-only production seam.
    owner, csrf = sign_up(client)
    created = client.post(
        "/api/v1/projects",
        headers={"x-csrf-token": csrf},
        json={"name": "Private project", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["data"]["id"]

    _, other_csrf = sign_up(client)
    listed = client.get("/api/v1/projects")
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["items"] == []
    assert listed.json()["data"]["pagination"]["totalItems"] == 0
    exported = client.get("/api/v1/projects/export")
    assert exported.status_code == 200, exported.text
    assert exported.text == "Name,Status,Created (UTC),Updated (UTC)\r\n"
    assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
    assert (
        client.put(
            f"/api/v1/projects/{project_id}",
            headers={"x-csrf-token": other_csrf},
            json={"name": "Changed by another organisation", "status": "archived"},
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


def test_a_new_account_is_the_only_admin_of_its_organisation(
    client: httpx.Client,
) -> None:
    # Audit: signup must create the first organisation and admin membership, and sessions must
    # retain that role. Existing auth coverage does not check roles or the member-list contract.
    account = credentials()
    signed_up = client.post("/api/v1/auth/sign-up", json=account)
    assert signed_up.status_code == 201, signed_up.text
    user_id = signed_up.json()["data"]["id"]
    assert user_id
    assert signed_up.json()["data"]["email"] == account["email"]
    assert signed_up.json()["data"]["role"] == "admin"

    signed_in = client.post("/api/v1/auth/sign-in", json=account)
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["data"]["id"] == user_id
    assert signed_in.json()["data"]["email"] == account["email"]
    assert signed_in.json()["data"]["role"] == "admin"
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["data"]["id"] == user_id
    assert me.json()["data"]["email"] == account["email"]
    assert me.json()["data"]["role"] == "admin"

    members = client.get("/api/v1/members?page=1&limit=20")
    assert members.status_code == 200, members.text
    data = members.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["accountId"] == user_id
    assert data["items"][0]["email"] == account["email"]
    assert data["items"][0]["role"] == "admin"
    assert isinstance(data["items"][0]["createdAtUtc"], str)
    assert data["pagination"] == {
        "page": 1,
        "limit": 20,
        "totalItems": 1,
        "totalPages": 1,
    }
    next_page = client.get("/api/v1/members?page=2&limit=1")
    assert next_page.status_code == 200, next_page.text
    assert next_page.json()["data"]["items"] == []
    assert next_page.json()["data"]["pagination"]["totalItems"] == 1
    for query in ("page=0", "limit=101", "unexpected=true"):
        invalid = client.get(f"/api/v1/members?{query}")
        assert invalid.status_code == 400, invalid.text
        assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_members_export_as_csv(client: httpx.Client) -> None:
    # Audit: the export query can omit or mislabel members even when the list is correct. The
    # existing CSV test covers projects only; this exercises the real endpoint and database.
    assert client.get("/api/v1/members").status_code == 401
    assert client.get("/api/v1/members/export").status_code == 401
    sign_up(client)  # The next organisation's export must not include this member.
    account, _ = sign_up(client)

    response = client.get("/api/v1/members/export")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert (
        response.headers["content-disposition"] == 'attachment; filename="members.csv"'
    )
    lines = response.text.split("\r\n")
    assert len(lines) == 3, response.text
    assert lines[0] == "Email,Role,Joined (UTC)"
    assert re.fullmatch(
        rf"{re.escape(account['email'])},admin,\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}",
        lines[1],
    )
    assert lines[2] == ""
