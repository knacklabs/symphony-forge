"""A real Claude Code session answers /forge with the pane's hook.

The mod's own tests play Claude Code's side. This one runs the real program, because the earlier
pane failed only there: Claude Code refuses the name /forge when Forge's guide skill has it, and
the refusal skipped the rest of the start step. Claude Code's debug log is the proof.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

from conftest import ROOT, patient
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, make_work, start
from test_pane_data import QUESTION, client, hold_tests, row_of, step_gates
from test_setup import _fresh_client
from test_story import worktree

STORY = "FORGE-PANE-1"
REAL_CLAUDE = shutil.which("claude")
MOD = ROOT / "src/forge/mod"
PROBE = ROOT / "tests/fixtures/pane-skill-probe"


def _claude(repo, home, folder, prompt, log, *plugins, first=None):
    """Run `claude -p` with the repo's forge first on PATH, in a home that holds nothing else."""
    scratch = home / "tmp"
    patient(lambda: scratch.mkdir(exist_ok=True))
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC"))}
    environment.update(
        HOME=str(home), USERPROFILE=str(home), CLAUDE_CONFIG_DIR=str(home / ".claude"),
        TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch), CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
        PATH=os.pathsep.join([*([str(first)] if first else []), str(repo.bin), os.environ["PATH"]]))
    environment.pop("CLAUDE_CODE_PLUGIN_DIRS", None)
    command = [REAL_CLAUDE, "-p", prompt, "--debug-file", str(log)]
    for plugin in plugins:
        command += ["--plugin-dir", str(plugin)]
    return subprocess.run(command, cwd=folder, env=environment, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, encoding="utf-8", timeout=60)


@pytest.mark.parametrize("guide", ["guide present", "guide absent"])
def test_1_a_real_session_answers_slash_forge_with_or_without_the_guide_skill(repo, gh, tmp_path, guide):
    if not REAL_CLAUDE:
        pytest.skip("Real Claude Code is not installed; the plugin CI job installs its pinned version.")
    if guide == "guide present":
        folder, started = _fresh_client(repo, gh, tmp_path)
        assert started.returncode == 0, started.stdout + started.stderr
        assert (folder / ".claude/skills/forge/SKILL.md").exists()
    else:
        folder = tmp_path / "plain"
        patient(lambda: folder.mkdir())
        repo.git("init", "-q", "-b", "main", cwd=folder)
        repo.git("commit", "-q", "--allow-empty", "-m", "Start", cwd=folder)
    home = tmp_path / "home"
    patient(lambda: home.mkdir())
    log = tmp_path / "forge.log"
    for _ in range(3):  # a busy laptop can make Forge miss the pane's 0.3 s limit; ask again
        done = _claude(repo, home, folder, "/forge", log, MOD)
        if "Forge did not answer." not in done.stdout:
            break
    text = log.read_text("utf-8", errors="replace")
    if "Loaded inline plugin from path: forge" not in text:
        pytest.skip("This Claude Code did not load the plugin folder under `claude -p`; the by-hand steps are the proof.")
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.strip().splitlines()[-1] == "Nothing is running."
    assert "forge (user) answered command.run without next()" in text
    assert re.search(r"hooks module forge@inline loaded .*events: session\.start,command\.run,ui\.render\s*$", text, re.M)
    # The start step adds almost nothing to the start of the session.
    assert float(re.search(r"hooks module forge@inline session\.start settled in ([\d.]+)ms", text)[1]) < 50
    assert "forge: session.start hook skipped" not in text
    if guide == "guide present":
        assert "\"/forge\" refused: it is the user's /forge" in text
        # The agent still loads the guide by itself, and the pane does not answer that.
        probed = _claude(repo, home, folder, "/probeskill", tmp_path / "probe.log", MOD, PROBE)
        assert '"commandName":"forge"' in probed.stdout, probed.stdout + probed.stderr
        skill = (tmp_path / "probe.log").read_text("utf-8", errors="replace")
        assert "tool_dispatch_start tool=Skill" in skill and "for skill forge" in skill
        assert "forge (user) answered command.run" not in skill
    else:
        assert "$.command.register (forge): /forge listed" in text


