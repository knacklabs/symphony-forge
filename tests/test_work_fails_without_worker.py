"""forge work fails, with the reason and the next step, when it starts no worker round."""
import re

import pytest

from test_claude_worker_recovery import FIX, _client

STORY = "work-fails-without-worker"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
def test_1_claude_ending_without_a_turn_fails_forge_work(repo, gh, tmp_path, previous):
    _, folder = _client(repo, gh, tmp_path, previous)
    # Claude ends at once without a turn, as when it holds the run on a prompt such as hooks approval.
    stub = repo.bin / "claude"
    stub.write_text(stub.read_text("utf-8").replace(
        "atexit.register(", "(").replace(
        'print("stub claude: built it")', 'print("Review the changed hooks in /hooks.")'),
        encoding="utf-8")

    worked = repo.forge("work", FIX)

    assert worked.returncode != 0, worked.stdout
    problem = ("Claude ended without running a turn, so no worker ran; it may be waiting on a "
               "prompt such as a hooks review. Its log is ")
    assert re.fullmatch(re.escape(problem) + rf".*work-{FIX}\.log\.\n" + re.escape(
        f"Next: run claude once in {folder} and answer its prompt, then forge work {FIX}\n"),
        worked.stderr), worked.stderr
