"""Every demo follows the script, reactions are kept, and sign-off is read back and reviewed first.

Checked in the skill as `forge sync` writes it into a client repo, for both hosts, and as
`forge init` writes it into a new client repo.
"""
import subprocess

import pytest
from test_aha_prepare import HOSTS, _synced

STORY = "FORGE-AHA-1"


def _initialized(repo, gh, tmp_path) -> str:
    """The skill `forge init` gives a new client repo, identical for both hosts."""
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    made = repo.forge("init", cwd=client)
    assert made.returncode == 0, made.stderr
    copies = {(client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
              for host in HOSTS}
    assert len(copies) == 1
    return " ".join(copies.pop().split())


@pytest.fixture(params=["sync", "init"])
def skill(request, repo, tmp_path):
    if request.param == "sync":
        return _synced(repo)["SKILL.md"]
    return _initialized(repo, request.getfixturevalue("gh"), tmp_path)


def _prototype(skill: str) -> str:
    return skill.split(" ## Prototype ")[1].split(" ## Adopt a live app ")[0]


def test_4_every_demo_follows_the_script(skill):
    section = _prototype(skill)
    for rule in (
        "Every demo follows five steps, in order:",
        "1. their workaround today;", "2. the same job in the app;",
        "3. the time or money it saves, in their numbers;", "4. they take the controls;",
        '5. ask "what would stop you using this?"',
        "Send the demo link only after the guided demo, never before it.",
        'With each new version, draft a three-line "what changed" note for the salesperson to send',
    ):
        assert rule in section, rule


def test_5_reactions_are_kept_after_each_demo(skill):
    section = _prototype(skill)
    for rule in (
        "After each demo, ask the salesperson one question at a time: what the customer did "
        "themselves, what they said word for word, and what they asked for.",
        "under `## Prototype notes` in `docs/product/DISCOVERY.md`",
        "`- Did:`", '`- Said: "<their words>"`', "`- Asked:`",
        "`(serves the problem)` or `(after sign-off)`",
    ):
        assert rule in section, rule


def test_6_signoff_is_read_back_and_reviewed_first(skill):
    # Old contract: the agent drafted a sign-off email and the review ran only at accept, after
    # the reply. New contract (owner, 2026-09-29): read-back call, then accept before any reply
    # (the strict review alone), then the salesperson asks in their own way, then record and accept.
    section = _prototype(skill)
    steps = (
        "Before anyone asks for sign-off, hold one read-back call",
        "goes through every answer on the answers page: our defaults, the agent's guesses and "
        "the topics marked later",
        "Settle every open must-answer topic in that call",
        "Then run the strict sign-off review before anyone asks for sign-off:",
        "`forge decision new client-signoff`",
        'run `forge decision accept client-signoff --by "<name>"` before any reply is recorded',
        "it runs the strict review alone and stops",
        "Once it passes, tell the salesperson to ask the customer's named person for sign-off "
        "their own way.",
        "When they bring the reply back, record it in `approved_via` and `approved_on`",
        'run `forge decision accept client-signoff --by "<name>"` again to accept.',
    )
    places = [section.find(step) for step in steps]
    assert -1 not in places, [s for s, p in zip(steps, places) if p == -1]
    assert places == sorted(places)
    assert "Draft no sign-off email; Forge sends nothing." in section
    assert "The customer's reply is the approval evidence the sign-off decision records." in section
    assert "sign-off email for" not in section and "Before the sign-off email" not in section
