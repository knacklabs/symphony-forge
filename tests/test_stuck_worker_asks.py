"""When a worker can't get past the same failing test or finding, Forge stops the item and prints
a ready-to-ask question; the owner's choice, such as switching the item to the other tool, is
recorded and the next round follows it. Both client hosts get the guide paragraph."""
from __future__ import annotations

import json
import sys

import pytest

from test_close import env  # noqa: F401
from test_land import land  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import _repo_adopted_on_the_previous_release, unsynced_up  # noqa: F401

STORY = "stuck-worker-asks"

# The repo's test command fails the same test whatever the worker commits.
SUITE = 'print("FAILED test_readme.py::test_greeting - AssertionError")\nraise SystemExit(1)\n'
QUESTION = [
    "Readme greets new readers is stuck. It should deliver: The readme opens with a greeting",
    "Two rounds in a row left the failing test test_readme.py::test_greeting.",
    "The worker tried: Worker round.",
    "Choose one: switch this item to Codex; keep Claude for one more round; or narrow or split it.",
    'Next: forge close tidy-readme --resolve <switch|same|narrow|split> --reason "<human\'s choice>"',
]


def test_1_the_same_failing_test_after_two_rounds_stops_and_the_choice_switches_the_tool(land):
    env = land
    script = env.tmp / "suite.py"
    script.write_text(SUITE, "utf-8")
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + "test = " + json.dumps(f"{sys.executable} {script}") + "\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    for _ in range(2):
        assert env.close(item).returncode == 1
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
    assert env.close(item).returncode == 1

    stuck = env.repo.forge("work", item)
    assert stuck.returncode == 1, stuck.stdout + stuck.stderr
    assert stuck.stderr.splitlines()[-5:] == QUESTION
    assert env.close(item).stderr.splitlines()[-5:] == QUESTION
    shown = env.repo.forge("next").stdout
    assert QUESTION[0] in shown and QUESTION[-1] in shown

    assert env.close(item, "--resolve", "accept", "--reason", "Accept it").returncode == 1
    chosen = env.close(item, "--resolve", "switch", "--reason", "Try the other tool")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    assert "Codex builds it" in env.repo.forge("next").stdout
    # This env has no trusted Codex project, so reaching Codex's own setup check proves the switch.
    switched = env.repo.forge("work", item)
    assert "Forge starts no Codex turn here." in switched.stderr, switched.stdout + switched.stderr


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_2_clients_receive_the_stuck_worker_guidance(unsynced_up, adoption):
    up = unsynced_up
    if adoption == "new init":
        client, made = _fresh_client(up.repo, up.env.gh, up.tmp)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        _repo_adopted_on_the_previous_release(up)
        client = up.folder
    for host in (".codex", ".claude"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "When two fix rounds in a row leave the same failing test or finding" in guide
        assert ('`forge close <item> --resolve <switch|same|narrow|split> --reason '
                '"<human\'s choice>"`') in guide
