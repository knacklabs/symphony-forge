STORY = "FORGE-PROTO-1"

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_11_prototype_precedes_signoff_and_stories_in_the_docs():
    decision = ROOT / "docs/decisions/0095-prototype-before-stories.md"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs/guide.md").read_text(encoding="utf-8")
    ruling = decision.read_text(encoding="utf-8")

    stages = [line.split("|", 2)[1].strip() for line in readme.splitlines()
              if line.startswith("| ") and line.split("|", 2)[1].strip()[:1].isdigit()]
    assert [stage.split(". ", 1)[1] for stage in stages[:6]] == [
        "Find the problem", "Pick an option", "Build the prototype",
        "Demo and review", "Client sign-off", "Plan the stories",
    ]
    route = guide.split("### A new client project", 1)[1].split("## Commands", 1)[0]
    assert route.index("Start with FDE discovery") < route.index("Build and demo the prototype")
    assert route.index("prototype and answers strictly reviewed") < route.index(
        "The customer's named person approves") < route.index("Only after accepted client sign-off")
    assert route.index("Only after accepted client sign-off") < route.index("create stories")
    assert "[decision 0095](docs/decisions/0095-prototype-before-stories.md)" in readme
    assert "[decision 0095](decisions/0095-prototype-before-stories.md)" in guide

    assert "[decision 0014](0014-specs-before-signoff.md)" in ruling
    assert "[the prototype sign-off spec](../specs/prototype-signoff.md)" in ruling
    assert "a derived roadmap is no longer required before sign-off" in ruling
    assert "after the customer signs off" in ruling
    for link in (ROOT / "docs/decisions/0014-specs-before-signoff.md",
                 ROOT / "docs/specs/prototype-signoff.md"):
        assert link.is_file()
