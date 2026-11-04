"""Sign-in status chooses new-repo defaults; existing settings stay unchanged."""
import json
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import _install
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

STORY = "FIX-INIT-DETECTS-CLAUDE-ONLY"


def _auth(repo, claude, codex):
    # Fake only the CLI edge. Other Claude calls still use the shared plugin stub.
    path = repo.bin / "claude"
    original = path.read_text(encoding="utf-8")
    body = (f"if sys.argv[1:] == ['auth', 'status']:\n"
            f"    print({json.dumps({'loggedIn': claude})!r})\n"
            "    sys.exit(0)\n")
    _install(repo.bin, "claude", original.replace("args = sys.argv[1:]", body + "args = sys.argv[1:]"))
    _install(repo.bin, "codex", f"#!{sys.executable}\nimport sys\n"
             "if sys.argv[1:] == ['login', 'status']:\n"
             f"    print({'Logged in using ChatGPT' if codex is True else 'Not logged in'!r})\n"
             f"    sys.exit({0 if codex is True else 1 if codex is False else 2})\n"
             "sys.exit(2)\n")


@pytest.mark.parametrize("claude,codex,tools,workers,message", [
    (True, False, "claude", "claude", "Only Claude is signed in. Forge uses Claude for all work."),
    (True, True, "both", "split", ""),
    (False, False, "both", "split", "Sign in to Claude or Codex before you start work."),
    (True, None, "both", "split", ""),
    (None, False, "both", "split", ""),
    (False, True, "both", "split", ""),
])
def test_1_init_uses_signed_in_tools(repo, gh, tmp_path, claude, codex, tools, workers, message):
    _auth(repo, claude, codex)
    client = _new_repo(repo, gh, tmp_path)
    done = repo.forge("init", "--actions", "yes", cwd=client)
    assert done.returncode == 0, done.stdout + done.stderr
    cfg = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))
    assert cfg.get("tools", "both") == tools
    assert cfg["workers"] == workers
    if message:
        assert message in done.stdout


@pytest.mark.parametrize("workers,codex,warns,adopted", [
    ("split", False, True, False), ("codex", False, True, False),
    ("claude", False, False, False), ("split", True, False, False),
    ("split", None, False, False), ("split", False, True, True),
])
def test_2_doctor_reports_codex_sign_in_without_changing_existing_settings(
        repo, gh, tmp_path, workers, codex, warns, adopted):
    _auth(repo, True, codex)
    if adopted:
        old = Path(__file__).parent / "fixtures/adopted-v1.2.2/client/forge.toml"
        text = old.read_text(encoding="utf-8").replace('workers = "codex"', f'workers = "{workers}"')
        settings = repo.write("forge.toml", text)
        client = repo.path
    else:
        version = repo.forge("--version").stdout.split()[-1]
        text = f'version = "{version}"\nworkers = "{workers}"\n'
        client = _new_repo(repo, gh, tmp_path, text)
        done = repo.forge("init", "--actions", "yes", cwd=client)
        assert done.returncode == 0, done.stdout + done.stderr
        settings = client / "forge.toml"
    done = repo.forge("doctor", cwd=client)
    assert ("Codex is not signed in.\n  Fix: codex login" in done.stdout) is warns, done.stdout
    assert settings.read_text(encoding="utf-8") == text
