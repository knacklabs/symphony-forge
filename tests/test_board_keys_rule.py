"""The shipped AGENTS.md lets the board show a story's key small beside its title, the one
exception to the plain-English rule, in new repos and in repos adopted on an earlier release."""
from test_board_dependency_timelines import _client

STORY = "FORGE-BOARD-2"
LINE = ("Write for humans in plain English: no IDs, hashes or jargon in questions, pull request "
        "summaries or the board, except story keys shown small beside titles on the board.")


def agents_md_allows_story_keys(repo, gh, tmp_path, history):
    """Run from criterion 12's one test in tests/test_board_how_it_went.py."""
    _client(repo, gh, tmp_path, history)
    text = " ".join((repo.path / "AGENTS.md").read_text("utf-8").split())
    assert LINE in text
