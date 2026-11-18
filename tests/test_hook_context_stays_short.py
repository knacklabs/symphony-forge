"""The session-start context lists at most three hotspots and points to forge next."""
import json

import pytest

from test_spotted import entry
from test_story import setup

pytestmark = pytest.mark.platform


def test_hook_context_with_many_hotspots_stays_short(repo):
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
