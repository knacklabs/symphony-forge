"""Failed-test repairs and test backlog control which work gets agent places."""
import json

import pytest

from conftest import machine_cores
from test_close import Forge, env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, start
from test_lanes_tests import accepted, configure, release_server, reap, release
from test_runs_wait_for_machine_load import client
from test_story import worktree

STORY = "FIX-BUILD-TEST-BALANCE"
pytestmark = pytest.mark.platform

# Test audit:
# 1. These tests protect command-visible admission order: a repair round after a failed test
#    outranks an older first build, and a build waits on a test backlog until its low watermark.
# 2. They fail if the agent line admits new builds before repairs, or resumes overloaded builds
#    when the backlog falls to twice the test places instead of the place count.
# 3. test_close_stops_before_review.py::test_2_a_failing_test_command_blocks_the_round_and_the_worker_gets_its_output
#    owns creating the failed-test state. Existing lane tests cover review admission and test
#    capacity separately, but no test covers repair order or build hysteresis. The review-order case
#    is already owned by test_fix_agent_runs_wait_in_line.py::test_1_a_third_work_round_from_another_repo_waits_while_reads_and_reviews_start.
# 4. No production seam is needed. The tests run real `forge work` and `forge test` commands; only
#    model and test processes are held at their external command edges by the existing fixtures.


def _client(env, tmp_path, adopted):
    repo = client(env, tmp_path, adopted)
    settings = repo.path / "forge.toml"
    lines = [line for line in settings.read_text("utf-8").splitlines()
             if line.partition("=")[0].strip() not in ("workers", "test", "fast_test")]
    settings.write_text('workers = "claude"\n' + "\n".join(lines) + "\n", encoding="utf-8")
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Use the Claude test worker")
    repo.git("push", "-q", "origin", "main")
    return repo


def make_work(repo, name):
    made = repo.forge("fix", "start", name, "--done", "The typo is corrected", "--kind", "mechanical")
    assert made.returncode == 0, made.stderr
    item = name.lower().replace(" ", "-")
    return item, worktree(repo, "fix/" + item).name


def _record_failed_test(repo, item):
    folder = worktree(repo, f"fix/{item}")
    rel = f".factory/fixes/{item}.json"
    path = folder / rel
    state = json.loads(path.read_text("utf-8"))
    state.update(status="fixing", round=1,
                 tests="AssertionError: the previous test run failed")
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    repo.git("add", rel, cwd=folder)
    repo.git("commit", "-q", "-m", "Record a failed test", cwd=folder)
    return folder


def _await_agent(repo, process, output, name, what):
    marker = repo.bin / f"started-{name}"
    _until(lambda: marker.exists() or process.poll() is not None, what)
    assert process.poll() is None, output.read_text("utf-8")
    return marker


def _await_queue(process, output, what):
    _until(lambda: "waits its turn" in output.read_text("utf-8") or process.poll() is not None, what)
    assert process.poll() is None, output.read_text("utf-8")
    assert "waits its turn" in output.read_text("utf-8"), output.read_text("utf-8")


