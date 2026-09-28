"""Shipped output stays compatible while new owners need no collector edit."""

import json
import shutil
import sys
from pathlib import Path

import conftest
import pytest

STORY = "FORGE-SPLIT-1"

ROOT = Path(__file__).resolve().parents[1]
# Each shipped file sync copies as it is, with the file it copies. Old contract: pinned sha256
# hashes of the whole output, so every skill edit broke this test and two edits conflicted here.
# New contract: sync writes these byte for byte from their source, whatever the source says.
SOURCES = {
    **{f"{host}/{rel}": source for host in (".claude", ".codex") for rel, source in {
        "skills/forge/SKILL.md": "src/forge/templates/skill.md",
        "skills/forge/standards.md": "src/forge/standards.md",
        "skills/forge/fde.md": ".codex/skills/forge/fde.md",
        "skills/app-baseline/SKILL.md": ".codex/skills/app-baseline/SKILL.md",
        "skills/test-audit/NOTICE.md": ".codex/skills/test-audit/NOTICE.md",
        "skills/test-audit/SKILL.md": ".codex/skills/test-audit/SKILL.md",
    }.items()},
    ".claude/skills/remote-approval/SKILL.md": ".claude/skills/remote-approval/SKILL.md",
}
# Built from code rather than copied; their own tests check what they say.
GENERATED = {"plain": {".claude/settings.json", ".codex/hooks.json", ".codex/config.toml",
                       ".github/workflows/forge.yml", "git-hook/pre-commit", "git-hook/pre-push"}}
GENERATED["claude_node"] = GENERATED["plain"] | {"CLAUDE.md"}


@pytest.mark.parametrize("case", ["plain", "claude_node"])
def test_3_sync_keeps_previous_output_and_gathers_new_owner(repo, case, tmp_path):
    repo.git("checkout", "-q", "-b", "fix/sync-compatibility")
    repo.write("forge.toml", 'version = "v1.1.0"\ntest = "echo ok"\n'
                             'checks = ["tests", "forge-pr-check"]\n')
    if case == "claude_node":
        repo.write("CLAUDE.md", "# Team notes\n")
        repo.write("package.json", json.dumps({"engines": {"node": "20"}}))
        repo.write(".nvmrc", "20\n")
    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    paths = [line.removeprefix("Wrote ") for line in result.stdout.splitlines()
             if line.startswith("Wrote ")]
    hooks = Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    files = {**{path: repo.path / path for path in paths},
             **{f"git-hook/{name}": hooks / name for name in ("pre-commit", "pre-push")}}
    assert set(files) == {"AGENTS.md", *SOURCES, *GENERATED[case]}
    for path, source in SOURCES.items():
        assert files[path].read_bytes() == (ROOT / source).read_bytes(), path
    agents = (ROOT / "src/forge/templates/adapters/AGENTS.md").read_text(encoding="utf-8")
    assert files["AGENTS.md"].read_text(encoding="utf-8") == (
        f"<!-- forge:begin -->\n{agents.rstrip()}\n<!-- forge:end -->\n")
    if case != "plain":
        return

    package = tmp_path / "package" / "forge"
    shutil.copytree(ROOT / "src" / "forge", package)
    for rel in (".codex/skills/forge/fde.md", ".codex/skills/app-baseline/SKILL.md",
                ".codex/skills/test-audit/SKILL.md",
                ".codex/skills/test-audit/NOTICE.md",
                ".claude/skills/remote-approval/SKILL.md"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, target)
    launcher = repo.bin / "forge"
    launcher.write_text(conftest.FORGE_SHIM.format(python=sys.executable,
                                                  src=str(package.parent)), encoding="utf-8")
    before = {rel: file.read_bytes() for rel, file in files.items()}
    (package / "new_ship.py").write_text(
        'def ships(top, cfg):\n    return {"docs/new-owner.md": "Shipped by its owner.\\n"}\n',
        encoding="utf-8")
    second = repo.forge("sync")
    assert second.returncode == 0, second.stderr
    assert "Wrote docs/new-owner.md" in second.stdout
    assert (repo.path / "docs/new-owner.md").read_bytes() == b"Shipped by its owner.\n"
    assert before == {rel: file.read_bytes() for rel, file in files.items()}
