"""Codex merges and close preserve the default branch's coordinator settings.

Audit: work restores HEAD during an open merge, and close trusts that stale
commit. Existing settings tests cover worker edits, not incoming main settings.
Real Forge commands and installed hooks own both repairs; only Codex and GitHub
are faked at their external boundaries. No production test seam is needed.
"""
import json
import sys

import pytest

from conftest import ROOT, _install
from test_close import GREEN, env  # noqa: F401
from test_codex_worker import MODELS, _toml, sdk_data  # noqa: F401
from test_upgrade_command import Upgrade
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "close-keeps-main-settings"
MESSAGE = "Kept main's settings in forge.toml and this branch's version pin."


def _setup(env, client, tmp_path, named=False):
    env.checks(GREEN)
    setup = Upgrade(env, tmp_path)
    version = client.forge("--version").stdout.split()[-1]
    settings = _toml(version, "codex", MODELS, "client")
    settings = settings.replace(f'version = "{version}"', f'version = "{version}" # branch pin')
    settings = 'test = "echo ok"\nfast_test = "echo ok"\nchecks = ["tests", "forge-pr-check"]\n' + settings
    setup.on_main("forge.toml", settings)
    started = client.forge("fix", "start", "Correct spelling", "--done",
                           "Update forge.toml" if named else "Correct the spelling", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = client.path.parent / f"{client.path.name}-fix-correct-spelling"
    env.commit(folder, "product.txt", "Correct spelling\n")
    incoming = settings.replace('# branch pin', '# main pin').replace('echo ok', 'echo main')
    setup.on_main("forge.toml", incoming)
    client.git("fetch", "-q", "origin", "main", cwd=folder)
    return folder, settings, incoming


@pytest.mark.parametrize("client", [False, True], indirect=True, ids=["new", "adopted"])
@pytest.mark.usefixtures("claude_session")
def test_1_codex_open_merge_keeps_incoming_settings_through_close(
        env, client, monkeypatch, sdk_data, tmp_path):
    folder, _, incoming = _setup(env, client, tmp_path)
    source = (ROOT / "tests/stubs/codex-app-server").read_text("utf-8")
    insertion = '                if os.environ.get("STUB_CODEX_TOUCH"):'
    merge = '''                import subprocess
                subprocess.run(["git", "merge", "-q", "--no-commit", "origin/main"],
                               cwd=cwd, check=True, stdout=sys.stderr, stderr=sys.stderr)
                merged = subprocess.run(["git", "commit", "-qm", "Merge main"],
                                        cwd=cwd, capture_output=True, text=True)
                assert merged.returncode != 0, merged.stdout + merged.stderr
                assert "Workers leave forge.toml" in merged.stderr, merged.stderr
'''
    _install(client.bin, "codex-app-server", source.replace(insertion, merge + insertion, 1))
    program = client.bin / ("codex-app-server.cmd" if sys.platform == "win32" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    home = tmp_path / "settings-codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(client.path))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    # A failed round still restores settings, without a second model turn to commit.
    monkeypatch.setenv("STUB_CODEX_STATUS", "failed")
    worked = client.forge("work", "correct-spelling")
    assert worked.returncode == 1, worked.stdout + worked.stderr
    log = (client.path / ".git/forge/work-correct-spelling.log").read_text("utf-8")
    assert "Codex reported it failed" in worked.stderr, worked.stdout + worked.stderr + log
    assert (folder / "forge.toml").read_text("utf-8") == incoming
    assert client.git("show", ":forge.toml", cwd=folder) == incoming.strip()
    assert "Restored uncommitted forge.toml changes from the incoming merge" in worked.stdout
    client.git("add", "-A", cwd=folder)
    client.git("commit", "-qm", "Finish the main merge", cwd=folder)
    closed = client.forge("close", "correct-spelling")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    assert (folder / "forge.toml").read_text("utf-8") == incoming
    assert client.git("status", "--porcelain", cwd=folder) == ""


@pytest.mark.parametrize("client, case", [
    pytest.param(False, case, id=f"new-{case}")
    for case in ("stale", "pin-only", "allowed", "clean")
] + [pytest.param(True, "stale", id="adopted-stale")], indirect=["client"])
def test_2_close_commits_main_settings_with_head_pin_unless_settings_are_allowed(
        env, client, tmp_path, case):
    folder, original, incoming = _setup(env, client, tmp_path, named=case == "allowed")
    client.git("merge", "-q", "--no-commit", "origin/main", cwd=folder)
    # Reproduce the old Codex restore, including the stale copy committed by its nudge.
    if case != "clean":
        stale = incoming.replace('# main pin', '# branch pin') if case == "pin-only" else original
        (folder / "forge.toml").write_text(stale, "utf-8")
        client.git("add", "forge.toml", cwd=folder)
    client.git("commit", "-qm", "Finish the worker merge", cwd=folder)
    before = client.git("rev-parse", "HEAD", cwd=folder)
    closed = client.forge("close", "correct-spelling")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    expected = (original if case == "allowed" else incoming if case == "clean"
                else incoming.replace('# main pin', '# branch pin'))
    assert (folder / "forge.toml").read_text("utf-8") == expected
    assert client.git("show", "HEAD:forge.toml", cwd=folder) == expected.strip()
    repaired = case == "stale"
    assert closed.stdout.count(MESSAGE) == int(repaired)
    commits = client.git("log", "--format=%H", f"{before}..HEAD", "--", "forge.toml", cwd=folder).splitlines()
    assert len(commits) == int(repaired)
    assert client.git("status", "--porcelain", cwd=folder) == ""
