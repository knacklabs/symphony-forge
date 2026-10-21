"""The owner decides on review leftovers; workers keep repairing P0s until stuck.

Only Autoreview and the worker's model are faked. Real Forge commands own the
rounds, stops, recorded choices and Known issues on new and upgraded clients.
"""
import pytest

from test_close import CLEAN, blocked, env  # noqa: F401
from test_tools_session_hold import Session
from test_two_round_limit import client, known, note
from test_worker import calls, install_claude

STORY = "FORGE-ROUNDS-2"


@pytest.mark.parametrize("case", ["part", "fix", "adopted fix", "session"])
def test_1_at_the_round_limit_an_open_finding_below_p0_stops_for_the_owner(env, monkeypatch, case):
    # The former contract silently kept P1s as follow-ups at the limit. Now
    # only the owner's accept can turn these findings into follow-ups.
    client(env, case == "adopted fix")
    log = install_claude(env.repo)
    entry = note("P1", "Saving loses quantities")
    env.reviews(blocked(entry))
    item, where = env.start_task() if case == "part" else env.start_fix()
    if case == "part":
        first = env.close(item)
        assert first.returncode == 1, first.stdout + first.stderr
        assert "The review left serious findings open" in first.stderr
        assert "reached the round limit" not in first.stderr
        env.commit(where, "app.py", "print('save quantities')\n", "Repair saving")
    stopped = env.close(item)
    round_number = 2 if case == "part" else 1
    line = (f"Review round {round_number} of {item} reached the round limit with open findings, "
            "so Forge stopped.")
    step = f'forge close {item} --resolve <more|split|accept> --reason "<human\'s choice>"'
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    for text in (line, "One more round, split or accept?", entry["title"], step):
        assert text in stopped.stderr
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "One more round, split or accept?" in shown.stdout and step in shown.stdout
    if case == "part":
        assert ("Forge asks the owner about each finding below P0 that is still open at the "
                "round limit.") in " ".join(env.prompt().split())
        held = env.repo.forge("work", item)
        assert held.returncode == 1, held.stdout + held.stderr
        assert line in held.stderr and step in held.stderr
        assert calls(log) == []
    elif case == "fix":
        held = env.repo.forge("land", item)
        assert held.returncode == 3, held.stdout + held.stderr
        assert "One more round, split or accept?" in held.stdout + held.stderr
        assert entry["title"] in held.stdout + held.stderr
        assert calls(log) == []
    elif case == "session":
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
        host = Session(env.repo, env.tmp / "host", "claude-session")
        try:
            held = host.forge("work", item)
            assert held.returncode == 1, held.stdout + held.stderr
            assert line in held.stderr and step in held.stderr
            assert "--round" not in held.stdout
            assert calls(log) == []
        finally:
            host.close()
    if case == "adopted fix":
        chosen = env.close(item, "--resolve", "more", "--reason", "Repair the quantity loss")
        assert chosen.returncode == 0, chosen.stdout + chosen.stderr
        assert "Next: forge work tidy-readme" in chosen.stdout
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        assert "The owner chose more" in calls(log)[-1]["brief"]
        env.commit(where, "app.py", "print('quantities kept')\n", "Keep quantities")
        env.reviews(CLEAN)
        ready = env.close(item)
    else:
        ready = env.close(item, "--resolve", "accept", "--reason", "Keep the current quantity flow")
        issues = known(env, where)
        assert issues[entry["title"]]["kept"] == "follow-up"
        assert issues[entry["title"]]["reason"].startswith("Human accepted the remaining finding:")
    assert ready.returncode == 0 and "Ready" in ready.stdout, ready.stdout + ready.stderr
    assert len(env.review_calls()) == (2 if case in ("part", "adopted fix") else 1)


@pytest.mark.parametrize("case", ["fix", "part", "adopted fix", "other p0"])
def test_2_an_open_p0_goes_back_to_the_worker_until_it_is_stuck_two_rounds(env, case):
    # A P0 used to stop at the review limit. It now goes back to the worker,
    # and only leaving the same P0 in two worker rounds asks for a choice.
    client(env, case == "adopted fix")
    log = install_claude(env.repo)
    item, where = env.start_task() if case == "part" else env.start_fix()
    first_work = env.repo.forge("work", item)
    assert first_work.returncode == 0, first_work.stdout + first_work.stderr
    first_p0 = note("P0", "Saving deletes the basket")
    env.reviews(blocked(first_p0))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert "The review left serious findings open" in first.stderr
    assert "Forge stopped" not in first.stderr and "--resolve <more" not in first.stderr
    second_work = env.repo.forge("work", item)
    assert second_work.returncode == 0, second_work.stdout + second_work.stderr
    assert "An open P0 never stops for the owner: fix it in this round." in calls(log)[-1]["brief"]
    env.commit(where, "app.py", "print('repair saving')\n", "Repair saving")
    second_p0 = note("P0", "Reopening deletes the basket") if case == "other p0" else first_p0
    env.reviews(blocked(second_p0))
    second = env.close(item)
    assert second.returncode == 1, second.stdout + second.stderr
    assert "The review left serious findings open" in second.stderr
    assert "Forge stopped" not in second.stderr and "--resolve <more" not in second.stderr
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "One more round, split or accept?" not in shown.stdout
    third_work = env.repo.forge("work", item)
    if case == "other p0":
        assert third_work.returncode == 0, third_work.stdout + third_work.stderr
        assert len(calls(log)) == 3
    else:
        assert third_work.returncode == 1, third_work.stdout + third_work.stderr
        assert "The worker can't get past the same problem" in third_work.stderr
        assert ("Two rounds in a row left the open P0 saving deletes the basket in app.py."
                in third_work.stderr)
        assert third_work.stderr.splitlines()[-1] == (
            f'Next: forge close {item} --resolve <switch|same|narrow|split> '
            '--reason "<human\'s choice>"')
        assert len(calls(log)) == 2
        if case == "fix":
            chosen = env.close(item, "--resolve", "same", "--reason", "One more try")
            assert chosen.returncode == 0, chosen.stdout + chosen.stderr
            resumed = env.repo.forge("work", item)
            assert resumed.returncode == 0, resumed.stdout + resumed.stderr
            assert "The owner chose same: One more try" in calls(log)[-1]["brief"]
            assert len(calls(log)) == 3
    assert len(env.review_calls()) == 2
