"""Sync keeps an unavailable chat and still preserves the other local chats.

Audit: the command must finish, warn once and retain the unavailable record.
A stale registered worktree previously became a missing subprocess cwd. Existing
sync tests remove worktrees through Git, which removes their registrations too.
This uses real Git and sync, with no production seam or mocked migration.
New and earlier-adopted clients use this same migration path.
"""
import json
import shutil

from test_codex_worker import sdk_data  # noqa: F401
from test_records import SPEC
from test_story import worktree
from test_worker_and_reader_chats_survive_rounds import _client_reader

STORY = "sync-survives-missing-chat-checkout"


def test_1_sync_warns_and_keeps_a_missing_chat_while_other_chats_move(
        repo, monkeypatch, tmp_path, sdk_data):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, "codex", adopted=False)
    records = repo.path / ".git/forge/threads/read"
    records.mkdir(parents=True, exist_ok=True)
    missing = records / "SHOP.json"
    missing.write_text(json.dumps({"checkout": reader.shop.as_posix(),
                                   "conversation": "missing-checkout-chat"}), encoding="utf-8")
    original = missing.read_bytes()
    shutil.rmtree(reader.shop)  # A temporary folder disappears without git worktree remove.

    started = repo.forge("fix", "start", "Keep invoice chat", "--done", "Invoice chat survives")
    assert started.returncode == 0, started.stdout + started.stderr
    owner = worktree(repo, "fix/keep-invoice-chat")
    spec = owner / "docs/specs/invoices.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC, encoding="utf-8")
    repo.git("add", "docs/specs/invoices.md", cwd=owner)
    repo.git("commit", "-qm", "Add invoice plan", cwd=owner)
    (records / "invoices.json").write_text(json.dumps({
        "checkout": owner.as_posix(), "conversation": "invoice-chat"}), encoding="utf-8")

    synced = repo.forge("sync", cwd=owner)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert [line for line in synced.stdout.splitlines() if line.startswith("Warning:") and "chat" in line] == [
        "Warning: The checkout for SHOP's chat no longer exists. Its saved chat record stays on this machine."]
    assert missing.read_bytes() == original
    assert "conversation: invoice-chat" in (owner / "docs/specs/invoices.read.md").read_text("utf-8")
