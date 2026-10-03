"""The phone-readable guidance Forge delivers to both agents and story authors."""

import re

from test_story import setup, worktree

STORY = "FIX-FORGE-S-QUESTIONS-AND-STORY-DOCS-ARE-HAR"


def synced_skills(repo):
    setup(repo)
    repo.git("checkout", "-q", "-b", "fix/readable-docs")
    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    claude = (repo.path / ".claude/skills/forge/SKILL.md").read_text(encoding="utf-8")
    codex = (repo.path / ".codex/skills/forge/SKILL.md").read_text(encoding="utf-8")
    assert claude == codex
    return claude


def test_1_questions_have_short_context_headers_and_outcome_options_after_sync(repo):
    skill = synced_skills(repo)
    assert "one line of context" in skill
    assert "12 characters or less" in skill
    assert "1-5 word options" in skill
    assert "say what happens" in skill
    assert "recommended one first" in skill
    assert "no IDs, paths or slugs" in skill


def test_2_story_done_when_and_builder_sections_are_readable_after_sync(repo):
    skill = synced_skills(repo)
    # FORGE-SHORTPLAN-1: each item was a bold sentence followed by its detail; now it is the bold
    # sentence alone, and the detail moves under the same number in Done-when details below.
    assert "one bold plain sentence and nothing more" in skill
    # New and existing repo planning now sits between Done when and Risks; the owner's
    # sections still precede the builder details.
    assert "Put Risks after New and existing repos" in skill
    assert "For the builders" in skill

    made = repo.forge("story", "new", "SHOP", "Shoppers can save a basket")
    assert made.returncode == 0, made.stderr
    doc = (worktree(repo, "story/SHOP") / "plans/SHOP.md").read_text(encoding="utf-8")
    assert re.search(r"^1\. \*\*[^*]+\.\*\*$", doc, re.M)
    headings = re.findall(r"^## (.+)$", doc, re.M)
    assert headings.index("Done when") + 1 == headings.index("New and existing repos")
    assert headings.index("New and existing repos") + 1 == headings.index("Risks")
    assert headings.index("Risks") < headings.index("For the builders") < headings.index("Tasks")


def test_3_plan_framing_and_status_updates_have_one_shape_after_sync(repo):
    skill = synced_skills(repo)
    assert "one framing line before showing a story in Plan Mode" in skill
    assert "Approving: <title>, <n> parts, <risks>" in skill
    assert "Ready to merge (n): ... · Needs you (n): ..." in skill


def test_4_new_story_has_an_at_a_glance_line_outside_approved_sections(repo):
    synced_skills(repo)
    made = repo.forge("story", "new", "SHOP", "Shoppers can save a basket")
    assert made.returncode == 0, made.stderr
    doc = (worktree(repo, "story/SHOP") / "plans/SHOP.md").read_text(encoding="utf-8")
    lines = doc.splitlines()
    assert lines[:5] == [
        "# Shoppers can save a basket",
        "",
        "<n> parts · Risks: ... · New moving parts: ...",
        "",
        "## What changes for you",
    ]
