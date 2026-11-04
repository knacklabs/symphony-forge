"""Authentication security contracts at the running API boundary."""

import hashlib
import time
from statistics import median
from typing import cast
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import pytest
from test_api import compose_logs, credentials, sign_up
from test_soft_delete import psql


def _token_from_url(value: object, link_name: str) -> str:
    assert isinstance(value, str), f"The API did not return the {link_name}."
    token = parse_qs(urlsplit(value).query).get("token", [None])[0]
    assert token, f"The {link_name} has no token."
    return token


def _sign_in(client: httpx.Client, email: str, password: str) -> httpx.Response:
    return client.post(
        "/api/v1/auth/sign-in", json={"email": email, "password": password}
    )


def _expect_invalid_credentials(response: httpx.Response) -> None:
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.json()["error"]["message"] == (
        "The email or password is incorrect."
    )


def _make_member(
    admin: httpx.Client,
    member: httpx.Client,
    csrf: str,
    invited: dict[str, str],
    cookie_header: str | None = None,
) -> dict[str, object]:
    headers = {"x-csrf-token": csrf}
    if cookie_header is not None:
        headers["Cookie"] = cookie_header
    response = admin.post(
        "/api/v1/invites",
        headers=headers,
        json={"email": invited["email"]},
    )
    assert response.status_code == 201, response.text
    token = _token_from_url(response.json()["data"].get("inviteUrl"), "invite link")
    joined = member.post(
        "/api/v1/auth/accept-invite",
        json={**invited, "token": token},
    )
    assert joined.status_code == 201, joined.text
    return cast(dict[str, object], joined.json()["data"])


# Audit: these HTTP cases own account lockout, neutral failure timing, and invite/reset access.
# Missing lock state, account-specific answers, or weak reset-link scope can expose accounts or
# deny a legitimate member. Existing tests cover session and invite workflows, but not these
# security contracts in one Python API. Accounts and links are made through HTTP; SQL only moves
# expiry forward or back so the tests do not wait. No production seam is needed.
@pytest.mark.parametrize(
    "_report_title",
    [pytest.param(None, id="five failed sign-ins lock the email for 15 minutes")],
)
def test_five_failed_sign_ins_lock_the_email_for_15_minutes(
    client: httpx.Client,
    _report_title: None,
) -> None:
    account, _ = sign_up(client)

    for _ in range(5):
        _expect_invalid_credentials(
            _sign_in(client, account["email"], "wrong-password")
        )
    _expect_invalid_credentials(_sign_in(client, account["email"], account["password"]))

    duration = psql(
        "SELECT CASE WHEN expires_at_utc > NOW() + INTERVAL '14 minutes' "
        "AND expires_at_utc <= NOW() + INTERVAL '15 minutes' "
        "THEN 'fifteen_minutes' ELSE 'wrong_duration' END "
        "FROM core.sign_in_attempt "
        f"WHERE email = '{account['email'].lower()}'"
    )
    assert duration.returncode == 0, duration.stdout + duration.stderr
    assert "fifteen_minutes" in duration.stdout
    near_expiry = psql(
        "UPDATE core.sign_in_attempt "
        "SET expires_at_utc = expires_at_utc - INTERVAL '14 minutes' "
        f"WHERE email = '{account['email'].lower()}'"
    )
    assert near_expiry.returncode == 0, near_expiry.stdout + near_expiry.stderr
    assert "UPDATE 1" in near_expiry.stdout
    _expect_invalid_credentials(_sign_in(client, account["email"], account["password"]))

    expired = psql(
        "UPDATE core.sign_in_attempt SET expires_at_utc = NOW() - INTERVAL '1 second' "
        f"WHERE email = '{account['email'].lower()}'"
    )
    assert expired.returncode == 0, expired.stdout + expired.stderr
    assert "UPDATE 1" in expired.stdout
    signed_in = _sign_in(client, account["email"], account["password"])
    assert signed_in.status_code == 200, signed_in.text


@pytest.mark.parametrize(
    "_report_title",
    [pytest.param(None, id="an unknown email is counted and locked the same way")],
)
def test_an_unknown_email_is_counted_and_locked_the_same_way(
    client: httpx.Client,
    _report_title: None,
) -> None:
    account = credentials()
    for _ in range(5):
        _expect_invalid_credentials(
            _sign_in(client, account["email"], "wrong-password")
        )

    registered = client.post("/api/v1/auth/sign-up", json=account)
    assert registered.status_code == 201, registered.text
    _expect_invalid_credentials(_sign_in(client, account["email"], account["password"]))
    duration = psql(
        "SELECT CASE WHEN expires_at_utc > NOW() + INTERVAL '14 minutes' "
        "AND expires_at_utc <= NOW() + INTERVAL '15 minutes' "
        "THEN 'fifteen_minutes' ELSE 'wrong_duration' END "
        "FROM core.sign_in_attempt "
        f"WHERE email = '{account['email'].lower()}'"
    )
    assert duration.returncode == 0, duration.stdout + duration.stderr
    assert "fifteen_minutes" in duration.stdout
    expired = psql(
        "UPDATE core.sign_in_attempt SET expires_at_utc = NOW() - INTERVAL '1 second' "
        f"WHERE email = '{account['email'].lower()}'"
    )
    assert expired.returncode == 0, expired.stdout + expired.stderr
    assert "UPDATE 1" in expired.stdout
    signed_in = _sign_in(client, account["email"], account["password"])
    assert signed_in.status_code == 200, signed_in.text


