"""Both worker hosts receive delegation guidance; Codex enables the configured helpers."""
import json
import os
import shutil

import pytest

from conftest import ROOT, _install
from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "codex-spawns-subagents-only-when-explici"


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
        guidance = " ".join(brief.split())
        for invitation in ("spawn the repo's subagent roles", "independent parts",
                           "explorer to trace code paths", "tester to write tests while you build",
                           "separate files edited in parallel", "at most 3 subagents at a time",
                           "Do small tasks yourself"):
            assert invitation in guidance
