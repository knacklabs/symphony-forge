"""forge work waits for locked records, or refuses without losing its conversation."""
from __future__ import annotations

import json
import os
from pathlib import Path

from test_codex_resume import _resuming
from test_codex_worker import _sent, sdk_data  # noqa: F401 (a fixture)

STORY = "FIX-TEST-AUDIT-FOLLOWUPS"


def _locked_record(tmp_path, monkeypatch, record: Path, refusal: str):
    """Refuse the OS rename as Windows does while a reader holds the destination.

    The real command owns waiting, writing and cleanup. The marker confirms the fault
    reached that command rather than an unrelated guard.
    """
    startup = tmp_path / "locked-record"
    startup.mkdir()
    marker = startup / "refused"
    (startup / "sitecustomize.py").write_text(
        "import os, time\n"
        "from pathlib import Path\n"
        f"target = Path({json.dumps(str(record))})\n"
        f"marker = Path({json.dumps(str(marker))})\n"
        "real_replace, attempts, first = os.replace, 0, None\n"
        "def replace(source, destination, *args, **kwargs):\n"
        "    global attempts, first\n"
        "    if Path(destination) == target:\n"
        "        attempts += 1\n"
        "        if first is None: first = time.monotonic()\n"
        f"        if {refusal}:\n"
        "            marker.write_text('Access is denied\\n', encoding='utf-8')\n"
        "            raise PermissionError(5, 'Access is denied')\n"
        "    return real_replace(source, destination, *args, **kwargs)\n"
        "os.replace = replace\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(filter(None, (
        str(startup), os.environ.get("PYTHONPATH")))))
    return marker


def test_2_work_waits_for_a_reader_before_creating_its_record(
        repo, monkeypatch, sdk_data, tmp_path, claude_session):
    _, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    with monkeypatch.context() as locked:
        marker = _locked_record(tmp_path, locked, turns.with_suffix(".json"), "attempts <= 3")
        built = repo.forge("work", "BOARD/PAGE")
    assert marker.exists()
    assert built.returncode == 0, built.stdout + built.stderr
    assert "Codex ended the turn: completed" in built.stdout

    # A later command must find the newly saved conversation and continue it.
    resumed = repo.forge("work", "BOARD/PAGE")
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert _sent(calls, "thread/resume")[-1]["threadId"] == "thr-stub-1"
    assert "stub codex: turn-stub-2 on thr-stub-1" in resumed.stdout


def test_3_work_refuses_a_permanent_lock_and_keeps_the_existing_conversation(
        repo, monkeypatch, sdk_data, tmp_path, claude_session):
    _, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr
    record = turns.with_suffix(".json")
    with monkeypatch.context() as locked:
        marker = _locked_record(tmp_path, locked, record, "True")
        refused = repo.forge("work", "BOARD/PAGE")
    assert marker.exists()
    assert refused.returncode != 0
    assert refused.stderr == (
        f"Forge couldn't update {record} because another program kept it open.\n"
        f"Next: close whatever reads {record}, then run the command again\n")
    assert not record.with_suffix(".tmp").exists()
    assert len(_sent(calls, "turn/start")) == 1

    # Once the reader closes the file, no state was lost and no second turn started early.
    resumed = repo.forge("work", "BOARD/PAGE")
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert _sent(calls, "thread/resume")[-1]["threadId"] == "thr-stub-1"
    assert "stub codex: turn-stub-2 on thr-stub-1" in resumed.stdout


def test_4_work_waits_until_a_reader_releases_an_existing_record(
        repo, monkeypatch, sdk_data, tmp_path, claude_session):
    _, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr
    with monkeypatch.context() as locked:
        marker = _locked_record(tmp_path, locked, turns.with_suffix(".json"),
                                "time.monotonic() - first < 0.5")
        resumed = repo.forge("work", "BOARD/PAGE")
    assert marker.exists()
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert _sent(calls, "thread/resume")[-1]["threadId"] == "thr-stub-1"
    assert "stub codex: turn-stub-2 on thr-stub-1" in resumed.stdout
