"""One standing permission buys one functional repair round through close."""
import pytest

from test_close import STORY_DOC, blocked, env  # noqa: F401
from test_two_round_limit import client, note

STORY = "FIX-STANDING-OWNER-POLICY"


@pytest.mark.parametrize("case", ["enabled", "task", "p0", "off", "false", "other", "mixed"])
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
    entry["body"] += "\nRaise: Functional"
    other = note("P1", "Missing proof")
    other["body"] += "\nRaise: Standard"
    findings = [other] if case == "other" else [entry, other] if case == "mixed" else [entry]
    env.reviews(blocked(*findings))
    item, where = env.start_approved_task(STORY_DOC) if case == "task" else env.start_fix()
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
    assert "Applied the owner's policy: one more round for functional findings." in output
    assert "One more round, split or accept?" not in output
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert f"forge work {item}" in shown.stdout
    again = env.close(item)
    assert "One more round, split or accept?" not in again.stdout + again.stderr
    assert "Applied the owner's policy" not in again.stdout + again.stderr
    if case == "p0":
        return  # P0's separate stuck-worker stop retains the existing owner choice.
    env.commit(where, "app.py", "print('repair quantities')\n", "Repair quantities")
    second = env.close(item)
    assert "One more round, split or accept?" in second.stdout + second.stderr
    assert "Applied the owner's policy" not in second.stdout + second.stderr
