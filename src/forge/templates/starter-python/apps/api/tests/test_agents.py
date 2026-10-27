"""Agent accounts, their one key and the agent access list at the HTTP boundary."""

import re
from typing import Any

import httpx
from test_api import credentials, sign_up
from test_invites import invite


def _add_agent(client: httpx.Client, csrf: str, name: str, role: str) -> dict[str, Any]:
    added = client.post(
        "/api/v1/agents",
        headers={"x-csrf-token": csrf},
        json={"name": name, "role": role},
    )
    assert added.status_code == 201, added.text
    agent: dict[str, Any] = added.json()["data"]
    return agent


def test_an_admin_adds_an_agent_account_and_creates_and_revokes_its_key(
    client: httpx.Client,
) -> None:
    # Audit: an agent missing from the member list, a key that shows twice or keeps working
    # after a new one, or a change with no history row breaks the agent account contract. No
    # other test covers these routes; they run through the real API and database.
    admin, csrf = sign_up(client)
    agent = _add_agent(client, csrf, "gantry", "member")
    assert agent["role"] == "member"
    assert agent["isAgent"] is True
    assert agent["hasKey"] is False
    assert re.fullmatch(r"gantry-[a-z0-9]{6}@agents\.invalid", agent["email"])
    invalid = client.post(
        "/api/v1/agents",
        headers={"x-csrf-token": csrf},
        json={"name": "Not valid", "role": "member"},
    )
    assert invalid.status_code == 400, invalid.text
    assert [
        error["field"] for error in invalid.json()["error"]["details"]["fieldErrors"]
    ] == ["name"]

    key_path = f"/api/v1/members/{agent['accountId']}/key"
    first = client.post(key_path, headers={"x-csrf-token": csrf})
    assert first.status_code == 201, first.text
    second = client.post(key_path, headers={"x-csrf-token": csrf})
    assert second.status_code == 201, second.text
    first_key, second_key = first.json()["data"]["key"], second.json()["data"]["key"]
    assert re.fullmatch(r"agent_[A-Za-z0-9_-]{43}", first_key)
    assert second_key.startswith("agent_") and second_key != first_key

    listed = client.get("/api/v1/members?page=1&limit=20")
    assert listed.status_code == 200, listed.text
    members = {member["email"]: member for member in listed.json()["data"]["items"]}
    assert members[admin["email"]]["isAgent"] is False
    assert members[agent["email"]]["isAgent"] is True
    assert members[agent["email"]]["hasKey"] is True
    # The key shows one time only: no member read returns it.
    assert second_key not in listed.text

    revoked = client.delete(key_path, headers={"x-csrf-token": csrf})
    assert revoked.status_code == 200, revoked.text
    after = client.get("/api/v1/members?page=1&limit=20").json()["data"]["items"]
    assert next(m for m in after if m["email"] == agent["email"])["hasKey"] is False

    # A person's membership has no key to create.
    own = client.post(
        f"/api/v1/members/{members[admin['email']]['accountId']}/key",
        headers={"x-csrf-token": csrf},
    )
    assert own.status_code == 404, own.text
    assert own.json()["error"]["code"] == "MEMBER_NOT_FOUND"

    history = client.get("/api/v1/history").json()["data"]
    assert [(entry["actorEmail"], entry["summary"]) for entry in history] == [
        (admin["email"], f"Revoked the key for {agent['email']}"),
        (admin["email"], f"Created a key for {agent['email']}"),
        (admin["email"], f"Created a key for {agent['email']}"),
        (admin["email"], f"Added the agent account {agent['email']} as Member"),
    ]

    # The agent access list starts empty, and a change to it adds one history row.
    tools = client.get("/api/v1/agent-tools")
    assert tools.json()["data"] == {"deleteAndRestore": []}, tools.text
    changed = client.put(
        "/api/v1/agent-tools/projects",
        headers={"x-csrf-token": csrf},
        json={"deleteAndRestore": True},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"] == {"deleteAndRestore": ["projects"]}
    bad = client.put(
        "/api/v1/agent-tools/Not%20a%20feature",
        headers={"x-csrf-token": csrf},
        json={"deleteAndRestore": True},
    )
    assert bad.status_code == 400, bad.text
    latest = client.get("/api/v1/history").json()["data"][0]
    assert latest["actorEmail"] == admin["email"]
    assert latest["summary"] == "Turned on agent delete and restore for projects"


def test_a_member_cannot_add_an_agent_account_or_change_its_key_or_agent_access(
    client: httpx.Client,
) -> None:
    # Audit: a member who reaches an admin-only agent route, or an admin of another
    # organisation who reaches this agent, breaks the permission and scope rule.
    with httpx.Client(base_url=client.base_url, timeout=15) as admin:
        _, admin_csrf = sign_up(admin)
        agent = _add_agent(admin, admin_csrf, "reports-bot", "admin")
        invited = credentials()
        token = invite(admin, admin_csrf, invited["email"])

    key_path = f"/api/v1/members/{agent['accountId']}/key"
    with httpx.Client(base_url=client.base_url, timeout=15) as member:
        joined = member.post(
            "/api/v1/auth/accept-invite", json={**invited, "token": token}
        )
        assert joined.status_code == 201, joined.text
        headers = {"x-csrf-token": joined.cookies["starter_csrf"]}
        for response in (
            member.post(
                "/api/v1/agents",
                headers=headers,
                json={"name": "sneaky", "role": "admin"},
            ),
            member.post(key_path, headers=headers),
            member.delete(key_path, headers=headers),
            member.get("/api/v1/agent-tools"),
            member.put(
                "/api/v1/agent-tools/projects",
                headers=headers,
                json={"deleteAndRestore": True},
            ),
        ):
            assert response.status_code == 403, response.text
            assert response.json()["error"]["code"] == "ADMIN_ONLY"

    with httpx.Client(base_url=client.base_url, timeout=15) as other:
        _, other_csrf = sign_up(other)
        for response in (
            other.post(key_path, headers={"x-csrf-token": other_csrf}),
            other.delete(key_path, headers={"x-csrf-token": other_csrf}),
        ):
            assert response.status_code == 404, response.text
            assert response.json()["error"]["code"] == "MEMBER_NOT_FOUND"


def test_an_agent_account_cannot_sign_in_with_a_password(client: httpx.Client) -> None:
    # Audit: an agent account must act only through its key; a password sign-in that works
    # would give a session to anyone who guesses one.
    _, csrf = sign_up(client)
    agent = _add_agent(client, csrf, "gantry", "admin")
    created = client.post(
        f"/api/v1/members/{agent['accountId']}/key", headers={"x-csrf-token": csrf}
    )
    assert created.status_code == 201, created.text
    with httpx.Client(base_url=client.base_url, timeout=15) as stranger:
        for password in ("correct-horse-battery-staple", "x" * 12):
            signed_in = stranger.post(
                "/api/v1/auth/sign-in",
                json={"email": agent["email"], "password": password},
            )
            assert signed_in.status_code == 401, signed_in.text
            assert signed_in.json()["error"]["code"] == "INVALID_CREDENTIALS"
