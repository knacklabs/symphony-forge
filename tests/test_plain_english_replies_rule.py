"""The shipped AGENTS.md tells agents to write plain English for humans, report progress plainly
and keep status exact, in new repos and in repos adopted on an earlier release."""
import pytest

from test_board_dependency_timelines import _client

STORY = "plain-english-replies-rule"
RULES = (
    "Write every reply, summary and question for a human in plain English that a non-native "
    "speaker understands on the first read.",
    "merge, not land;",
    "Explain each technical term the first time it comes up.",
    "Notes and prompts for other agents are exempt.",
    "Report progress in plain sentences: what changed, what failed, what comes next.",
    "Start with three lines, and add detail only when it changes the next action.",
    "Never make anything sound more certain or more finished than it is.",
    "A correlation stays a correlation, and a plan stays a plan.",
)


@pytest.mark.parametrize("history", ["new", "adopted"])
def test_1_agents_md_states_the_plain_english_rules(repo, gh, tmp_path, history):
    _client(repo, gh, tmp_path, history)
    text = " ".join((repo.path / "AGENTS.md").read_text("utf-8").split())
    for rule in RULES:
        assert rule in text, rule
