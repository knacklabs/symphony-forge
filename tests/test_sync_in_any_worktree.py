"""forge sync writes its generated files in any worktree, even when other worktrees hold copies
of a spec whose earlier reader chat it would otherwise look for; that chat stays recoverable."""
import pytest

from test_codex_worker import sdk_data  # noqa: F401 (a fixture)
from test_records import SPEC
from test_story import worktree
from test_worker_and_reader_chats_survive_rounds import _client_reader, _old_round, _reader_chat

STORY = "sync-in-any-worktree"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
@pytest.mark.parametrize("family", ["codex", "claude"])
def test_1_sync_writes_generated_files_while_two_worktrees_hold_one_spec(
        repo, monkeypatch, tmp_path, sdk_data, family, adopted):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, family, adopted)
    reader.say("No findings.\n")
    started = repo.forge("fix", "start", "Plan invoices", "--done", "The plan is read")
    assert started.returncode == 0, started.stdout + started.stderr
    owner = worktree(repo, "fix/plan-invoices")
    spec = owner / "docs/specs/invoices.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC, encoding="utf-8")
    saved = repo.forge("spec", "save", "invoices", cwd=owner)
    assert saved.returncode == 0, saved.stdout + saved.stderr
    # Control: a fresh checkout of the same branch, synced while no reader chat needs an owner.
    control = tmp_path / "control"
    repo.git("worktree", "add", "-qb", "fix/control", str(control), "fix/plan-invoices")
    control_sync = repo.forge("sync", cwd=control)
    assert control_sync.returncode == 0, control_sync.stdout + control_sync.stderr
    expected = {line[6:] for line in control_sync.stdout.splitlines() if line.startswith("Wrote ")}
    assert "Warning" not in control_sync.stdout
    assert {".claude/skills/forge/SKILL.md", ".codex/skills/forge/SKILL.md", ".codex/hooks.json",
            ".claude/settings.json", ".github/workflows/forge.yml"} < expected
    repo.git("worktree", "remove", "--force", str(control))
    repo.git("branch", "-D", "fix/control")
    # An earlier release kept the reader chat only on this machine.
    _old_round(repo, tmp_path, owner, "read", "invoices")
    first = _reader_chat(reader)
    # A second worktree takes its own copy of the spec, and the reader's checkout moves, so
    # both worktrees hold the spec while sync runs and neither is the recorded one.
    copied = tmp_path / "copied spec"
    repo.git("worktree", "add", "-qb", "fix/copied-plan", str(copied), "fix/plan-invoices")
    moved = tmp_path / "moved reader checkout"
    repo.git("worktree", "move", str(owner), str(moved))

    # Like the control, the fresh worktree has none of the generated files.
    synced = repo.forge("sync", cwd=copied)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert {line[6:] for line in synced.stdout.splitlines() if line.startswith("Wrote ")} == expected
    assert all((copied / rel).is_file() for rel in expected)
    assert synced.stdout.endswith(
        "Warning: More than one worktree holds docs/specs/invoices.md, so sync can't tell which "
        "branch owns its earlier reader chat.\n"
        "The earlier reader conversation for invoices stays on this machine only; run forge read "
        "invoices on its own branch before removing .git/forge to keep it.\n")
    again = repo.forge("sync", cwd=copied)
    assert again.returncode == 0, again.stdout + again.stderr
    # A second sync finds nothing to write: the first wrote every generated file.
    assert "Nothing to change" in again.stdout and "Wrote" not in again.stdout
    # The reader's chat is still there for the next read of the spec in its own branch.
    reread = repo.forge("read", "invoices", cwd=moved)
    assert reread.returncode == 0, reread.stdout + reread.stderr
    assert "Starting a new" not in reread.stdout
    assert _reader_chat(reader, resumed=True) == first
