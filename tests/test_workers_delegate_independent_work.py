"""Both worker hosts receive delegation guidance; Codex enables the configured helpers."""
import json
import os
import shutil
import sys

import pytest

from conftest import FORGE_SHIM, ROOT, _install
from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_codex_resume import _resuming
from test_fix_claude_workers_start_a_fresh_session_eve import FIX, _started
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "codex-spawns-subagents-only-when-explici"


def _invitation(brief):
    guidance = " ".join(brief.split())
    # New and resumed workers must learn the person-only stop rule after an upgrade.
    assert "Never run `forge stop`" in guidance
    for invitation in ("spawn the repo's subagent roles", "independent parts",
                       "explorer to trace code paths", "tester to write tests while you build",
                       "separate files edited in parallel", "at most 3 subagents at a time",
                       "Do small tasks yourself"):
        assert invitation in guidance


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
def test_1_workers_invite_delegation_and_codex_enables_configured_helpers(
        repo, gh, tmp_path, monkeypatch, sdk_data, previous):
    # Setup and sync deliver roles without requiring a new forge.toml setting. The prompt
    # and SDK settings sent by forge work are the contract; third-party stubs only record them.
    if previous:
        client = _new_repo(repo, gh, tmp_path)
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client,
                        dirs_exist_ok=True)
        path = client / "forge.toml"
        path.write_text(path.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{repo.forge("--version").stdout.split()[-1]}"'),
            encoding="utf-8")
        repo.git("switch", "-q", "-c", "fix/delegation", cwd=client)
        before = path.read_bytes()
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert path.read_bytes() == before
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.git("switch", "-q", "-c", "fix/delegation", cwd=client)
    for host, suffix in ((".codex", ".toml"), (".claude", ".md")):
        for role in ("explorer", "tester", "coder"):
            assert (client / host / "agents" / (role + suffix)).is_file()

    _install(repo.bin, "codex-app-server",
             (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(client))}]\ntrust_level = "trusted"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    codex_log = repo.bin / "codex-app-server.jsonl"
    claude_log = install_claude(repo)
    # Even a checkout explicitly disabling this Codex feature must get an enabled worker.
    config_path = client / ".codex/config.toml"
    config_path.write_text(config_path.read_text("utf-8").replace(
        "[features]", "[features]\nmulti_agent = false"), encoding="utf-8")
    path = client / "forge.toml"
    path.write_text(path.read_text("utf-8").replace('workers = "split"', 'workers = "codex"'),
                    encoding="utf-8")
    repo.git("add", "-A", cwd=client)
    # Seed the landed setup as the upgrade tests do, before there is an active fix record.
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-q", "-m",
             "Set up client workers", cwd=client)
    if previous:
        repo.git("branch", "main", cwd=client)
    repo.git("switch", "-q", "main", cwd=client)
    repo.git("merge", "-q", "--ff-only", "fix/delegation", cwd=client)
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main",
             cwd=client)
    started = repo.forge("fix", "start", "Delegate independent work", "--done",
                         "Workers may delegate independent parts", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    worked = repo.forge("work", "delegate-independent-work", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    config = _sent(codex_log, "thread/start")[-1]["config"]
    assert config["features.multi_agent"] is True
    assert config["agents.default_subagent_model"] == "gpt-6-luna"
    assert config["agents.default_subagent_reasoning_effort"] == "max"
    codex_brief = _sent(codex_log, "turn/start")[0]["input"][0]["text"]
    folder = client.parent / "client-fix-delegate-independent-work"
    path = folder / "forge.toml"
    path.write_text(path.read_text("utf-8").replace('workers = "codex"',
                    'workers = "claude"').replace('workers = "split"', 'workers = "claude"'),
                    encoding="utf-8")
    repo.git("commit", "-qam", "Choose Claude workers", cwd=folder)
    worked = repo.forge("work", "delegate-independent-work", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    for brief in (codex_brief, calls(claude_log)[0]["brief"]):
        _invitation(brief)


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_2_sync_gives_existing_sessions_the_invitation_when_they_resume(
        repo, gh, tmp_path, monkeypatch, sdk_data, host):
    # Start the real command with the earlier release's prompt bytes. Keep today's host
    # tracking, so the upgrade resumes rather than restarting for a separate record migration.
    if host == "codex":
        folder, log, _ = _resuming(repo, monkeypatch, sdk_data)
        item = "BOARD/PAGE"
        monkeypatch.setenv("STUB_CODEX_COMMIT", "built.py")
    else:
        log = _started(repo)
        item = FIX
        folder = repo.path.parent / "repo-fix-fix-the-login-typo"
    old_src = tmp_path / "pre-invitation"
    shutil.copytree(ROOT / "src/forge", old_src / "forge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    # Plain-text brief from the fix's base release, before the delegation invitation.
    shutil.copyfile(ROOT / "tests/fixtures/worker-brief-before-delegation.md",
                    old_src / "forge/templates/brief.md")
    command = repo.bin / "forge"
    current_command = command.read_text("utf-8")
    _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=str(old_src)))
    try:
        worked = repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
    finally:
        command.write_text(current_command, encoding="utf-8")
    if host == "codex":
        first = _sent(log, "turn/start")[0]["threadId"]
        old_brief = _sent(log, "turn/start")[0]["input"][0]["text"]
        monkeypatch.delenv("STUB_CODEX_COMMIT")
    else:
        [started] = calls(log)
        first = started["args"][started["args"].index("--session-id") + 1]
        old_brief = started["brief"]
    assert "spawn the repo's subagent roles" not in old_brief
    before = (folder / "forge.toml").read_bytes()
    synced = repo.forge("sync", cwd=folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert (folder / "forge.toml").read_bytes() == before
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "-q", "-m", "Sync upgraded instructions", cwd=folder)

    worked = repo.forge("work", item)

    assert worked.returncode == 0, worked.stdout + worked.stderr
    if host == "codex":
        assert len(_sent(log, "thread/start")) == 1
        assert _sent(log, "thread/resume")[-1]["threadId"] == first
        brief = _sent(log, "turn/start")[-1]["input"][0]["text"]
    else:
        [_, resumed] = calls(log)
        assert resumed["args"][resumed["args"].index("--resume") + 1] == first
        brief = resumed["brief"]
    assert "The earlier brief in this conversation still applies." in brief
    assert "# Worker brief" not in brief
    _invitation(brief)
