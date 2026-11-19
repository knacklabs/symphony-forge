"""One standing permission buys one functional repair round through close."""
import pytest

from test_close import CLEAN, STORY_DOC, blocked, env  # noqa: F401
from test_land import land, _workers  # noqa: F401
from test_two_round_limit import client, note
from test_worker import calls, install_claude

STORY = "FIX-STANDING-OWNER-POLICY"


@pytest.mark.parametrize("case", ["enabled", "task", "p0", "off", "false", "other", "mixed",
                                  "unchanged", "indented"])
def test_1_standing_policy_grants_only_one_functional_round(env, case):
    # The owner can pre-authorize one functional repair, not other choices.
    # Existing limit tests cover only explicit choices. No production seam is needed.
    client(env, False)
    if case != "off":
        path = env.repo.path / "forge.toml"
        value = "false" if case == "false" else "true"
        env.commit(env.repo.path, "forge.toml", f"auto_more_round = {value}\n" + path.read_text("utf-8"),
                   "Authorize one functional round")
        env.repo.git("push", "-q", "origin", "main")
    entry = note("P0" if case == "p0" else "P1", "Saving loses quantities")
    entry["body"] += "\n  Raise: Functional" if case == "indented" else "\nRaise: Functional"
    other = note("P1", "Missing proof")
    other["body"] += "\nRaise: Standard"
    findings = [other] if case == "other" else [entry, other] if case == "mixed" else [entry]
    if case == "p0":
        critical = note("P0", "Saving deletes the basket")
        critical["body"] += "\nRaise: Functional"
        entry = note("P1", "Saving loses quantities")
        entry["body"] += "\nRaise: Functional"
        findings = [critical, entry]
    env.reviews(blocked(*findings))
    item, where = env.start_approved_task(STORY_DOC) if case == "task" else env.start_fix()
    if case == "unchanged":
        log = install_claude(env.repo)
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        session = calls(log)[-1]["session_id"]
    if case == "task":
        early = env.close(item)
        assert "Applied the owner's policy" not in early.stdout + early.stderr
        env.commit(where, "app.py", "print('repair saving')\n", "Repair saving")
    first = env.close(item)
    output = first.stdout + first.stderr
    assert first.returncode == 1, output
    if case in ("off", "false", "other", "mixed"):
        assert "One more round, split or accept?" in output
        assert "Applied the owner's policy" not in output
        return
    if case == "p0":
        assert "Applied the owner's policy" not in output
        env.commit(where, "app.py", "print('repair critical saving')\n", "Repair critical saving")
        entry = note("P1", "Saving loses quantities")
        entry["body"] += "\nRaise: Functional"
        env.reviews(blocked(entry))
        first = env.close(item)
        output = first.stdout + first.stderr
    assert "Applied the owner's policy: one more round for functional findings." in output
    assert "One more round, split or accept?" not in output
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert f"forge work {item}" in shown.stdout
    again = env.close(item)
    assert "One more round, split or accept?" not in again.stdout + again.stderr
    assert "Applied the owner's policy" not in again.stdout + again.stderr
    if case == "unchanged":
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        resumed = calls(log)[-1]
        assert resumed["options"]["resume"] == session
    else:
        env.commit(where, "app.py", "print('repair quantities')\n", "Repair quantities")
    second = env.close(item)
    assert "One more round, split or accept?" in second.stdout + second.stderr
    assert "Applied the owner's policy" not in second.stdout + second.stderr
    if case == "unchanged":
        assert "The owner's policy authorized this repair round. Continue with the open functional findings." in resumed["brief"]


@pytest.mark.parametrize("queued", [False, True])
def test_2_land_runs_the_policy_round_after_its_normal_repair(land, monkeypatch, queued):
    # Land owns dispatch and queue limits, which a close-only test cannot reach.
    # A grant must dispatch once after the ordinary repair. No new test seam is needed.
    env = land
    path = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", "auto_more_round = true\n" + path.read_text("utf-8"))
    env.repo.git("push", "-q", "origin", "main")
    entry = note("P1", "Saving loses quantities")
    entry["body"] += "\nRaise: Functional"
    item, where = env.start_approved_task(STORY_DOC)
    if queued:
        env.reviews(blocked(entry))
        early = env.close(item)
        assert "The review left serious findings open" in early.stderr
        env.commit(where, "app.py", "print('first repair')\n", "First repair")
        monkeypatch.setenv("FORGE_LAND_QUEUED", "1")
        monkeypatch.setenv("FORGE_LAND_ROUNDS", "1")
    env.reviews(blocked(entry), CLEAN) if queued else env.reviews(blocked(entry), blocked(entry), CLEAN)
    done = env.repo.forge("land", item)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Applied the owner's policy: one more round for functional findings." in done.stdout
    assert len(_workers(env)) == (1 if queued else 2)
    assert "The owner's policy authorized this repair round." in _workers(env)[-1]["brief"]
    assert "is ready; a human merges" in done.stdout
