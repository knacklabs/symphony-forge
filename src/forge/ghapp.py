"""Private GitHub app keys and one-repository installation tokens."""
from __future__ import annotations

import base64
import hashlib
import getpass
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_INSTALLATIONS: dict[tuple[int, str, str], dict[str, Any] | None] = {}
_TOKENS: dict[tuple[int, str, str], tuple[str, float]] = {}
_SELECTIONS: dict[Path, tuple[str, str, dict[str, Any] | None] | None] = {}
_FAILED: set[tuple[int, str, str]] = set()
_WARNED = False
_SELECTING = False
_URL = re.compile(
    r"(?:https?://github\.com/|ssh://git@(?:ssh\.)?github\.com(?::443)?/|"
    r"git@github\.com:)([^/]+)/([^/]+?)(?:\.git)?$"
)


def folder() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root.expanduser() / "forge" / "github-apps"


def saved(login: str | None, owner: str) -> dict[str, Any] | None:
    matches = []
    for path in sorted(folder().glob("*.json")):
        try:
            app = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (not isinstance(app, dict) or not isinstance(app.get("id"), int)
                or not isinstance(app.get("slug"), str)
                or not isinstance(app.get("owner"), str)
                or not isinstance(app.get("login"), str)):
            continue
        if app["owner"].casefold() != owner.casefold():
            continue
        if login and app["login"].casefold() != login.casefold():
            continue
        matches.append(app)
    return matches[0] if len(matches) == 1 else None


def _refuse(problem: str, next_step: str) -> None:
    from forge import repo

    raise repo.Refused(problem, next_step)


def _inside_repo(path: Path) -> bool:
    parent = path
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    done = subprocess.run(["git", "-C", str(parent), "rev-parse", "--is-inside-work-tree"],
                          capture_output=True, text=True)
    return done.returncode == 0 and done.stdout.strip() == "true"


def _windows_user() -> str:
    domain, username = os.environ.get("USERDOMAIN", ""), os.environ.get("USERNAME", "")
    if username:
        return f"{domain}\\{username}" if domain else username
    return getpass.getuser()


def _acl_accounts(path: Path, output: str) -> set[str]:
    lines = output.splitlines()
    if lines and lines[0].casefold().startswith(str(path).casefold()):
        lines[0] = lines[0][len(str(path)):]
    return {match.group(1).strip() for line in lines
            if (match := re.match(r"^\s*(.+?):\(", line))}


def _private_windows(path: Path, directory: bool) -> None:
    user = _windows_user()
    grant = f"{user}:" + ("(OI)(CI)F" if directory else "F")

    def run(*args: str) -> str:
        done = subprocess.run(["icacls", str(path), *args], capture_output=True, text=True)
        if done.returncode:
            said = (done.stdout or done.stderr).splitlines()
            raise OSError(said[0].strip() if said else "icacls could not secure the GitHub app key")
        return done.stdout

    run("/inheritance:r", "/grant:r", grant)
    accounts = _acl_accounts(path, run())
    for account in sorted(accounts):
        if account.casefold() != user.casefold():
            run("/remove:g", account)
    remaining = _acl_accounts(path, run())
    other = next((account for account in sorted(remaining)
                  if account.casefold() != user.casefold()), None)
    if other:
        raise OSError(f"{other} can still access the GitHub app key")


