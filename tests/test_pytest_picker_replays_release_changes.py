"""A release's non-Python filenames must not pull most tests into the quick run."""
import json
import shutil
import sys
from pathlib import Path

from conftest import ROOT

STORY = "FIX-PICKER-TWO-RULES"


def test_5_release_1_2_6_changes_select_fewer_than_71_test_files(repo):
    # Frozen v1.2.6 parent/tag paths, Python content and shared inputs need no tags
    # in shallow CI clones. Other non-Python content uses markers: only its path
    # can affect selection. Current tests remain the candidate suite.
    changes = json.loads((ROOT / "tests/fixtures/release-v1.2.6-picker/changes.json").read_text("utf-8"))
    shutil.copytree(ROOT / "src", repo.path / "src")
    (repo.path / "tests").mkdir()
    for path in (ROOT / "tests").glob("*.py"):
        shutil.copy2(path, repo.path / "tests" / path.name)
    for phase in ("before", "after"):
        for name, snapshot in changes.items():
            if snapshot[phase] is not None:
                repo.write(name, snapshot[phase])
            elif (repo.path / name).exists():
                (repo.path / name).unlink()
        config = repo.path / "forge.toml"
        command = f'"{Path(sys.executable).as_posix()}" -m pytest tests --collect-only -q'
        text = config.read_text("utf-8")
        lines = ["test = " + json.dumps(command) if line.startswith("test = ") else line
                 for line in text.splitlines()]
        config.write_text("\n".join(lines) + "\n", "utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Replay release " + phase)
        if phase == "before":
            base = repo.git("rev-parse", "HEAD")
    result = repo.forge("test", "--pytest", base)
    related = next(line for line in result.stdout.splitlines() if line.startswith("Related tests: "))
    selected = related.removeprefix("Related tests: ").split(", ")
    assert 0 < len(selected) < 71, related
    assert result.returncode == 0, result.stdout + result.stderr
