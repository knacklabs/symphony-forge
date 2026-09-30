"""A full-access Codex worker turn accepts every approval request; a read-only turn declines."""
from __future__ import annotations

from test_codex_worker import KNOWN, UNKNOWN, _codex_repo, _sent, _stub, sdk_data  # noqa: F401

STORY = "codex-worker-turns-decline-every-approva"
ACCEPT, DECLINE = {"decision": "accept"}, {"decision": "decline"}


def _answers(calls, before):
    return [(call["answered"], call["result"], call["ran"]) for call in _stub(calls)[before:]
            if "answered" in call]


def test_1_full_access_turn_accepts_and_read_only_turn_declines(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)

    # forge work: Codex never asks and its automatic reviewer isn't used, and each request that
    # still arrives is accepted, so what it asks runs, and each acceptance is logged.
    built = repo.forge("work", "BOARD/PAGE")
    assert built.returncode == 0, built.stdout + built.stderr
    [start], [turn] = _sent(calls, "thread/start"), _sent(calls, "turn/start")
    for sent in (start, turn):
        assert sent["approvalPolicy"] == "never" and "approvalsReviewer" not in sent
    assert _answers(calls, 0) == [(KNOWN, ACCEPT, True), (UNKNOWN, ACCEPT, True)]
    assert (folder / "ran-stub-ask-1").exists() and (folder / "ran-stub-ask-2").exists()
    log = (repo.path / ".git" / "forge" / "work-BOARD-PAGE.log").read_text(encoding="utf-8")
    for method in (KNOWN, UNKNOWN):
        assert f"Accepted Codex's request {method}" in built.stdout
        assert f"Accepted Codex's request {method}" in log
    assert "Declined" not in built.stdout

    # forge ask, a read-only turn: the same requests are declined and nothing runs.
    for name in ("ran-stub-ask-1", "ran-stub-ask-2"):
        (folder / name).unlink()
    before = len(_stub(calls))
    asked = repo.forge("ask", "Where is the parser?", cwd=folder)
    assert asked.returncode == 0, asked.stdout + asked.stderr
    assert _sent(calls, "thread/start")[-1]["approvalPolicy"] == "never"
    assert _answers(calls, before) == [(KNOWN, DECLINE, False), (UNKNOWN, DECLINE, False)]
    assert not list(folder.glob("ran-*"))
    assert "Accepted" not in asked.stdout
