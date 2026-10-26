"""One-company setup, sign-up and organisation-switch contracts at the API boundary."""

import os
import subprocess

import httpx
from test_api import credentials
from test_invites import invite
from test_soft_delete import psql


def one_company_client() -> httpx.Client:
    return httpx.Client(base_url=os.environ["ONE_COMPANY_API_TEST_URL"], timeout=15)


def setup_company(email: str, password: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose.test.yml",
            "exec",
            "-T",
            "-e",
            f"ADMIN_EMAIL={email}",
            "-e",
            f"ADMIN_PASSWORD={password}",
            "one-company-api",
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            "app.setup_company",
        ],
        cwd="../..",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )


def test_the_setup_command_makes_the_company_and_its_first_admin() -> None:
    admin = credentials()
    setup = setup_company(admin["email"], admin["password"])
    assert setup.returncode == 0, setup.stdout + setup.stderr

    with one_company_client() as client:
        signed_in = client.post("/api/v1/auth/sign-in", json=admin)
        assert signed_in.status_code == 200, signed_in.text
        assert signed_in.json()["data"]["role"] == "admin"

        members = client.get("/api/v1/members?page=1&limit=20")
        assert members.status_code == 200, members.text
        assert [
            (item["email"], item["role"]) for item in members.json()["data"]["items"]
        ] == [(admin["email"], "admin")]

    duplicate = setup_company(admin["email"], admin["password"])
    assert duplicate.returncode == 1
    assert "An account already uses that email." in duplicate.stdout + duplicate.stderr

    invalid = setup_company("not-an-email", admin["password"])
    assert invalid.returncode == 1
    assert "String should match pattern" in invalid.stdout + invalid.stderr
    with one_company_client() as client:
        invalid_sign_in = client.post(
            "/api/v1/auth/sign-in",
            json={"email": "not-an-email", "password": admin["password"]},
        )
        assert invalid_sign_in.status_code in {400, 401}

    account = psql(
        "SELECT CASE WHEN EXISTS (SELECT 1 FROM core.account "
        "WHERE email = 'not-an-email') THEN 'found' ELSE 'missing' END"
    )
    assert account.returncode == 0, account.stderr
    assert "missing" in account.stdout


def test_a_one_company_app_refuses_sign_up_and_still_takes_invites() -> None:
    admin = credentials()
    setup = setup_company(admin["email"], admin["password"])
    assert setup.returncode == 0, setup.stdout + setup.stderr

    with one_company_client() as client:
        options = client.get("/api/v1/auth/options")
        assert options.status_code == 200, options.text
        assert options.json()["data"]["signUpOpen"] is False

        would_be_account = credentials()
        refused = client.post("/api/v1/auth/sign-up", json=would_be_account)
        assert refused.status_code == 403, refused.text
        assert refused.json()["error"]["code"] == "SIGN_UP_CLOSED"
        assert refused.json()["error"]["message"] == (
            "This app is for one company. Ask an admin of your team for an invite."
        )
        absent = client.post("/api/v1/auth/sign-in", json=would_be_account)
        assert absent.status_code == 401, absent.text

        signed_in = client.post("/api/v1/auth/sign-in", json=admin)
        assert signed_in.status_code == 200, signed_in.text
        csrf = client.cookies["starter_csrf"]
        project = client.post(
            "/api/v1/projects",
            headers={"x-csrf-token": csrf},
            json={"name": "Company project", "status": "active"},
        )
        assert project.status_code == 201, project.text

        member = credentials()
        token = invite(client, csrf, member["email"], "one-company-api")

    with one_company_client() as member_client:
        joined = member_client.post(
            "/api/v1/auth/accept-invite",
            json={**member, "token": token},
        )
        assert joined.status_code == 201, joined.text
        assert joined.json()["data"]["role"] == "member"

        projects = member_client.get("/api/v1/projects?page=1&limit=20")
        assert projects.status_code == 200, projects.text
        assert [item["name"] for item in projects.json()["data"]["items"]] == [
            "Company project"
        ]


def test_a_one_company_app_becomes_many_company_by_its_setting_alone(
    client: httpx.Client,
) -> None:
    admin = credentials()
    setup = setup_company(admin["email"], admin["password"])
    assert setup.returncode == 0, setup.stdout + setup.stderr

    with one_company_client() as one_company:
        signed_in = one_company.post("/api/v1/auth/sign-in", json=admin)
        assert signed_in.status_code == 200, signed_in.text
        csrf = one_company.cookies["starter_csrf"]
        project = one_company.post(
            "/api/v1/projects",
            headers={"x-csrf-token": csrf},
            json={"name": "Kept after switch", "status": "active"},
        )
        assert project.status_code == 201, project.text

        member = credentials()
        token = invite(one_company, csrf, member["email"], "one-company-api")

    with one_company_client() as member_client:
        joined = member_client.post(
            "/api/v1/auth/accept-invite",
            json={**member, "token": token},
        )
        assert joined.status_code == 201, joined.text
        assert joined.json()["data"]["role"] == "member"

    signed_in_many = client.post("/api/v1/auth/sign-in", json=admin)
    assert signed_in_many.status_code == 200, signed_in_many.text
    assert signed_in_many.json()["data"]["role"] == "admin"
    members = client.get("/api/v1/members?page=1&limit=20")
    assert members.status_code == 200, members.text
    assert {
        (item["email"], item["role"]) for item in members.json()["data"]["items"]
    } == {(admin["email"], "admin"), (member["email"], "member")}

    projects = client.get("/api/v1/projects?page=1&limit=20")
    assert projects.status_code == 200, projects.text
    assert [item["name"] for item in projects.json()["data"]["items"]] == [
        "Kept after switch"
    ]

    options = client.get("/api/v1/auth/options")
    assert options.status_code == 200, options.text
    assert options.json()["data"]["signUpOpen"] is True

    new_account = credentials()
    signed_up = client.post("/api/v1/auth/sign-up", json=new_account)
    assert signed_up.status_code == 201, signed_up.text
    assert signed_up.json()["data"]["role"] == "admin"
    new_members = client.get("/api/v1/members?page=1&limit=20")
    assert new_members.status_code == 200, new_members.text
    assert [
        (item["email"], item["role"]) for item in new_members.json()["data"]["items"]
    ] == [(new_account["email"], "admin")]