@pytest.mark.parametrize(
    "_report_title",
    [pytest.param(None, id="a good sign-in clears the count")],
)
def test_a_good_sign_in_clears_the_count(
    client: httpx.Client, _report_title: None
) -> None:
    account, _ = sign_up(client)
    for _ in range(4):
        _expect_invalid_credentials(
            _sign_in(client, account["email"], "wrong-password")
        )

    signed_in = _sign_in(client, account["email"], account["password"])
    assert signed_in.status_code == 200, signed_in.text
    _expect_invalid_credentials(_sign_in(client, account["email"], "wrong-password"))
    signed_in = _sign_in(client, account["email"], account["password"])
    assert signed_in.status_code == 200, signed_in.text


@pytest.mark.parametrize(
    "_report_title",
    [
        pytest.param(
            None,
            id="an unknown email takes about as long to refuse as a wrong password",
        )
    ],
)
def test_an_unknown_email_takes_about_as_long_to_refuse_as_a_wrong_password(
    client: httpx.Client,
    _report_title: None,
) -> None:
    account, _ = sign_up(client)
    unknown_email = credentials()["email"]
    wrong_password_durations: list[float] = []
    unknown_email_durations: list[float] = []

    for _ in range(3):
        started = time.perf_counter()
        _expect_invalid_credentials(
            _sign_in(client, account["email"], "wrong-password")
        )
        wrong_password_durations.append(time.perf_counter() - started)

        started = time.perf_counter()
        _expect_invalid_credentials(_sign_in(client, unknown_email, "wrong-password"))
        unknown_email_durations.append(time.perf_counter() - started)

    assert median(unknown_email_durations) >= median(wrong_password_durations) / 2


@pytest.mark.parametrize(
    "_report_title",
    [pytest.param(None, id="an invite answers its link and the link opens once")],
)
def test_an_invite_answers_its_link_and_the_link_opens_once(
    client: httpx.Client,
    _report_title: None,
) -> None:
    _, csrf = sign_up(client)
    invited = credentials()
    invite_response = client.post(
        "/api/v1/invites",
        headers={"x-csrf-token": csrf},
        json={"email": invited["email"]},
    )
    assert invite_response.status_code == 201, invite_response.text
    token = _token_from_url(
        invite_response.json()["data"].get("inviteUrl"), "invite link"
    )

    with httpx.Client(base_url=client.base_url, timeout=15) as member:
        joined = member.post(
            "/api/v1/auth/accept-invite",
            json={**invited, "token": token},
        )
        assert joined.status_code == 201, joined.text
        repeated = member.post(
            "/api/v1/auth/accept-invite",
            json={**invited, "token": token},
        )
    assert repeated.status_code == 400, repeated.text
    assert repeated.json()["error"]["code"] == "INVITE_INVALID"


@pytest.mark.parametrize(
    "_report_title",
    [pytest.param(None, id="an expired invite link is refused")],
)
def test_an_expired_invite_link_is_refused(
    client: httpx.Client, _report_title: None
) -> None:
    _, csrf = sign_up(client)
    invited = credentials()
    invite_response = client.post(
        "/api/v1/invites",
        headers={"x-csrf-token": csrf},
        json={"email": invited["email"]},
    )
    assert invite_response.status_code == 201, invite_response.text
    token = _token_from_url(
        invite_response.json()["data"].get("inviteUrl"), "invite link"
    )
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = psql(
        "UPDATE core.invite SET expires_at_utc = NOW() - INTERVAL '1 second' "
        f"WHERE token_hash = '{token_hash}'"
    )
    assert expiry.returncode == 0, expiry.stdout + expiry.stderr
    assert "UPDATE 1" in expiry.stdout

    expired = client.post(
        "/api/v1/auth/accept-invite",
        json={**invited, "token": token},
    )
    assert expired.status_code == 400, expired.text
    assert expired.json()["error"]["code"] == "INVITE_INVALID"


