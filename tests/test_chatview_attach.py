"""forge close links the item's pull request in its recorded Codex chat."""
from __future__ import annotations

import json
import shutil

from conftest import REAL_CODEX_HOME
from test_chatview_start import _ready
from test_close import CLEAN, GREEN, PIN, ROOT
from test_codex_worker import _sent, _stub, sdk_data  # noqa: F401

STORY = "FORGE-CHATVIEW-1"
URL = "https://github.com/acme/board/pull/12"


def _closable(repo, gh, monkeypatch, tmp_path, sdk_data, client=False):
    """BOARD/PAGE after one Codex round, with a stub Autoreview, green checks and its pull request."""
    folder, calls = _ready(repo, monkeypatch, sdk_data, client=client)
    toml = folder / "forge.toml"
    toml.write_text(toml.read_text("utf-8").replace(
        'workers = "codex"', 'workers = "codex"\nchecks = ["tests"]', 1), encoding="utf-8")
    repo.git("commit", "-q", "-am", "Close waits for tests", cwd=folder)
    skill = tmp_path / "autoreview"
    (skill / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "tests" / "stubs" / "autoreview", skill / "scripts" / "autoreview")
    (skill / ".upstream-sha").write_text(PIN + "\n", "utf-8")
    queue = tmp_path / "reviews.json"
    queue.write_text(json.dumps([CLEAN]), "utf-8")
    monkeypatch.setenv("AUTOREVIEW", str(skill / "scripts" / "autoreview"))
    monkeypatch.setenv("AUTOREVIEW_STUB", str(queue))
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    lines = "".join(json.dumps(row) + "\n" for row in GREEN)
    gh.respond("api", "--paginate", "--jq", ".check_runs[]", stdout=lines)
    gh.respond("api", "--paginate", "--jq", ".statuses[]", stdout="")
    gh.respond("pr", "list", stdout=json.dumps(
        [{"number": 12, "state": "OPEN", "body": "", "isDraft": False}]))
    gh.respond("pr", "edit")
    gh.respond("pr", "view", stdout=json.dumps(
        {"number": 12, "url": URL, "headRefName": "task/BOARD-PAGE"}))
    return folder, calls


def test_5_close_attaches_its_pull_request_once_to_the_recorded_chat(
        repo, gh, monkeypatch, tmp_path, sdk_data, claude_session):
    _, calls = _closable(repo, gh, monkeypatch, tmp_path, sdk_data)
    # With no recorded chat, close sends Codex nothing and never asks GitHub for the link.
    before = repo.forge("close", "BOARD/PAGE")
    assert before.returncode == 0, before.stdout + before.stderr
    assert "Ready:" in before.stdout
    assert not any(call[:2] == ["pr", "view"] for call in gh.calls())
    assert _sent(calls, "thread/attachment/add") == []

    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    started = len(_stub(calls))

    # A close that finds no pull request opens one, then links it in the recorded chat.
    gh.respond("pr", "list", stdout="[]")
    gh.respond("pr", "create", stdout=URL + "\n")
    closed = repo.forge("close", "BOARD/PAGE")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert f"Opened the pull request: {URL}" in closed.stdout
    assert "Ready:" in closed.stdout
    assert ["pr", "view", "task/BOARD-PAGE", "--json", "number,url,headRefName"] in gh.calls()
    assert _sent(calls, "thread/attachment/add") == [{
        "threadId": "thr-stub-1", "attachmentType": "pull_request",
        # Codex takes opaque text, not the old array; the serialized identity stays stable.
        "identityKey": json.dumps(["github.com", "acme", "board", 12]),
        "payload": {"url": URL, "root": str(repo.path.resolve()),
                    "headBranch": "task/BOARD-PAGE"}}]

    # Item 6: the close's own Codex runs used the test's throwaway home, never the owner's.
    homes = {entry["codex_home"] for entry in _stub(calls)[started:] if "codex_home" in entry}
    assert homes == {str(repo.path.parent / "codex-home")} and str(REAL_CODEX_HOME) not in homes

    # A repeat sends the same identity, which the app-server keeps as one attachment.
    gh.respond("pr", "list", stdout=json.dumps(
        [{"number": 12, "state": "OPEN", "body": "", "isDraft": False}]))
    again = repo.forge("close", "BOARD/PAGE")
    assert again.returncode == 0, again.stdout + again.stderr
    sent = _sent(calls, "thread/attachment/add")
    assert len(sent) == 2 and sent[0] == sent[1]

    # Codex refusing the attachment is said plainly, and the close still ends Ready.
    monkeypatch.setenv("STUB_CHATVIEW_FAIL", "thread/attachment/add")
    failed = repo.forge("close", "BOARD/PAGE")
    assert failed.returncode == 0, failed.stdout + failed.stderr
    assert "Could not link the pull request in its Codex chat" in failed.stdout
    assert "The next forge close tries again" in failed.stdout
    assert "Ready:" in failed.stdout
    log = (repo.path / ".git/forge/work-BOARD-PAGE.log").read_text("utf-8")
    assert "Could not attach the pull request to the Codex chat" in log
    assert "stub unavailable" in log

    # A close that finds the pull request already merged still links it in the recorded chat.
    monkeypatch.delenv("STUB_CHATVIEW_FAIL")
    gh.respond("pr", "list", stdout=json.dumps(
        [{"number": 12, "state": "MERGED", "body": "", "isDraft": False}]))
    merged = repo.forge("close", "BOARD/PAGE")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert "is merged" in merged.stdout
    assert len(_sent(calls, "thread/attachment/add")) == 4
