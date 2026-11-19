"""Choices precede work at the command boundary.

Test-audit: a late size hook and routine advice before a pending question are
the credible regressions. Existing allowance and board tests do not cover
intake or next's ordering. Cross-machine pickup and amendment have separate
lifecycle risks: an unpublished stop and a guard that blocks a narrower result.
The real commands protect those contracts without a production test seam.
"""
import pytest

from conftest import Repo

from test_start_sorts_ideas import intake, land, env, _offer, _back, _fix, _signed_off, _checkout  # noqa: F401
from test_board_status_and_times import client, _fix as make_fix, _records  # noqa: F401
from test_story import setup, ready, new_story, DOC
from test_readloop_gates import dispose_all
from test_worker import calls, install_claude

STORY = "FIX-OWNER-CHOICES-ON-TIME"


@pytest.mark.parametrize("file_count", [5, 6])
def test_1_intake_requests_size_allowance_before_work(intake, file_count):
    repo, top, *_ = intake
    with (top / ".gitattributes").open("a", encoding="utf-8") as attributes:
        attributes.write("\nsnapshots/*.json linguist-generated\n")
    _signed_off(intake)
    offered = _offer(intake, "Repair labels across six modules")
    assert "For a fix, list each predicted code file as File: <repo-relative path>." in offered["prompt"]
    assert ("Exclude tests, Markdown, generated files (including lockfiles), and files that forge sync writes."
            in offered["prompt"])
    assert "Forge asks for the size allowance before work starts." in offered["prompt"]
    assert ("If one repair needs more than five code files, keep Lane: fix and list them all;"
            in offered["prompt"])
    reply = _fix("Repair labels across six modules") + "\n" + "\n".join(
        f"File: module{n}.py" for n in range(file_count))
    reply += "\nFile: src/test_labels.py\nFile: README.md\nFile: module0.py"
    reply += ("\nFile: snapshots/generated.json\nFile: pnpm-lock.yaml"
              "\nFile: .github/workflows/forge.yml\nFile: .codex/hooks.json"
              "\nFile: .factory/fixes/generated.json")
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
    assert 'Next: cd ' in blocked.stderr and ' && forge fix allow-large "<reason>"' in blocked.stderr
    assert tree.as_posix() in blocked.stderr.replace("\\", "/")
    allowed = repo.forge("fix", "allow-large", "The owner permits this six-file repair", cwd=tree)
    assert allowed.returncode == 0, allowed.stderr
    shown = repo.forge("next", cwd=top)
    assert "Allow this fix to change" not in shown.stdout


