"""A story with no linked spec gets the cold read's original checks, minus the spec mapping."""
import json

from test_phases import _flat
from test_story import DOC, new_story, setup

STORY = "FIX-READRULES-MIDDLE"


def _prompt(repo) -> str:
    """The first-round prompt a real `forge read` sends the reader, whitespace flattened."""
    setup(repo)
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    read = repo.forge("read", "SHOP", cwd=shop)
    assert read.returncode == 0, read.stdout + read.stderr
    call = (repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1]
    return _flat(json.loads(call)["prompt"])


def test_1_a_story_without_a_spec_gets_the_conditional_mapping(repo):
    first = _prompt(repo)
    assert "No linked confirmed spec was found" in first
    assert "A story with no linked confirmed spec is not a finding." in first
    assert ("When a confirmed spec is included above, each \"Done when\" item must also map to the "
            "spec's behaviour or success measure; with no confirmed spec, skip that mapping.") in first
    # The original checks the tightening cut are back.
    assert "Windows PowerShell and cmd, WSL, macOS, Linux CI" in first
    assert "Is every edge case pinned down and proven?" in first
