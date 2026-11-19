"""A developer's GitHub app identity and token at Forge's command boundary."""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import conftest
from github_api_stub import GitHubApiStub
from test_close import GREEN, env
from test_queue_land_all import client, _fix
from test_train_land_all import train, _ready, _all

STORY = "FORGE-GHAPP-1"


def openssl_executable() -> str:
    openssl = shutil.which("openssl")
    if openssl is None and os.name == "nt":
        git = shutil.which("git")
        if git:
            root = Path(git).resolve().parent.parent
            openssl = next((str(candidate) for candidate in (
                root / "usr/bin/openssl.exe", root / "mingw64/bin/openssl.exe",
            ) if candidate.is_file()), None)
    if openssl is None:
        raise AssertionError("OpenSSL is required to check the GitHub app test key")
    return openssl


def save_app(tmp_path: Path, login: str = "octocat", owner: str = "acme",
             slug: str = "forge-octocat") -> Path:
    config = tmp_path / ("local-app-data" if os.name == "nt" else "config")
    folder = config / "forge" / "github-apps"
    folder.mkdir(parents=True, exist_ok=True)
    key = folder / "123.pem"
    openssl = openssl_executable()
    subprocess.run([openssl, "genrsa", "-out", str(key), "2048"], check=True,
                   capture_output=True, timeout=30)
    (folder / "123.json").write_text(json.dumps({
        "id": 123, "slug": slug, "owner": owner, "login": login,
    }), "utf-8")
    return key


def verify_app_jwt(request: dict, key: Path, tmp_path: Path) -> str:
    authorization = request["authorization"]
    assert authorization and authorization.startswith("Bearer ")
    token = authorization.removeprefix("Bearer ")
    header, claims, signature = token.split(".")
    decode = lambda part: base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))
    assert json.loads(decode(header))["alg"] == "RS256"
    payload = json.loads(decode(claims))
    assert payload["iss"] == 123
    assert payload["exp"] - payload["iat"] <= 600

    public, signed, sig = tmp_path / "app-public.pem", tmp_path / "jwt-input", tmp_path / "jwt-signature"
    openssl = openssl_executable()
    subprocess.run([openssl, "pkey", "-in", str(key), "-pubout", "-out", str(public)],
                   check=True, capture_output=True, timeout=30)
    signed.write_bytes(f"{header}.{claims}".encode("ascii"))
    sig.write_bytes(decode(signature))
    verified = subprocess.run([openssl, "dgst", "-sha256", "-verify", str(public),
                               "-signature", str(sig), str(signed)],
                              check=False, capture_output=True, text=True, timeout=30)
    assert verified.returncode == 0, verified.stdout + verified.stderr
    return token


def github_repo(repo: conftest.Repo) -> None:
    repo.git("remote", "set-url", "origin", "gh:acme/app")
    repo.git("config", "url.https://github.com/.insteadOf", "gh:")


