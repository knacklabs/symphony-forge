"""Pin the test guidance delivered to workers and reviewers."""
from pathlib import Path

STORY = "FIX-END-TO-END-TEST-GUIDANCE"
ROOT = Path(__file__).resolve().parents[1] / "src" / "forge"


def guidance(path: str) -> str:
    return " ".join((ROOT / path).read_text(encoding="utf-8").split())


def assert_end_to_end_rule(text: str) -> None:
    for phrase in (
        "Every Done-when item needs an end-to-end test through the real entry point",
        "Forge's own command",
        "running API with a real database",
        "user flows in a browser through Playwright",
        "Fake only third-party services at their edge",
        "Unit tests are only for pure logic with many cases",
        "never an item's only proof",
    ):
        assert phrase in text, phrase


def test_1_standards_require_end_to_end_proof_for_every_item():
    assert_end_to_end_rule(guidance("standards.md"))


def test_2_testing_convention_requires_end_to_end_proof_for_every_item():
    assert_end_to_end_rule(guidance("templates/conventions/testing.md"))


def test_3_worker_brief_requires_end_to_end_proof_for_every_item():
    assert_end_to_end_rule(guidance("templates/brief.md"))


def test_4_review_rejects_unit_only_proof_and_never_requests_helper_unit_tests():
    text = guidance("templates/review.md")
    assert_end_to_end_rule(text)
    assert "an item proven only by unit tests" in text
    assert "P1 finding titled `Not done: <the item>`" in text
    assert "Never ask for unit tests of helpers" in text
