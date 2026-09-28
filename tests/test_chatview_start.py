"""Codex chat placement and test-home isolation through Forge commands."""
from __future__ import annotations

import json
import sys

from conftest import REAL_CODEX_HOME, _install
from test_codex_resume import RESUMING, _resuming
from test_codex_worker import MODELS, ROOT, _sent, _stub, _toml, sdk_data  # noqa: F401

STORY = "FORGE-CHATVIEW-1"

SERVER = RESUMING.replace(
    '    log(pid=os.getpid(), args=sys.argv[1:])\n',
    '    log(pid=os.getpid(), args=sys.argv[1:], codex_home=os.environ.get("CODEX_HOME"))\n', 1
).replace(
    '        threads = json.loads(STORE.read_text("utf-8")) if STORE.exists() else {}\n',
    '''        if method == "project/list":
            if os.environ.get("STUB_CHATVIEW_FAIL") == method:
                send(id=message["id"], error={"code": -32603, "message": "stub unavailable"})
                continue
            projects = json.loads(os.environ.get("STUB_PROJECTS", "[]"))
            cursor = params.get("cursor")
            offset = int(cursor) if cursor else 0
            result = {"data": projects[offset:offset + 1],
                      "nextCursor": str(offset + 1) if offset + 1 < len(projects) else None}
            send(id=message["id"], result=result)
            continue
        if method in ("thread/metadata/update", "thread/attachment/add"):
            if os.environ.get("STUB_CHATVIEW_FAIL") == method:
                send(id=message["id"], error={"code": -32603, "message": "stub unavailable"})
            else:
                send(id=message["id"], result={})
            continue
        threads = json.loads(STORE.read_text("utf-8")) if STORE.exists() else {}
''', 1)
READ_SERVER = (ROOT / "tests/stubs/codex-app-server").read_text(encoding="utf-8").replace(
    '        elif method == "thread/start":\n',
    '''        elif method == "project/list":
            reply(message, {"data": [{"id": "main", "roots": [os.environ["STUB_MAIN_ROOT"]]}],
                            "nextCursor": None})
        elif method == "thread/metadata/update":
            reply(message, {})
        elif method == "thread/start":
''', 1)


def _ready(repo, monkeypatch, sdk_data):
    folder, calls, _ = _resuming(repo, monkeypatch, sdk_data)
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{SERVER}")
    return folder, calls


def test_2_worker_joins_only_the_unique_main_checkout_project(repo, monkeypatch, sdk_data):
    folder, calls = _ready(repo, monkeypatch, sdk_data)
    monkeypatch.setenv("STUB_PROJECTS", json.dumps([
        {"id": "other", "roots": [str(folder)]},
        {"id": "main", "roots": [str(repo.path / ".." / repo.path.name)]},
    ]))
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr
    assert _sent(calls, "thread/start")[-1]["cwd"] == str(folder)
    assert _sent(calls, "thread/metadata/update")[-1] == {
        "threadId": "thr-stub-1", "projectId": "main"}
    assert "project=main" in repo.path.joinpath(".git/forge/work-BOARD-PAGE.log").read_text()
    assert len(_sent(calls, "project/list")) == 2

    resumed = repo.forge("work", "BOARD/PAGE")
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert len(_sent(calls, "thread/metadata/update")) == 2

    monkeypatch.setenv("STUB_PROJECTS", json.dumps([
        {"id": "one", "roots": [str(repo.path)]},
        {"id": "two", "roots": [str(repo.path)]},
    ]))
    second = repo.forge("work", "BOARD/PAGE")
    assert second.returncode == 0, second.stdout + second.stderr
    assert len(_sent(calls, "thread/metadata/update")) == 2
    assert "project_skipped=" in repo.path.joinpath(".git/forge/work-BOARD-PAGE.log").read_text()

    monkeypatch.setenv("STUB_PROJECTS", "[]")
    missing = repo.forge("work", "BOARD/PAGE")
    assert missing.returncode == 0, missing.stdout + missing.stderr
    assert len(_sent(calls, "thread/metadata/update")) == 2
    assert "project_skipped=no matching project" in repo.path.joinpath(
        ".git/forge/work-BOARD-PAGE.log").read_text()

    monkeypatch.setenv("STUB_CHATVIEW_FAIL", "project/list")
    failed = repo.forge("work", "BOARD/PAGE")
    assert failed.returncode == 0, failed.stdout + failed.stderr
    assert "Check Codex and try again" in repo.path.joinpath(
        ".git/forge/work-BOARD-PAGE.log").read_text()

    story = repo.path.parent / "repo-story-BOARD"
    repo.git("worktree", "add", "-q", str(story), "story/BOARD")
    version = repo.forge("--version").stdout.split()[-1]
    (story / "forge.toml").write_text(_toml(version, "claude", {
        **MODELS, "grill.codex": {"model": "gpt-6-sol", "effort": "high"},
        "grill.claude": {"model": "opus", "effort": "high"}}), encoding="utf-8")
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{READ_SERVER}")
    monkeypatch.setenv("STUB_MAIN_ROOT", str(repo.path))
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    read = repo.forge("read", "BOARD")
    assert read.returncode == 0, read.stdout + read.stderr
    assert _sent(calls, "thread/metadata/update")[-1] == {
        "threadId": "thr-stub-1", "projectId": "main"}


def test_6_codex_home_is_throwaway(repo, monkeypatch, sdk_data):
    _, calls = _ready(repo, monkeypatch, sdk_data)
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _sent(calls, "thread/start")
    used = [entry["codex_home"] for entry in _stub(calls) if "codex_home" in entry]
    assert used == [str(repo.path.parent / "codex-home")]
    assert used[0] != str(REAL_CODEX_HOME)
