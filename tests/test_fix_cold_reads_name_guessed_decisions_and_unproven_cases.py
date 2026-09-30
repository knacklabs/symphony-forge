"""The cold reader names every decision a builder would guess and each case's proving test,
while still leaving out generic traps, unchanged behaviour and a missing spec."""
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


def test_1_the_reader_names_every_decision_a_builder_would_guess(repo):
    first = _prompt(repo)
    assert ("Name every decision a builder would otherwise have to guess: a name, format, rule, "
            "order or boundary that two parts rely on, or that a Done-when item leaves open.") in first


def test_2_the_reader_names_each_items_own_cases_and_the_test_proving_each(repo):
    first = _prompt(repo)
    assert ("For each \"Done when\" item, name the cases this story's own change must handle and "
            "which test, in which task's Tests cell, proves each.") in first


def test_3_the_exclusions_stay(repo):
    first = _prompt(repo)
    assert "Behaviour the story doesn't change is not a finding." in first
    assert "A story with no linked spec is not a finding." in first
    assert "Report an edge case, platform or trap only where this story's own change meets it" in first
    assert "Windows PowerShell and cmd, WSL, macOS, Linux CI" not in first
