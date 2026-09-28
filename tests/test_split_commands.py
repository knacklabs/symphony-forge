"""FORGE-SPLIT-1 command declarations at the installed command boundary."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import conftest

STORY = "FORGE-SPLIT-1"
SOURCE = Path(__file__).resolve().parents[1] / "src" / "forge"


def _copy_forge(repo, tmp_path):
    package = tmp_path / "plugged" / "forge"
    shutil.copytree(SOURCE, package)
    (repo.bin / "forge").write_text(
        conftest.FORGE_SHIM.format(python=sys.executable, src=str(package.parent)),
        encoding="utf-8",
    )
    return package


def test_2_commands_keep_their_help_and_discover_a_new_owner(repo, tmp_path):
    help_text = repo.forge("--help").stdout
    expected = (
        ("init", "Set up a new repo: forge.toml, the docs skeleton, the first commit, then sync"),
        ("sync", "Write the generated adapter files and git hooks for the pinned version"),
        ("doctor", "Check tools, versions, hooks, adapter drift and the named CI checks"),
        ("migrate", "Move a client from the copied-in Forge to v1 in one pull request"),
        ("next", "Say where things stand and give the exact next command"),
        ("board", "Write and open the plain-English board page"),
    )
    for words, description in expected:
        assert description in repo.forge(words, "--help").stdout
        assert words in help_text
    assert help_text.index("init") < help_text.index("sync") < help_text.index("doctor")
    assert help_text.index("doctor") < help_text.index("migrate") < help_text.index("next")
    assert help_text.index("next") < help_text.index("board")

    package = _copy_forge(repo, tmp_path)
    (package / "probe.py").write_text(
        'def probe(args):\n    print("new owner ran")\n'
        'COMMANDS = [{"words": "probe", "run": "probe", "changes_state": False, '
        '"help": "A newly owned command", "args": [], "position": 15, '
        '"listing": "| `forge probe` | A newly owned command |"}]\n',
        encoding="utf-8",
    )
    assert "probe" in repo.forge("--help").stdout
    assert repo.forge("probe").stdout == "new owner ran\n"
    (package / "probe.py").write_text(
        'def run(args):\n    print("group command ran")\n'
        'COMMANDS = [{"words": "probe run", "run": "run", "changes_state": False, '
        '"help": "Run the probe", "args": [], "position": 15, '
        '"listing": "| `forge probe run` | Run the probe |"}]\n',
        encoding="utf-8",
    )
    assert "group help missing: probe" in repo.forge("--help").stderr
    with (package / "probe.py").open("a", encoding="utf-8") as file:
        file.write('GROUP_HELP = {"probe": "Probe commands"}\n')
    assert repo.forge("probe", "run").stdout == "group command ran\n"
    (package / "other.py").write_text('GROUP_HELP = {"probe": "Duplicate"}\n',
                                      encoding="utf-8")
    assert "group help declared twice: probe" in repo.forge("--help").stderr
