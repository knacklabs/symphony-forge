"""Forge's data for the /forge pane names a decision by its heading and gives a plain test run an output file.

Real commands and real git; only the model programs are held at their edge.
"""
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, make_work, start
from test_pane_data import client, hold_tests, lanes
from test_story import worktree

STORY = "FIX-PANE-DECISION-OUTPUT"
HEADING = "Show decision titles in the pane"


@pytest.mark.platform
@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier adopted"])
def test_1_a_decision_read_by_its_short_name_shows_its_heading(env, tmp_path, previous):
    client(env, previous)
    repo = env.repo
    hold_agents(env)
    item, _ = make_work(repo, "Hosts the decision read")
    host = worktree(repo, "fix/" + item)
    decision = host / "docs/decisions/0045-pane-decision.md"
    decision.parent.mkdir(parents=True, exist_ok=True)
    decision.write_text(f"---\nstatus: proposed\n---\n\n# {HEADING}\n\nWhy: a read names its decision.\n", encoding="utf-8")
    reader, _ = start(host, tmp_path / "decision", repo, "read", "pane-decision")
    try:
        _until(lambda: any(row["kind"] == "read" for row in lanes(env)["agents"]["entries"]), "the decision read")
        titles = [row["title"] for row in lanes(env)["agents"]["entries"] if row["kind"] == "read"]
        assert titles == [HEADING]
    finally:
        finish(repo, [reader])


@pytest.mark.platform
@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier adopted"])
def test_2_a_plain_test_run_has_an_output_file_to_open(env, tmp_path, previous):
    client(env, previous)
    repo = env.repo
    # The default branch is no item: the run has no name of its own and its tests print to a held command.
    gate = hold_tests(env, repo.path, "go-plain-test")
    script = repo.bin / "go-plain-test.py"
    script.write_text(script.read_text("utf-8") + "print('The held tests passed')\n", "utf-8")
    base = repo.git("rev-parse", "HEAD")
    env.commit(repo.path, "conftest.py", "# Shared test setup\n", "Change shared test setup")
    tester, _ = start(repo.path, tmp_path / "plain", repo, "test", "--pytest", base)
    try:
        _until(lambda: lanes(env)["tests"]["entries"], "the test run")
        _until(lambda: lanes(env)["tests"]["entries"][0]["output_path"], "the output file")
        row = lanes(env)["tests"]["entries"][0]
        assert row["item"] is None
        assert Path(row["output_path"]).is_file()
    finally:
        gate.touch()
        assert tester.wait(timeout=60) == 0
    assert "The held tests passed" in Path(row["output_path"]).read_text("utf-8")
