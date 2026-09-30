"""When the installed Forge isn't the version forge.toml pins, a command runs the pinned release
through uv instead of refusing; without uv, or inside that run, it still refuses."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from conftest import _install
from test_upgrade_pending import OLD, _pin_old, _refused_as_today, _upgrade

STORY = "when-the-installed-forge-differs-from-th"

# uv stands in at its edge: it records each call, then answers as the release it would run.
# Asked to, it runs this checkout's forge again, so "the pinned release" still isn't the pin.
UV = """#!{python}
import json, os, pathlib, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
with open(here / "uv-calls.jsonl", "a", encoding="utf-8") as calls:
    calls.write(json.dumps({{"args": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
if (here / "uv-reruns").exists():
    sys.exit(subprocess.run([sys.executable, str(here / "forge"), *sys.argv[6:]]).returncode)
print("the pinned release ran")
sys.exit(3)
"""
GIT = """#!{python}
import subprocess, sys
sys.exit(subprocess.call([{git!r}, *sys.argv[1:]]))
"""


def _uv(repo) -> Path:
    _install(repo.bin, "uv", UV.format(python=sys.executable))
    return repo.bin / "uv-calls.jsonl"


def _calls(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []


def test_1_a_command_runs_the_pinned_release_through_uv(repo):
    log = _uv(repo)
    version = _pin_old(repo)
    ran = repo.forge("fix", "start", "Tidy the readme", "--done", "It reads well")
    assert ran.stderr == (f"Forge {version} is installed, but this repo pins {OLD}, so {OLD} runs "
                          "through uv.\n")
    assert ran.stdout == "the pinned release ran\n"
    assert ran.returncode == 3  # the pinned release's own exit code
    assert _calls(log) == [{"args": [
        "tool", "run", "--from", f"git+https://github.com/knacklabs/symphony-forge@{OLD}",
        "forge", "fix", "start", "Tidy the readme", "--done", "It reads well"],
        "cwd": str(repo.path)}]


def test_2_it_refuses_inside_the_pinned_run_so_it_never_loops(repo):
    log = _uv(repo)
    (repo.bin / "uv-reruns").touch()
    version = _pin_old(repo)
    ran = repo.forge("fix", "start", "Tidy the readme", "--done", "It reads well")
    assert ran.returncode == 1
    assert ran.stderr.endswith(
        f"Forge {version} is installed, but this repo pins {OLD}.\n"
        f"Next: uv tool install git+https://github.com/knacklabs/symphony-forge@{OLD}\n")
    assert len(_calls(log)) == 1


def test_3_it_refuses_when_uv_is_missing(repo, tmp_path, monkeypatch):
    version = _pin_old(repo)
    # Only folders without uv, plus git on its own, so this test holds wherever uv is installed.
    tools = tmp_path / "git-only"
    tools.mkdir()
    _install(tools, "git", GIT.format(python=sys.executable, git=shutil.which("git")))
    kept = [d for d in os.environ["PATH"].split(os.pathsep) if not shutil.which("uv", path=d)]
    monkeypatch.setenv("PATH", os.pathsep.join([*kept, str(tools)]))
    _refused_as_today(repo.forge("fix", "start", "Tidy the readme", "--done", "It reads well"), version)


def test_4_cases_with_their_own_handling_keep_it(repo, tmp_path):
    log = _uv(repo)
    version = _pin_old(repo)
    fix = _upgrade(repo, tmp_path, version)
    # An upgrade fix waiting to merge: the installed Forge runs on the default branch.
    started = repo.forge("fix", "start", "Tidy the readme", "--done", "It reads well")
    assert started.returncode == 0, started.stderr
    assert "upgrade-forge" in started.stderr
    # An item checked out in another folder: the command points there.
    other = tmp_path / "repo-fix-other"
    repo.git("worktree", "add", "-q", "-b", "fix/other", str(other), "main")
    refused = repo.forge("close", "upgrade-forge", cwd=other)
    assert refused.returncode == 1
    assert refused.stderr.startswith(f"upgrade-forge is checked out in {fix}")
    assert _calls(log) == []
