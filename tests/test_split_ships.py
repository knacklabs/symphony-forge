"""Shipped output stays compatible while new owners need no collector edit."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import conftest
import pytest

STORY = "FORGE-SPLIT-1"

# Captured from forge sync with these two client setups. Hashes use LF newlines.
# The skill hash now includes prototype demo-round guidance; all other output stays pinned.
# .gitattributes is new: it carries the roadmap's merge rule.
GOLDEN = {
    "plain": {
        ".gitattributes": "a843f971979438197905e041ead7a83c1ecb514a06ecdbb47126cd3f42c64c7a",
        "AGENTS.md": "752518c2126659d959e562d3cab725e4d39bb42611afd963e743b8932e9387af",
        ".claude/settings.json": "f0e550f035db6feb93de9aeea566253326500d5925bee3d2a41faf8b5f40df7d",
        ".codex/hooks.json": "6359773ba4fb597c6f1e4e6fc504227b419afcaa2236abd459942f8fcf99dbd8",
        ".claude/skills/forge/SKILL.md": "3d1c11ae51f1dd5841597fc4416a0380442c35e3d2d1de5fb2960360cafd600d",
        ".codex/skills/forge/SKILL.md": "3d1c11ae51f1dd5841597fc4416a0380442c35e3d2d1de5fb2960360cafd600d",
        ".claude/skills/forge/standards.md": "774eb5b730e3b96ed43b7d47a5c02cb9e4f49676c58a1b10318cb69a2f4422d1",
        ".codex/skills/forge/standards.md": "774eb5b730e3b96ed43b7d47a5c02cb9e4f49676c58a1b10318cb69a2f4422d1",
        ".claude/skills/app-baseline/SKILL.md": "2f6876a725e67c0576437824ca67dc946d77a9566b4c312e6df764f5514e6d42",
        ".codex/skills/app-baseline/SKILL.md": "2f6876a725e67c0576437824ca67dc946d77a9566b4c312e6df764f5514e6d42",
        ".claude/skills/forge/fde.md": "b6d2644c32593e06aa40598f8e9018d983770ad2c34679052778718e48e02442",
        ".codex/skills/forge/fde.md": "b6d2644c32593e06aa40598f8e9018d983770ad2c34679052778718e48e02442",
        ".claude/skills/test-audit/NOTICE.md": "05713febd8aeaca480afdc78074c66544635517e1868d3a59d7fe1cb54d70149",
        ".claude/skills/test-audit/SKILL.md": "d0bd6a7f13510241a334a5991f2b860c80283933f963603c5d88abb1e4859126",
        ".codex/skills/test-audit/NOTICE.md": "05713febd8aeaca480afdc78074c66544635517e1868d3a59d7fe1cb54d70149",
        ".codex/skills/test-audit/SKILL.md": "d0bd6a7f13510241a334a5991f2b860c80283933f963603c5d88abb1e4859126",
        ".claude/skills/remote-approval/SKILL.md": "f3d334b989b73b65f6255d874592c052db96089df476dd1f0c9efa1d95ce8e01",
        ".codex/config.toml": "d1054f20197f0e651f75e2c0641d6d6f08fb422e5754da8e93d9fefb3660bd58",
        ".github/workflows/forge.yml": "08424f7bfe80b5ad33a75b59082556503cf976aabc2b2c24155029063f8f46e5",
        "git-hook/pre-commit": "a1cec093f1d06900ee2dab2af6244ebe3060731276f0af5c9c055729ceed84ef",
        "git-hook/pre-push": "773142aa23bd5ec4e962cc9fca64a698b6a42f1a1885bf10633c24b831fbf743",
    },
}
GOLDEN["claude_node"] = {**GOLDEN["plain"],
                         "CLAUDE.md": "850d862c89806458474555ee2dbd3349e99fd2048c54b64f204155a525f0ad6a",
                         ".github/workflows/forge.yml":
                             "b59a8391b9b7a58599dd2f601f73d805069573e6a70948622bd284770cf0260a"}


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
    actual = {path: hashlib.sha256(file.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
              for path, file in files.items()}
    assert actual == GOLDEN[case]
    if case != "plain":
        return

    source = Path(__file__).resolve().parents[1] / "src" / "forge"
    package = tmp_path / "package" / "forge"
    shutil.copytree(source, package)
    root = source.parents[1]
    for rel in (".codex/skills/forge/fde.md", ".codex/skills/app-baseline/SKILL.md",
                ".codex/skills/test-audit/SKILL.md",
                ".codex/skills/test-audit/NOTICE.md",
                ".claude/skills/remote-approval/SKILL.md"):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, target)
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
