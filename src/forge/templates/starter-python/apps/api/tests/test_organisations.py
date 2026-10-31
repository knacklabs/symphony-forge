"""Organisation membership and project scope at the HTTP boundary."""

import re

import httpx
from conftest import add_agent_key
from test_api import credentials, sign_up
from test_invites import invite


def test_an_admin_removes_a_member_who_is_signed_out_at_once(
    client: httpx.Client,
) -> None:
    # Audit: real HTTP and Postgres own removal, session/key revocation and side effects.
    # Missing cleanup or a wrong scope filter breaks this flow. Existing invite/role tests
    # never remove membership, so cannot catch these failures. No production seam is needed.
    _, csrf = sign_up(client)
    admin_id = client.get("/api/v1/auth/me").json()["data"]["id"]
    headers = {"x-csrf-token": csrf}
    invited = credentials()
    token = invite(client, csrf, invited["email"])
    kept = credentials()
    kept_token = invite(client, csrf, kept["email"])
    replaced = credentials()
    invite(client, csrf, replaced["email"])
    with httpx.Client(base_url=client.base_url, timeout=15) as member:
        joined = member.post(
            "/api/v1/auth/accept-invite", json={**invited, "token": token}
        )
        assert joined.status_code == 201, joined.text
        path = f"/api/v1/members/{joined.json()['data']['id']}"
        denied = member.delete(
            f"/api/v1/members/{admin_id}",
            headers={"x-csrf-token": member.cookies["starter_csrf"]},
        )
        assert denied.status_code == 403, denied.text
        assert denied.json()["error"]["code"] == "ADMIN_ONLY"
        promoted = client.patch(path, headers=headers, json={"role": "admin"})
        assert promoted.status_code == 200, promoted.text
        pending = credentials()
        pending_token = invite(member, member.cookies["starter_csrf"], pending["email"])
        replaced_token = invite(
            member, member.cookies["starter_csrf"], replaced["email"]
        )
        with httpx.Client(base_url=client.base_url, timeout=15) as other:
            assert other.delete(path).status_code == 401
            _, other_csrf = sign_up(other)
            denied = other.delete(path, headers={"x-csrf-token": other_csrf})
            assert denied.status_code == 404, denied.text
            assert denied.json()["error"]["code"] == "MEMBER_NOT_FOUND"
        assert client.delete(path).status_code == 403
        invalid_id = client.delete("/api/v1/members/not-a-uuid", headers=headers)
        assert invalid_id.status_code == 400, invalid_id.text
        assert invalid_id.json()["error"]["code"] == "VALIDATION_ERROR"
        with httpx.Client(base_url=client.base_url, timeout=15) as second:
            signed_in = second.post("/api/v1/auth/sign-in", json=invited)
            assert signed_in.status_code == 200, signed_in.text
            removed = client.delete(path, headers=headers)
            assert removed.status_code == 200, removed.text
            assert removed.json() == {"success": True, "data": None, "error": None}
            assert member.get("/api/v1/auth/me").status_code == 401
            assert second.get("/api/v1/auth/me").status_code == 401
        assert member.post("/api/v1/auth/sign-in", json=invited).status_code == 401
        for person, link in ((pending, pending_token), (replaced, replaced_token)):
            invalid = member.post(
                "/api/v1/auth/accept-invite", json={**person, "token": link}
            )
            assert invalid.status_code == 400, invalid.text
            assert invalid.json()["error"]["code"] == "INVITE_INVALID"
        accepted = member.post(
            "/api/v1/auth/accept-invite", json={**kept, "token": kept_token}
        )
        assert accepted.status_code == 201, accepted.text
    members = client.get("/api/v1/members").json()["data"]["items"]
    assert invited["email"] not in [m["email"] for m in members]
    assert invited["email"] not in client.get("/api/v1/members/export").text
    history = client.get("/api/v1/history").json()["data"]
    assert any(row["summary"] == f"Removed {invited['email']}" for row in history)
    repeated = client.delete(path, headers=headers)
    assert repeated.status_code == 404, repeated.text
    assert repeated.json()["error"]["code"] == "MEMBER_NOT_FOUND"
    own = client.delete(f"/api/v1/members/{admin_id}", headers=headers)
    assert own.status_code == 403, own.text
    assert own.json()["error"]["code"] == "CANNOT_REMOVE_SELF"
    conflict = client.post(
        "/api/v1/invites", headers=headers, json={"email": invited["email"]}
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["error"]["message"] == "That person already has an account."
    agent, key = add_agent_key(client, csrf, "removal-bot", "member")
    with httpx.Client(base_url=client.base_url, timeout=15) as bearer:
        key_headers = {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json, text/event-stream",
        }
        initialize = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "removal-test", "version": "1"},
            },
        }
        before = bearer.post("/mcp", headers=key_headers, json=initialize)
        assert before.status_code == 200, before.text
        removed_agent = client.delete(
            f"/api/v1/members/{agent['accountId']}", headers=headers
        )
        assert removed_agent.status_code == 200, removed_agent.text
        assert (
            bearer.post("/mcp", headers=key_headers, json=initialize).status_code == 401
        )


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
    assert listed.json()["data"]["paging"]["total"] == 0
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
