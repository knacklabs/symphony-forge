STORY = "FORGE-PROTO-1"

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_11_prototype_precedes_signoff_and_stories_in_the_docs():
    decision = ROOT / "docs/decisions/0095-prototype-before-stories.md"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs/guide.md").read_text(encoding="utf-8")
    ruling = decision.read_text(encoding="utf-8")

    # The new seven-step README journey has its own owner-boundary test.
    route = " ".join(guide.split("### A new client project", 1)[1].split("## Commands", 1)[0].split())
    assert route.index("Start with FDE discovery") < route.index("Build and demo the prototype")
    assert route.index("Resolve the answers, then run the sign-off checks") < route.index(
        "The customer's named person approves") < route.index("Only after accepted client sign-off")
    assert route.index("reviews the canvas against the whole brief") < route.index(
        "The customer's named person approves")
    assert route.index("A working prototype also gets one strict whole-product review") < route.index(
        "The customer's named person approves")
    assert route.index("Only after accepted client sign-off") < route.index("create stories")
    assert "a canvas-only sign-off does not need that review." in route
    assert "A working prototype also gets one strict whole-product review" in route
    assert "[decision 0095](docs/decisions/0095-prototype-before-stories.md)" in readme
    assert "[decision 0095](decisions/0095-prototype-before-stories.md)" in guide

    assert "[decision 0014](0014-specs-before-signoff.md)" in ruling
    assert "[the prototype sign-off spec](../specs/prototype-signoff.md)" in ruling
    assert "a derived roadmap is no longer required before sign-off" in ruling
    assert "after the customer signs off" in ruling
    for link in (ROOT / "docs/decisions/0014-specs-before-signoff.md",
                 ROOT / "docs/specs/prototype-signoff.md"):
        assert link.is_file()
