"""The worker brief says every commit's Proof list carries the previous one forward."""
from test_worker import calls, install_claude
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "FIX-PROOF-LIST-CARRIES-FORWARD"


def test_1_brief_says_each_proof_list_carries_the_previous_one_forward(client):  # noqa: F811
    # The review reads only the latest commit's list; a repair round must not drop earlier proofs.
    log = install_claude(client)
    started = client.forge("fix", "start", "Correct spelling", "--done", "Correct the spelling")
    assert started.returncode == 0, started.stdout + started.stderr
    worked = client.forge("work", "correct-spelling")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert ("Every commit's `Proof list:` carries the previous one forward and adds to it, "
            "even in a small repair commit; never list only the latest change.") in brief