def test_2_next_puts_all_pending_choices_before_routine_steps(client):
    make_fix(client, slug="a-routine")
    question = "Allow six code files for this repair?"
    make_fix(client, slug="z-choice", stop={"question": question, "at": "2026-10-09T11:05:00+00:00",
                                           "wait_id": "size-wait"})
    make_fix(client, slug="y-review", stop={"round": 2, "at": "2026-10-01T11:46:00+00:00",
                                           "wait_id": "review-wait"})
    _records(client, "events.jsonl", [
        {"id": "size-wait", "item": "z-choice", "event": "owner wait start", "reason": "stuck",
         "at": "2026-10-09T11:05:00+00:00"},
        {"id": "review-wait", "item": "y-review", "event": "owner wait start", "reason": "review loop",
         "at": "2026-10-09T11:46:00+00:00"},
        {"id": "unrelated", "item": "y-review", "event": "owner wait start", "reason": "merge conflict",
         "at": "2026-10-09T11:59:00+00:00"},
    ])
    result = client.forge("next")
    assert result.returncode == 0, result.stderr
    assert result.stdout.index(question) < result.stdout.index("a-routine")
    assert result.stdout.index("One more round, split or accept?") < result.stdout.index("a-routine")
    review_question = (
        "Ask the human to choose one more round, split or accept the remaining findings, in these words:\n"
        "Readers see the correct state: The board agrees\n"
        "One more round, split or accept?\n"
        "- One more round: repair these cases in its Done when and run one more round.\n"
        "- Split: move these cases into a new story or fix of their own; this one goes on without them.\n"
        "- Accept: the 0 findings listed become follow-ups in Known issues with your reason; close then goes on "
        "to the checks, and merging is still a separate step.")
    assert f"Waited 55 minutes.\nForge stopped The fix z-choice. Ask the human:\n{question}" in result.stdout
    assert ("Waited 14 minutes.\nClose stopped The fix y-review: its review reached the round limit with open findings.\n"
            + review_question) in result.stdout
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
    assert "If the list exceeds five and no recorded allowance covers it, ask in your handoff:" in brief
    assert "Question: Allow this fix to change these code files: <files>?" in brief
    assert "Stop before edits or tests." in brief
    assert "Markdown, generated files (including lockfiles), and files that `forge sync` writes." in brief
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
    _records(repo, "events.jsonl", [
        {"id": "approval", "item": "SHOP", "event": "owner wait start", "reason": "approval",
         "at": "2026-10-09T11:20:00+00:00"},
        {"id": "read", "item": "WAIT", "event": "owner wait start", "reason": "read",
         "at": "2026-10-09T11:46:00+00:00"},
        {"id": "unrelated", "item": "WAIT", "event": "owner wait start", "reason": "merge conflict",
         "at": "2026-10-09T11:59:00+00:00"},
    ])
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T12:00:00+00:00")
    result = repo.forge("next")
    assert result.returncode == 0, result.stderr
    for question in ("Approve this plan?", "One more round, split or accept?"):
        assert result.stdout.index(question) < result.stdout.index("Step ")
    approval = result.stdout.split("Waited 40 minutes.\n", 1)[1].split("\nWaited ", 1)[0]
    assert "Approve this plan?" in approval
    exact_question = stopped.stderr.split("\nNext: ", 1)[0]
    assert f"Waited 14 minutes.\n{exact_question}" in result.stdout


def _large_intake(intake):
    repo, top, *_ = intake
    _signed_off(intake)
    offered = _offer(intake, "Repair labels across six modules")
    reply = _fix("Repair labels across six modules") + "\n" + "\n".join(
        f"File: module{n}.py" for n in range(6))
    result = _back(intake, offered, reply)
    assert result.returncode == 0, result.stdout + result.stderr
    return repo, top, "repair-labels-across-six-modules"


def test_5_size_stop_holds_on_first_pickup_on_another_machine(intake, tmp_path):
    repo, top, item = _large_intake(intake)
    second = tmp_path / "second-machine"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin", cwd=top), str(second))
    other = Repo(second, repo.bin)
    question = "Allow this fix to change 6 code files: " + ", ".join(f"module{n}.py" for n in range(6)) + "?"
    blocked = other.forge("work", item)
    assert blocked.returncode != 0 and question in blocked.stderr
    tree = _checkout(other, second, f"fix/{item}")
    assert 'Next: cd ' in blocked.stderr and ' && forge fix allow-large "<reason>"' in blocked.stderr
    assert tree.as_posix() in blocked.stderr.replace("\\", "/")


def test_6_owner_can_narrow_a_size_stopped_fix_without_an_allowance(intake):
    repo, top, item = _large_intake(intake)
    narrowed = repo.forge("fix", "amend", item, "--done", "Only the welcome label changes",
                          "--because", "The owner chose a smaller repair", cwd=top)
    assert narrowed.returncode == 0, narrowed.stdout + narrowed.stderr
    assert f"Next: forge work {item}" in narrowed.stdout
    log = install_claude(repo)
    resumed = repo.forge("work", item, cwd=top)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    brief = calls(log)[-1]["brief"]
    assert "Done when: Only the welcome label changes" in brief
    assert "Recorded allowance: No recorded allowance" in brief
