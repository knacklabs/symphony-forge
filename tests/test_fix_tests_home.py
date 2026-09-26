"""A fix's tests go in their own file, so they can't take a story's criterion number."""
import re
from pathlib import Path

STORY = "FIX-TESTS-HOME"
ROOT = Path(__file__).resolve().parents[1]


def test_1_the_fix_brief_says_its_tests_go_in_their_own_file_with_the_fix_key():
    text = (ROOT / "src/forge/templates/brief.md").read_text(encoding="utf-8")
    fix = " ".join(text.split("<!-- if fix -->")[1].split("<!-- end -->")[0].split())
    assert re.search(r"tests go in their own file with the fix's own STORY key", fix)
    assert re.search(r"never into a story's test file", fix)
