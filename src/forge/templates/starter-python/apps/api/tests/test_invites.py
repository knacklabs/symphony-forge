"""Invite and role contracts at the running API boundary."""

import hashlib
import json
from urllib.parse import parse_qs, urlsplit

import httpx
from test_api import compose_logs, credentials, sign_up
from test_soft_delete import psql


def invite(client: httpx.Client, csrf: str, email: str, service: str = "api") -> str:
    previous_lines = compose_logs(service).splitlines()
    response = client.post(
        "/api/v1/invites",
        headers={"x-csrf-token": csrf},
        json={"email": email},
    )
    assert response.status_code == 201, response.text

    new_lines = compose_logs(service).splitlines()[len(previous_lines) :]
    for line in reversed(new_lines):
        if '"inviteUrl"' not in line:
            continue
        event = json.loads(line[line.index("{") :])
        invite_url = event["context"]["inviteUrl"]
        assert isinstance(invite_url, str)
        token = parse_qs(urlsplit(invite_url).query).get("token", [None])[0]
        assert token
        return token
    raise AssertionError("The test mail provider did not log an invite link.")


def test_an_admin_invites_a_person_by_email_who_joins_the_organisation(
    client: httpx.Client,
) -> None:
    # Audit: this protects invite acceptance, membership, and member project access over HTTP.
    # A missing invite route or a join that fails to scope projects breaks the flow. Existing
    # tests cover signup and project access separately, not invite-based membership. It uses the
    # real API and database; only the mail edge is represented by the logged test link.
    assert (
        client.post(
            "/api/v1/invites", json={"email": credentials()["email"]}
        ).status_code
        == 401
    )
    admin, admin_csrf = sign_up(client)
    no_csrf = client.post("/api/v1/invites", json={"email": credentials()["email"]})
    assert no_csrf.status_code == 403, no_csrf.text
    assert no_csrf.json()["error"]["code"] == "CSRF_CHECK_FAILED"
    project = client.post(
        "/api/v1/projects",
        headers={"x-csrf-token": admin_csrf},
        json={"name": "Shared project", "status": "active"},
    )
    assert project.status_code == 201, project.text
    invited = credentials()
    token = invite(client, admin_csrf, invited["email"])

    invalid = client.post(
        "/api/v1/invites",
        headers={"x-csrf-token": admin_csrf},
        json={"email": "not-an-email"},
    )
    assert invalid.status_code == 400, invalid.text
    assert any(
        error["field"] == "email"
        for error in invalid.json()["error"]["details"]["fieldErrors"]
    )

    with httpx.Client(base_url=client.base_url, timeout=15) as member:
        joined = member.post(
            "/api/v1/auth/accept-invite",
            json={**invited, "token": token},
        )
        assert joined.status_code == 201, joined.text
        assert joined.json()["data"]["email"] == invited["email"]
        assert joined.json()["data"]["role"] == "member"
        member_csrf = joined.cookies["starter_csrf"]

        members = member.get("/api/v1/members?page=1&limit=20")
        assert members.status_code == 200, members.text
        assert {
            (item["email"], item["role"]) for item in members.json()["data"]["items"]
        } == {(admin["email"], "admin"), (invited["email"], "member")}

        created = member.post(
            "/api/v1/projects",
            headers={"x-csrf-token": member_csrf},
            json={"name": "Member project", "status": "active"},
        )
        assert created.status_code == 201, created.text
        project_id = created.json()["data"]["id"]
        updated = member.put(
            f"/api/v1/projects/{project_id}",
            headers={"x-csrf-token": member_csrf},
            json={"name": "Updated member project", "status": "archived"},
        )
        assert updated.status_code == 200, updated.text
        deleted = member.delete(
            f"/api/v1/projects/{project_id}",
            headers={"x-csrf-token": member_csrf},
        )
        assert deleted.status_code == 200, deleted.text
        projects = member.get("/api/v1/projects?page=1&limit=20")
        assert projects.status_code == 200, projects.text
        assert [item["name"] for item in projects.json()["data"]["items"]] == [
            "Shared project"
        ]


