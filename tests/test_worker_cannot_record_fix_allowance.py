"""A worker stops at the five-file limit; only the coordinator between rounds records the allowance.

Test-audit: the refusal is Forge's own command output. The running round is recorded the way
forge work records it (a run start event and a live lock); there is no production test seam.
"""
import pytest

from test_board_status_and_times import OLD, _fix, _live_work_lock, _records, client  # noqa: F401

STORY = "FIX-WORKER-ALLOWANCE"
REFUSAL = ("A worker cannot allow a fix past the five-file limit: stop and report this refusal to the "
           "coordinator, who records the allowance between rounds.")


@pytest.mark.parametrize("who", ["marker", "recorded round", "coordinator"])
def test_1_worker_cannot_record_its_own_fix_allowance(client, who, monkeypatch):
    tree = _fix(client)
    if who == "marker":
        monkeypatch.setenv("FORGE_WORKER", "1")
    elif who == "recorded round":
        _records(client, "events.jsonl", [{"event": "run start", "id": "running-work",
                                           "item": "correct-state", "kind": "work", "round": 1, "at": OLD}])
        _live_work_lock(client, "correct-state")
    result = client.forge("fix", "allow-large", "Rename one label everywhere", cwd=tree)
    if who == "coordinator":
        assert result.returncode == 0, result.stderr
        assert "may now go over the fix limit." in result.stdout
    else:
        assert result.returncode != 0
        assert REFUSAL in result.stderr
