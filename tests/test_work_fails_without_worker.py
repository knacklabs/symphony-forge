"""forge work fails, with the reason and the next step, when it starts no worker round."""
import re

import pytest

from test_claude_worker_recovery import FIX, _client

STORY = "work-fails-without-worker"


# Claude ends without a model turn: with no result event, as when it holds the run on a prompt
# such as a hooks review, or with a successful result of no turns, empty and with no reply.
SHAPES = {"no-result": '    return',
          "zero-turns": '    yield ResultMessage(session_id=session, num_turns=0, result="")',
          "null-result": '    yield ResultMessage(session_id=session, num_turns=0)',
          "empty-answer": '    yield ResultMessage(session_id=session, result="")',
          "null-answer": '    yield ResultMessage(session_id=session)',
          "empty-error": ('    yield ResultMessage(session_id=session, is_error=True, '
                          'subtype="error_during_execution", result="")'),
          "null-error": ('    yield ResultMessage(session_id=session, is_error=True, '
                         'subtype="error_during_execution")'),
          "exception-error": ('    error = RuntimeError("Claude could not complete the turn")\n'
                              '    error.data = {"subtype": "error_during_execution", '
                              '"is_error": True, "num_turns": 0, "result": None, "errors": None}\n'
                              '    raise error')}


@pytest.mark.parametrize("shape", list(SHAPES))
@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
def test_1_claude_ending_without_a_turn_fails_forge_work(repo, gh, tmp_path, previous, shape):
    _, folder = _client(repo, gh, tmp_path, previous)
    stub = repo.bin / "claude_agent_sdk" / "__init__.py"
    source = stub.read_text("utf-8")
    source = source[:source.index('    yield AssistantMessage')] + SHAPES[shape] + "\n"
    stub.write_text(source, encoding="utf-8")

    worked = repo.forge("work", FIX)

    assert worked.returncode != 0, worked.stdout
    assert "Traceback" not in worked.stdout + worked.stderr
    if shape.endswith("error"):
        assert worked.stderr.startswith("The worker stopped with exit code 1; its log is ")
        assert worked.stderr.endswith(f"work-{FIX}.log.\nNext: forge work {FIX}\n")
        assert "success" not in worked.stdout
        return
    problem = ("Claude ended without running a turn, so no worker ran; it may be waiting on a "
               "prompt such as a hooks review. Its log is ")
    assert re.fullmatch(re.escape(problem) + rf".*work-{FIX}\.log\.\n" + re.escape(
        f"Next: run claude once in {folder} and answer its prompt, then forge work {FIX}\n"),
        worked.stderr), worked.stderr
