"""Decision records use the real read command and keep the spec cold-read lifecycle."""
import json

import pytest

from test_fix_plan_reads_capped import _client
from test_readloop_gates import dispose_all, say
from test_story import worktree

STORY = "FIX-READ-DECISIONS"


@pytest.mark.platform
@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption-upgrade-sync"])
def test_1_decisions_get_cold_read_rounds(repo, gh, tmp_path, previous):
    _client(repo, gh, tmp_path, previous)
    started = repo.forge("fix", "start", "Choose private storage", "--done", "The decision is read")
    assert started.returncode == 0, started.stdout + started.stderr
    where = worktree(repo, "fix/choose-private-storage")
    created = repo.forge("decision", "new", "private-storage", cwd=where)
    assert created.returncode == 0, created.stdout + created.stderr
    doc = next((where / "docs/decisions").glob("[0-9]*-private-storage.md"))
    doc.write_text(doc.read_text("utf-8").replace(
        "<!-- What was decided, in one or two sentences. -->",
        "Store private records on the company's server."), encoding="utf-8")
    notes = doc.with_suffix(".read.md")
    say(repo, "1. Blocking: The decision has no retention period.\n")
    first = repo.forge("read", "private-storage", cwd=where)
    assert first.returncode == 0, first.stdout + first.stderr
    assert "round: 1\n" in notes.read_text("utf-8")
    assert "passed: no\n" in notes.read_text("utf-8")
    held = repo.forge("read", "private-storage", cwd=where)
    assert held.returncode == 1 and "has no disposition" in held.stderr
    dispose_all(notes)
    doc.write_text(doc.read_text("utf-8") + "\nDelete records after thirty days.\n", encoding="utf-8")
    say(repo, "No findings.\n")
    second = repo.forge("read", "private-storage", cwd=where)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "round: 2\n" in notes.read_text("utf-8")
    assert "passed: yes\n" in notes.read_text("utf-8")
    assert "status: proposed\n" in doc.read_text("utf-8")
    assert repo.git("status", "--porcelain", cwd=where) == ""
    assert {doc.relative_to(where).as_posix(), notes.relative_to(where).as_posix()} <= set(
        repo.git("show", "--format=", "--name-only", "HEAD", cwd=where).splitlines())
    prompts = [json.loads(line)["prompt"] for line in
               (repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()]
    assert len(prompts) == 2
    assert doc.relative_to(where).as_posix() in prompts[0]
    assert "Store private records on the company's server." in prompts[0]
    assert "For a decision" in prompts[0]
    assert "The decision has no retention period." in prompts[1]
    assert "Disposition: cut" in prompts[1]
    assert "+Delete records after thirty days." in prompts[1]
    for host in (".codex", ".claude"):
        guide = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "forge read <decision-slug>" in guide
