"""A worker's question pauses its item until the coordinator answers."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time

import pytest

from conftest import _install
from test_codex_resume import _resuming
from test_codex_worker import _codex_repo, _lines, _sent, sdk_data  # noqa: F401

STORY = "FORGE-STEER-1"


def _resumable_question(repo, monkeypatch, sdk_data):
    folder, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    stub = repo.bin / "codex-app-server"
    source = stub.read_text("utf-8")
    original = '"text": f"stub codex: {turn} on {id}"'
    assert source.count(original) == 1
    source = source.replace(original, original + ' + os.environ.get("STUB_SAY", "")')
    # The resume fixture only displays its message. Give the SDK the timestamp it requires to
    # recognize the message as a final answer, as the worker fixture does.
    source = source.replace('"turnId": turn, "item": said',
                            '"turnId": turn, "completedAtMs": 2, "item": said')
    _install(repo.bin, "codex-app-server", source)
    question = "Question: May I use the existing parser?"
    monkeypatch.setenv("STUB_SAY", "\n\n" + question)
    asked = repo.forge("work", "BOARD/PAGE")
    assert asked.returncode == 0, asked.stderr
    record = turns.with_suffix(".json")
    assert json.loads(record.read_text("utf-8"))["question"] == question, asked.stdout
    monkeypatch.delenv("STUB_SAY")
    return folder, calls, turns, record, question


@pytest.mark.parametrize("scenario", ("fresh", "resume", "interrupt"))
def test_2_question_blocks_work_and_close_until_answered(repo, monkeypatch, sdk_data, gh,
                                                         scenario, claude_session):
    if scenario == "resume":
        _answer_continues_the_same_conversation(repo, monkeypatch, sdk_data)
        return
    if scenario == "interrupt":
        _interrupted_answer_keeps_the_question_unanswered(repo, monkeypatch, sdk_data)
        return
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


def _answer_continues_the_same_conversation(repo, monkeypatch, sdk_data):
    folder, calls, turns, record, question = _resumable_question(repo, monkeypatch, sdk_data)
    conversation = json.loads(record.read_text("utf-8"))["conversation"]
    started = len(_sent(calls, "thread/start"))

    answered = repo.forge("work", "BOARD/PAGE", "--note", "Yes, use it.")
    assert answered.returncode == 0, answered.stderr
    assert len(_sent(calls, "thread/start")) == started
    assert _sent(calls, "thread/resume")[-1]["threadId"] == conversation
    assert _lines(turns)[-1]["continued"] is True
    brief = _sent(calls, "turn/start")[-1]["input"][0]["text"]
    assert question in brief and "Yes, use it." in brief
    assert json.loads(record.read_text("utf-8"))["question"] is None


def _interrupted_answer_keeps_the_question_unanswered(repo, monkeypatch, sdk_data):
    if os.name == "nt":
        pytest.skip("sending one process SIGINT is POSIX-only")
    folder, calls, turns, record, question = _resumable_question(repo, monkeypatch, sdk_data)
    before = len(_lines(turns))
    answering = subprocess.Popen(
        [sys.executable, str(repo.bin / "forge"), "work", "BOARD/PAGE", "--note", "Yes, use it."],
        cwd=repo.path, env={**os.environ, "STUB_CODEX_STATUS": "hold"},
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and answering.poll() is None:
            try:
                # The turn log precedes the recovery record; wait for both, as _holding does.
                if len(_lines(turns)) > before:
                    saved = json.loads(record.read_text("utf-8"))
                    if saved.get("pending") is None and "continued" in saved:
                        break
            except (FileNotFoundError, ValueError):
                pass  # either file may be halfway written
            time.sleep(0.05)
        else:
            pytest.fail("the answering turn never started")
        answering.send_signal(signal.SIGINT)
        # Driver cleanup itself has a five-second wait and a thirty-second group-exit bound.
        _, error = answering.communicate(timeout=60)
        assert answering.returncode == 130, error
    finally:
        if answering.poll() is None:
            answering.kill()
        answering.communicate(timeout=60)

    assert json.loads(record.read_text("utf-8"))["question"] == question
    expected = (f"The worker is waiting for an answer:\n{question}\n"
                'Next: forge work BOARD/PAGE --note "<answer>"\n')
    assert repo.forge("work", "BOARD/PAGE").stderr == expected
    assert repo.forge("close", "BOARD/PAGE").stderr == expected
