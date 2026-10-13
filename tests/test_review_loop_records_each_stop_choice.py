"""Each new review-loop stop needs its own owner decision.

Test-audit: earlier tests unlock only the first stop. An old choice retained on
the next stop would either bypass the wait or refuse its new decision. Exercise
real close, next and board commands; fake only GitHub and the external reviewer.
The earlier command fixture records choices before upgrading, covering both
old stop formats that an upgrade before the first choice cannot exercise.
"""
import shutil
import sys

import pytest

from conftest import FORGE_SHIM, ROOT, _install
from test_close import blocked, env, finding  # noqa: F401
from test_close_holds_after_three_blocked_reviews import PATHS, client_item
from test_item_time_history import row

STORY = "second-stop-choice"


@pytest.mark.parametrize("legacy", [False, True], ids=["current-choice", "pre-upgrade-choice"])
@pytest.mark.parametrize("previous,same_file,first,second", [
    (False, True, "narrow", "split"),
    (True, True, "split", "narrow"),
    (False, True, "accept", "accept"),
    (True, False, "narrow", "accept"),
    (False, False, "split", "split"),
    (True, False, "accept", "narrow"),
])
def test_1_each_new_stop_waits_for_and_records_its_own_choice(
        env, tmp_path, previous, same_file, first, second, legacy):
    item, where = client_item(env, tmp_path, previous)
    # With the default on, land waits out the stop; this checks the owner's own choices.
    env.commit(where, "forge.toml", 'stop_default = "off"\n' + (where / "forge.toml").read_text("utf-8"))
    if legacy:
        # The actual earlier close writes the choice; no synthetic stop record.
        old = tmp_path / "earlier-close"
        shutil.copytree(ROOT / "src/forge", old / "src/forge",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for host in (".codex", ".claude"):
            shutil.copytree(ROOT / host / "skills", old / host / "skills")
        shutil.copyfile(ROOT / "tests/fixtures/close-before-choice-round.txt", old / "src/forge/close.py")
        current = (env.repo.bin / "forge").read_text("utf-8")
        _install(env.repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=(old / "src").as_posix()))
    paths = [PATHS[0]] * 3 if same_file else PATHS
    for cycle, choice in enumerate((first, second)):
        # Keep the any-file case from hitting the same-file rule across cycles.
        if cycle and not same_file:
            paths = ["README.md", ".codex/skills/forge/SKILL.md", ".claude/skills/forge/SKILL.md"]
        for offset, path in enumerate(paths, 1):
            number = cycle * 3 + offset
            env.commit(where, "app.py", f"print('round {number}')\n")
            env.reviews(blocked(finding("P1", f"New defect {number}", path)))
            result = env.close(item)
            assert result.returncode == 1, result.stdout + result.stderr
            assert len(env.review_calls()) == number
            if offset < 3 or not same_file:
                assert "The review left serious findings open:" in result.stderr
        if not same_file:
            env.commit(where, "app.py", f"print('attempt after cycle {cycle}')\n")
            result = env.close(item)
        assert "Ask the human to narrow the part" in result.stderr
        assert len(env.review_calls()) == (cycle + 1) * 3
        # The first stop's wait is test_close_holds_after_three_blocked_reviews' job; this
        # test checks that the second stop waits again despite the first choice.
        if cycle:
            assert row(env.repo, item)["status"] == "Needs your decision"
            next_step = env.repo.forge("next")
            assert next_step.returncode == 0, next_step.stderr
            assert f"forge close {item} --resolve <narrow|split|accept>" in next_step.stdout
            for command in ("close", "land"):
                waiting = env.repo.forge(command, item)
                assert waiting.returncode == 1, waiting.stdout + waiting.stderr
                assert "Ask the human to narrow the part" in waiting.stderr
                assert len(env.review_calls()) == (cycle + 1) * 3
        reason = f"The owner chose {choice} for stop {cycle + 1}"
        chosen = env.close(item, "--resolve", choice, "--reason", reason)
        assert chosen.returncode == 0, chosen.stdout + chosen.stderr
        assert "Recorded the human's choice" in chosen.stdout
        if cycle:
            assert row(env.repo, item)["status"] != "Needs your decision"
            duplicate = env.close(item, "--resolve", choice, "--reason", reason)
            assert duplicate.returncode == 1
            assert "Record the human's choice only on a stopped review loop" in duplicate.stderr
        if legacy and not cycle:
            _install(env.repo.bin, "forge", current)
