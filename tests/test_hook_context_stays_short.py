"""The session-start context lists at most three hotspots and points to forge next."""
import json
import time

import pytest

from test_proto_signoff import _client, _decision
from test_spotted import entry
from test_story import setup

STORY = "FIX-HOOK-CONTEXT-STAYS-SHORT"
pytestmark = pytest.mark.platform


def test_1_hook_context_with_many_hotspots_stays_short(repo):
    setup(repo)
    items = []
    for number in range(8):
        name = f"file{number}.md"
        repo.write(name, "x\n")
        items += [entry("bug", name, 1, f"Problem {n}", "worker", item="old") for n in range(3)]
    repo.write("plans/spotted.json", json.dumps({"items": items}))
    repo.git("add", ".")
    repo.git("commit", "-q", "-m", "Note problems")
    repo.git("push", "-q", "origin", "main")

    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    full = shown.stdout
    assert full.count("keeps breaking") == 8
    context = repo.forge("hook", "context").stdout
    assert context.count("keeps breaking") == 3
    assert "forge fix start \"Simplify" not in context
    assert "5 more files keep breaking. Run forge next for the list." in context
    assert context.rstrip().endswith("Run forge next for the full picture.")


def test_2_hook_context_is_fast_and_offline_in_a_client_repo(repo, tmp_path, monkeypatch):
    fix, answers, _ = _client(repo, tmp_path, monkeypatch, working_build=True)
    old = [entry("bug", "PRODUCT.md", 1, text, "worker", item="prototype")
           for text in ("Alpha", "Beta", "Gamma")]
    path = fix / "plans/spotted.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"items": old}), encoding="utf-8")
    repo.git("add", "plans/spotted.json", cwd=fix)
    repo.git("commit", "-q", "-m", "Note prototype problems", cwd=fix)
    _decision(fix, answers)
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    branch = repo.git("branch", "--show-current", cwd=fix)
    repo.git("merge", "--no-ff", "-m", "Merge sign-off", branch)
    fresh = []
    for number in range(6):
        repo.write(f"file{number}.md", "x\n")
        fresh += [entry("bug", f"file{number}.md", 1, f"Problem {n}", "worker", item="later")
                  for n in range(3)]
    repo.write("plans/spotted/later.json", json.dumps({"items": fresh}))
    repo.git("add", ".")
    repo.git("commit", "-q", "-m", "Note later problems")
    repo.git("push", "-q", "origin", "main")
    # The session hook must not fetch: with the remote gone it still answers at once, within
    # a worker's start-up limit.
    repo.git("remote", "set-url", "origin", str(tmp_path / "gone"))
    started = time.monotonic()
    context = repo.forge("hook", "context")
    assert time.monotonic() - started < 10
    assert context.returncode == 0, context.stdout + context.stderr
    assert context.stdout.count("keeps breaking") == 3
    assert "PRODUCT.md keeps breaking" not in context.stdout  # noted before sign-off
    assert "3 more files keep breaking" in context.stdout
