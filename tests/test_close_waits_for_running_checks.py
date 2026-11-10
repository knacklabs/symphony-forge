"""Close and merge keep running checks past ten minutes, with a bounded wait.

Audit: owns standalone command waits, generated test groups and commit statuses.
The fixed deadline and a check-run-only deadline each fail before green. Land
does not exercise standalone merge. No production test seam is needed.
"""
import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_ci_waits_for_busy_runners import _client
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401

STORY = "FIX-CLOSE-WAITS-RUNNING-CHECKS"


@pytest.mark.parametrize("history,command,provider", [
    ("new", "close", "groups"), ("new", "merge", "groups"),
    ("new", "close", "status"), ("new", "merge", "status"),
    ("upgraded", "close", "groups"),
])
@pytest.mark.parametrize("fake_clock", [600], indirect=True)
def test_1_close_and_merge_wait_for_running_checks_until_green_or_the_limit(
        land, fake_clock, monkeypatch, tmp_path, history, command, provider):
    env = land
    monkeypatch.delenv("FORGE_CHECKS_WAIT", raising=False)
    _client(env, history, "ubuntu-latest")
    if command == "merge":
        _agent(env)
    where = _fix(env, "working", worked=True)
    if command == "merge":
        done = env.repo.forge("close", ITEM, cwd=where)
        assert done.returncode == 0, done.stdout + done.stderr

    # The generated aggregate does not exist until the test groups finish.
    name = "test group 1 of 2" if provider == "groups" else "tests"
    api = RUNS if provider == "groups" else ["api", "--paginate", "--jq", ".statuses[]"]
    running = ([run(name, None, "in_progress"), run("test group 2 of 2"), run("forge-pr-check")]
               if provider == "groups" else [{"context": name, "state": "pending"}])
    green = GREEN if provider == "groups" else [{"context": name, "state": "success"}]
    elapsed = tmp_path / "clock" / "elapsed"

    (env.repo.bin / "gh-queues.json").write_text("[]", encoding="utf-8")
    _queue(env, api, *_runs(running))
    before = float(elapsed.read_text("utf-8"))
    done = env.repo.forge(command, ITEM)
    waited = float(elapsed.read_text("utf-8")) - before
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    assert 89 * 60 <= waited <= 91 * 60, (waited, output)
    assert "90 minutes limit" in output
    assert f"{name} is still running" in output
    assert f"forge close {ITEM}" in output

    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    before = float(elapsed.read_text("utf-8"))
    calls = len(env.gh_calls(*api))
    done = env.repo.forge(command, ITEM)
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    assert float(elapsed.read_text("utf-8")) - before < 15
    assert len(env.gh_calls(*api)) == calls + 1
    assert "no check progress for 0 minutes" in output
    assert f"{name} is still running" in output
    assert f"forge close {ITEM}" in output

    monkeypatch.delenv("FORGE_CHECKS_WAIT")
    (env.repo.bin / "gh-queues.json").write_text("[]", encoding="utf-8")
    _queue(env, api, *_runs(*([running] * 5), green))
    before = float(elapsed.read_text("utf-8"))
    done = env.repo.forge(command, ITEM)
    output = done.stdout + done.stderr
    assert done.returncode == 0, output
    assert 30 * 60 <= float(elapsed.read_text("utf-8")) - before < 90 * 60
    assert ("clean review and green checks" if command == "close" else "Merged") in output
