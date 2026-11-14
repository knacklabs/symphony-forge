"""A real Claude Code session answers /forge with the pane's hook.

The mod's own tests play Claude Code's side. This one runs the real program, because the earlier
pane failed only there: Claude Code refuses the name /forge when Forge's guide skill has it, and
the refusal skipped the rest of the start step. Claude Code's debug log is the proof.
"""
import os
import re
import shutil
import subprocess

import pytest

from conftest import ROOT, patient
from test_setup import _fresh_client

STORY = "FORGE-PANE-1"
REAL_CLAUDE = shutil.which("claude")
MOD = ROOT / "src/forge/mod"
PROBE = ROOT / "tests/fixtures/pane-skill-probe"


def _claude(repo, home, folder, prompt, log, *plugins):
    """Run `claude -p` with the repo's forge first on PATH, in a home that holds nothing else."""
    scratch = home / "tmp"
    patient(lambda: scratch.mkdir(exist_ok=True))
    environment = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC"))}
    environment.update(
        HOME=str(home), USERPROFILE=str(home), CLAUDE_CONFIG_DIR=str(home / ".claude"),
        TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch), CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
        PATH=str(repo.bin) + os.pathsep + os.environ["PATH"])
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
    done = _claude(repo, home, folder, "/forge", log, MOD)
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
