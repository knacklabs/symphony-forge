"""Busy Codex chats: readers start fresh.

The CLI and pinned SDK run for real. Only the Codex app-server is a stand-in.
"""
import sys

import pytest

from conftest import _install
from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_readloop_rounds import CODEX
from test_worker_and_reader_chats_survive_rounds import _client_reader

STORY = "busy-codex-conversation"

BUSY_READER = CODEX.replace(
    "        save(threads)\n",
    '''        if method == "thread/resume" and os.environ.get("STUB_RESUME_ERROR"):
            send(id=message["id"], error={"code": -32603,
                 "message": "thread " + id + " already has an active writer"})
            continue
        save(threads)
''', 1)


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_cold_read_starts_fresh_after_busy_conversation_retry(
        repo, monkeypatch, tmp_path, sdk_data, adopted):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, "codex", adopted)
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{BUSY_READER}")
    reader.ok()
    reader.doc.write_text(reader.doc.read_text("utf-8") + "\nAn amendment.\n", encoding="utf-8")
    monkeypatch.setenv("STUB_RESUME_ERROR", "hold")
    done = reader.read()
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.count("Starting a new Codex conversation, because another program "
                             "holds the earlier conversation.") == 1
    assert "Codex never reported" not in done.stdout + done.stderr
    assert [call["threadId"] for call in _sent(reader.log, "thread/resume")] == ["thr-stub-1"] * 2
    assert len(_sent(reader.log, "thread/start")) == 2
    assert _sent(reader.log, "turn/start")[-1]["threadId"] == "thr-stub-2"
    assert reader.doc.read_text("utf-8") in reader.prompt()
    assert "No findings." in reader.notes.read_text("utf-8")