def test_1_doctor_shows_who_close_acts_as_and_the_budget_left(repo, gh, tmp_path,
                                                              monkeypatch):
    config = tmp_path / ("local-app-data" if os.name == "nt" else "config")
    monkeypatch.setenv("LOCALAPPDATA" if os.name == "nt" else "XDG_CONFIG_HOME", str(config))
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "echo ok"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Add Forge settings")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    github_repo(repo)
    gh.respond("auth", "status", stdout="Logged in to github.com as octocat\n")
    rate_limit = json.dumps({"resources": {
        "core": {"remaining": 6500, "limit": 6750, "reset": 1800000000},
        "graphql": {"remaining": 6700, "limit": 6750, "reset": 1800000000},
    }})

    def run_doctor(*answers: tuple[str, str, int, dict], login: str = "octocat"):
        save_app(tmp_path, login=login)
        gh.respond("api", "rate_limit", stdout=rate_limit)
        with GitHubApiStub() as api:
            for method, path, status, data in answers:
                api.respond(method, path, data, status)
            monkeypatch.setenv("FORGE_GITHUB_API", api.url)
            result = repo.forge("doctor")
            requests = list(api.requests)
        return result, requests, gh.token_calls("api", "rate_limit")[-1:]

    result, requests, token_call = run_doctor(
        ("GET", "/repos/acme/app/installation", 200,
         {"id": 9, "repository_selection": "selected"}),
        ("POST", "/app/installations/9/access_tokens", 200,
         {"token": "ghs_doctor", "expires_at": "2099-01-01T00:00:00Z"}),
    )
    assert ("- GitHub: close, merge and land act as your app forge-octocat. "
            "6,500 of 6,750 requests and 6,700 of 6,750 GraphQL points are left") in result.stdout
    assert len([line for line in result.stdout.splitlines() if line.startswith("- GitHub:")]) == 1
    assert "Warning: Your app forge-octocat" not in result.stdout
    assert "could not be used" not in result.stdout
    assert [request["path"] for request in requests] == [
        "/repos/acme/app/installation", "/app/installations/9/access_tokens"]
    assert requests[0]["authorization"].startswith("Bearer ")
    assert requests[1]["body"] == {"repositories": ["app"]}
    assert token_call[0]["token"] == "ghs_doctor"

    result, requests, _ = run_doctor(
        ("GET", "/repos/acme/app/installation", 200,
         {"id": 9, "repository_selection": "all"}),
    )
    assert 'installed on all repos of acme' in result.stdout
    assert "https://github.com/organizations/acme/settings/installations" in result.stdout
    assert len([line for line in result.stdout.splitlines() if line.startswith("- GitHub:")]) == 1
    assert [request["path"] for request in requests] == ["/repos/acme/app/installation"]

    app_folder = config / "forge" / "github-apps"
    (app_folder / "123.json").unlink()
    (app_folder / "123.pem").unlink()
    gh.respond("api", "rate_limit", stdout=rate_limit)
    with GitHubApiStub() as api:
        monkeypatch.setenv("FORGE_GITHUB_API", api.url)
        result = repo.forge("doctor")
        assert api.requests == []
    assert "use your gh sign-in octocat" in result.stdout
    assert "forge init --github-app" in result.stdout
    assert "could not be used" not in result.stdout
    assert len([line for line in result.stdout.splitlines() if line.startswith("- GitHub:")]) == 1
    assert "Your GitHub app forge-octocat could not be used" not in result.stdout
    assert gh.token_calls("api", "rate_limit")[-1]["token"] is None

    result, requests, token_call = run_doctor(
        ("GET", "/repos/acme/app/installation", 404, {"message": "Not Found"}),
    )
    assert "not installed on acme/app yet" in result.stdout
    assert "https://github.com/apps/forge-octocat/installations/new" in result.stdout
    assert [request["path"] for request in requests] == ["/repos/acme/app/installation"]
    assert token_call[0]["token"] is None

    result, requests, token_call = run_doctor(
        ("GET", "/repos/acme/app/installation", 200,
         {"id": 9, "repository_selection": "selected"}),
        ("POST", "/app/installations/9/access_tokens", 401,
         {"message": "Bad credentials"}),
    )
    assert "Your GitHub app forge-octocat could not be used" in result.stdout
    assert "123.pem" in result.stdout and "123.json" in result.stdout
    assert "forge init --github-app" in result.stdout
    assert [request["path"] for request in requests][-1] == "/app/installations/9/access_tokens"
    assert result.stdout.count("Your GitHub app forge-octocat could not be used") == 1
    assert token_call[0]["token"] is None

    result, requests, token_call = run_doctor(login="hubot")
    assert "use your gh sign-in octocat" in result.stdout
    assert "forge init --github-app" in result.stdout
    assert requests == []
    assert token_call[0]["token"] is None

    # A caller-supplied credential is already the developer's chosen identity. Neither token
    # variable may trigger app discovery or mint an app token.
    save_app(tmp_path)
    for variable in ("GH_TOKEN", "GITHUB_TOKEN"):
        other = "GITHUB_TOKEN" if variable == "GH_TOKEN" else "GH_TOKEN"
        monkeypatch.delenv(other, raising=False)
        monkeypatch.setenv(variable, "ghp_developer")
        gh.respond("api", "rate_limit", stdout=rate_limit)
        with GitHubApiStub() as api:
            monkeypatch.setenv("FORGE_GITHUB_API", api.url)
            result = repo.forge("doctor")
            assert api.requests == []
        assert f"use the token in {variable}" in result.stdout
        assert "could not be used" not in result.stdout
        assert gh.token_calls("api", "rate_limit")[-1]["token"] == (
            "ghp_developer" if variable == "GH_TOKEN" else None)
        monkeypatch.delenv(variable, raising=False)


