"""A new Codex conversation joins its project after its first turn creates a rollout.

Test-audit: the app-server rejects metadata updates before a rollout exists.
Existing project tests accept updates before any turn and miss this lifecycle error.
Only the external Codex server is changed; Forge runs through its work command.
"""
import json
import shutil
import sys

import pytest

from conftest import ROOT, _install
from test_chatview_start import SERVER, _ready
from test_codex_worker import sdk_data  # noqa: F401
from test_setup import _fresh_client, _version

STORY = "issue-1044-every-codex-round-prints-a-pr"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("client", ["new", "earlier-adopted"])
def test_1_new_conversation_sets_project_after_rollout_without_error(
        repo, gh, monkeypatch, tmp_path, sdk_data, client, claude_session):
    if client == "new":
        repo.path, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("switch", "-qc", "fix/upgrade")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
        config = (repo.path / "forge.toml").read_text("utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                                f'version = "{_version(repo)}"'))
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("config", "core.hooksPath", str(tmp_path / "setup-hooks"))
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade Forge")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/upgrade")
    repo.git("config", "core.hooksPath", str(tmp_path / "setup-hooks"))
    _ready(repo, monkeypatch, sdk_data, client=True)
    server = SERVER.replace(
        '        if method in ("thread/metadata/update", "thread/attachment/add"):',
        '''        if method == "thread/metadata/update":
            threads = json.loads(STORE.read_text("utf-8"))
            saved = threads[params["threadId"]]
            if not saved["turns"]:
                send(id=message["id"], error={"code": -32603,
                     "message": "no rollout found for thread id " + params["threadId"]})
            else:
                saved["projectId"] = params["projectId"]
                save(threads)
                send(id=message["id"], result={})
            continue
        if method in ("thread/metadata/update", "thread/attachment/add"):''')
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{server}")
    monkeypatch.setenv("STUB_PROJECTS", json.dumps([
        {"id": "main", "roots": [repo.path.as_posix()]}]))

    worked = repo.forge("work", "BOARD/PAGE")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    log = (repo.path / ".git/forge/work-BOARD-PAGE.log").read_text("utf-8")
    assert "project_skipped" not in worked.stdout + worked.stderr + log
    threads = json.loads((repo.bin / "threads.json").read_text("utf-8"))
    assert threads["thr-stub-1"]["projectId"] == "main"
    assert "project=main" in log