def test_2_real_lane_rows_reach_the_real_pane_and_a_late_forge_keeps_them(env, tmp_path, monkeypatch):
    if not REAL_CLAUDE:
        pytest.skip("Real Claude Code is not installed; the plugin CI job installs its pinned version.")
    client(env, False)
    repo = env.repo
    # Something waits for the person: a worker's question.
    asked, _ = make_work(repo, "Asks about parsers")
    monkeypatch.setenv("STUB_CLAUDE_RESULT", QUESTION)
    assert repo.forge("work", asked).returncode == 0
    monkeypatch.delenv("STUB_CLAUDE_RESULT")
    # A build that edits a file, held while the pane looks.
    hold_agents(env)
    step_gates(env)
    item, name = make_work(repo, "Builds the thing")
    builder, _ = start(worktree(repo, "fix/" + item), tmp_path / "build", repo, "work", item)
    _until(lambda: (repo.bin / f"started-{name}").exists(), "the build")
    (repo.bin / f"go-{name}").touch()
    _until(lambda: (repo.bin / f"edited-{name}-1").exists(), "its first step")
    _until(lambda: row_of(env, item)["step"], "Forge to record the step")
    home = tmp_path / "home"
    patient(lambda: home.mkdir())
    count = 0

    def pane(first=None):
        """What `claude -p /forge` answers, as lines. A busy laptop can make Forge miss the pane's 0.3 s limit, so ask again."""
        nonlocal count
        for _ in range(1 if first else 3):
            count += 1
            log = tmp_path / f"pane-{count}.log"
            done = _claude(repo, home, repo.path, "/forge", log, MOD, first=first)
            if "Loaded inline plugin from path: forge" not in log.read_text("utf-8", errors="replace"):
                finish(repo, [builder])  # the held build must not outlive the skipped test
                pytest.skip("This Claude Code did not load the plugin folder under `claude -p`; the by-hand steps are the proof.")
            assert done.returncode == 0, done.stdout + done.stderr
            shown = done.stdout.split("forge: ", 1)[-1]
            if "Forge did not answer." not in shown:
                break
        assert not re.search(r"unknown|\b0 ?s\b|None|null|[0-9a-f]{8}-[0-9a-f]{4}", shown), shown
        return [line.strip() for line in shown.splitlines()]

    # The build runs: its row has the round, the time and the file it edits; the question is on top.
    lines = pane()
    assert lines[0] == "Asks about parsers needs you."
    building = lines.index("BUILDING")
    assert lines[building + 1] == "Builds the thing"
    assert re.fullmatch(r"Round \d+ · \d+ (?:s|min) · editing land\.py", lines[building + 2]), lines[building + 2]
    # A read of a decision shows the decision's heading, not its file name.
    host_item, host_name = make_work(repo, "Hosts the decision read")
    host = worktree(repo, "fix/" + host_item)
    decision = host / "docs/decisions/0045-pane-decision.md"
    decision.parent.mkdir(parents=True, exist_ok=True)
    decision.write_text("---\nstatus: proposed\n---\n\n# Show decision titles in the pane\n\nWhy: a read names its decision.\n", encoding="utf-8")
    reader, _ = start(host, tmp_path / "decision", repo, "read", "0045-pane-decision")
    _until(lambda: any(row["kind"] == "read" for row in env_lanes(env)["agents"]["entries"]), "the decision read")
    assert "Show decision titles in the pane" in "\n".join(pane())
    # A test run of another item and a review join.
    tested, _ = make_work(repo, "Tests the thing")
    tests_folder = worktree(repo, "fix/" + tested)
    gate = hold_tests(env, tests_folder, "go-pane-test")
    tester, _ = start(tests_folder, tmp_path / "tests", repo, "test")
    _until(lambda: any(row["item"] == tested for row in env_lanes(env)["tests"]["entries"]), "the test run")
    reviewed, review_folder = env.start_fix({"README.md": "Reviewed while the pane looks\n"})
    (repo.bin / "started-review").unlink(missing_ok=True)
    (repo.bin / "go-review").unlink(missing_ok=True)
    reviewer, _ = start(review_folder, tmp_path / "review", repo, "close", reviewed)
    _until(lambda: (repo.bin / "started-review").exists(), "the review")
    _until(lambda: any(row["kind"] == "review" for row in env_lanes(env)["agents"]["entries"]), "the review's row")
    lines = pane()
    for heading in ("BUILDING", "TESTS", "REVIEW"):
        assert heading in lines
    assert lines[lines.index("BUILDING") + 1] == "Builds the thing"
    assert "Tests the thing" in lines[lines.index("TESTS") + 1:lines.index("REVIEW")]
    assert "Show decision titles in the pane" in lines[lines.index("REVIEW") + 1:]
    assert any(re.fullmatch(r"Round \d+ · \d+ (?:s|min)", line) for line in lines[lines.index("REVIEW") + 1:]), lines
    gate.touch()
    (repo.bin / "go-review").touch()
    finish(repo, [builder, reviewer, reader])
    tester.wait(timeout=60)

    # Forge goes missing after a good answer: the rows stay, with how old they are.
    broken = tmp_path / "broken-bin"
    patient(lambda: broken.mkdir())
    (broken / "forge").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (broken / "forge").chmod(0o755)
    (broken / "forge.cmd").write_text("@exit /b 1\r\n", encoding="utf-8")  # Windows finds this launcher first
    kept = "\n".join(pane(first=broken))
    assert "Builds the thing" in kept and "Asks about parsers needs you." in kept
    assert re.search(r"Last update \d+ (?:s|min) ago\. Forge did not answer\.", kept), kept
    assert "Loading" not in kept


def env_lanes(env):
    done = env.repo.forge("lanes", "--json")
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)
