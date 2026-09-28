"""FORGE-SPLIT-1 command declarations at the installed command boundary."""
from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

import conftest

STORY = "FORGE-SPLIT-1"
SOURCE = Path(__file__).resolve().parents[1] / "src" / "forge"
BASELINE = "35a7324dc31a8e34db3b53c99af32a4e8ff7d330"  # main before COLLECTOR


def _copy_forge(repo, tmp_path):
    package = tmp_path / "plugged" / "forge"
    shutil.copytree(SOURCE, package)
    (repo.bin / "forge").write_text(
        conftest.FORGE_SHIM.format(python=sys.executable, src=str(package.parent)),
        encoding="utf-8",
    )
    return package


def test_2_commands_keep_their_help_and_discover_a_new_owner(repo, tmp_path):
    old_cli = subprocess.run(
        ["git", "show", f"{BASELINE}:src/forge/cli.py"], cwd=SOURCE.parents[1],
        check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    table = next(node.value for node in ast.parse(old_cli).body
                 if isinstance(node, ast.Assign)
                 and [getattr(target, "id", "") for target in node.targets] == ["TABLE"])
    commands = [tuple(row.elts[0].value.split()) for row in table.elts]
    groups = {(words[0],) for words in commands if len(words) > 1}
    help_args = [(), *sorted(groups), *commands]
    current = {words: repo.forge(*words, "--help") for words in help_args}

    baseline_package = tmp_path / "baseline" / "forge"
    shutil.copytree(SOURCE, baseline_package)
    (baseline_package / "cli.py").write_text(old_cli, encoding="utf-8")
    (repo.bin / "forge").write_text(
        conftest.FORGE_SHIM.format(python=sys.executable, src=str(baseline_package.parent)),
        encoding="utf-8",
    )
    for words in help_args:
        before, after = repo.forge(*words, "--help"), current[words]
        assert (before.returncode, before.stdout, before.stderr) == (
            after.returncode, after.stdout, after.stderr), f"help changed for forge {' '.join(words)}"

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
