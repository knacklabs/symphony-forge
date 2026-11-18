"""Choices precede work at the command boundary.

Test-audit: a late size hook and routine advice before a pending question are
the credible regressions. Existing allowance and board tests do not cover
intake or next's ordering. No production test seam is needed.
"""
import pytest

from test_start_sorts_ideas import intake, land, env, _offer, _back, _fix, _signed_off, _checkout  # noqa: F401
from test_board_status_and_times import client, _fix as make_fix, _records  # noqa: F401
from test_story import setup, ready, new_story, DOC
from test_readloop_gates import dispose_all
from test_worker import calls, install_claude

STORY = "FIX-OWNER-CHOICES-ON-TIME"


@pytest.mark.parametrize("file_count", [5, 6])
def test_1_intake_requests_size_allowance_before_work(intake, file_count):
    repo, top, *_ = intake
    _signed_off(intake)
    offered = _offer(intake, "Repair labels across six modules")
    reply = _fix("Repair labels across six modules") + "\n" + "\n".join(
        f"File: module{n}.py" for n in range(file_count))
    reply += "\nFile: src/test_labels.py\nFile: README.md\nFile: module0.py"
    started = _back(intake, offered, reply)
    assert started.returncode == 0, started.stdout + started.stderr
    if file_count == 5:
        assert "Next: forge land " in started.stdout
        assert "forge fix allow-large" not in started.stdout
        return
    assert 'forge fix allow-large "<reason>"' in started.stdout
    assert all(f"module{n}.py" in started.stdout for n in range(6))
    assert "Next: forge land " not in started.stdout
    item = "repair-labels-across-six-modules"
    blocked = repo.forge("work", item, cwd=top)
    assert blocked.returncode != 0 and "Allow this fix" in blocked.stderr
    tree = _checkout(repo, top, f"fix/{item}")
    allowed = repo.forge("fix", "allow-large", "The owner permits this six-file repair", cwd=tree)
    assert allowed.returncode == 0, allowed.stderr
    shown = repo.forge("next", cwd=top)
    assert "Allow this fix to change" not in shown.stdout


def test_2_next_puts_all_pending_choices_before_routine_steps(client):
    make_fix(client, slug="a-routine")
    question = "Allow six code files for this repair?"
    make_fix(client, slug="z-choice", stop={"question": question, "at": "2026-10-09T11:05:00+00:00",
                                           "wait_id": "size-wait"})
    make_fix(client, slug="y-review", stop={"round": 2, "at": "2026-10-09T11:46:00+00:00",
                                           "wait_id": "review-wait"})
    _records(client, "events.jsonl", [
        {"id": "size-wait", "item": "z-choice", "event": "owner wait start", "reason": "stuck",
         "at": "2026-10-09T11:05:00+00:00"},
        {"id": "review-wait", "item": "y-review", "event": "owner wait start", "reason": "review loop",
         "at": "2026-10-09T11:46:00+00:00"},
    ])
    result = client.forge("next")
    assert result.returncode == 0, result.stderr
    assert result.stdout.index(question) < result.stdout.index("a-routine")
    assert result.stdout.index("One more round, split or accept?") < result.stdout.index("a-routine")
    assert "55 minutes" in result.stdout and "14 minutes" in result.stdout
    assert result.stdout.count(question) == 1


def test_3_first_round_brief_asks_for_size_before_edits(env, monkeypatch):
    item, _ = env.start_fix()
    log = install_claude(env.repo)
    question = "Question: Allow this fix to change these code files: a.py, b.py, c.py, d.py, e.py, f.py?"
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T11:05:00+00:00")
    monkeypatch.setenv("STUB_CLAUDE_RESULT", "\n\n" + question)
    result = env.repo.forge("work", item)
    assert result.returncode == 0, result.stdout + result.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert "Before the first fix round's code edits, list the code files your plan needs." in brief
    assert "Do not wait for a commit refusal." in brief
    assert 'forge fix allow-large "<reason>"' in brief
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T12:00:00+00:00")
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert shown.stdout.index(question) < shown.stdout.index("Step ")
    assert "Waited 55 minutes." in shown.stdout


def test_4_next_surfaces_approval_and_read_resolution_before_routine_advice(repo, monkeypatch):
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T11:05:00+00:00")
    setup(repo, keys=("SHOP", "WAIT"))
    ready(repo, "SHOP")
    waiting = new_story(repo, "WAIT")
    (waiting / "plans/WAIT.md").write_text(DOC, encoding="utf-8")
    (repo.bin / "claude-says.md").write_text(
        "1. Required basket recovery is missing.\n   Case: normal use - A saved basket loses its contents.\n"
        "   Gain 4, Work 1, Harm 3\n", encoding="utf-8")
    assert repo.forge("read", "WAIT").returncode == 0
    dispose_all(waiting / "plans/WAIT.read.md")
    (repo.bin / "claude-says.md").write_text(
        "2. Checkout discards the saved basket.\n   Case: normal use - Checkout loses all saved items.\n"
        "   Gain 4, Work 1, Harm 3\n", encoding="utf-8")
    stopped = repo.forge("read", "WAIT")
    assert stopped.returncode != 0 and "One more round, split or accept?" in stopped.stderr
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T12:00:00+00:00")
    result = repo.forge("next")
    assert result.returncode == 0, result.stderr
    for question in ("Approve this plan?", "One more round, split or accept?"):
        assert result.stdout.index(question) < result.stdout.index("Step ")
    assert result.stdout.count("Waited 55 minutes.") == 2
