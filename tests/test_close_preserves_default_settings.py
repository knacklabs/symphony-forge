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
from test_close import GREEN, env, run  # noqa: F401
from test_codex_worker import MODELS, _toml, sdk_data  # noqa: F401
from test_migrate import _copied_client, _review_and_checks
from test_upgrade_command import Upgrade
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "close-keeps-main-settings"
MESSAGE = "Kept main's settings in forge.toml and this branch's version pin."


def _setup(env, client, tmp_path, named=False, renamed_check=False):
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
    if renamed_check:
        incoming = incoming.replace('checks = ["tests",', 'checks = ["current-tests",')
        env.checks([run("current-tests"), run("forge-pr-check")])
    setup.on_main("forge.toml", incoming)
    client.git("fetch", "-q", "origin", "main", cwd=folder)
    return folder, settings, incoming


@pytest.mark.platform
@pytest.mark.parametrize("client", [False, True], indirect=True, ids=["new", "adopted"])
@pytest.mark.usefixtures("claude_session")
def test_1_codex_open_merge_keeps_incoming_settings_through_close(
        env, client, monkeypatch, sdk_data, tmp_path):
    folder, _, incoming = _setup(env, client, tmp_path)
    source = (ROOT / "tests/stubs/codex-app-server").read_text("utf-8")
    insertion = '                if os.environ.get("STUB_CODEX_TOUCH"):'
    merge = '''                import subprocess
                marker = pathlib.Path(cwd) / "merged-main.txt"
                if not marker.exists():
                    subprocess.run(["git", "merge", "-q", "--no-commit", "origin/main"],
                                   cwd=cwd, check=True, stdout=sys.stderr, stderr=sys.stderr)
                    settings = pathlib.Path(cwd) / "forge.toml"
                    settings.write_text(settings.read_text("utf-8") + "# Worker edit\\n", "utf-8")
                    subprocess.run(["git", "add", "forge.toml"], cwd=cwd, check=True)
                    merged = subprocess.run(["git", "commit", "-qm", "Merge main"],
                                            cwd=cwd, capture_output=True, text=True)
                    assert merged.returncode != 0, merged.stdout + merged.stderr
                    assert "Workers leave forge.toml" in merged.stderr, merged.stderr
                    marker.write_text("Merged main\\n", "utf-8")
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
    # The successful turn leaves the rejected merge open. The real commit nudge
    # must finish it after cleanup removes only the worker's edit.
    monkeypatch.setenv("STUB_CODEX_COMMIT_FROM", "2")
    worked = client.forge("work", "correct-spelling")
    log = (client.path / ".git/forge/work-correct-spelling.log").read_text("utf-8")
    assert worked.returncode == 0, worked.stdout + worked.stderr + log
    assert (folder / "forge.toml").read_text("utf-8") == incoming
    assert client.git("show", ":forge.toml", cwd=folder) == incoming.strip()
    assert "Restored uncommitted forge.toml changes from the incoming merge" in worked.stdout
    assert "The worker left changes uncommitted" in worked.stdout
    assert client.git("rev-parse", "HEAD^2", cwd=folder) == client.git("rev-parse", "origin/main")
    assert client.git("status", "--porcelain", cwd=folder) == ""
    closed = client.forge("close", "correct-spelling")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    assert (folder / "forge.toml").read_text("utf-8") == incoming
    assert client.git("status", "--porcelain", cwd=folder) == ""


@pytest.mark.parametrize("client, case", [
    pytest.param(False, case, id=f"new-{case}")
    for case in ("stale", "pin-only", "allowed", "clean", "checks")
] + [pytest.param(True, "checks", id="adopted-stale-and-renamed-checks")], indirect=["client"])
def test_2_close_commits_main_settings_with_head_pin_unless_settings_are_allowed(
        env, client, tmp_path, case):
    folder, original, incoming = _setup(env, client, tmp_path, named=case == "allowed",
                                        renamed_check=case == "checks")
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
    repaired = case in ("stale", "checks")
    assert closed.stdout.count(MESSAGE) == int(repaired)
    commits = client.git("log", "--format=%H", f"{before}..HEAD", "--", "forge.toml", cwd=folder).splitlines()
    assert len(commits) == int(repaired)
    assert client.git("status", "--porcelain", cwd=folder) == ""


def test_3_initial_migration_keeps_its_settings_until_the_initial_merge(repo, gh, tmp_path, monkeypatch):
    # Initial migration owns its new settings: main has no copy to restore yet.
    _copied_client(repo, tmp_path, monkeypatch)
    migrated = repo.forge("migrate")
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    folder = repo.path.parent / f"{repo.path.name}-forge-migrate-v1"
    before = (folder / "forge.toml").read_text("utf-8")
    _review_and_checks(repo, gh, tmp_path, monkeypatch)
    closed = repo.forge("close", "migrate-v1")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    assert (folder / "forge.toml").read_text("utf-8") == before
    assert repo.git("show", "HEAD:forge.toml", cwd=folder) == before.strip()
    assert MESSAGE not in closed.stdout
