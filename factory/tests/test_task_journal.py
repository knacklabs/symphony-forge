"""One task journal, written only through the harness and read by both
agents (decision 0080)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from test_gates import HARNESS, intake, repo, run, sign_off  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import journal  # noqa: E402


def _story(repo: Path) -> str:
    sign_off(repo)
    intake(repo)
    return "ENG-1"


def test_entries_are_validated_numbered_and_rendered(repo):
    story = _story(repo)
    first = journal.append(repo, story, "T1", kind="note", by="coordinator",
                           title="Heartbeat every five minutes", body="Nandu said so in chat.")
    second = journal.append(repo, story, "T1", kind="proof", by="harness",
                            title="npx vitest run", body="9 passed", command="npx vitest run",
                            exit_code=0)
    assert first["id"] == "J-1" and second["id"] == "J-2"
    items = journal.entries(repo, story, "T1")
    assert [e["kind"] for e in items] == ["note", "proof"]
    assert journal.head_id(items) == "J-2"
    assert [e["id"] for e in journal.since(items, "J-1")] == ["J-2"]
    md = (repo / ".factory" / "stories" / story / "tasks" / "T1" / "journal.md").read_text(
        encoding="utf-8")
    assert "## J-1 · note · coordinator" in md and "Nandu said so in chat." in md
    assert "- command: npx vitest run" in md
    raw = (repo / ".factory" / "stories" / story / "tasks" / "T1" / "journal.jsonl").read_bytes()
    assert b"\r\n" not in raw


def test_kind_actor_and_required_fields_are_enforced(repo):
    story = _story(repo)
    with pytest.raises(SystemExit):
        journal.append(repo, story, "T1", kind="proof", by="coordinator",
                       title="x", command="c", exit_code=0)
    with pytest.raises(SystemExit):
        journal.append(repo, story, "T1", kind="refusal", by="coordinator",
                       title="lockfile claim", finding="F1")
    with pytest.raises(SystemExit):
        journal.append(repo, story, "T1", kind="note", by="nobody", title="x")
    with pytest.raises(SystemExit):
        journal.append(repo, story, "T1", kind="gossip", by="coordinator", title="x")
    assert journal.entries(repo, story, "T1") == []


def test_long_bodies_become_attachments_and_repeats_do_not_double(repo):
    story = _story(repo)
    body = "\n".join(f"line {n}" for n in range(2000))
    entry = journal.append(repo, story, "T1", kind="proof", by="harness",
                           title="long", body=body, command="c", exit_code=1)
    assert entry["truncated"] is True
    attachment = repo / entry["attachment"]
    assert attachment.read_text(encoding="utf-8") == body
    assert entry["body"].endswith("line 1999") and "line 1960" in entry["body"]
    again = journal.append(repo, story, "T1", kind="proof", by="harness",
                           title="long", body=body, command="c", exit_code=1)
    assert again["id"] == entry["id"]
    assert len(journal.entries(repo, story, "T1")) == 1


def test_acted_on_must_name_existing_entries(repo):
    story = _story(repo)
    journal.append(repo, story, "T1", kind="note", by="coordinator", title="n")
    with pytest.raises(SystemExit):
        journal.append(repo, story, "T1", kind="report", by="harness", title="r",
                       launch_id="launch-1", acted_on=["J-9"])
    entry = journal.append(repo, story, "T1", kind="report", by="harness", title="r",
                           launch_id="launch-1", acted_on=["J-1"])
    assert entry["acted_on"] == ["J-1"]


def test_standing_entries_keep_the_latest_contract_and_every_instruction(repo):
    story = _story(repo)
    journal.append(repo, story, "T1", kind="contract", by="harness", title="v1", body="a")
    journal.append(repo, story, "T1", kind="note", by="coordinator", title="keep", body="b")
    journal.append(repo, story, "T1", kind="proof", by="harness", title="p", command="c",
                   exit_code=0)
    journal.append(repo, story, "T1", kind="contract", by="harness", title="v2", body="c")
    kept = journal.standing(journal.entries(repo, story, "T1"))
    assert [e["title"] for e in kept] == ["v2", "keep"]


def test_cli_adds_shows_and_reports_status(repo):
    _story(repo)
    code, out = run(repo, "forge.py", "journal", "add", "T1", "--kind", "decision",
                    "--title", "Drop the connector CI", "--reason", "Nandu, chat 11:58",
                    "--by", "human")
    assert code == 0 and "J-1 decision recorded for T1" in out, out
    code, out = run(repo, "forge.py", "journal", "add", "T1", "--kind", "scope",
                    "--title", "shared test helper", "--path", "apps/api/test/database.ts",
                    "--reason", "the cleanup grace is what blocks the seal")
    assert code == 0 and "J-2 scope" in out, out
    code, out = run(repo, "forge.py", "journal", "show", "T1", "--kind", "decision")
    assert code == 0 and "Drop the connector CI" in out and "J-2" not in out, out
    code, out = run(repo, "forge.py", "journal", "status", "T1")
    assert code == 0 and "2 entries; head J-2" in out and "decision=1, scope=1" in out, out
    code, out = run(repo, "forge.py", "journal", "add", "T1", "--kind", "proof",
                    "--title", "x", "--command", "c", "--exit-code", "0")
    assert code != 0 and "coordinator entry cannot be of kind" in out, out
