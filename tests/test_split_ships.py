"""A new shipping owner is picked up through the real sync command."""

import shutil
from pathlib import Path

STORY = "FORGE-SPLIT-1"


def test_3_sync_gathers_a_new_modules_file_without_changing_existing_output(repo, tmp_path):
    source = Path(__file__).resolve().parents[1] / "src" / "forge"
    package = tmp_path / "package" / "forge"
    shutil.copytree(source, package)
    root = source.parents[1]
    for rel in (".codex/skills/forge/fde.md", ".codex/skills/test-audit/SKILL.md",
                ".codex/skills/test-audit/NOTICE.md",
                ".claude/skills/remote-approval/SKILL.md"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, target)
    launcher = repo.bin / "forge"
    launcher.write_text(launcher.read_text(encoding="utf-8").replace(
        str(source.parent), str(package.parent)), encoding="utf-8")
    repo.git("checkout", "-q", "-b", "fix/sync-owners")
    repo.write("forge.toml", 'version = "v1.1.0"\ntest = "echo ok"\n')

    first = repo.forge("sync")
    assert first.returncode == 0, first.stderr
    before = {str(path.relative_to(repo.path)): path.read_bytes()
              for path in repo.path.rglob("*") if path.is_file() and ".git" not in path.parts}

    (package / "new_ship.py").write_text(
        'def ships(top, cfg):\n    return {"docs/new-owner.md": "Shipped by its owner.\\n"}\n',
        encoding="utf-8")
    second = repo.forge("sync")
    assert second.returncode == 0, second.stderr
    assert "Wrote docs/new-owner.md" in second.stdout
    assert (repo.path / "docs/new-owner.md").read_bytes() == b"Shipped by its owner.\n"
    assert before == {rel: (repo.path / rel).read_bytes() for rel in before}