def _await_backlog_wait(process, output, what):
    message = "New builds wait for the test line to clear."
    _until(lambda: message in output.read_text("utf-8") or process.poll() is not None, what)
    assert process.poll() is None, output.read_text("utf-8")
    assert message in output.read_text("utf-8"), output.read_text("utf-8")


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
def test_2_failed_test_repair_gets_the_place_before_an_earlier_new_build(env, tmp_path, adopted):
    repo = _client(env, tmp_path, adopted)
    machine_cores(repo, 2)
    hold_agents(env)
    holder, holder_name = make_work(repo, "Current worker")
    new_build, build_name = make_work(repo, "New build")
    repair, repair_name = make_work(repo, "Failed test repair")
    _record_failed_test(repo, repair)

    processes = []
    try:
        running, running_output = start(repo.path, tmp_path / "holder", repo, "work", holder)
        processes.append(running)
        _await_agent(repo, running, running_output, holder_name, "the current worker to start")

        build, build_output = start(repo.path, tmp_path / "build", repo, "work", new_build)
        processes.append(build)
        _await_queue(build, build_output, "the new build to queue")
        assert not (repo.bin / f"started-{build_name}").exists()

        fixed, fixed_output = start(repo.path, tmp_path / "repair", repo, "work", repair)
        processes.append(fixed)
        _await_queue(fixed, fixed_output, "the failed-test repair to queue")

        (repo.bin / f"go-{holder_name}").touch()
        assert running.wait(timeout=60) == 0, running_output.read_text("utf-8")
        _await_agent(repo, fixed, fixed_output, repair_name,
                     "the failed-test repair to get the next place")
        assert "This round is near the end, so it goes before new builds." in fixed_output.read_text("utf-8")
        assert not (repo.bin / f"started-{build_name}").exists()

        (repo.bin / f"go-{repair_name}").touch()
        assert fixed.wait(timeout=60) == 0, fixed_output.read_text("utf-8")
        _await_agent(repo, build, build_output, build_name, "the queued build to start after the repair")
        (repo.bin / f"go-{build_name}").touch()
        assert build.wait(timeout=60) == 0, build_output.read_text("utf-8")
    finally:
        finish(repo, processes)


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
def test_3_build_waits_above_twice_test_places_and_resumes_at_test_places(
        env, tmp_path, adopted, release_server):
    repo = _client(env, tmp_path, adopted)
    server, connections = release_server
    configure(Forge(repo, env.gh, env.tmp), server)
    machine_cores(repo, 2)  # one test place and one agent place
    hold_agents(env)

    tests = [make_work(repo, name) for name in
             ("Active test", "Waiting test one", "Waiting test two", "Waiting test three")]
    holder, holder_name = make_work(repo, "Current worker")
    early_build, early_build_name = make_work(repo, "Build at high water")
    queued_build, queued_build_name = make_work(repo, "Queued build above threshold")
    late_build, late_build_name = make_work(repo, "Build at two after overload")
    repair, repair_name = make_work(repo, "Failed test repair")
    _record_failed_test(repo, repair)

    test_processes = []
    agent_processes = []
    try:
        current, current_output = start(repo.path, tmp_path / "holder", repo, "work", holder)
        agent_processes = [current]
        _await_agent(repo, current, current_output, holder_name, "the current worker to start")

        active, _ = tests[0]
        active_folder = worktree(repo, f"fix/{active}")
        active_process, active_output = start(active_folder, tmp_path / "active-test", repo, "test")
        test_processes.append(active_process)
        active_connection, _ = accepted(server, connections, active_folder, active_process, active_output)

        waiters = []
        for index, (item, _) in enumerate(tests[1:3], 1):
            folder = worktree(repo, f"fix/{item}")
            process, output = start(folder, tmp_path / f"waiting-test-{index}", repo, "test")
            test_processes.append(process)
            _until(lambda: f"number {index} in line." in output.read_text("utf-8") or process.poll() is not None,
                   "test items to wait in line")
            assert process.poll() is None, output.read_text("utf-8")
            waiters.append((item, folder, process, output))

        early, early_output = start(repo.path, tmp_path / "early-build", repo, "work", early_build)
        agent_processes.append(early)
        _await_queue(early, early_output, "the new build to queue at exactly twice the test places")

        (repo.bin / f"go-{holder_name}").touch()
        assert current.wait(timeout=60) == 0, current_output.read_text("utf-8")
        _await_agent(repo, early, early_output, early_build_name,
                     "a new build to start at exactly twice the test places before overload")

        item, _ = tests[3]
        folder = worktree(repo, f"fix/{item}")
        process, output = start(folder, tmp_path / "waiting-test-3", repo, "test")
        test_processes.append(process)
        _until(lambda: "number 3 in line." in output.read_text("utf-8") or process.poll() is not None,
               "a third test item to wait in line")
        assert process.poll() is None, output.read_text("utf-8")
        waiters.append((item, folder, process, output))

        fixed, fixed_output = start(repo.path, tmp_path / "repair", repo, "work", repair)
        agent_processes.append(fixed)
        _await_queue(fixed, fixed_output, "the repair to queue behind the held build")

        blocked, blocked_output = start(repo.path, tmp_path / "blocked-build", repo, "work", queued_build)
        agent_processes.append(blocked)
        _await_backlog_wait(blocked, blocked_output,
                            "a new build to wait while more than twice the test places wait")

        (repo.bin / f"go-{early_build_name}").touch()
        assert early.wait(timeout=60) == 0, early_output.read_text("utf-8")
        _await_agent(repo, fixed, fixed_output, repair_name,
                     "the repair to start while more than twice the test places wait")
        assert not (repo.bin / f"started-{queued_build_name}").exists()

        (repo.bin / f"go-{repair_name}").touch()
        assert fixed.wait(timeout=60) == 0, fixed_output.read_text("utf-8")
        assert not (repo.bin / f"started-{queued_build_name}").exists()

        release([active_connection])
        _, first_folder, first_process, first_output = waiters[0]
        first_connection, _ = accepted(server, connections, first_folder, first_process, first_output)

        late, late_output = start(repo.path, tmp_path / "late-build", repo, "work", late_build)
        agent_processes.append(late)
        _await_backlog_wait(late, late_output,
                            "a new build to remain paused when the overloaded backlog falls to twice the test places")
        assert not (repo.bin / f"started-{queued_build_name}").exists()
        assert not (repo.bin / f"started-{late_build_name}").exists()

        release([first_connection])
        _, second_folder, second_process, second_output = waiters[1]
        second_connection, _ = accepted(server, connections, second_folder, second_process, second_output)

        _await_agent(repo, blocked, blocked_output, queued_build_name,
                     "the earlier build to start when one test item waits")
        (repo.bin / f"go-{queued_build_name}").touch()
        assert blocked.wait(timeout=60) == 0, blocked_output.read_text("utf-8")
        _await_agent(repo, late, late_output, late_build_name,
                     "the later build to start while one test item still waits")
        (repo.bin / f"go-{late_build_name}").touch()
        assert late.wait(timeout=60) == 0, late_output.read_text("utf-8")
        release([second_connection])
        _, third_folder, third_process, third_output = waiters[2]
        third_connection, _ = accepted(server, connections, third_folder, third_process, third_output)
        release([third_connection])
    finally:
        reap(test_processes, server, connections)
        finish(repo, agent_processes)
