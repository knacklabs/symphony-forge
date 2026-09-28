"""The ask command chooses a model per question and leaves no saved Codex chat."""
from __future__ import annotations

from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401

STORY = "FORGE-STEER-1"


def test_6_ask_uses_chosen_model_and_effort_in_an_ephemeral_conversation(
        repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)

    chosen = repo.forge("ask", "Where is the parser?", "--model", "gpt-6-astra",
                        "--effort", "high", cwd=folder)
    assert chosen.returncode == 0, chosen.stderr
    assert "stub codex: built it" in chosen.stdout
    [started] = _sent(calls, "thread/start")
    assert started["config"] == {"model": "gpt-6-astra", "model_reasoning_effort": "high"}
    assert started["ephemeral"] is True

    effort_only = repo.forge("ask", "Where is the parser?", "--effort", "medium", cwd=folder)
    assert effort_only.returncode == 0, effort_only.stderr
    _, started = _sent(calls, "thread/start")
    assert started["config"] == {"model": "gpt-6-sol", "model_reasoning_effort": "medium"}
    assert started["ephemeral"] is True

    default = repo.forge("ask", "Where is the parser?", cwd=folder)
    assert default.returncode == 0, default.stderr
    assert "stub codex: built it" in default.stdout
    _, _, started = _sent(calls, "thread/start")
    assert started["config"] == {"model": "gpt-6-sol", "model_reasoning_effort": "low"}
    assert started["ephemeral"] is True
    assert repo.git("status", "--porcelain", cwd=folder) == ""
