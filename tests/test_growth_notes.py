"""Growth instructions reach both hosts on new and earlier-adopted apps."""
import pytest

from test_notes_first_discovery import client  # noqa: F401 (fixture)


STORY = "FORGE-LIBS-1"


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_5_setup_asks_growth_questions_only_where_the_notes_leave_them_open(client, adoption):
    # Audit: init/sync must deliver this prompt contract to both hosts. Losing a topic,
    # its new-app limit or its answer destination must fail; existing constitution tests
    # cover defaults, not growth. Use the real commands and no production test seam.
    paragraph = (
        "On a new app, check the client notes for five growth topics: the users and records in "
        "year one and year three, heavy background work, other systems that call in or that "
        "the app calls, rules on where the data stays, and parts that can become their own "
        "product. Ask about a topic only when the notes touch it and do not answer it, one "
        "question at a time. Write each answer under ## Growth notes in the constitution. "
        "A later story reads these notes before it plans modules, jobs or links."
    )
    for host in (".claude", ".codex"):
        guide = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
        constitution = guide.split("\n## App constitution\n")[1].split("\n## Adopt a live app\n")[0]
        assert paragraph in " ".join(constitution.split())
        outline = constitution.split("```markdown\n")[1].split("```", 1)[0]
        assert "\n## Growth notes\n" in outline
