"""Next reports machine build capacity promptly with fifteen planned parts."""
import hashlib
import json
import time

import pytest

from test_machine_views_recent_finished_items import NOW, client, landed
from test_story import DOC

STORY = "next-build-capacity"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_next_reports_build_capacity_with_fifteen_parts(repo, gh, monkeypatch, history):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    heading = DOC.split("| SAVE |", 1)[0]
    text = heading + "\n".join(
        f"| PART{n} | Part {n} | Save a basket | 1 | `src/part{n}.py` | `tests/test_part{n}.py` | none | no |"
        for n in range(15)) + "\n\nNew moving parts: none\n\n## Risks\n\nRisks: none\n"
    digest = hashlib.sha1(b"blob %d\0" % len(text.encode()) + text.encode()).hexdigest()
    landed(repo, monkeypatch, NOW, {
        ".factory/stories/MANY/story.json": {"status": "approved", "title": "Many parts"},
        "plans/MANY.md": text,
        "plans/MANY.read.md": f"---\nround: 1\nread_hash: {digest}\n---\n\n## Round 1\n\nNo findings.\n",
    })
    # The real machine command supplies the independent expected capacity.
    lanes = repo.forge("lanes", "--json")
    assert lanes.returncode == 0, lanes.stderr
    agents = json.loads(lanes.stdout)["agents"]
    used = sum(bool(row.get("started_at") or row.get("admitted") or row.get("legacy"))
               and not row.get("suspended_by") and not row.get("free")
               for row in agents["entries"])
    started = time.monotonic()
    shown = repo.forge("next")
    elapsed = time.monotonic() - started
    assert shown.returncode == 0, shown.stderr
    assert f"Builds running: {used} of {agents['size']}" in shown.stdout
    assert "forge task start MANY/PART14" in shown.stdout
    assert elapsed < 10, f"next took {elapsed:.2f}s for fifteen parts"
