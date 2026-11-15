"""Forge's data for the /forge pane names a decision by its heading and gives a plain test run an output file.

Real commands and real git; only the model programs are held at their edge. The pane itself draws
the real `forge lanes --json` answer and reads the real log Forge wrote: the mod's test runs on it.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, make_work, start
from test_pane_data import client, hold_tests
from test_story import worktree

pytestmark = pytest.mark.platform

STORY = "FIX-PANE-DECISION-OUTPUT"
HEADING = "Show decision titles in the pane"
MOD = ROOT / "src/forge/mod"
REAL = ROOT / "tests/fixtures/pane-real-data.test.ts"
CLAUDE = shutil.which("claude")


def lanes_text(env):
    done = env.repo.forge("lanes", "--json")
    assert done.returncode == 0, done.stderr
    return done.stdout


def pane_draws(env, tmp_path, lanes, *, titles, absent, open_run, last, path=""):
    """Run the shipped mod's code on real Forge data: its test file reads the answer and the logs from real-data.ts."""
    if not CLAUDE:
        pytest.skip("Real Claude Code is not installed; the plugin CI job installs its pinned version.")
    # The test tool has no real file system: the log's real size goes in, and its text when the API could read it.
    size = Path(path).stat().st_size if path else 0
    log = Path(path).read_text("utf-8") if path and size <= 4 * 1024 * 1024 else ""
    piece = -(-len(log) // 4) or 1
    copy = tmp_path / "mod"
    shutil.copytree(MOD, copy)
    for old in (copy / "hooks").glob("*.test.ts"):
        old.unlink()
    shutil.copy(REAL, copy / "hooks/real.test.ts")
    (copy / "hooks/real-data.ts").write_text("export default " + json.dumps({
        "root": env.repo.path.resolve().as_posix(), "lanes": lanes, "logPath": path, "size": size, "titles": titles,
        "absent": absent, "open": open_run, "last": last}) + "\n", "utf-8")
    for part in range(4):
        (copy / f"hooks/real-log-{part}.ts").write_text("export default " + json.dumps(log[part * piece:(part + 1) * piece]) + "\n", "utf-8")
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC"))}
    done = subprocess.run([CLAUDE, "plugin", "test", str(copy)], env=environment, text=True, encoding="utf-8",
                          capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "1 pass" in done.stdout + done.stderr, done.stdout + done.stderr


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier adopted"])
def test_1_a_decision_read_by_its_short_name_shows_its_heading_even_beside_a_fix_of_that_name(env, tmp_path, previous):
    client(env, previous)
    repo = env.repo
    hold_agents(env)
    # A fix and a decision share the short name, and the decision is read from the fix's own checkout.
    item, _ = make_work(repo, "pane decision")
    host = worktree(repo, "fix/" + item)
    decision = host / f"docs/decisions/0045-{item}.md"
    decision.parent.mkdir(parents=True, exist_ok=True)
    decision.write_text(f"---\nstatus: proposed\n---\n\n# {HEADING}\n\nWhy: a read names its decision.\n", encoding="utf-8")
    reader, _ = start(host, tmp_path / "decision", repo, "read", item)
    try:
        _until(lambda: any(row["kind"] == "read" for row in json.loads(lanes_text(env))["agents"]["entries"]), "the decision read")
        lanes = lanes_text(env)
        row = next(row for row in json.loads(lanes)["agents"]["entries"] if row["kind"] == "read")
        assert row["title"] == HEADING
        pane_draws(env, tmp_path, lanes, titles=[HEADING], absent=["pane decision"], open_run=row["id"], last="")
    finally:
        finish(repo, [reader])


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier adopted"])
@pytest.mark.parametrize("selected", ["tests selected", "only a check"])
@pytest.mark.parametrize("lines", [18000, 70000], ids=["1.5 MiB", "5.9 MiB"])
def test_2_a_plain_test_run_has_an_output_file_the_pane_opens_even_when_it_is_over_1_mib(env, tmp_path, previous, selected, lines):
    client(env, previous)
    repo = env.repo
    # The default branch is no item. The held command prints over 1 MiB, waits, then prints its last line.
    gate = hold_tests(env, repo.path, "go-plain-test")
    script = repo.bin / "go-plain-test.py"
    script.write_text(script.read_text("utf-8").replace(
        "import pathlib, time\n", f"import pathlib, time\nfor n in range({lines}): print(f'test output line {{n}} ' + 'x' * 60)\n", 1)
        + "print('The last test line')\n", "utf-8")
    base = repo.git("rev-parse", "HEAD")
    if selected == "tests selected":
        env.commit(repo.path, "conftest.py", "# Shared test setup\n", "Change shared test setup")
    tester, _ = start(repo.path, tmp_path / "plain", repo, "test", "--pytest", base)
    try:
        _until(lambda: json.loads(lanes_text(env))["tests"]["entries"], "the test run")
        # The output path is on the row from the moment it joins the line, before the command starts.
        row = json.loads(lanes_text(env))["tests"]["entries"][0]
        assert row["item"] is None and row["output_path"]
        log = Path(row["output_path"])
        _until(lambda: log.is_file() and log.stat().st_size > 1024 * 1024, "the command's first 1 MiB")
        lanes = lanes_text(env)
        gate.touch()
        assert tester.wait(timeout=60) == 0
        size = log.stat().st_size
        assert size > 1024 * 1024
        # The pane reads up to 4 MiB and shows the end; a larger log is named by its path, as Forge gave it.
        last = ("The last test line" if size <= 4 * 1024 * 1024
                else f"This output is too large to show here. It is in {row['output_path']}.")
        pane_draws(env, tmp_path, lanes, titles=["A test run"], absent=[], open_run=row["id"], last=last, path=row["output_path"])
    finally:
        gate.touch()
        tester.wait(timeout=60)
