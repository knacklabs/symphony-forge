"""When a worker can't get past the same failing test or finding, Forge stops the item and prints
a ready-to-ask question; the owner's choice, such as switching the item to the other tool, is
recorded and the next round follows it. Both client hosts get the guide paragraph."""
from __future__ import annotations

import json
import sys

import pytest

from conftest import _install
from test_close import CLEAN, ROOT, blocked, env, finding  # noqa: F401
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_land import _workers, land  # noqa: F401
from test_setup import _fresh_client
from test_worker import install_claude
from test_upgrade_command import _repo_adopted_on_the_previous_release, unsynced_up  # noqa: F401

STORY = "stuck-worker-asks"

# The repo's test commands: failing every run, failing once the worker has built, and failing on
# the first and third runs only.
SUITES = {
    "failing": 'print("FAILED test_readme.py::test_greeting - AssertionError")\nraise SystemExit(1)\n',
    "finding then test": ('import pathlib, sys\nif pathlib.Path("work-1.txt").exists():\n'
                          '    print("FAILED test_readme.py::test_greeting")\n    sys.exit(1)\n'),
    "fail pass fail": ('import pathlib, sys\nrun = pathlib.Path("{runs}")\n'
                       'run.write_text(run.read_text() + "x" if run.exists() else "x")\n'
                       'sys.exit(len(run.read_text()) != 2)\n'),
}
SUITES["work twice"] = SUITES["failing"]
TESTS = "close's tests failing"
STUCK = {"failing": TESTS, "work twice": TESTS,
         "finding": 'the review finding "Saving drops the greeting" in app.py',
         "no change": 'the review finding "Saving drops the greeting" in app.py'}
NEXT = 'Next: forge close tidy-readme --resolve <switch|same|narrow|split> --reason "<human\'s choice>"'


def question(stuck, tried="Worker round"):
    return ["Readme greets new readers is stuck. It should deliver: The readme opens with a greeting",
            f"Two rounds in a row left {stuck}.", f"The worker tried: {tried}.",
            "Choose one: switch this item to Codex; keep Claude for one more round; or narrow or split it.",
            NEXT]


def _rounds(env, case):
    """Start the fix whose every close fails, then run work and close once (twice for fail pass
    fail)."""
    if case in ("finding", "no change"):
        env.reviews(blocked(finding("P1", "Saving drops the greeting")))
    if case == "no change":  # a worker that commits nothing, so close reuses its review
        _install(env.repo.bin, "claude", (ROOT / "tests/stubs/claude").read_text("utf-8"))
    if case == "finding then test":  # the worker fixes the finding, and a test then fails
        env.reviews(blocked(finding("P1", "Saving drops the greeting")), CLEAN)
    if case == "fail pass fail":  # a new finding each close keeps the closes failing
        env.reviews(*(blocked(finding("P1", f"Defect {n}")) for n in (1, 2, 3)))
    if case not in ("finding", "no change"):
        script = env.tmp / "suite.py"
        script.write_text(SUITES[case].format(runs=(env.tmp / "runs").as_posix()), "utf-8")
        toml = env.repo.path / "forge.toml"
        env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
                   + "test = " + json.dumps(f"{sys.executable} {script}") + "\n")
        env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    for _ in range(2 if case == "fail pass fail" else 1):
        assert env.close(item).returncode == 1
        # A second round with no close between has no new result, so it counts nothing.
        for _ in range(2 if case == "work twice" else 1):
            worked = env.repo.forge("work", item)
            assert worked.returncode == 0, worked.stdout + worked.stderr
    assert env.close(item).returncode == 1
    return item


@pytest.mark.parametrize("case", ["failing", "work twice", "fail pass fail", "finding", "finding then test",
                                  "no change"])
def test_1_two_rounds_leaving_the_same_failure_stop_with_a_question(land, case):
    env = land
    item = _rounds(env, case)
    stuck = env.repo.forge("work", item)
    # A passing round between failing ones, or a fixed finding followed by failing tests, is progress.
    if case in ("fail pass fail", "finding then test"):
        assert stuck.returncode == 0, stuck.stdout + stuck.stderr
        return
    asked = question(STUCK[case], "no new commits" if case == "no change" else "Worker round")
    assert stuck.returncode == 1, stuck.stdout + stuck.stderr
    assert ("The worker can't get past the same problem, so Forge stopped sending it back. "
            "Ask the human:\n") in stuck.stderr
    assert stuck.stderr.splitlines()[-5:] == asked
    assert env.close(item).stderr.splitlines()[-5:] == asked
    shown = env.repo.forge("next").stdout
    assert question(STUCK[case])[0] in shown and NEXT in shown
    refused = env.close(item, "--resolve", "accept", "--reason", "Accept it")
    assert refused.returncode == 1 and refused.stderr.splitlines()[-1] == NEXT


