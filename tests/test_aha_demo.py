"""Every demo follows the script, reactions are kept, and sign-off is read back and drafted.

Checked in the skill as `forge sync` writes it into a client repo, for both hosts.
"""
from test_aha_prepare import _synced

STORY = "FORGE-AHA-1"


def _prototype(repo) -> str:
    return _synced(repo)["SKILL.md"].split(" ## Prototype ")[1].split(" ## Adopt a live app ")[0]


def test_4_every_demo_follows_the_script(repo):
    section = _prototype(repo)
    for rule in (
        "Every demo follows five steps, in order:",
        "1. their workaround today;", "2. the same job in the app;",
        "3. the time or money it saves, in their numbers;", "4. they take the controls;",
        '5. ask "what would stop you using this?"',
        "Send the demo link only after the guided demo, never before it.",
        'With each new version, draft a three-line "what changed" note for the salesperson to send',
    ):
        assert rule in section, rule


def test_5_reactions_are_kept_after_each_demo(repo):
    section = _prototype(repo)
    for rule in (
        "After each demo, ask the salesperson one question at a time: what the customer did "
        "themselves, what they said word for word, and what they asked for.",
        "under `## Prototype notes` in `docs/product/DISCOVERY.md`",
        "`- Did:`", '`- Said: "<their words>"`', "`- Asked:`",
        "`(serves the problem)` or `(after sign-off)`",
    ):
        assert rule in section, rule


def test_6_signoff_is_read_back_and_drafted(repo):
    section = _prototype(repo)
    for rule in (
        "Before the sign-off review, hold one read-back call",
        "goes through every answer on the answers page: our defaults, the agent's guesses and "
        "the topics marked later",
        "Settle every open must-answer topic in that call",
        "After the sign-off review passes, draft the sign-off email for the reviewed version",
        "its demo address", "what the app does", "the problem and the saving",
        "every answer in plain words, with our defaults called out", "what happens next",
        "The customer's reply is the approval evidence the sign-off decision records",
        "The salesperson sends it; Forge sends nothing.",
    ):
        assert rule in section, rule
