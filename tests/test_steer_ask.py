"""A quick Codex question leaves the checkout unchanged."""
from __future__ import annotations

from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401

STORY = "FORGE-STEER-1"


def test_4_ask_is_read_only_and_discards_changed_checkout(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    head = repo.git("rev-parse", "HEAD", cwd=folder)
    asked = repo.forge("ask", "Where is the parser?", cwd=folder)
    assert asked.returncode == 0, asked.stderr
    assert "stub codex: built it" in asked.stdout
    [started] = _sent(calls, "thread/start")
    [turn] = _sent(calls, "turn/start")
    assert started["sandbox"] == "read-only" and turn["sandboxPolicy"]["type"] == "readOnly"
    assert started["config"]["model"] == "gpt-6-sol"
    assert "Where is the parser?" in turn["input"][0]["text"]
    assert repo.git("status", "--porcelain", cwd=folder) == ""
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head
    records = repo.path / ".git" / "forge" / "threads" / "ask"
    assert list(records.glob("*.json")) and list(records.glob("*.log"))

    empty = repo.forge("ask", "   ", cwd=folder)
    assert empty.stderr == 'The question is empty.\nNext: forge ask "<question>"\n'
    monkeypatch.setenv("STUB_CODEX_STATUS", "failed")
    failed = repo.forge("ask", "Where is the parser?", cwd=folder)
    assert failed.stderr == 'Codex did not complete the answer.\nNext: forge ask "<question>"\n'
    monkeypatch.delenv("STUB_CODEX_STATUS")
    monkeypatch.setenv("STUB_CODEX_TOUCH", "unexpected.txt")
    discarded = repo.forge("ask", "Where is the parser?", cwd=folder)
    assert discarded.stderr == ("A file changed while Codex answered, so its answer was discarded.\n"
                                'Next: git status, then forge ask "<question>"\n')
    assert "stub codex: built it" not in discarded.stdout
    assert (folder / "unexpected.txt").exists()
    (folder / "unexpected.txt").unlink()
    monkeypatch.setenv("STUB_CODEX_TOUCH", "README.md")
    tracked = repo.forge("ask", "Where is the parser?", cwd=folder)
    assert tracked.stderr == discarded.stderr and "stub codex: built it" not in tracked.stdout
    assert repo.git("status", "--porcelain", cwd=folder) == "M README.md"