@pytest.mark.parametrize("choice", ["same", "narrow", "split"])
def test_2_a_choice_buys_one_more_round_then_forge_asks_again(land, choice):
    env = land
    item = _rounds(env, "failing")
    assert env.repo.forge("work", item).returncode == 1
    chosen = env.close(item, "--resolve", choice, "--reason", "One more try")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    before = len(_workers(env))
    again = env.repo.forge("work", item)
    assert again.returncode == 0, again.stdout + again.stderr
    assert len(_workers(env)) == before + 1
    # The owner's choice reaches the worker's brief.
    assert f"The owner chose {choice}: One more try. Follow the owner's choice." in _workers(env)[-1]["brief"]
    assert env.close(item).returncode == 1
    asked = env.repo.forge("work", item)
    assert asked.returncode == 1 and asked.stderr.splitlines()[-1] == NEXT


def test_3_switch_runs_the_next_round_on_the_other_tool(land, sdk_data, monkeypatch):
    env = land
    item = _rounds(env, "failing")
    assert env.repo.forge("work", item).returncode == 1
    chosen = env.close(item, "--resolve", "switch", "--reason", "Try the other tool")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    assert "Codex builds it" in env.repo.forge("next").stdout
    # A Codex this project trusts, as test_codex_worker sets it up.
    _install(env.repo.bin, "codex-app-server", (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
    monkeypatch.setenv("CODEX_BIN", str(env.repo.bin / "codex-app-server"))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    home = env.tmp / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(env.repo.path))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    before = len(_workers(env))
    switched = env.repo.forge("work", item)
    assert switched.returncode == 0, switched.stdout + switched.stderr
    assert f"Building {item} with Codex" in switched.stdout
    assert (env.repo.bin / "codex-app-server.jsonl").exists()
    assert len(_workers(env)) == before  # Claude ran no round


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_4_clients_receive_the_stuck_worker_guidance(unsynced_up, adoption):
    up = unsynced_up
    if adoption == "new init":
        client, made = _fresh_client(up.repo, up.env.gh, up.tmp)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        _repo_adopted_on_the_previous_release(up)
        client = up.folder
    for host in (".codex", ".claude"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "When two rounds in a row leave close's tests failing or the same finding open" in guide
        assert ('`forge close <item> --resolve <switch|same|narrow|split> --reason '
                '"<human\'s choice>"`') in guide


def test_5_a_rerun_close_without_a_round_counts_once(land):
    env = land
    script = env.tmp / "suite.py"
    script.write_text(SUITES["failing"], "utf-8")
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + "test = " + json.dumps(f"{sys.executable} {script}") + "\n")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    # Work, close, close, work: no question; one more close and round: the question.
    steps = ["work", "close", "close", "work", "close", "work"]
    results = [env.repo.forge("work", item) if step == "work" else env.close(item) for step in steps]
    worked = [result for step, result in zip(steps, results) if step == "work"]
    assert [result.returncode for result in worked] == [0, 0, 1], worked[-1].stdout + worked[-1].stderr
    assert worked[-1].stderr.splitlines()[-1] == NEXT


def test_6_the_owners_chosen_tool_never_falls_back(repo, monkeypatch, sdk_data):
    # The owner switched this item to Claude at a stuck stop; a failed Claude round stays failed.
    monkeypatch.delenv("CODEX_THREAD_ID")
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    install_claude(repo)
    config = folder / "forge.toml"
    config.write_text(config.read_text("utf-8").replace('workers = "codex"', 'workers = "split"'), "utf-8")
    state = folder / ".factory/stories/BOARD/tasks/PAGE.json"
    state.write_text(json.dumps({**json.loads(state.read_text("utf-8")), "tool": "claude"}), "utf-8")
    repo.git("commit", "-qam", "The owner chose Claude", cwd=folder)
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    failed = repo.forge("work", "BOARD/PAGE")
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "fell back to Codex" not in failed.stdout
    assert "exit code 3" in failed.stderr
    assert _sent(codex_log, "turn/start") == []
