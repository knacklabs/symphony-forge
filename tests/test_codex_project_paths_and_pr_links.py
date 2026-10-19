"""Codex's project and attachment contracts through real work and close commands.

Test-audit: dict roots currently reach Path and abort placement; an array identity is
refused by Codex. Existing chat tests only send plain roots and accept any identity.
Only the third-party app-server, GitHub and reviewer are faked; no production seam.
"""
import json
import shutil
import sys

import pytest

from conftest import ROOT, _install
from test_chatview_attach import URL, _closable
from test_chatview_start import SERVER, _ready
from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_setup import _fresh_client, _version

STORY = "codex-project-roots"


@pytest.mark.parametrize("shape", ["plain", "object", "mixed", "unknown"])
def test_1_worker_matches_path_and_object_roots_and_skips_unknown_records(
        repo, monkeypatch, sdk_data, shape, claude_session):
    folder, calls = _ready(repo, monkeypatch, sdk_data)
    path = str(repo.path / ".." / repo.path.name)
    roots = {"plain": [path], "object": [{"path": path, "future": True}],
             "mixed": [None, 7, {}, {"path": []}, {"path": ""}, {"path": path}],
             "unknown": [None, {}, {"path": 7}, {"future": path}]}[shape]
    projects = [{"id": "other", "roots": [str(folder)]}, {"id": "main", "roots": roots}]
    if shape in ("mixed", "unknown"):
        projects = [None, [], {"roots": [path]}, {"id": {}, "roots": [path]},
                    {"id": "bad", "roots": None}, *projects]
    monkeypatch.setenv("STUB_PROJECTS", json.dumps(projects))
    for _ in range(2):  # Both a new chat and the worker's continued round use the boundary.
        worked = repo.forge("work", "BOARD/PAGE")
        assert worked.returncode == 0, worked.stdout + worked.stderr
    log = (repo.path / ".git/forge/work-BOARD-PAGE.log").read_text("utf-8")
    if shape == "unknown":
        assert _sent(calls, "thread/metadata/update") == []
        assert log.count("project_skipped=no matching project") == 2
    else:
        assert _sent(calls, "thread/metadata/update") == [
            {"threadId": "thr-stub-1", "projectId": "main"}] * 2
        assert log.count("project=main") == 2
    assert "Codex could not update the chat project" not in log
    assert "Traceback" not in log


@pytest.mark.parametrize("client", ["new", "earlier-adopted"])
def test_2_close_links_the_pr_using_codex_string_identity_after_client_setup(
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
        # Setup commits represent releases already landed, as in the upgrade fixtures.
        repo.git("config", "core.hooksPath", str(tmp_path / "setup-hooks"))
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade Forge")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/upgrade")
    repo.git("config", "core.hooksPath", str(tmp_path / "setup-hooks"))
    _, calls = _closable(repo, gh, monkeypatch, tmp_path, sdk_data, client=True)
    # Codex rejects a sequence identity; its successful reply carries a record object.
    server = SERVER.replace('        if method in ("thread/metadata/update", "thread/attachment/add"):',
        '''        if method == "thread/attachment/add":
            if not isinstance(params.get("identityKey"), str):
                send(id=message["id"], error={"code": -32600,
                     "message": "Invalid request: invalid type: sequence, expected a string"})
            else:
                send(id=message["id"], result={"attachment": {"id": "pr-link", "future": True}})
            continue
        if method in ("thread/metadata/update", "thread/attachment/add"):''')
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{server}")
    monkeypatch.setenv("STUB_PROJECTS", json.dumps([
        {"id": "main", "roots": [{"path": str(repo.path)}]}]))
    worked = repo.forge("work", "BOARD/PAGE")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    for _ in range(2):
        closed = repo.forge("close", "BOARD/PAGE")
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert "Ready:" in closed.stdout
        assert "Could not link the pull request in its Codex chat" not in closed.stdout
    links = _sent(calls, "thread/attachment/add")
    assert len(links) == 2 and links[0] == links[1]
    assert links[0]["threadId"] == "thr-stub-1"
    assert json.loads(links[0]["identityKey"]) == ["github.com", "acme", "board", 12]
    assert links[0]["payload"] == {"url": URL, "root": str(repo.path.resolve()),
                                   "headBranch": "task/BOARD-PAGE"}
    assert _sent(calls, "thread/metadata/update") == [
        {"threadId": "thr-stub-1", "projectId": "main"}]
