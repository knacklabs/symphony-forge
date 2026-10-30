"""Sync refreshes task adapters without turning that task into a Forge upgrade."""
from __future__ import annotations

import shutil
import tomllib

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version

STORY = "no-wasted-rounds"


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
def test_4_sync_in_a_task_worktree_preserves_the_forge_pin(repo, gh, tmp_path, adopted):
    # Sync already regenerates adapters on any branch; this guards the distinct risk that
    # an adapter refresh in a task also starts an unrequested version upgrade.
    version = _version(repo)
    if adopted:
        client = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client,
                        dirs_exist_ok=True)
        settings = client / "forge.toml"
        settings.write_text(settings.read_text("utf-8").replace('"v1.2.2"', f'"{version}"'),
                            encoding="utf-8")
        repo.git("switch", "-qc", "adoption")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade the earlier adoption")
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    task = tmp_path / "task checkout"
    repo.git("worktree", "add", "-qb", "task/SHOP-SAVE", str(task), cwd=client)
    before = (task / "forge.toml").read_bytes()
    # An upgrade lands after the task starts. Keep the installed release on the
    # task so this exercises real sync, without faking release dispatch through uv.
    # The task pin is older than the fetched default, which sync must not inherit.
    repo.git("config", "core.hooksPath", str(tmp_path / "no-hooks"), cwd=client)
    repo.git("switch", "-qc", "fix/upgrade", cwd=client)
    major, minor, patch = map(int, version.removeprefix("v").split("."))
    newer = f"v{major}.{minor}.{patch + 1}"
    settings = client / "forge.toml"
    settings.write_text(settings.read_text("utf-8").replace(f'"{version}"', f'"{newer}"'),
                        encoding="utf-8")
    repo.git("add", "forge.toml", cwd=client)
    repo.git("commit", "-qm", "Upgrade the default branch", cwd=client)
    repo.git("push", "-q", "origin", "HEAD:main", cwd=client)
    repo.git("fetch", "-q", "origin", cwd=client)
    assert tomllib.loads(repo.git("show", "origin/main:forge.toml", cwd=task))["version"] == newer
    assert tomllib.loads(before.decode("utf-8"))["version"] == version
    # Force real adapter work even in the newly initialized repo.
    guide = task / ".codex/skills/forge/SKILL.md"
    guide.write_text("An adapter from an earlier release.\n", encoding="utf-8")

    synced = repo.forge("sync", cwd=task)

    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "Wrote .codex/skills/forge/SKILL.md" in synced.stdout
    assert guide.read_text("utf-8") != "An adapter from an earlier release.\n"
    assert (task / "forge.toml").read_bytes() == before
    assert repo.git("diff", "--", "forge.toml", cwd=task) == ""
