"""The source command page follows the declarations without changing client output."""

import shutil
import sys
from pathlib import Path

import conftest

STORY = "FORGE-SPLIT-1"
ROOT = Path(__file__).resolve().parents[1]


def _source_repo(repo):
    repo.git("checkout", "-q", "-b", "fix/command-page")
    repo.write("forge.toml", 'version = "v1.2.6"\nrepo = "forge-source"\n')
    return repo


def test_4_sync_keeps_the_command_page_current(repo):
    _source_repo(repo)
    repo.write("docs/commands.md", "Out of date\n")
    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    assert "Wrote docs/commands.md" in result.stdout
    generated = (repo.path / "docs/commands.md").read_bytes()
    assert generated == (ROOT / "docs/commands.md").read_text(encoding="utf-8").encode("utf-8"), "Command page is stale; run forge sync."
    guide = (ROOT / "docs/guide.md").read_text(encoding="utf-8")
    assert "[command list](commands.md)" in guide
    assert "| Command | What it does |" not in guide
    assert b"| `forge sync` |" in generated


def test_5_new_owners_join_the_page_and_shipped_files(repo, tmp_path):
    _source_repo(repo)
    package = tmp_path / "plugged" / "forge"
    shutil.copytree(ROOT / "src/forge", package)
    (repo.bin / "forge").write_text(
        conftest.FORGE_SHIM.format(python=sys.executable, src=str(package.parent)), encoding="utf-8")
    for rel in (".codex/skills/forge/fde.md", ".codex/skills/app-baseline/SKILL.md",
                ".codex/skills/test-audit/SKILL.md",
                ".codex/skills/test-audit/NOTICE.md", ".claude/skills/remote-approval/SKILL.md"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    (package / "new_command.py").write_text(
        'def run(args):\n    print("New owner ran")\n'
        'COMMANDS = [{"words": "new-owner", "run": "run", "changes_state": False, '
        '"help": "Run new owner", "args": [], "position": 15, '
        '"listing": "| `forge new-owner` | Runs the new owner |"}]\n', encoding="utf-8")
    (package / "new_ship.py").write_text(
        'def ships(top, cfg):\n    return {"docs/new-owner.md": "New owner file.\\n"}\n',
        encoding="utf-8")
    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    assert "Wrote docs/new-owner.md" in result.stdout
    assert "Wrote docs/commands.md" in result.stdout
    assert (repo.path / "docs/new-owner.md").read_text() == "New owner file.\n"
    page = (repo.path / "docs/commands.md").read_text()
    assert page.index("| `forge init` |") < page.index("| `forge new-owner` |") < page.index("| `forge sync` |")
    assert "| `forge new-owner` | Runs the new owner |" in page
    assert repo.forge("new-owner").stdout == "New owner ran\n"