def test_a_member_cannot_invite_people_or_change_roles(client: httpx.Client) -> None:
    # Audit: a member must receive ADMIN_ONLY for both protected actions. Existing auth tests
    # do not exercise invite or role permissions. The requests cross the real HTTP permission
    # boundary and need no production test seam.
    with httpx.Client(base_url=client.base_url, timeout=15) as admin:
        _, admin_csrf = sign_up(admin)
        invited = credentials()
        token = invite(admin, admin_csrf, invited["email"])

    with httpx.Client(base_url=client.base_url, timeout=15) as member:
        joined = member.post(
            "/api/v1/auth/accept-invite",
            json={**invited, "token": token},
        )
        assert joined.status_code == 201, joined.text
        csrf = joined.cookies["starter_csrf"]

        invite_attempt = member.post(
            "/api/v1/invites",
            headers={"x-csrf-token": csrf},
            json={"email": credentials()["email"]},
        )
        assert invite_attempt.status_code == 403, invite_attempt.text
        assert invite_attempt.json()["error"]["code"] == "ADMIN_ONLY"
        role_attempt = member.patch(
            f"/api/v1/members/{joined.json()['data']['id']}",
            headers={"x-csrf-token": csrf},
            json={"role": "admin"},
        )
        assert role_attempt.status_code == 403, role_attempt.text
        assert role_attempt.json()["error"]["code"] == "ADMIN_ONLY"


def test_an_admin_changes_another_members_role_but_not_their_own(
    client: httpx.Client,
) -> None:
    # Audit: admins can promote another member but cannot remove their own admin role. Existing
    # organisation tests cover initial admin membership, not role changes. The requests use the
    # public member endpoints with a real database and no production test seam. This also owns
    # the new PATCH transport: the project's PUT checks cannot catch a missing CSRF or CORS rule.
    _, csrf = sign_up(client)
    invited = credentials()
    token = invite(client, csrf, invited["email"])
    with httpx.Client(base_url=client.base_url, timeout=15) as member:
        joined = member.post(
            "/api/v1/auth/accept-invite",
            json={**invited, "token": token},
        )
    assert joined.status_code == 201, joined.text

    role_path = f"/api/v1/members/{joined.json()['data']['id']}"
    no_csrf = client.patch(role_path, json={"role": "admin"})
    assert no_csrf.status_code == 403, no_csrf.text
    assert no_csrf.json()["error"]["code"] == "CSRF_CHECK_FAILED"
    invalid = client.patch(
        role_path, headers={"x-csrf-token": csrf}, json={"role": "owner"}
    )
    assert invalid.status_code == 400, invalid.text
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
    preflight = client.options(
        role_path,
        headers={
            "Origin": str(client.base_url).rstrip("/"),
            "Access-Control-Request-Method": "PATCH",
        },
    )
    assert "PATCH" in preflight.headers["access-control-allow-methods"]
    changed = client.patch(
        role_path,
        headers={"x-csrf-token": csrf},
        json={"role": "admin"},
    )
    assert changed.status_code == 200, changed.text
    own_id = client.get("/api/v1/auth/me").json()["data"]["id"]
    own_change = client.patch(
        f"/api/v1/members/{own_id}",
        headers={"x-csrf-token": csrf},
        json={"role": "member"},
    )
    assert own_change.status_code == 403, own_change.text
    assert own_change.json()["error"]["code"] == "CANNOT_CHANGE_OWN_ROLE"

    members = client.get("/api/v1/members?page=1&limit=20")
    assert members.status_code == 200, members.text
    roles = {
        item["accountId"]: item["role"] for item in members.json()["data"]["items"]
    }
    assert roles[own_id] == "admin"
    assert roles[joined.json()["data"]["id"]] == "admin"


def test_an_admin_cannot_change_the_role_of_another_organisations_account(
    client: httpx.Client,
) -> None:
    # Audit: an admin must not target accounts outside their organisation. Existing organisation
    # coverage checks project isolation but not role changes. This real HTTP call distinguishes
    # an absent organisation member from a permission denial without a test-only seam.
    first, _ = sign_up(client)
    first_id = client.get("/api/v1/auth/me").json()["data"]["id"]
    with httpx.Client(base_url=client.base_url, timeout=15) as second_client:
        _, second_csrf = sign_up(second_client)
        changed = second_client.patch(
            f"/api/v1/members/{first_id}",
            headers={"x-csrf-token": second_csrf},
            json={"role": "member"},
        )
        assert changed.status_code == 404, changed.text
        assert changed.json()["error"]["code"] == "MEMBER_NOT_FOUND"

    first_members = client.get("/api/v1/members?page=1&limit=20")
    assert first_members.status_code == 200, first_members.text
    first_items = first_members.json()["data"]["items"]
    assert len(first_items) == 1
    assert first_items[0]["accountId"] == first_id
    assert first_items[0]["email"] == first["email"]
    assert first_items[0]["role"] == "admin"