@pytest.mark.parametrize(
    "_report_title",
    [pytest.param(None, id="an admin makes a reset link that works once")],
)
def test_an_admin_makes_a_reset_link_that_works_once(
    client: httpx.Client, _report_title: None
) -> None:
    _, csrf = sign_up(client)
    member = credentials()
    with httpx.Client(base_url=client.base_url, timeout=15) as member_client:
        member_account = _make_member(client, member_client, csrf, member)
    idempotency_key = str(uuid4())

    def make_reset_link() -> httpx.Response:
        return client.post(
            f"/api/v1/members/{member_account['id']}/reset-link",
            headers={"x-csrf-token": csrf, "Idempotency-Key": idempotency_key},
        )

    first = make_reset_link()
    assert first.status_code == 201, first.text
    replay = make_reset_link()
    assert replay.status_code == 201, replay.text
    assert "resetUrl" not in replay.json()["data"]
    token = _token_from_url(first.json()["data"].get("resetUrl"), "reset link")
    new_password = "different-correct-horse-password"
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": new_password},
    )
    assert reset.status_code == 200, reset.text
    repeated = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": member["password"]},
    )
    assert repeated.status_code == 400, repeated.text
    assert repeated.json()["error"]["code"] == "RESET_TOKEN_INVALID"
    with httpx.Client(base_url=client.base_url, timeout=15) as member_client:
        signed_in = _sign_in(member_client, member["email"], new_password)
        assert signed_in.status_code == 200, signed_in.text


@pytest.mark.parametrize(
    "_report_title",
    [pytest.param(None, id="an expired reset link is refused")],
)
def test_an_expired_reset_link_is_refused(
    client: httpx.Client, _report_title: None
) -> None:
    _, csrf = sign_up(client)
    member = credentials()
    with httpx.Client(base_url=client.base_url, timeout=15) as member_client:
        member_account = _make_member(client, member_client, csrf, member)
    link = client.post(
        f"/api/v1/members/{member_account['id']}/reset-link",
        headers={"x-csrf-token": csrf},
    )
    assert link.status_code == 201, link.text
    token = _token_from_url(link.json()["data"].get("resetUrl"), "reset link")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = psql(
        "UPDATE core.password_reset_token "
        "SET expires_at_utc = NOW() - INTERVAL '1 second' "
        f"WHERE token_hash = '{token_hash}'"
    )
    assert expiry.returncode == 0, expiry.stdout + expiry.stderr
    assert "UPDATE 1" in expiry.stdout

    expired = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "password": "different-correct-horse-password"},
    )
    assert expired.status_code == 400, expired.text
    assert expired.json()["error"]["code"] == "RESET_TOKEN_INVALID"


@pytest.mark.parametrize(
    "_report_title",
    [pytest.param(None, id="a member cannot make a reset link")],
)
def test_a_member_cannot_make_a_reset_link(
    client: httpx.Client, _report_title: None
) -> None:
    _, csrf = sign_up(client)
    member = credentials()
    with httpx.Client(base_url=client.base_url, timeout=15) as member_client:
        member_account = _make_member(client, member_client, csrf, member)
        member_csrf = member_client.cookies["starter_csrf"]
        response = member_client.post(
            f"/api/v1/members/{member_account['id']}/reset-link",
            headers={"x-csrf-token": member_csrf},
        )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "ADMIN_ONLY"


@pytest.mark.parametrize(
    "_report_title",
    [
        pytest.param(
            None,
            id="an admin cannot make a reset link for another organisation's member",
        )
    ],
)
def test_an_admin_cannot_make_a_reset_link_for_another_organisations_member(
    client: httpx.Client,
    _report_title: None,
) -> None:
    sign_up(client)
    first_account = client.get("/api/v1/auth/me").json()["data"]
    with httpx.Client(base_url=client.base_url, timeout=15) as second_client:
        _, second_csrf = sign_up(second_client)
        response = second_client.post(
            f"/api/v1/members/{first_account['id']}/reset-link",
            headers={"x-csrf-token": second_csrf},
        )

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "MEMBER_NOT_FOUND"


@pytest.mark.parametrize(
    "_report_title",
    [
        pytest.param(
            None,
            id="production admin can create and use a reset link without a mail provider",
        )
    ],
)
def test_production_admin_can_create_and_use_a_reset_link_without_a_mail_provider(
    production_client: httpx.Client,
    _report_title: None,
) -> None:
    admin_response = production_client.post("/api/v1/auth/sign-up", json=credentials())
    assert admin_response.status_code == 201, admin_response.text
    csrf = admin_response.cookies["starter_csrf"]
    cookie_header = (
        f"starter_session={admin_response.cookies['starter_session']}; "
        f"starter_csrf={csrf}"
    )
    member = credentials()
    with httpx.Client(base_url=production_client.base_url, timeout=15) as member_client:
        member_account = _make_member(
            production_client, member_client, csrf, member, cookie_header
        )
        link = production_client.post(
            f"/api/v1/members/{member_account['id']}/reset-link",
            headers={"Cookie": cookie_header, "x-csrf-token": csrf},
        )
        assert link.status_code == 201, link.text
        token = _token_from_url(link.json()["data"].get("resetUrl"), "reset link")
        new_password = "different-correct-horse-password"
        reset = member_client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": new_password},
        )
        assert reset.status_code == 200, reset.text
        signed_in = _sign_in(member_client, member["email"], new_password)
        assert signed_in.status_code == 200, signed_in.text
    assert token not in compose_logs("production-api")
