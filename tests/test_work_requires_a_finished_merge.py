"""Work refuses unfinished merges without changing the index or launching a worker.

Real command/git proof owns this regression; existing worker tests start clean.
Only Claude is faked at its external edge, with no production test seam.
"""
import shutil
import subprocess

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version
from test_task import story
from test_worker import calls, install_claude

STORY = "work-during-merge"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
@pytest.mark.parametrize("kind", ["task", "fix"])
@pytest.mark.parametrize("conflict", ["merge.txt", "forge.toml"])
def test_1_work_requires_resolving_and_committing_the_default_branch_merge(
        repo, gh, tmp_path, adopted, kind, conflict):
    version = _version(repo)
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("switch", "-qc", "adoption")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "adoption")
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    repo.git("switch", "-qc", "fix/upgrade")
    repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n'
               'models.build = { model = "sonnet", effort = "medium" }\n'
               'models.lite = { model = "sonnet", effort = "medium" }\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".codex", ".claude"):
        skill = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "resolve any unfinished merge in the item's checkout" in skill
    repo.git("add", "-A")
    # Seed an already landed upgrade, before a Forge item exists to own this setup.
    no_hooks = f"core.hooksPath={tmp_path / 'no-hooks'}"
    repo.git("-c", no_hooks, "commit", "-qm", "Upgrade client")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/upgrade")
    repo.git("-c", no_hooks, "push", "-q", "origin", "main")
    log = install_claude(repo)
    if kind == "task":
        story(repo)
        item = "BOARD/PAGE"
        started = repo.forge("task", "start", item)
    else:
        item = "login"
        started = repo.forge("fix", "start", "Fix login", "--done", "Login works",
                             "--slug", item)
    assert started.returncode == 0, started.stdout + started.stderr
    folder = repo.path.parent / (f"{repo.path.name}-BOARD-PAGE" if kind == "task"
                                else f"{repo.path.name}-fix-{item}")
    settings = (folder / "forge.toml").read_text("utf-8")
    branch_text = (settings.replace('effort = "medium"', 'effort = "high"')
                   if conflict == "forge.toml" else "Branch work\n")
    default_text = (settings.replace('effort = "medium"', 'effort = "low"')
                    if conflict == "forge.toml" else "Default work\n")
    (folder / conflict).write_text(branch_text, "utf-8")
    repo.git("add", conflict, cwd=folder)
    repo.git("commit", "-qm", "Branch work", cwd=folder)
    repo.git("switch", "-qc", "fix/default-change")
    repo.write(conflict, default_text)
    repo.git("add", conflict)
    repo.git("-c", no_hooks, "commit", "-qm", "Default work")
    repo.git("-c", no_hooks, "push", "-q", "origin", "HEAD:main")
    merged = subprocess.run(["git", "merge", "--no-edit", "origin/main"], cwd=folder,
                            capture_output=True, text=True)
    assert merged.returncode == 1, merged.stdout + merged.stderr
    assert repo.git("diff", "--name-only", "--diff-filter=U", cwd=folder) == conflict
    head = repo.git("rev-parse", "HEAD", cwd=folder)
    status = repo.git("status", "--porcelain", cwd=folder)
    index = repo.git("ls-files", "--stage", cwd=folder)
    expected = (f"Resolve the merge conflicts, if any, in {folder}, then commit the merge.\n"
                f"Next: forge work {item}\n")
    refused = repo.forge("work", item)
    assert refused.returncode == 1
    assert refused.stderr == expected
    inside = repo.forge("work", item, cwd=folder)
    assert inside.returncode == 1 and inside.stderr == expected
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head
    assert repo.git("status", "--porcelain", cwd=folder) == status
    assert repo.git("ls-files", "--stage", cwd=folder) == index
    assert repo.git("rev-parse", "MERGE_HEAD", cwd=folder) == repo.git("rev-parse", "origin/main")
    assert calls(log) == []
    # Resolving the files alone still leaves a merge pending; no partial commit is safe yet.
    (folder / conflict).write_text(settings if conflict == "forge.toml"
                                  else "Both changes kept\n", "utf-8")
    repo.git("add", conflict, cwd=folder)
    index = repo.git("ls-files", "--stage", cwd=folder)
    pending = repo.forge("work", item, cwd=folder)
    assert pending.returncode == 1 and pending.stderr == expected
    assert repo.git("ls-files", "--stage", cwd=folder) == index
    assert calls(log) == []
    repo.git("commit", "-qm", "Resolve the merge", cwd=folder)
    retried = repo.forge("work", item, cwd=folder)
    assert retried.returncode == 0, retried.stdout + retried.stderr
    assert len(calls(log)) == 1
