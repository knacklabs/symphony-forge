"""forge upgrade updates Claude Code and the Codex CLI with the installer that installed each.

Only the programs at the edge are stubs: claude, codex, npm and brew log their calls and move
their own version. The installer is found from the real path of the codex on PATH, so the unix
layouts put a symlink on PATH, as real installers do. A failed update prints the line to run and
the upgrade still succeeds.
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
elif sys.argv[1:] == ["--help"]:
    print("Commands:\\n  update  Update {name}")
elif sys.argv[1:] == ["update"]:
    here.joinpath("calls").open("a").write("update\\n")
    if (here / "{name}-fails").exists():
        sys.exit("error: EACCES permission denied, try sudo")
    version.write_text("{new}")
"""
INSTALL = "irm https://chatgpt.com/codex/install.ps1 | iex" if os.name == "nt" else "curl -fsSL https://chatgpt.com/codex/install.sh | sh"
symlinks = pytest.mark.skipif(os.name == "nt", reason="needs symlinks")


def stub(folder, name, new):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}-version").write_text("0.0.1")
    conftest._install(folder, name, TOOL.format(python=sys.executable, name=name, new=new))


def on_path(monkeypatch, *folders):
    monkeypatch.setenv("PATH", os.pathsep.join([*map(str, folders), os.environ["PATH"]]))


def manager(folder, name, bumps):
    """npm or brew: logs its arguments and moves the Codex stub's version, as the real one would."""
    folder.mkdir(parents=True, exist_ok=True)
    conftest._install(folder, name, f"""#!{sys.executable}
import pathlib, sys
pathlib.Path({str(folder / "calls")!r}).open("a").write(" ".join(sys.argv[1:]) + "\\n")
pathlib.Path({str(bumps / "codex-version")!r}).write_text("0.9.0")
""")


def layout(kind, tmp_path):
    """Where the codex binary really lives, the PATH folder that finds it, and the package
    manager's expected call (None when Codex updates itself)."""
    if kind == "npm-windows-shim":  # codex.cmd beside node_modules, no symlink
        shim = tmp_path / "npm-win"
        (shim / "node_modules/@openai/codex").mkdir(parents=True)
        return shim, shim, ("npm", f"install -g --prefix {shim} @openai/codex@latest\n")
    real = {"npm": tmp_path / "npm" / "lib/node_modules/@openai/codex/bin",
            "brew": tmp_path / "brew/Cellar/codex/0.0.1/bin",
            "standalone": tmp_path / "home/.codex/packages/standalone/releases/0.0.1/bin"}[kind]
    expected = {"npm": ("npm", f"install -g --prefix {tmp_path / 'npm'} @openai/codex@latest\n"),
                "brew": ("brew", "upgrade codex\n"), "standalone": None}[kind]
    return real, tmp_path / "links", expected


@pytest.mark.parametrize("kind", [
    pytest.param("npm", marks=symlinks), pytest.param("brew", marks=symlinks),
    pytest.param("standalone", marks=symlinks), "npm-windows-shim"])
def test_1_upgrade_updates_both_tools_and_names_their_versions(up, tmp_path, monkeypatch, kind):
    mine = tmp_path / "tools"
    stub(mine, "claude", "2.5.0")
    real, found, expected = layout(kind, tmp_path)
    stub(real, "codex", "0.9.0")
    if found != real:  # a launcher on PATH that is only a symlink, whose real path says the installer
        found.mkdir()
        (found / "codex").symlink_to(real / "codex")
    folders = [mine, found]
    if expected:
        manager(tmp_path / "pm", expected[0], real)
        folders.append(tmp_path / "pm")
    on_path(monkeypatch, *folders)

    done = up.run(RELEASE)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Installed Claude Code 2.5.0." in done.stdout.splitlines()
    assert "Installed Codex CLI 0.9.0." in done.stdout.splitlines()
    assert (mine / "calls").read_text() == "update\n"
    assert (tmp_path / "pm" / "calls").read_text() == expected[1] if expected else (
        (real / "calls").read_text() == "update\n")


def test_2_a_failed_update_prints_a_command_to_paste_and_the_upgrade_goes_on(up, tmp_path, monkeypatch):
    mine = tmp_path / "tools"
    stub(mine, "claude", "2.5.0")
    (mine / "claude-fails").touch()
    stub(mine / "elsewhere", "codex", "0.9.0")  # no installer's folder
    on_path(monkeypatch, mine, mine / "elsewhere")

    done = up.run(RELEASE)

    assert done.returncode == 0, done.stdout + done.stderr
    lines = done.stdout.splitlines()
    to_run = ("run this in an administrator terminal: claude update" if os.name == "nt"
              else 'run: sudo env PATH="$PATH" claude update')
    assert f"Claude Code was not updated (error: EACCES permission denied, try sudo). To update it, {to_run}" in lines
    assert ("Codex CLI was not updated (Forge could not tell which installer put it there). "
            f"To update it, run: {INSTALL}") in lines


@symlinks
def test_3_an_old_standalone_codex_without_update_is_not_run_and_gets_the_install_line(
        up, tmp_path, monkeypatch):
    real, found, _ = layout("standalone", tmp_path)
    real.mkdir(parents=True)
    # An old Codex reads `update` as a prompt: it logs every call and has no update command.
    conftest._install(real, "codex", f"""#!{sys.executable}
import pathlib, sys
pathlib.Path({str(real / "calls")!r}).open("a").write(" ".join(sys.argv[1:]) + "\\n")
print("codex-cli 0.125.0" if sys.argv[1:] == ["--version"] else "Commands:\\n  exec  Run non-interactively")
""")
    found.mkdir()
    (found / "codex").symlink_to(real / "codex")
    on_path(monkeypatch, found)

    done = up.run(RELEASE)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "update" not in (real / "calls").read_text().split()
    assert ("Codex CLI was not updated (Forge could not tell which installer put it there). "
            f"To update it, run: {INSTALL}") in done.stdout.splitlines()
