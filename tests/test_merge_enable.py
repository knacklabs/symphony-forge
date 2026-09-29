"""The owner switches a repo to agent merges with one command; the agent never does."""
from __future__ import annotations

import tomllib

import pytest

from test_close import ROOT, env  # noqa: F401

STORY = "FORGE-MERGESWITCH-1"
FIX = "let-the-agent-merge"
TABLE = '[models.build]\nmodel = "opus"\neffort = "high"\n'


@pytest.mark.parametrize("setting", ("absent", "human", "table"))
def test_1_owner_switches_on_agent_merges_with_one_command(env, monkeypatch, setting):
    toml = env.repo.path / "forge.toml"
    before = toml.read_text("utf-8")
    if setting == "human":
        before = 'merge = "human"\n' + before
    elif setting == "table":  # a table at the end: the setting must land above it, at the top level
        before = before.replace('models.build = { model = "opus", effort = "high" }\n', TABLE)
    if setting != "absent":
        env.commit(env.repo.path, "forge.toml", before)
        env.repo.git("push", "-q", "origin", "main")
    monkeypatch.delenv("CODEX_THREAD_ID")  # the owner's own terminal: no agent's variables

    switched = env.repo.forge("merge", "enable")

    assert switched.returncode == 0, switched.stdout + switched.stderr
    assert switched.stdout.splitlines()[-1] == (
        f"Ready: {FIX} has a clean review and green checks. A human merges its pull request.")
    assert env.gh_calls("pr", "create")
    pushed = env.repo.git("show", f"origin/fix/{FIX}:forge.toml")
    expected = {**tomllib.loads(before), "merge": "agent"}
    assert tomllib.loads(pushed) == expected
    assert tomllib.loads(env.repo.git("show", "origin/main:forge.toml")).get("merge") != "agent"

    # Running it again before the merge points back to the open change instead of opening another.
    twice = env.repo.forge("merge", "enable")
    assert twice.stderr == ("The change that lets the agent merge is already open.\n"
                            f"Next: forge close {FIX}\n")

    # The owner merges it; then the switch is on, and running the command again changes nothing.
    env.repo.git("merge", "-q", "--ff-only", f"origin/fix/{FIX}")
    env.repo.git("push", "-q", "origin", "main")
    again = env.repo.forge("merge", "enable")
    assert again.returncode != 0
    assert again.stderr == ("The default branch's forge.toml already lets the agent merge.\n"
                            "Next: forge next\n")


@pytest.mark.parametrize("agent", ("CODEX_THREAD_ID", "CLAUDECODE"))
def test_2_agent_never_switches_and_points_to_the_command(env, monkeypatch, agent):
    monkeypatch.delenv("CODEX_THREAD_ID")
    monkeypatch.setenv(agent, "1")
    creates = len(env.gh_calls("pr", "create"))

    refused = env.repo.forge("merge", "enable")

    assert refused.returncode != 0
    assert refused.stderr == (
        "Only the repo owner switches on agent merges, so Forge won't do it from an agent's shell.\n"
        "Next: the repo owner runs forge merge enable in their own terminal\n")
    assert f"fix/{FIX}" not in env.repo.git("branch", "--all")
    assert len(env.gh_calls("pr", "create")) == creates

    # With agent merges off, forge merge names the owner's command.
    denied = env.repo.forge("merge", "tidy-readme")
    assert denied.returncode != 0
    assert denied.stderr.splitlines()[-1] == (
        "Next: the repo owner runs forge merge enable in their own terminal")

    # Both hosts' skills tell the agent never to make the switch and to point the owner to it.
    for host in (".claude", ".codex"):
        skill = " ".join((ROOT / host / "skills" / "forge" / "SKILL.md").read_text("utf-8").split())
        assert "never change `merge` in `forge.toml` or run `forge merge enable`" in skill
        assert "tell them to run `forge merge enable` in their own terminal" in skill
