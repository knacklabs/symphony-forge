"""One approved plan reaches both hosts and the worker's demo-data page."""
import pytest

from test_guides_agree import guided_client, _worker_conventions

STORY = "FORGE-ONEPLAN-1"


@pytest.mark.platform
def test_2_the_guide_says_one_plan_then_build_every_record_type(repo, guided_client, request):
    # Audit: delivered prompt text is the contract; stale init/sync instructions can
    # restore extra approvals. Gate tests do not check host delivery. Reuse real
    # init/sync fixtures, with no new production seam.
    sentences = (
        "Then write the prototype plan: record types with their fields in `docs/product/BRIEF.md`, the Roles table and architecture choices in `docs/product/CONSTITUTION.md`, one link to the design in the BRIEF, and the demo steps.",
        "Each demo step is one Done-when item in the plan, with the client's business task first and basic screens (sign-in, members, settings) last.",
        'Run `forge decision accept prototype-plan --by "<name>"` once, then build.',
        "Right after approval, build every record type in the plan with `forge task feature`, with the Roles table and without more questions.",
        "For each record type whose row differs from the command's default (member view, create), edit that feature's one `definePermissions` call.",
        "The design can be made through Forge or separately; the BRIEF holds one link to it.",
        "A UI fix needs no saved design images.",
        "Run each demo step from the plan in a browser and write its Proof line unticked.",
        "Write the tick only when the client says yes during the demo, with how and when the client replied.",
        "A screenshot-only change skips code review.",
        "A full review after sign-off holds work that goes against the Roles table and architecture choices.",
        "For every prototype, build the demo-data loader in the first version",
        "The approval before the prototype needs neither a saved design nor a personal-data answer.",
        "The light review of a prototype fix holds only serious problems (P0).",
    )
    for host in (".claude", ".codex"):
        guide = " ".join((guided_client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        for sentence in sentences:
            assert sentence in guide, sentence
        for obsolete in ('decision accept prototype-design', 'decision accept prototype-build',
                         'decision accept app-constitution'):
            assert obsolete not in guide
        assert "## Roles" in guide
        assert "| admin | view, create, edit, delete, restore |" in guide
        assert "| member | view, create |" in guide
    if request.node.callspec.params["guided_client"] == "previous release":
        changed = repo.git("diff", "--name-only", "HEAD~1", "HEAD", cwd=guided_client).splitlines()
        assert changed
        # An earlier release also gains Forge's host roles, hooks, settings and
        # CI files. Allow those managed paths while still excluding app code.
        assert all(name.startswith((".claude/", ".codex/", ".forge/", ".github/workflows/")) or
                   name in ("AGENTS.md", "CLAUDE.md", ".gitattributes", ".gitignore")
                   for name in changed), changed
        assert not repo.git("status", "--porcelain", "-uall", cwd=guided_client)


@pytest.mark.platform
def test_3_the_demo_data_page_asks_for_about_20_records(repo, guided_client):
    # Audit: the worker receives this page through its real brief. Missing quantity,
    # vocabulary or Python path causes the wrong loader; older tests own its guards.
    # Reuse worker setup and add no production seam.
    pages = _worker_conventions(repo, guided_client)
    demo = " ".join((pages / "demo-data.md").read_text("utf-8").split())
    for sentence in ("About 20 records for each record type", "in the client's words",
                     "no real personal data", "for the prototype and its demo run only, never production",
                     "apps/api/app/demo/"):
        assert sentence in demo, sentence
