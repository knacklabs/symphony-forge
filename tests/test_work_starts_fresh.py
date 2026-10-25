"""Work resumes a held Codex chat by starting fresh with the whole brief.

The command and SDK run for real; only the Codex app-server is a stand-in.
"""
import pytest

from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_steer_resume import _ready, _writer
from test_worker_and_reader_chats_survive_rounds import _adopted

STORY = "work-starts-fresh-when-conversation-held"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_work_starts_fresh_with_whole_brief_when_conversation_is_held(
        repo, monkeypatch, sdk_data, claude_session, adopted):
    # The old contract refused work. The new contract continues without closing the holder.
    if adopted:
        _adopted(repo)
    _, calls, _ = _ready(repo, monkeypatch, sdk_data)
    first_prompt = _sent(calls, "turn/start")[0]["input"][0]["text"]
    monkeypatch.setenv("STUB_RESUME_ERROR", "hold")
    with _writer(repo, "hold") as holder:
        done = repo.forge("work", "BOARD/PAGE", "--note", "Keep the page keyboard accessible.")
        assert done.returncode == 0, done.stdout + done.stderr
        assert holder.poll() is None
    assert done.stdout.count("Starting a new Codex conversation, because another program "
                             "holds the earlier conversation.") == 1
    assert "Another program holds this Codex conversation" not in done.stderr
    assert [call["threadId"] for call in _sent(calls, "thread/resume")] == ["thr-stub-1"] * 2
    assert len(_sent(calls, "thread/start")) == 2
    turn = _sent(calls, "turn/start")[-1]
    assert turn["threadId"] == "thr-stub-2"
    prompt = turn["input"][0]["text"]
    assert "Keep the page keyboard accessible." in prompt
    # The stable whole-brief sections must survive the fresh start, not just a continuation note.
    for section in ("# Worker brief", "## Standards", "## Before you hand over"):
        assert section in first_prompt
        assert section in prompt
