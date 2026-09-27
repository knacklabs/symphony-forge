"""A worker's question pauses its item until the coordinator answers."""
from __future__ import annotations

import json

from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401

STORY = "FORGE-STEER-1"


def test_2_question_blocks_work_and_close_until_answered(repo, monkeypatch, sdk_data, gh):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    question = "Question: May I use the existing parser?"
    monkeypatch.setenv("STUB_SAY", "\n\n" + question)
    before = repo.git("rev-list", "--count", "HEAD", cwd=folder)
    asked = repo.forge("work", "BOARD/PAGE")
    assert asked.returncode == 0, asked.stderr
    assert question in asked.stdout and 'forge work BOARD/PAGE --note "<answer>"' in asked.stdout
    assert int(repo.git("rev-list", "--count", "HEAD", cwd=folder)) == int(before) + 1
    record = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD" / "PAGE.json"
    assert json.loads(record.read_text("utf-8"))["question"] == question

    head = repo.git("rev-parse", "HEAD", cwd=folder)
    blocked = repo.forge("work", "BOARD/PAGE")
    closed = repo.forge("close", "BOARD/PAGE")
    expected = (f"The worker is waiting for an answer:\n{question}\n"
                'Next: forge work BOARD/PAGE --note "<answer>"\n')
    assert blocked.stderr == expected
    assert closed.stderr == expected
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head
    assert not gh.calls()

    monkeypatch.setenv("STUB_CODEX_STATUS", "failed")
    failed = repo.forge("work", "BOARD/PAGE", "--note", "Yes, use it.")
    assert failed.returncode != 0
    assert json.loads(record.read_text("utf-8"))["question"] == question
    monkeypatch.delenv("STUB_CODEX_STATUS")
    monkeypatch.delenv("STUB_SAY")
    answered = repo.forge("work", "BOARD/PAGE", "--note", "Yes, use it.")
    assert answered.returncode == 0, answered.stderr
    brief = _sent(calls, "turn/start")[-1]["input"][0]["text"]
    assert question in brief and "Yes, use it." in brief
    assert json.loads(record.read_text("utf-8"))["question"] is None
