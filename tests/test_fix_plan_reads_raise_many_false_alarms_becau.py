"""The cold read's safety and one-way checks survive the plan-read tightening and its revert.

Tests 1-3 pinned the tightened wording, which the fix FIX-READRULES-MIDDLE reverted; the
no-linked-spec rule they also checked is now proven in that fix's own test file.
"""
import json

from test_phases import _flat
from test_story import DOC, new_story, setup

STORY = "FIX-PLAN-READS-RAISE-MANY-FALSE-ALARMS-BECAU"


def _prompt(repo) -> str:
    """The first-round prompt a real `forge read` sends the reader, whitespace flattened."""
    setup(repo)
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    read = repo.forge("read", "SHOP", cwd=shop)
    assert read.returncode == 0, read.stdout + read.stderr
    call = (repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1]
    return _flat(json.loads(call)["prompt"])


def test_4_the_safety_and_one_way_checks_stay(repo):
    first = _prompt(repo)
    for rule in ("Never propose dropping validation, security, data-loss protection or accessibility.",
                 "Flag any one-way step (deleting data, a destructive migration, a new vendor) that "
                 "isn't listed under Risks.",
                 "Each entry in `New moving parts` needs its \"Done when\" item"):
        assert rule in first, rule
