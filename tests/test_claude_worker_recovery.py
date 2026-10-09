"""Claude workers recover lost sessions and transient progress-file contention."""
import json
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "skipped-workers"
FIX = "recover-worker-output"


def _client(repo, gh, tmp_path, previous, *, subagents=False):
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    settings = (f'version = "{version}"\nrepo = "client"\n'
               'workers = "claude"\ntest = "git status --porcelain"\n'
               'models.lite = { model = "sonnet", effort = "medium"' +
               (', subagents = "gpt-6-luna", subagent_effort = "max"' if subagents else '') + '}\n')
    if previous:
        repo.write("forge.toml", settings)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Configure Claude client")
        repo.git("push", "-q", "origin", "main")
    else:
        client = tmp_path / "client"
        client.mkdir()
        (client / "forge.toml").write_text(settings, encoding="utf-8")
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    log = install_claude(repo)
    started = repo.forge("fix", "start", "Recover worker output", "--done",
                         "Worker finishes after a lost session")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = repo.path.parent / f"{repo.path.name}-fix-{FIX}"
    synced = repo.forge("sync", cwd=folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    if repo.git("status", "--porcelain", cwd=folder):
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-q", "-m", "Sync client adapters", cwd=folder)
    return log, folder


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
def test_1_lost_session_recovery_searches_all_claude_output(repo, gh, tmp_path, previous):
    log, folder = _client(repo, gh, tmp_path, previous)
    first = repo.forge("work", FIX)
    assert first.returncode == 0, first.stdout + first.stderr
    original = calls(log)[0]
    session = original["args"][original["args"].index("--session-id") + 1]
    (repo.bin / "claude-sessions.json").unlink()
    stub = repo.bin / "claude"
    source = stub.read_text("utf-8").replace(
        'print(f"No conversation found with session ID: {session}", file=sys.stderr)',
        'print(json.dumps({"type": "result", "subtype": "error_during_execution", '
        '"result": "Resume failed", "errors": ["Diagnostic before the error", '
        'f"No conversation found with session ID: {session}"]}))')
    stub.write_text(source, encoding="utf-8")

    recovered = repo.forge("work", FIX)

    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    _, rejected, fresh = calls(log)
    assert rejected["args"][rejected["args"].index("--resume") + 1] == session
    assert "--session-id" in fresh["args"] and "--resume" not in fresh["args"]
    assert "# Worker brief" in fresh["brief"]
    assert "Starting a new Claude session with the whole brief" in recovered.stdout
    assert fresh["cwd"] == str(folder)


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
def test_2_claude_ignores_codex_only_subagent_keys_on_first_fix(repo, gh, tmp_path, previous):
    log, _ = _client(repo, gh, tmp_path, previous, subagents=True)
    worked = repo.forge("work", FIX)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    [sent] = calls(log)
    assert sent["args"][:5] == ["-p", "--model", "sonnet", "--effort", "medium"]
    assert "subagents" not in sent["args"] and "gpt-6-luna" not in sent["args"]


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
def test_3_progress_retries_a_busy_events_file_without_aborting_worker(repo, gh, tmp_path, previous):
    log, _ = _client(repo, gh, tmp_path, previous)
    stub = repo.bin / "claude"
    stub.write_text(stub.read_text("utf-8").replace(
        'print("stub claude: built it")',
        'print(json.dumps({"type": "system", "subtype": "init", "model": "sonnet"}))\n'
        'print(json.dumps({"type": "result", "result": "Worker completed"}))'), encoding="utf-8")
    # The command shim supplies one Windows sharing violation at the filesystem edge;
    # the real progress writer decides whether to retry, without a production seam.
    shim = repo.bin / "forge"
    marker = repo.bin / "busy-events-observed"
    shim.write_text(shim.read_text("utf-8").replace('from forge.cli import main', f'''import os
from pathlib import Path
real_replace = os.replace
busy = True
def replace(source, target):
    global busy
    if busy and str(target).endswith("events.jsonl"):
        busy = False
        Path({json.dumps(marker.as_posix())}).write_text("busy", encoding="utf-8")
        raise PermissionError("events file is held by a reader")
    return real_replace(source, target)
os.replace = replace
from forge.cli import main'''), encoding="utf-8")

    worked = repo.forge("work", FIX)

    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert marker.read_text("utf-8") == "busy"
    assert "Worker completed" in worked.stdout
    assert len(calls(log)) == 1
