"""Upgrade keeps an amended spec's reader on its retained work branch.

The existing moved-owner cases introduce a spec absent from the default branch.
This case keeps that default copy while the amendment's checkout is removed;
only the external readers are faked, and the final read proves durable recovery.
"""
import shutil

import pytest

from test_codex_worker import sdk_data  # noqa: F401
from test_records import SPEC
from test_story import worktree
from test_worker_and_reader_chats_survive_rounds import (
    _client_reader, _old_round, _reader_chat, _sync_elsewhere,
)

STORY = "reuse-worker-chats"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
@pytest.mark.parametrize("family,amended,failed", [
    (family, amended, False) for family in ("codex", "claude") for amended in (True, False)
] + [("codex", False, True)], ids=[
    "codex-changed-spec", "codex-unchanged-spec", "claude-changed-spec",
    "claude-unchanged-spec", "codex-failed-unchanged-spec",
])
def test_22_upgrade_keeps_removed_spec_amendment_reader_on_its_branch(
        repo, monkeypatch, tmp_path, sdk_data, adopted, family, amended, failed):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, family, adopted)
    started = repo.forge("fix", "start", "Publish invoice plan", "--done", "The plan is saved")
    assert started.returncode == 0, started.stdout + started.stderr
    published = worktree(repo, "fix/publish-invoice-plan")
    spec = published / "docs/specs/invoices.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC, encoding="utf-8")
    saved = repo.forge("spec", "save", "invoices", cwd=published)
    assert saved.returncode == 0, saved.stdout + saved.stderr
    repo.git("merge", "-q", "--ff-only", "fix/publish-invoice-plan")
    repo.git("worktree", "remove", str(published))
    repo.git("branch", "-D", "fix/publish-invoice-plan")
    repo.git("push", "-q", "origin", "main")

    started = repo.forge("fix", "start", "Amend invoice plan", "--done", "The amendment is read")
    assert started.returncode == 0, started.stdout + started.stderr
    branch = "fix/amend-invoice-plan"
    owner = worktree(repo, branch)
    spec = owner / "docs/specs/invoices.md"
    if amended:
        spec.write_text(SPEC.replace("## Roadmap", "Invoices also show their payment date.\n\n## Roadmap"),
                        encoding="utf-8")
        saved = repo.forge("spec", "save", "invoices", cwd=owner)
        assert saved.returncode == 0, saved.stdout + saved.stderr
    reader.say("No findings.\n")
    if failed:
        reader.fail(True)
    read = _old_round(repo, tmp_path, owner, "read", "invoices", expect_success=not failed)
    first = _reader_chat(reader)
    if failed:
        assert "Codex reported the turn failed" in read.stderr
        assert not (owner / "docs/specs/invoices.read.md").exists()
        reader.fail(False)
    if repo.git("diff", "--name-only", "--", "forge.toml", cwd=owner):
        repo.git("commit", "-qam", "Keep the current Forge pin", "--", "forge.toml", cwd=owner)
    repo.git("worktree", "remove", str(owner))

    upgrade, _ = _sync_elsewhere(repo, tmp_path)
    assert "Invoices also show their payment date." not in (
        upgrade / "docs/specs/invoices.md").read_text("utf-8")
    shutil.rmtree(repo.path / ".git/forge")
    recreated = tmp_path / "recreated amendment with spaces"
    repo.git("worktree", "add", "-q", str(recreated), branch)
    read = repo.forge("read", "invoices", cwd=recreated)
    assert read.returncode == 0, read.stdout + read.stderr
    assert "Starting a new" not in read.stdout
    assert _reader_chat(reader, resumed=True) == first
