STORY = "FORGE-UPGRADECMD-1"
"""The upgrade's version edit changes only forge.toml's version string (Done-when 3), and a release
runs through uv with its exit code returned (Done-when 1). The upgrade command that calls these
arrives with its own end-to-end tests; until then they are proven here directly."""

import json
import os
import sys

import pytest
from conftest import _install

from forge import repo

TOML = (
    '# Forge\'s settings. Keep this comment.\r\n'
    'version = "v1.2.1"  # pinned\r\n'
    'repo = "client"\r\n'
    'merge = "agent"\r\n'
    'test = "npm test"\r\n'
    '\r\n'
    '[models.build]\r\n'
    'model = "claude-opus-5-5"\r\n'
    'effort = "medium"\r\n'
    '\r\n'
    '[models.review.codex]\r\n'
    "model = 'gpt-6.1-sol'\r\n"
)


def test_3_the_version_edit_keeps_every_other_byte():
    edited = repo.set_version(TOML, "v1.3.0")
    assert edited == TOML.replace('"v1.2.1"', '"v1.3.0"')


def test_3_a_multi_line_version_refuses():
    text = 'version = """v1.2.1"""\nrepo = "client"\n'
    with pytest.raises(repo.Refused) as refused:
        repo.set_version(text, "v1.3.0")
    assert str(refused.value) == (
        'forge.toml is not usable: Forge could not set version = "v1.3.0" in it, so it left it '
        "alone.\nNext: forge doctor")


# uv stands in at its edge: it records its arguments, folder and pinned-run setting, then exits 4.
UV = """#!{python}
import json, os, pathlib, sys
here = pathlib.Path(__file__).resolve().parent
(here / "uv-call.json").write_text(json.dumps(
    {{"args": sys.argv[1:], "cwd": os.getcwd(), "pinned": os.environ.get("FORGE_PINNED_RUN")}}))
print("the release ran")
sys.exit(4)
"""


def test_1_a_release_runs_through_uv_with_its_exit_code(tmp_path, monkeypatch, capfd):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install(bin_dir, "uv", UV.format(python=sys.executable))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    assert repo.run_release("v1.3.0", ["sync"], tmp_path) == 4
    assert "the release ran" in capfd.readouterr().out
    assert json.loads((bin_dir / "uv-call.json").read_text("utf-8")) == {
        "args": ["tool", "run", "--from", "git+https://github.com/knacklabs/symphony-forge@v1.3.0",
                 "forge", "sync"],
        "cwd": os.path.realpath(tmp_path), "pinned": "v1.3.0"}
