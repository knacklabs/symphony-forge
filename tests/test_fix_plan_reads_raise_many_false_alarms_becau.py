"""The cold reader reports concrete gaps in this story's own change, not a general checklist."""
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


def test_1_a_finding_names_a_concrete_gap_with_its_evidence(repo):
    first = _prompt(repo)
    assert ("A finding names a concrete gap a builder would hit or a bug that would ship, and "
            "cites the file or Done-when item that shows it.") in first


def test_2_edge_cases_platforms_and_traps_only_where_the_change_meets_them(repo):
    first = _prompt(repo)
    assert "Report an edge case, platform or trap only where this story's own change meets it, never as a general checklist." in first
    assert "Windows PowerShell and cmd, WSL, macOS, Linux CI" not in first


def test_3_unchanged_behaviour_and_a_missing_spec_are_not_findings(repo):
    first = _prompt(repo)
    assert "Behaviour the story doesn't change is not a finding." in first
    assert "A story with no linked spec is not a finding." in first


def test_4_the_safety_and_one_way_checks_stay(repo):
    first = _prompt(repo)
    for rule in ("Never propose dropping validation, security, data-loss protection or accessibility.",
                 "Flag any one-way step (deleting data, a destructive migration, a new vendor) that "
                 "isn't listed under Risks.",
                 "Each entry in `New moving parts` needs its \"Done when\" item"):
        assert rule in first, rule
