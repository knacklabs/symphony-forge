"""Claude sign-in failures must name the cause at the command boundary.

Audit: doctor currently never asks for auth status; close streams and retries
the error. Existing close failures cover unavailable models, not sign-in.
Only the external CLI and Autoreview are faked; no production seam is needed.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

import conftest
from test_close import env  # noqa: F401 -- shared command fixture

STORY = "claude-sign-in"
pytestmark = pytest.mark.platform


@pytest.fixture(params=["new", "earlier-release"])
def client(env, request):
    repo = env.repo
    repo.git("checkout", "-q", "-b", "fix/select-claude")
    if request.param == "earlier-release":
        fixture = Path(__file__).parent / "fixtures/adopted-v1.2.2/client"
        shutil.copytree(fixture, repo.path, dirs_exist_ok=True)
        config = repo.path / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            '"v1.2.2"', json.dumps(repo.forge("--version").stdout.split()[-1])), encoding="utf-8")
    config = repo.path / "forge.toml"
    config.write_text('tools = "claude"\n' + config.read_text("utf-8"), encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Select Claude")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/select-claude")
    repo.git("push", "-q", "origin", "main")
    env.earlier_release = request.param == "earlier-release"
    return env


def test_1_doctor_reports_selected_claude_sign_in(client):
    repo = client.repo
    conftest._install(repo.bin, "claude", f'''#!{sys.executable}
import json, sys
if sys.argv[1:] == ["auth", "status"]:
    print(json.dumps({{"loggedIn": False}}))
    sys.exit(1)
print("2.1.317")
''')
    result = repo.forge("doctor")
    assert "Claude is not signed in." in result.stdout, result.stdout + result.stderr
    assert "run claude and sign in" in result.stdout
    if not client.earlier_release:
        # An unsupported status command or a signed-in CLI is not a sign-in failure.
        for output, code in [(json.dumps({"loggedIn": True}), 0), ("Unknown command: auth", 1), ("", 1)]:
            conftest._install(repo.bin, "claude", f'''#!{sys.executable}
import sys
print({output!r})
sys.exit({code})
''')
            result = repo.forge("doctor")
            assert "Claude is not signed in." not in result.stdout + result.stderr
        config = repo.path / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'tools = "claude"', 'tools = "codex"'), encoding="utf-8")
        conftest._install(repo.bin, "claude", f'''#!{sys.executable}
import json
print(json.dumps({{"loggedIn": False}}))
''')
        result = repo.forge("doctor")
        assert "Claude is not signed in." not in result.stdout + result.stderr


def test_2_close_stops_on_first_claude_sign_in_error(client):
    item, where = client.start_fix()
    client.reviews({"exit": 1, "report": None, "say": "claude engine failed (1)\n" + json.dumps({
        "type": "result", "is_error": True, "result": "Not logged in · Please run /login"})})
    result = client.repo.forge("close", item, cwd=where)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr.strip() == (
        f"Claude is not signed in. Next: run claude and sign in, then forge close {item}.")
    assert len(client.review_calls()) == 1
