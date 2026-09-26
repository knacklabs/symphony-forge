"""Coordinating agents don't narrate: the Rules say to speak only when it matters."""
import re
from pathlib import Path

STORY = "NARRATION"
ROOT = Path(__file__).resolve().parents[1]


def test_1_the_rules_say_no_running_commentary_and_when_to_speak():
    for rel in ("src/forge/templates/adapters/AGENTS.md", "AGENTS.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        rules = " ".join(text.split("### Rules")[1].split())
        assert re.search(r"no running commentary", rules, re.I), rel
        assert re.search(r"when something lands", rules), rel
        assert re.search(r"failure or finding needs the human", rules), rel
        assert re.search(r"decision is theirs", rules), rel
        assert re.search(r"line or two", rules), rel
