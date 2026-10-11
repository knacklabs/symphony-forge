"""A review loop stop nobody answers in 30 minutes gets the repo's default choice: narrow the part
to its Done-when lines and start a follow-up fix for each open finding. forge.toml's
stop_default = "off" keeps waiting for the owner, who can reverse the default later."""
STORY = "stop-default-answer"

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_close_waits_for_review_loop_choice import stopped
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
    item, where = stopped(env)
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
    [branch] = follow_ups(env)
    assert (env.repo.git("log", "-1", "--format=%s", branch)
            == "Start the fix: Review finding left open by tidy-readme: Round 3 defect (src/a.py:1)")
    shown = env.repo.forge("next").stdout
    assert (f"The repo's default answered the review loop stop on The fix {item}: narrow it to its "
            f"Done-when lines; follow-up fixes own the open findings: {branch.removeprefix('fix/')}.") in shown
    board = env.repo.forge("board", "--json")
    assert "answered by the repo's default" in board.stdout

    # Closing again records nothing new; the owner can still reverse the default.
    assert env.close(item).returncode == 1
    assert len(follow_ups(env)) == 1
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
    assert "Ask the human" in env.repo.forge("next").stdout
    assert follow_ups(env) == []


def test_3_land_carries_on_and_the_worker_narrows(land, monkeypatch):
    where = _fix(land, "working", worked=True, changes={
        "app.py": "print('hello')\n", "other.py": "print('hello')\n", "show.py": "print('hello')\n"})
    land.reviews(*(blocked(finding("P1", "Greeting is missing", file=file))
                   for file in ("app.py", "other.py", "show.py")))
    assert "Ask the human" in _land(land).stderr
    workers = len(_workers(land))
    later(monkeypatch, 31)
    land.reviews(blocked(finding("P1", "Greeting is missing", file="show.py")), CLEAN)
    landed = _land(land)
    assert landed.returncode == 0, landed.stdout + landed.stderr
    assert f"{ITEM} is ready; a human merges" in landed.stdout
    assert len(_workers(land)) == workers + 1
    brief = _workers(land)[-1]["brief"]
    assert "the repo's default choice: narrow this part to its Done-when lines" in brief
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