def test_4_close_merge_and_land_act_as_the_app_and_fall_back(train, tmp_path, monkeypatch):
    env = train
    config = tmp_path / ("local-app-data" if os.name == "nt" else "config")
    monkeypatch.setenv("LOCALAPPDATA" if os.name == "nt" else "XDG_CONFIG_HOME", str(config))
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    # Real fetches and pushes need the fixture's local transport. Doctor above
    # separately proves origin discovery, including insteadOf expansion.
    monkeypatch.setenv("FORGE_GITHUB_REPO", "acme/app")
    key = save_app(tmp_path)
    script = env.repo.bin / "gh"
    text = script.read_text("utf-8")
    # The train's edge can answer before the shared stub. Log every request once.
    text = text.replace("import json, pathlib, subprocess, sys, tempfile, time, zlib",
                        "import json, os, pathlib, subprocess, sys, tempfile, time, zlib", 1)
    text = text.replace('args = sys.argv[1:]\n',
                        'args = sys.argv[1:]\n'
                        'append_json(here / "app-token-calls.jsonl", '
                        '{"args": args, "token": os.environ.get("GH_TOKEN")})\n', 1)
    script.write_text(text, "utf-8")
    log = env.repo.bin / "app-token-calls.jsonl"

    def calls():
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text("utf-8").splitlines()]

    def expires(minutes):
        return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()

    with GitHubApiStub() as api:
        api.respond("GET", "/repos/acme/app/installation",
                    {"id": 9, "repository_selection": "selected"})
        api.respond("POST", "/app/installations/9/access_tokens",
                    {"token": "ghs_one", "expires_at": expires(2)})
        api.respond("POST", "/app/installations/9/access_tokens",
                    {"token": "ghs_two", "expires_at": expires(60)})
        monkeypatch.setenv("FORGE_GITHUB_API", api.url)
        _fix(env, monkeypatch, "aa", 1, {"aa.py": "print('aa')\n"}, status="working")
        before = len(calls())
        closed = env.repo.forge("close", "aa")
        assert closed.returncode == 0, closed.stdout + closed.stderr
        close_calls = calls()[before:]
        used = [call for call in close_calls if call["token"] in {"ghs_one", "ghs_two"}]
        assert used and used[0]["token"] == "ghs_one"
        assert len(used) > 1 and all(call["token"] == "ghs_two" for call in used[1:])
        assert len(api.requests) == 3
        jwt = verify_app_jwt(api.requests[0], key, tmp_path)
        assert any(call["args"][:2] == ["pr", "view"] and call["token"] == "ghs_two"
                   for call in close_calls)
        assert any(call["args"][:1] == ["api"] and call["token"] == "ghs_two"
                   for call in close_calls)
        merged = env.repo.forge("merge", "aa")
        assert merged.returncode == 0, merged.stdout + merged.stderr
        _ready(env, monkeypatch, ("bb", "cc"), first=2)
        before = len(calls())
        landed = _all(env)
        assert landed.returncode == 0, landed.stdout + landed.stderr
        land_calls = calls()[before:]
        drafts = [call for call in land_calls
                  if call["args"][:2] == ["pr", "create"] and "--draft" in call["args"]]
        assert drafts and all(call["token"] is None for call in drafts)
        assert any(call["token"] == "ghs_two" for call in land_calls)
        all_calls = calls()
        authored = [call for call in all_calls if call["args"][:2] == ["pr", "create"]
                    or call["args"][:2] == ["pr", "edit"] and "--body-file" in call["args"]]
        assert authored and any("--body-file" in call["args"] for call in authored)
        assert all(call["token"] is None for call in authored)
        merges = [call for call in all_calls if call["args"][:2] == ["pr", "merge"]]
        assert len(merges) == 3 and all(call["token"] == "ghs_two" for call in merges)
        assert all(request["body"] == {"repositories": ["app"]}
                   for request in api.requests if request["method"] == "POST")
        arguments = json.dumps([call["args"] for call in all_calls])
        assert all(secret not in arguments for secret in (jwt, "ghs_one", "ghs_two"))

    # Separate commands keep the sign-in when the app is absent or refused.
    app_folder = config / "forge" / "github-apps"
    for day, scenario in enumerate(("missing", "404", "401", "GH_TOKEN", "GITHUB_TOKEN"), 4):
        slug = "fallback-" + scenario.lower().replace("_", "-")
        save_app(tmp_path)
        if scenario == "missing":
            (app_folder / "123.json").unlink()
        with monkeypatch.context() as case, GitHubApiStub() as api:
            case.setenv("FORGE_GITHUB_API", api.url)
            if scenario in ("GH_TOKEN", "GITHUB_TOKEN"):
                case.setenv(scenario, "personal")
            api.respond("GET", "/repos/acme/app/installation",
                        {"message": "Not Found"} if scenario == "404" else
                        {"id": 9, "repository_selection": "selected"},
                        404 if scenario == "404" else 200)
            api.respond("POST", "/app/installations/9/access_tokens",
                        {"message": "Bad credentials"}, 401)
            _fix(env, monkeypatch, slug, day, {slug + ".py": "print('fallback')\n"},
                 status="working")
            before = len(calls())
            done = env.repo.forge("close", slug)
            assert done.returncode == 0, done.stdout + done.stderr
            assert not any(call["token"] in {"ghs_one", "ghs_two"} for call in calls()[before:])
            if scenario == "401":
                assert done.stderr.count("could not be used: Bad credentials") == 1
                assert len(api.requests) == 2
            else:
                assert "could not be used" not in done.stderr
                assert len(api.requests) == (1 if scenario == "404" else 0)
