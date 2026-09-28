STORY = "FORGE-DESIGN-1"

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_1_decision_records_design_models_fallback_and_reason():
    # The decision is the owner-visible contract; routing tests cannot catch its removal.
    record = (ROOT / "docs/decisions/0097-design-work-uses-opus.md").read_text(encoding="utf-8")
    context = " ".join(record.split("## Context", 1)[1].split("## Decision", 1)[0].split())
    choice = " ".join(record.split("## Decision", 1)[1].split("## Consequences", 1)[0].split())

    assert "status: accepted" in record.split("---", 2)[1]
    assert "owner" in context and "screen" in context and "Codex" in context
    assert "[models.design.claude]" in choice and "[models.design.codex]" in choice
    assert "claude-opus-5-5` at high effort" in choice
    assert "gpt-6-sol` at high effort" in choice
    assert "User-facing" in choice and "Prototype before sign-off" in choice
    assert "HEAD, index and working tree are unchanged" in choice
    assert "work log names the fallback and its reason" in choice


def test_5_guide_explains_design_models_and_fallback():
    # Keep the explanation in the models section a reader uses to change the choice.
    guide = (ROOT / "docs/guide.md").read_text(encoding="utf-8")
    models = " ".join(guide.split("## Workers and conversations", 1)[1]
                      .split("### Notes, worker questions and quick answers", 1)[0].split())

    assert "[models.design.claude]" in models and "[models.design.codex]" in models
    assert "claude-opus-5-5` at high effort" in models
    assert "gpt-6-sol` at high effort" in models
    assert "User-facing" in models and "Prototype before sign-off" in models
    assert "`claude` command is missing" in models
    assert "Claude fails before changing the checkout" in models
    assert "prints and logs the fallback reason" in models
    assert "without a Codex retry" in models
