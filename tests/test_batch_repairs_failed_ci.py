"""A batch resumes the builder once after failed CI, then merges or explains the stop."""

import json
import pytest

from conftest import _install
from test_close import env  # noqa: F401
from test_land import COMMITS
from test_queue_land_all import client, _all, _fix, _number, _red  # noqa: F401

STORY = "when-ci-fails-on-a-change-in-a-batch-run"

# Authoring gate: the command must resume the original builder and close again after red CI.
# The batch-only early refusal breaks this; single-item tests cannot reach that refusal.
# Only the model and GitHub edges are faked, with no production seam.
@pytest.mark.parametrize("heals", [True, False], ids=["merges", "stops"])
def test_1_batch_gives_failed_ci_one_round_on_the_builder_thread(client, monkeypatch, heals):
    env = client
    module = env.repo.bin / "claude_agent_sdk" / "__init__.py"
    commits = "".join("    " + line + "\n" for line in COMMITS.splitlines())
    module.write_text(module.read_text("utf-8").replace(
        '    yield ResultMessage(session_id=session',
        commits + '    yield ResultMessage(session_id=session'), encoding="utf-8")
    where = _fix(env, monkeypatch, "repair", 1, {"repair.py": "x = 1\n"})
    built = env.repo.forge("work", "repair")
    assert built.returncode == 0, built.stdout + built.stderr
    # Publish the first build, then let GitHub report a failure for that pushed head.
    closed = env.repo.forge("close", "repair")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    _red(env, "repair")
    env.gh.respond("pr", "checks", "fix/repair", exit=1, stdout=json.dumps([{
        "name": "tests", "bucket": "fail", "link": "https://github.com/acme/shop/actions/runs/5/job/95"}]))
    env.gh.respond("run", "view", "--job", "95", stdout="FAILED repair.py: wrong result\n")
    if heals:
        # GitHub reports success for a new pushed commit, never for the original failed head.
        failed_head = env.repo.git("rev-parse", "HEAD", cwd=where)
        gh = env.repo.bin / "gh"
        code = gh.read_text("utf-8")
        code = code.replace('    if own.exists():\n        answer(own.read_text())',
            '    if own.exists():\n'
            '        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()\n'
            f'        if head != {failed_head!r}:\n'
            '            own.unlink()\n'
            '        else:\n'
            '            answer(own.read_text())', 1)
        _install(env.repo.bin, "gh", code)
    done = _all(env)
    calls = [json.loads(line) for line in (env.repo.bin / "claude-sdk-calls.jsonl").read_text("utf-8").splitlines()]
    assert len(calls) == 2, done.stdout + done.stderr
    assert calls[1]["options"]["resume"] == calls[0]["session_id"]
    assert "FAILED repair.py" in calls[1]["prompt"]
    assert "repair: Fix round 1 of 1: the worker fixes the failing checks." in done.stdout
    if heals:
        assert done.returncode == 0, done.stdout + done.stderr
        assert "repair merged." in done.stdout
        assert env.gh_calls("pr", "merge", _number("fix/repair"))
    else:
        assert done.returncode == 1, done.stdout + done.stderr
        assert "Stopped after one fix round: repair still has the failing checks." in done.stdout
        assert "Checks failed on the pull request: tests." in done.stdout
        assert not env.gh_calls("pr", "merge", _number("fix/repair"))