def save(answer: dict[str, Any], login: str) -> dict[str, Any]:
    app_owner = answer.get("owner", {}).get("login") if isinstance(answer.get("owner"), dict) else None
    try:
        app_id = int(answer["id"])
        slug = answer["slug"]
        pem = answer["pem"]
    except (KeyError, TypeError, ValueError):
        raise ValueError("GitHub did not return the app id, name or private key") from None
    if app_id < 1 or not isinstance(slug, str) or not isinstance(app_owner, str) or not isinstance(pem, str):
        raise ValueError("GitHub did not return the app id, name or private key")

    target = folder()
    next_step = ("point LOCALAPPDATA outside any repo, then forge init --github-app" if os.name == "nt"
                 else "point XDG_CONFIG_HOME outside any repo, then forge init --github-app")
    if _inside_repo(target):
        _refuse(f"Forge keeps app keys outside every repo, but {target} is inside one.", next_step)
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "nt":
        try:
            _private_windows(target, True)
        except OSError as error:
            _refuse(str(error).splitlines()[0], "forge init --github-app")
    else:
        target.chmod(0o700)

    app = {"id": app_id, "slug": slug, "owner": app_owner, "login": login}
    key_path, data_path = target / f"{app_id}.pem", target / f"{app_id}.json"
    suffix = f"{os.getpid()}.{time.time_ns()}"
    key_tmp, data_tmp = target / f".{app_id}.{suffix}.pem", target / f".{app_id}.{suffix}.json"
    try:
        fd = os.open(key_tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as key_file:
            key_file.write(pem.encode("utf-8"))
        if os.name == "nt":
            _private_windows(key_tmp, False)
        os.replace(key_tmp, key_path)
        fd = os.open(data_tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as data_file:
            json.dump(app, data_file)
        os.replace(data_tmp, data_path)
    except OSError as error:
        for path in (key_tmp, data_tmp):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        _refuse(str(error).splitlines()[0], "forge init --github-app")
    return app


def _der_value(data: bytes, offset: int = 0) -> tuple[int, bytes, int]:
    tag = data[offset]
    size = data[offset + 1]
    offset += 2
    if size & 0x80:
        count = size & 0x7f
        if not count or count > 4:
            raise ValueError("invalid private key")
        size = int.from_bytes(data[offset:offset + count], "big")
        offset += count
    end = offset + size
    if end > len(data):
        raise ValueError("invalid private key")
    return tag, data[offset:end], end


def _der_children(data: bytes) -> list[tuple[int, bytes]]:
    tag, contents, end = _der_value(data)
    if tag != 0x30 or end != len(data):
        raise ValueError("invalid private key")
    values = []
    offset = 0
    while offset < len(contents):
        tag, value, offset = _der_value(contents, offset)
        values.append((tag, value))
    return values


def _rsa_numbers(pem: str) -> tuple[int, int]:
    try:
        lines = pem.strip().splitlines()
        label = lines[0].strip()
        if not label.startswith("-----BEGIN ") or not label.endswith("-----"):
            raise ValueError
        encoded = "".join(line.strip() for line in lines[1:-1])
        der = base64.b64decode(encoded, validate=True)
        if label == "-----BEGIN PRIVATE KEY-----":
            fields = _der_children(der)
            key = next(value for tag, value in fields if tag == 0x04)
            fields = _der_children(key)
        elif label == "-----BEGIN RSA PRIVATE KEY-----":
            fields = _der_children(der)
        else:
            raise ValueError
        integers = [int.from_bytes(value, "big") for tag, value in fields if tag == 0x02]
        if len(integers) < 4 or not integers[1] or not integers[3]:
            raise ValueError
        return integers[1], integers[3]
    except (ValueError, IndexError, StopIteration, TypeError):
        raise ValueError("the GitHub app private key is not a supported RSA key") from None


def jwt(app: dict[str, Any]) -> str:
    try:
        pem = (folder() / f"{int(app['id'])}.pem").read_text(encoding="utf-8")
    except (OSError, KeyError, TypeError, ValueError):
        raise ValueError("the GitHub app private key cannot be read") from None
    modulus, private_exponent = _rsa_numbers(pem)
    now = int(time.time())
    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = _b64(json.dumps({"iat": now - 60, "exp": now + 540, "iss": int(app["id"])},
                             separators=(",", ":")).encode())
    unsigned = f"{header}.{claims}"
    digest = hashlib.sha256(unsigned.encode()).digest()
    # ponytail: signing in Python is not constant-time; only a process that can already read this user's key can observe it. Use a crypto library if Forge adds one.
    size = (modulus.bit_length() + 7) // 8
    block = b"\x00\x01" + b"\xff" * (size - len(digest) - 3 - 19) + b"\x00"
    block += bytes.fromhex("3031300d060960864801650304020105000420") + digest
    signature = pow(int.from_bytes(block, "big"), private_exponent, modulus)
    encoded = signature.to_bytes(size, "big")
    return f"{unsigned}.{_b64(encoded)}"


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _response(payload: bytes) -> Any:
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except (UnicodeDecodeError, ValueError):
        return payload.decode("utf-8", errors="replace")


def api(method: str, path: str, auth: str | None = None,
        body: dict[str, Any] | None = None) -> tuple[int, Any]:
    base = os.environ.get("FORGE_GITHUB_API", "https://api.github.com").rstrip("/")
    url = f"{base}/{path.lstrip('/')}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "symphony-forge"}
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, _response(response.read())
    except urllib.error.HTTPError as error:
        return error.code, _response(error.read())
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        reason = getattr(error, "reason", error)
        return 0, {"message": str(reason).splitlines()[0] or "GitHub did not answer"}


def _message(data: Any, secrets: tuple[str, ...] = ()) -> str:
    value = data.get("message", "GitHub did not accept the request") if isinstance(data, dict) else data
    message = str(value).splitlines()[0].strip() if value else "GitHub did not accept the request"
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[removed]")
    return message.rstrip(". ")


def installation(app: dict[str, Any], owner: str, repo: str) -> dict[str, Any] | None:
    auth = jwt(app)
    path = f"repos/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(repo, safe='')}/installation"
    status, data = api("GET", path, auth=auth)
    if status == 404:
        return None
    if not 200 <= status < 300 or not isinstance(data, dict):
        raise ValueError(_message(data, (auth,)))
    return data


def _key(app: dict[str, Any], owner: str, repo: str) -> tuple[int, str, str]:
    return int(app["id"]), owner.casefold(), repo.casefold()


def _token(app: dict[str, Any], owner: str, repo: str,
           installed: dict[str, Any] | None = None) -> str | None:
    key = _key(app, owner, repo)
    if key in _FAILED:
        raise ValueError("the GitHub app could not be used earlier in this command")
    cached = _TOKENS.get(key)
    now = time.time()
    if cached and cached[1] - now >= 300:
        return cached[0]
    if installed is not None:
        _INSTALLATIONS.setdefault(key, installed)
    if key not in _INSTALLATIONS:
        _INSTALLATIONS[key] = installation(app, owner, repo)
    installed = _INSTALLATIONS[key] if installed is None else installed
    if installed is None:
        return None
    auth = jwt(app)
    path = f"app/installations/{int(installed['id'])}/access_tokens"
    status, data = api("POST", path, auth=auth, body={"repositories": [repo]})
    if not 200 <= status < 300 or not isinstance(data, dict):
        raise ValueError(_message(data, (auth,)))
    token = data.get("token")
    expiry = data.get("expires_at")
    if not isinstance(token, str) or not isinstance(expiry, str):
        raise ValueError("GitHub did not return an installation token")
    try:
        expires = datetime.fromisoformat(expiry.replace("Z", "+00:00")).timestamp()
    except ValueError:
        raise ValueError("GitHub returned an invalid installation token expiry") from None
    _TOKENS[key] = token, expires
    return token


def _repository(top: Path) -> tuple[str, str] | None:
    from forge import repo

    if override := os.environ.get("FORGE_GITHUB_REPO"):
        owner, name = override.split("/", 1)
        return owner, name
    try:
        origin = repo.git("remote", "get-url", "origin", cwd=top).strip()
    except (repo.Refused, OSError):
        return None
    match = _URL.fullmatch(origin)
    return (match[1], match[2]) if match else None


def _login(top: Path) -> str | None:
    from forge import repo

    try:
        result = repo.run("gh", "config", "get", "user", "-h", "github.com", cwd=top)
    except repo.Refused:
        return None
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def _selection(top: Path) -> tuple[str, str, dict[str, Any] | None] | None:
    global _SELECTING

    key = top.resolve()
    if key in _SELECTIONS:
        return _SELECTIONS[key]
    location = _repository(top)
    if location is None:
        _SELECTIONS[key] = None
        return None
    owner, name = location
    _SELECTING = True
    try:
        app = saved(_login(top), owner)
    finally:
        _SELECTING = False
    selected = (owner, name, app)
    _SELECTIONS[key] = selected
    return selected


def _budget(top: Path, token: str | None) -> str | None:
    from forge import repo

    env = None if token is None else {**os.environ, "GH_TOKEN": token}
    result = repo.run("gh", "api", "rate_limit", cwd=top, env=env)
    if result.returncode:
        return None
    try:
        resources = json.loads(result.stdout)["resources"]
        core, graphql = resources["core"], resources["graphql"]
        reset = datetime.fromtimestamp(int(core["reset"]), timezone.utc).strftime("%H:%M UTC")
        line = (f"{int(core['remaining']):,} of {int(core['limit']):,} requests and "
                f"{int(graphql['remaining']):,} of {int(graphql['limit']):,} GraphQL points "
                f"are left this hour; it resets at {reset}.")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        return None
    return line


def doctor(top: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    location = _repository(top)
    if location is None:
        return rows
    owner, name = location
    login = _login(top)
    use_env = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    app = None if use_env else saved(login, owner)
    installed = None
    token = None
    app_failed = False

    if app:
        try:
            installed = installation(app, owner, name)
            if installed:
                token = _token(app, owner, name, installed)
        except (OSError, ValueError, KeyError, TypeError) as error:
            app_failed = True
            reason = _message(str(error))
            key_folder = folder()
            fix = (f"an owner of {owner} deletes the app {app['slug']} on GitHub; delete "
                   f"{key_folder / (str(app['id']) + '.pem')} and "
                   f"{key_folder / (str(app['id']) + '.json')}; then forge init --github-app")
            rows.append((f"Your GitHub app {app['slug']} could not be used: {reason}.", fix))

    if use_env:
        identity = f"use the token in {'GH_TOKEN' if os.environ.get('GH_TOKEN') else 'GITHUB_TOKEN'}"
    elif token:
        identity = f"act as your app {app['slug']}"
    else:
        identity = f"use your gh sign-in {login}" if login else "use your gh sign-in"

    if app and installed and installed.get("repository_selection") == "all":
        if owner.casefold() == (app.get("login") or "").casefold():
            settings = "https://github.com/settings/installations"
        else:
            settings = f"https://github.com/organizations/{urllib.parse.quote(owner, safe='')}/settings/installations"
        print(f'- Warning: Your app {app["slug"]} is installed on all repos of {owner}. Ask an '
              f'owner of {owner} to change it to "Only select repositories" with only the repos '
              f'you work on. {settings}')

    budget = _budget(top, token)
    line = f"- GitHub: close, merge and land {identity}."
    if budget:
        line += f" {budget}"
    else:
        line += " The request budget could not be read."
    if not use_env and not app:
        line += " You have no Forge GitHub app on this laptop for this repo: forge init --github-app."
    elif app and installed is None and not app_failed:
        install_url = f"https://github.com/apps/{urllib.parse.quote(app['slug'], safe='')}/installations/new"
        line += (f" Your app {app['slug']} is not installed on {owner}/{name} yet: an owner of "
                 f"{owner} installs it on {install_url}.")
    print(line)
    return rows


def env(args: tuple[str, ...] | list[str], cwd: str | os.PathLike[str] | None) -> dict[str, str]:
    from forge import github

    global _WARNED
    args = tuple(args)
    if (not github.wait_for_reset or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
            or _SELECTING
            or args[1:3] == ("pr", "create")
            or (args[1:3] == ("pr", "edit") and "--body-file" in args)):
        return {}
    top = Path(cwd or Path.cwd())
    selection = _selection(top)
    if selection is None:
        return {}
    owner, name, app = selection
    if app is None:
        return {}
    try:
        token = _token(app, owner, name)
    except (OSError, ValueError, KeyError, TypeError) as error:
        _FAILED.add(_key(app, owner, name))
        if not _WARNED:
            reason = _message(str(error))
            command = next((arg for arg in sys.argv[1:2] if arg in {"close", "merge", "land"}), "command")
            print(f"Your GitHub app {app['slug']} could not be used: {reason}. "
                  f"forge {command} uses your gh sign-in. Next: forge doctor",
                  file=sys.stderr, flush=True)
            _WARNED = True
        return {}
    if token is None:
        return {}
    return {"GH_TOKEN": token}