def test_an_invite_link_works_once_and_only_for_its_email(client: httpx.Client) -> None:
    # Audit: invite links must bind the invited email, expire, be replaced on reinvite, and be
    # single use; an existing account cannot gain a second membership. Existing auth tests cover
    # reset tokens only. HTTP requests prove invite behavior; SQL only advances the expiry clock.
    _, csrf = sign_up(client)
    invited = credentials()
    old_token = invite(client, csrf, invited["email"])

    wrong_email = credentials()
    wrong = client.post(
        "/api/v1/auth/accept-invite",
        json={**wrong_email, "token": old_token},
    )
    assert wrong.status_code == 400, wrong.text
    assert wrong.json()["error"]["code"] == "INVITE_INVALID"

    old_hash = hashlib.sha256(old_token.encode()).hexdigest()
    shortened = psql(
        "UPDATE core.invite SET expires_at_utc = NOW() + INTERVAL '1 hour' "
        f"WHERE token_hash = '{old_hash}'"
    )
    assert shortened.returncode == 0, shortened.stderr
    assert "UPDATE 1" in shortened.stdout
    replacement_token = invite(client, csrf, invited["email"])
    replacement_hash = hashlib.sha256(replacement_token.encode()).hexdigest()
    lifetime = psql(
        "SELECT CASE WHEN expires_at_utc > NOW() + INTERVAL '6 days 23 hours' "
        "AND expires_at_utc <= NOW() + INTERVAL '7 days' THEN 'seven_days' "
        f"ELSE 'wrong_expiry' END FROM core.invite WHERE token_hash = '{replacement_hash}'"
    )
    assert lifetime.returncode == 0, lifetime.stderr
    assert "seven_days" in lifetime.stdout
    replaced = client.post(
        "/api/v1/auth/accept-invite",
        json={**invited, "token": old_token},
    )
    assert replaced.status_code == 400, replaced.text
    assert replaced.json()["error"]["code"] == "INVITE_INVALID"

    accepted = client.post(
        "/api/v1/auth/accept-invite",
        json={**invited, "token": replacement_token},
    )
    assert accepted.status_code == 201, accepted.text
    repeated = client.post(
        "/api/v1/auth/accept-invite",
        json={**invited, "token": replacement_token},
    )
    assert repeated.status_code == 400, repeated.text
    assert repeated.json()["error"]["code"] == "INVITE_INVALID"

    existing, _ = sign_up(client)
    duplicate_invite = client.post(
        "/api/v1/invites",
        headers={"x-csrf-token": client.cookies["starter_csrf"]},
        json={"email": existing["email"]},
    )
    assert duplicate_invite.status_code == 409, duplicate_invite.text
    assert duplicate_invite.json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"

    account_before_accept = credentials()
    conflict_token = invite(
        client, client.cookies["starter_csrf"], account_before_accept["email"]
    )
    registered = client.post("/api/v1/auth/sign-up", json=account_before_accept)
    assert registered.status_code == 201, registered.text
    conflict = client.post(
        "/api/v1/auth/accept-invite",
        json={**account_before_accept, "token": conflict_token},
    )
    assert conflict.status_code == 409, conflict.text
    conflict_error = conflict.json()["error"]
    assert conflict_error["code"] == "EMAIL_ALREADY_REGISTERED"
    assert conflict_error["message"] == (
        "An account already uses that email, so it cannot join this organisation."
    )

    expired_account = credentials()
    expired_token = invite(
        client, client.cookies["starter_csrf"], expired_account["email"]
    )
    token_hash = hashlib.sha256(expired_token.encode()).hexdigest()
    expiry = psql(
        "UPDATE core.invite SET expires_at_utc = NOW() - INTERVAL '1 second' "
        f"WHERE token_hash = '{token_hash}'"
    )
    assert expiry.returncode == 0, expiry.stdout + expiry.stderr
    assert "UPDATE 1" in expiry.stdout
    expired = client.post(
        "/api/v1/auth/accept-invite",
        json={**expired_account, "token": expired_token},
    )
    assert expired.status_code == 400, expired.text
    assert expired.json()["error"]["code"] == "INVITE_INVALID"


def test_production_refuses_an_invite_without_a_mail_provider(
    production_client: httpx.Client,
) -> None:
    # Audit: production must fail clearly when no mail provider exists. Existing production tests
    # cover password reset's safe response but not invite delivery. This exercises the deployed
    # environment's HTTP contract and needs no fake provider or production seam.
    _, csrf = sign_up(production_client)
    cookies = production_client.cookies
    response = production_client.post(
        "/api/v1/invites",
        headers={
            "Cookie": (
                f"starter_session={cookies['starter_session']}; "
                f"starter_csrf={cookies['starter_csrf']}"
            ),
            "x-csrf-token": csrf,
        },
        json={"email": credentials()["email"]},
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "MAIL_NOT_CONFIGURED"
    assert (
        response.json()["error"]["message"] == "Email is not set up for this app yet."
    )
