"""Next and board follow a part from a reviewed base through its merge."""
import json

import pytest

from test_close import env  # noqa: F401
from test_stack_start import configured, reviewed, start
from test_last_task_records_story_outcome import github_merge


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "upgraded-client"])
def test_5_next_and_board_show_stacked_parts(env, previous):
    # Audit: the real commands own the ordered status contract. START tests
    # admission, not these statuses. Reusing its setup needs no production seam.
    # A missing stack label or a premature merge instruction breaks this test.
    repo = configured(env, previous)
    reviewed(env)
    shown = repo.forge("next")
    assert "Next: forge task start STACK/B  # Claude builds it on top of STACK/A" in shown.stdout
    upper, _ = start(repo, "B")

    def status(sentence, board_status):
        shown = repo.forge("next")
        assert shown.returncode == 0, shown.stdout + shown.stderr
        assert sentence in shown.stdout
        machine = repo.forge("board", "--json")
        assert machine.returncode == 0, machine.stdout + machine.stderr
        parts = {part["id"]: part for entry in json.loads(machine.stdout)["dependency_maps"]
                 for part in entry["parts"]}
        assert parts["STACK/B"]["status"] == board_status
        return shown.stdout

    status("STACK/B is building on STACK/A.", "Building on Save work")
    env.commit(upper, "use.py", "B_VALUE = 1\n")
    env.open_pr("")
    closed = env.close("STACK/B")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    shown = status("STACK/B is built and waits for STACK/A to merge.",
                   "Waiting for Save work to merge")
    assert "Next: forge merge STACK/A" in shown
    assert "Next: forge merge STACK/B" not in shown
    github_merge(env, "task/STACK-A")
    merged = repo.forge("merge", "STACK/A")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "Next: forge close STACK/B" in shown.stdout
    assert "Next: forge merge STACK/B" not in shown.stdout
