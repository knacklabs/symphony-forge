"""forge upgrade updates Claude Code and the Codex CLI with the installer that installed each.

Only the programs at the edge are stubs: claude, codex, npm and brew log their calls and move
their own version. A failed update prints the line to run and the upgrade still succeeds.
"""
import os
import sys

import pytest

import conftest
from test_close import env  # noqa: F401
from test_upgrade_command import RELEASE, unsynced_up, up  # noqa: F401

STORY = "upgrade-updates-agent-tools"
pytestmark = pytest.mark.platform

TOOL = """#!{python}
import pathlib, sys
here = pathlib.Path(__file__).resolve().parent
version = here / "{name}-version"
if sys.argv[1:] == ["--version"]:
    print("{name} " + version.read_text().strip())
elif {updates}:
    pathlib.Path(sys.argv[0]).with_name("calls").open("a").write(" ".join(sys.argv[1:]) + "\\n")
    if (here / "{name}-fails").exists():
        sys.exit("error: permission denied, try sudo")
    version.write_text("{new}")
"""


def stub(folder, name, new, updates):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}-version").write_text("0.0.1")
    conftest._install(folder, name, TOOL.format(python=sys.executable, name=name,
                                                new=new, updates=updates))


@pytest.mark.parametrize("installer", ["npm", "brew"])
def test_1_upgrade_updates_both_tools_and_names_their_versions(up, tmp_path, monkeypatch, installer):
    mine = tmp_path / "tools"
    stub(mine, "claude", "2.5.0", 'sys.argv[1:] == ["update"]')
    where = mine / "node_modules" / ".bin" if installer == "npm" else mine / "Cellar" / "codex" / "bin"
    stub(where, "codex", "0.9.0", "False")
    # The package manager's stub moves the Codex stub's version, as the real one would.
    (mine / "pm").mkdir()
    conftest._install(mine / "pm", installer, f"""#!{sys.executable}
import pathlib, sys
pathlib.Path({str(mine / "pm" / "calls")!r}).open("a").write(" ".join(sys.argv[1:]) + "\\n")
pathlib.Path({str(where / "codex-version")!r}).write_text("0.9.0")
""")
    monkeypatch.setenv("PATH", os.pathsep.join([str(mine), str(where), str(mine / "pm"),
                                                os.environ["PATH"]]))

    done = up.run(RELEASE)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Installed Claude Code 2.5.0." in done.stdout.splitlines()
    assert "Installed Codex CLI 0.9.0." in done.stdout.splitlines()
    assert (mine / "calls").read_text() == "update\n"
    assert (mine / "pm" / "calls").read_text() == (
        "install -g @openai/codex@latest\n" if installer == "npm" else "upgrade codex\n")


def test_2_a_failed_update_prints_the_line_to_run_and_the_upgrade_goes_on(up, tmp_path, monkeypatch):
    mine = tmp_path / "tools"
    stub(mine, "claude", "2.5.0", 'sys.argv[1:] == ["update"]')
    (mine / "claude-fails").touch()
    stub(mine / "elsewhere", "codex", "0.9.0", "False")  # no installer's folder
    monkeypatch.setenv("PATH", os.pathsep.join([str(mine), str(mine / "elsewhere"),
                                                os.environ["PATH"]]))

    done = up.run(RELEASE)

    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    assert ("Claude Code was not updated (error: permission denied, try sudo). "
            "To update it, run: claude update") in lines
    assert ("Codex CLI was not updated (Forge could not tell which installer put it there). "
            "To update it, run: npm install -g @openai/codex@latest") in lines
