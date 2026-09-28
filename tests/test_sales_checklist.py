"""The salesperson's published starting path."""

from pathlib import Path

STORY = "FORGE-SALES-1"
ROOT = Path(__file__).resolve().parents[1]


def test_5_salesperson_can_follow_the_checklist_in_order():
    checklist = (ROOT / "docs/start-a-prototype.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "[Start a prototype](docs/start-a-prototype.md)" in readme
    steps = (
        "GitHub seat and repo",
        "Set up your laptop",
        "Sign in to an AI coding agent",
        "Sign in to GitHub",
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
    # The old path reached init before CLI login, leaving a first commit when setup failed.
    assert checklist.index("gh auth login") < checklist.index("forge init")
    assert "browser" in checklist
    assert "already stopped after its first commit" in checklist
    assert "do not run `forge init` again" in checklist
    assert "branch protection" in checklist
    assert "forge init" in checklist and "forge doctor --fix" in checklist
    assert "Codex SDK" in checklist
    assert "deploy platform" in checklist and "subdomain" in checklist
    assert "placeholder" in checklist and "own login" in checklist
