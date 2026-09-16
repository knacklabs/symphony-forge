from __future__ import annotations

import sys

from test_gates import HARNESS

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from check_board_complete import board_problems  # noqa: E402
from forge_cli.events import load_events  # noqa: E402


def _workflow() -> str:
    return (HARNESS / ".github/workflows/pr-link.yml").read_text(encoding="utf-8")


def test_pr_link_workflow_stages_per_event_files_not_legacy_jsonl():
    text = _workflow()
    assert "git add -f .factory/events/" in text
    assert "git add -f .factory/events.jsonl" not in text
    assert "head_repository.full_name == github.repository" in text
    assert "workflow_run.event == 'pull_request'" in text


def test_pr_link_workflow_status_description_names_per_event_link_commit():
    text = _workflow()
    assert "link commit touches only per-event .factory/events/" in text
    assert "events.jsonl" not in text
    assert "context=scaffold-check" in text


def test_verified_forge_acc3_and_cfs1_pr_links_make_board_complete():
    expected = {
        "FORGE-CFS-1": "knacklabs/symphony-forge#109",
        "FORGE-ACC-3": "knacklabs/symphony-forge#110",
    }
    links = {
        event.get("story"): event.get("detail")
        for event in load_events(HARNESS, event="pr-linked")
        if event.get("story") in expected
    }
    assert links == expected
    problems = board_problems(HARNESS)
    assert not any(story in problem for story in expected for problem in problems)
