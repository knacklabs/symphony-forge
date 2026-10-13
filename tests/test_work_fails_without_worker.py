"""forge work fails, with the reason and the next step, when it starts no worker round."""
import re

import pytest

from test_claude_worker_recovery import FIX, _client

STORY = "work-fails-without-worker"


# Claude ends without a model turn: with no result event, as when it holds the run on a prompt
# such as a hooks review, or with a successful result of no turns, empty and with no reply.
SHAPES = {"no-result": 'print("Review the changed hooks in /hooks.")',
          "zero-turns": 'print(json.dumps({"type": "result", "subtype": "success", '
                        '"is_error": False, "num_turns": 0, "result": ""}))'}


@pytest.mark.parametrize("shape", list(SHAPES))
@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
def test_1_claude_ending_without_a_turn_fails_forge_work(repo, gh, tmp_path, previous, shape):
    _, folder = _client(repo, gh, tmp_path, previous)
    stub = repo.bin / "claude"
    stub.write_text(stub.read_text("utf-8").replace("atexit.register(", "(").replace(
        'print("stub claude: built it")', SHAPES[shape]), encoding="utf-8")

    worked = repo.forge("work", FIX)

    assert worked.returncode != 0, worked.stdout
    problem = ("Claude ended without running a turn, so no worker ran; it may be waiting on a "
               "prompt such as a hooks review. Its log is ")
    assert re.fullmatch(re.escape(problem) + rf".*work-{FIX}\.log\.\n" + re.escape(
        f"Next: run claude once in {folder} and answer its prompt, then forge work {FIX}\n"),
        worked.stderr), worked.stderr
