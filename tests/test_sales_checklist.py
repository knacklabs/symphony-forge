"""The salesperson's published starting path and merge decision."""

from pathlib import Path

STORY = "FORGE-SALES-1"
ROOT = Path(__file__).resolve().parents[1]


def test_1_prototype_merge_choice_is_recorded():
    decision = (ROOT / "docs/decisions/0097-agent-merges-before-client-signoff.md").read_text(
        encoding="utf-8"
    )
    assert "status: accepted" in decision
    assert "forge merge" in decision
    assert "default branch" in decision
    assert "accepted sign-off" in decision
    assert 'merge = "human"' in decision
    assert 'merge = "agent"' in decision
    assert "Forge's own repo" in decision


def test_5_salesperson_can_follow_the_checklist_in_order():
    checklist = (ROOT / "docs/start-a-prototype.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "[Start a prototype](docs/start-a-prototype.md)" in readme
    steps = (
        "GitHub seat and repo",
        "Set up your laptop",
        "Sign in to an AI coding agent",
        "Open the repo and set up Forge",
        "Discover the customer's problem",
        "Build and show the demo",
        "Put the demo online",
        "Get sign-off",
    )
    positions = [checklist.index(f"## {step}") for step in steps]
    assert positions == sorted(positions)
    assert "curl -fsSL" in checklist and "scripts/install-mac.sh | bash" in checklist
    assert "irm " in checklist and "scripts/install-windows.ps1 | iex" in checklist
    assert "forge init" in checklist and "forge doctor --fix" in checklist
    assert "Codex SDK" in checklist
    assert "deploy platform" in checklist and "subdomain" in checklist
    assert "placeholder" in checklist and "own login" in checklist
