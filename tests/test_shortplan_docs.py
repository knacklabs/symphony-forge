"""Short plans: a new story doc puts one plain sentence per result on top and the details below
`## For the builders`, and the owner approves only that top part, on either host.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import re

from test_approval import _digest  # pyright: ignore[reportPrivateUsage]
from test_fix_forge_s_questions_and_story_docs_are_har import synced_skills
from test_shortplan_briefs import NEW, TOP
from test_story import DOC, claude_plan, codex_question, hook, new_story, ready, setup

STORY = "FORGE-SHORTPLAN-1"

TOP_PART = "from its title down to ## For the builders"


def flat(text: str) -> str:
    return " ".join(text.split())


def test_1_new_plans_put_one_sentence_per_result_on_top_and_details_below(repo):
    skill = flat(synced_skills(repo))
    assert "no code names, file paths or test names" in skill
    assert "### Done-when details" in skill

    doc = (new_story(repo, "SHOP") / "plans" / "SHOP.md").read_text(encoding="utf-8")
    top, builders, below = doc.partition("\n## For the builders\n")
    assert builders, "the template has no For the builders heading"
    # On top: each result is one bold sentence and nothing else.
    done = re.search(r"^## Done when\n(.*?)^## ", top, re.M | re.S)[1]
    items = re.findall(r"^\d+\. .*$", done, re.M)
    assert items and all(re.fullmatch(r"\d+\. \*\*[^*]+\*\*", item) for item in items), items
    # Below: the details, under the same numbers, before the tasks.
    headings = re.findall(r"^#{2,3} (.+)$", below, re.M)
    assert headings[:2] == ["Done-when details", "Tasks"]
    details = re.search(r"^### Done-when details\n(.*?)^## ", below, re.M | re.S)[1]
    assert re.findall(r"^(\d+)\. ", details, re.M) == ["1"]


def test_2_you_approve_only_the_top_part(repo, claude_payload, codex_payload):
    setup(repo, keys=("SHOP", "WISH", "GIFT"))
    top = TOP.rstrip() + "\n"
    assert "Tasks" not in top and "details" not in top

    # Claude Code: forge next asks for the top part only, and exiting Plan Mode with it approves.
    shop = ready(repo, "SHOP", NEW)
    shown = flat(repo.forge("next").stdout)
    assert f"in Claude Code, show plans/SHOP.md {TOP_PART} in Plan Mode" in shown
    recorded = hook(repo, claude_plan(claude_payload, top))
    assert recorded.returncode == 0, recorded.stderr
    assert "Recorded the approval of" in recorded.stdout

    # After its next cold read, a tightened detail keeps the approval; a changed result doesn't.
    doc = shop / "plans" / "SHOP.md"
    doc.write_text(NEW.replace("an empty basket\n   can't be saved", "an empty basket\n   is refused"),
                   encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    shown = repo.forge("next").stdout
    assert "waiting for approval" not in shown and "Next: forge task start SHOP/T1" in shown
    doc.write_text(NEW.replace("A shopper can save a basket.", "A shopper can save two baskets."),
                   encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    assert "Shoppers can save a basket is waiting for approval" in repo.forge("next").stdout
    doc.write_text(NEW, encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0

    # Codex: forge next says to show the same top part before asking, and the answer approves.
    ready(repo, "WISH", NEW.replace("save a basket", "keep a wish list"))
    shown = flat(repo.forge("next").stdout)
    assert f"in Codex, show plans/WISH.md {TOP_PART}, then ask request_user_input" in shown
    recorded = hook(repo, codex_question(codex_payload, _digest(repo)))
    assert recorded.returncode == 0, recorded.stderr

    # A doc written the old way, with no For the builders heading, is shown and approved whole.
    ready(repo, "GIFT", DOC)
    shown = flat(repo.forge("next").stdout)
    assert "in Claude Code, show plans/GIFT.md in Plan Mode" in shown
    assert "in Codex, show plans/GIFT.md, then ask" in shown
    recorded = hook(repo, claude_plan(claude_payload, DOC))
    assert recorded.returncode == 0, recorded.stderr
