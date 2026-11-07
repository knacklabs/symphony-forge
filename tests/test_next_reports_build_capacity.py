"""Next counts this release's running builder rounds beside fifteen planned parts."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from conftest import machine_cores
from test_machine_views_recent_finished_items import NOW, client, landed
from test_story import DOC

STORY = "next-build-capacity"


@pytest.mark.platform
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
    machine_cores(repo, 8)
    version = repo.forge("--version").stdout.split()[-1].removeprefix("v")
    # Recorded live runs use this test's real process. Older readers have no free
    # field, as on v1.2.9. Only the first entry is a running builder on this release.
    runs = []
    for name, release, kind, extra in (
        ("builder", version, "work", {}),
        ("read", version, "read", {"free": True}),
        ("review", version, "review", {"free": True}),
        ("old-read", "1.2.9", "read", {}),
        ("old-review", "1.2.9", "review", {}),
        ("old-builder", "1.2.9", "work", {}),
        ("waiting-builder", version, "work", {"admitted": False, "started_at": None}),
        ("test-suspended-builder", version, "work", {"suspended_by": "test"}),
    ):
        runs.append({"id": name, "version": release, "kind": kind,
                     "repo_root": repo.path.as_posix(), "repo_name": repo.path.name,
                     "item": name, "joined_at": NOW, "started_at": NOW, "admitted": True,
                     "process": {"pid": os.getpid()}, "forge": {"pid": os.getpid()}, **extra})
    registry = Path(os.environ["APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME"]) / "forge/agent-runs.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps(runs), encoding="utf-8")
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert "Builds running: 1 of 4" in shown.stdout
    assert "forge task start MANY/PART14" in shown.stdout
