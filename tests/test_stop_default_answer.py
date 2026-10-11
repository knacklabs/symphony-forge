"""A review loop stop nobody answers in 30 minutes gets the repo's default choice: narrow the part
to its Done-when lines and start a follow-up fix for each open finding. forge.toml's
stop_default = "off" keeps waiting for the owner, who can reverse the default later."""
STORY = "stop-default-answer"

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_close_waits_for_review_loop_choice import stopped
from test_hotspot_stop import seed, rounds
from test_land import ITEM, _fix, _land, _workers, land  # noqa: F401
from test_setup import _fresh_client

GUIDANCE = ("When nobody answers a review-loop stop in 30 minutes, close or land records the repo's "
            "default choice")


def later(monkeypatch, minutes):
    monkeypatch.setenv("FORGE_NOW", (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat())


def follow_ups(env):
    return [b.strip() for b in env.repo.git("branch", "--list", "fix/*", "--format=%(refname:short)")
            .splitlines() if b.strip() != "fix/tidy-readme"]


def test_1_unanswered_stop_gets_the_default_after_30_minutes(env, monkeypatch):
    seed(env, "src/a.py")
    item, where = env.start_fix()
    rounds(env, item, where, ["src/a.py"] * 2)
    env.commit(where, "app.py", "print(3)\n")
    env.reviews(blocked(finding("P1", "Round 3 defect", "src/a.py"),
                        finding("P2", "Follow-up: advice", "src/a.py"),
                        finding("P3", "Polish advice", "src/a.py")))
    assert "Ask the human" in env.close(item).stderr
    before = len(env.review_calls())
    later(monkeypatch, 20)
    waiting = env.close(item)
    assert waiting.returncode == 1 and "Ask the human" in waiting.stderr
    assert follow_ups(env) == []

    later(monkeypatch, 31)
    shown = env.repo.forge("next").stdout
    assert (f"Nobody answered the review loop stop on The fix {item} in 30 minutes, so close "
            "records the repo's default choice: narrow.") in shown
    assert f"Next: forge close {item}\n" in shown
    answered = env.close(item)
    assert answered.returncode == 1, answered.stdout + answered.stderr
    assert ("Nobody answered the review loop stop in 30 minutes, so Forge recorded the repo's "
            "default choice: narrow the part to its Done-when lines.") in answered.stdout
    assert "The review left serious findings open" in answered.stderr
    assert len(env.review_calls()) == before
    branches = follow_ups(env)
    assert len(branches) == 3
    messages = [env.repo.git("log", "-1", "--format=%s", b) for b in branches]
    assert any("Follow-up: advice (src/a.py:1)" in message for message in messages)
    assert any("Polish advice (src/a.py:1)" in message for message in messages)
    branch = next(b for b in branches if "Round 3 defect" in
                  env.repo.git("log", "-1", "--format=%s", b))
    assert (env.repo.git("log", "-1", "--format=%s", branch)
            == "Start the fix: Review finding left open by tidy-readme: Round 3 defect (src/a.py:1): "
               "Evidence for: Round 3 defect")
    shown = env.repo.forge("next").stdout
    assert (f"The repo's default answered the review loop stop on The fix {item}: narrow it to its "
            "Done-when lines; follow-up fixes own the open findings:") in shown
    board = env.repo.forge("board", "--json")
    assert board.returncode == 0 and "fixing" in board.stdout

    # Closing again records nothing new; the owner can still reverse the default.
    assert env.close(item).returncode == 1
    assert len(follow_ups(env)) == 3
    reversed_ = env.close(item, "--resolve", "accept", "--reason", "The owner accepts these findings")
    assert reversed_.returncode == 0, reversed_.stdout + reversed_.stderr
    assert "Ready:" in reversed_.stdout
    assert "default" not in env.repo.forge("next").stdout


def test_2_off_keeps_waiting_for_the_owner(env, monkeypatch):
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8") + 'stop_default = "off"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = stopped(env)
    later(monkeypatch, 600)
    waiting = env.close(item)
    assert waiting.returncode == 1 and "Ask the human" in waiting.stderr
    waiting = env.repo.forge("land", item)
    assert waiting.returncode == 1 and "Ask the human" in waiting.stderr
    assert "Ask the human" in env.repo.forge("next").stdout
    assert follow_ups(env) == []


@pytest.mark.parametrize("entry", ["running", "same-file", "stopped"])
def test_3_land_carries_on_and_the_worker_narrows(land, entry):
    if entry == "stopped":
        item, where = stopped(land)
        land.reviews(CLEAN)
    else:
        if entry == "same-file":
            seed(land, "app.py")
        item = ITEM
        where = _fix(land, "working", worked=True, changes={
            "app.py": "print('hello')\n", "other.py": "print('hello')\n", "show.py": "print('hello')\n"})
        paths = ["app.py"] * 3 if entry == "same-file" else ["app.py", "other.py", "show.py"]
        land.reviews(*(blocked(finding("P1", "Greeting is missing", file=file))
                       for file in paths), CLEAN)
    # Advance only the clock; one real land invocation must wait and resume itself.
    # Rerunning land after moving the clock missed the unattended failure.
    shim = land.repo.bin / "forge"
    clock = """import os, time
from datetime import datetime, timedelta, timezone
def advance(seconds):
    current = datetime.fromisoformat(os.environ.get('FORGE_NOW') or datetime.now(timezone.utc).isoformat())
    os.environ['FORGE_NOW'] = (current + timedelta(seconds=seconds)).isoformat()
time.sleep = advance
"""
    shim.write_text(shim.read_text().replace("from forge.cli import main", clock + "from forge.cli import main"))
    landed = _land(land, item)
    assert landed.returncode == 0, landed.stdout + landed.stderr
    assert f"{item} is ready; a human merges" in landed.stdout
    assert "Nobody answered the review loop stop in 30 minutes" in landed.stdout
    brief = _workers(land)[-1]["brief"]
    assert "the repo's default choice: narrow this part to its Done-when lines" in brief
    # A fresh brief carries the fix-round rules; they must not contradict the narrowing.
    assert ("follow-up fixes own these findings: then\nremove what goes beyond" in brief) == (
        "Close stopped on these." in brief)
    shown = land.repo.forge("next").stdout
    assert f"The repo's default answered the review loop stop on The fix {item}" in shown
    assert where.exists()


def test_4_new_and_existing_clients_get_the_default(repo, gh, tmp_path):
    for previous in (False, True):
        if previous:
            shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                            repo.path, dirs_exist_ok=True)
            repo.git("checkout", "-q", "-b", "fix/stop-guide")
            version = repo.forge("--version").stdout.split()[-1]
            config = (repo.path / "forge.toml").read_text()
            repo.write("forge.toml", config.replace('version = "v1.2.2"', f'version = "{version}"'))
            client, result = repo.path, repo.forge("sync")
        else:
            client, result = _fresh_client(repo, gh, tmp_path)
        assert result.returncode == 0, result.stderr
        assert "stop_default" not in (client / "forge.toml").read_text()  # on unless set off
        for host in (".codex", ".claude"):
            text = " ".join((client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8").split())
            assert GUIDANCE in text


def test_5_owner_choice_after_the_default_reaches_the_worker(land, monkeypatch):
    item, _ = stopped(land)
    later(monkeypatch, 31)
    assert "repo's default" in land.close(item).stdout
    reason = "The owner splits the greeting into its own fix"
    assert land.close(item, "--resolve", "split", "--reason", reason).returncode == 0
    worked = land.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = _workers(land)[-1]["brief"]
    assert f"The owner replaced the repo's default choice with split: {reason}." in brief
    assert "Nobody answered the review loop stop" not in brief
