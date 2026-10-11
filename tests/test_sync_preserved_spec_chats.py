"""Ordinary sync does not search unrelated branches for landed reader bindings.

Real reads publish the bindings and Git removes their original checkouts. Git's
own trace observes work added by unrelated branches; only external readers are faked.
"""
import json
import shutil

import pytest

from test_codex_worker import sdk_data  # noqa: F401
from test_records import SPEC
from test_story import worktree
from test_worker_and_reader_chats_survive_rounds import _client_reader, _reader_chat

STORY = "reuse-worker-chats"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
@pytest.mark.parametrize("family", ["codex", "claude"])
def test_23_sync_cost_for_preserved_spec_chats_does_not_grow_with_work_branches(
        repo, monkeypatch, tmp_path, sdk_data, adopted, family):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, family, adopted)
    reader.say("No findings.\n")
    chats = {}
    for slug in ("invoices", "payments"):
        started = repo.forge("fix", "start", f"Publish {slug} plan", "--done", "The plan is read")
        assert started.returncode == 0, started.stdout + started.stderr
        branch = f"fix/publish-{slug}-plan"
        owner = worktree(repo, branch)
        spec = owner / f"docs/specs/{slug}.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(SPEC.replace("INV-", f"{slug.upper()}-"), encoding="utf-8")
        saved = repo.forge("spec", "save", slug, cwd=owner)
        assert saved.returncode == 0, saved.stdout + saved.stderr
        read = repo.forge("read", slug, cwd=owner)
        assert read.returncode == 0, read.stdout + read.stderr
        chats[slug] = _reader_chat(reader)
        repo.git("merge", "-q", "--ff-only", branch)
        repo.git("worktree", "remove", str(owner))
        repo.git("branch", "-D", branch)
        repo.git("push", "-q", "origin", "main")

    metadata = repo.path / ".git/forge"
    if family == "codex":
        stale = tmp_path / "earlier machine chat records"
        shutil.copytree(metadata, stale)
        started = repo.forge("fix", "start", "Replace invoice reader", "--done", "The replacement is read")
        assert started.returncode == 0, started.stdout + started.stderr
        branch = "fix/replace-invoice-reader"
        owner = worktree(repo, branch)
        reader.lose()
        # Keep the native stub's next ID distinct after its old rollout disappears.
        (repo.bin / "threads.json").write_text(json.dumps({"unrelated": {"cwd": str(owner)}}),
                                              encoding="utf-8")
        read = repo.forge("read", "invoices", cwd=owner)
        assert read.returncode == 0, read.stdout + read.stderr
        assert "Starting a new" in read.stdout
        replacement = _reader_chat(reader)
        assert replacement != chats["invoices"]
        chats["invoices"] = replacement
        repo.git("merge", "-q", "--ff-only", branch)
        repo.git("worktree", "remove", str(owner))
        repo.git("branch", "-D", branch)
        repo.git("push", "-q", "origin", "main")
        shutil.rmtree(metadata)
        shutil.copytree(stale, metadata)
    # Codex can also recover a missing local JSON from its terminal native-turn log.
    if family == "codex":
        (metadata / "threads/read/payments.json").unlink()
    upgrade = tmp_path / "ordinary sync checkout"
    repo.git("worktree", "add", "-qb", "fix/chat-upgrade", str(upgrade), "main")
    trace = tmp_path / "sync-git-trace.jsonl"

    def shows():
        trace.unlink(missing_ok=True)
        with monkeypatch.context() as tracing:
            tracing.setenv("GIT_TRACE2_EVENT", trace.as_posix())
            synced = repo.forge("sync", cwd=upgrade)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        calls = [json.loads(line) for line in trace.read_text("utf-8").splitlines()]
        return sum(call.get("event") == "start" and call.get("argv", [])[1:2] == ["show"]
                   for call in calls)

    before = shows()
    for number in range(6):
        repo.git("branch", f"fix/unrelated-work-{number}", "main")
    after = shows()
    assert after <= before, f"Six unrelated branches added {after - before} git show calls to sync"

    shutil.rmtree(metadata)
    started = repo.forge("fix", "start", "Continue invoice plan", "--done", "The reader keeps its context")
    assert started.returncode == 0, started.stdout + started.stderr
    owner = worktree(repo, "fix/continue-invoice-plan")
    read = repo.forge("read", "invoices", cwd=owner)
    assert read.returncode == 0, read.stdout + read.stderr
    assert "Starting a new" not in read.stdout
    assert _reader_chat(reader, resumed=True) == chats["invoices"]
