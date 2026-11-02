"""The linked run reference ships at init and after an earlier adoption.

Contract: coordinators open run details only when needed. A missing target or
moving deploy permission out breaks it. Mod tests do not cover this split.
The real init/sync commands need no new production seam.
"""
from test_mod_guide import guide_files  # noqa: F401

STORY = "the-shipped-forge-guide-is-about-171-kb"


def test_1_run_details_are_linked_and_deploy_permission_stays_in_the_guide(guide_files):
    for path in guide_files:
        shipped = path.read_text(encoding="utf-8")
        assert "[run reference](run-reference.md)" in shipped
        assert "waiting or stopped" in shipped
        assert "## Machine views" not in shipped
        assert "## The pane and strip" not in shipped
        assert "Use Mainline Deploy only when the user explicitly requests deployment" in shipped
        reference = (path.parent / "run-reference.md").read_text(encoding="utf-8")
        for heading in ("Machine views", "Claude Code plugin core", "Installing the mod",
                        "Approving with the pane", "The pane and strip"):
            assert f"## {heading}\n" in reference
        assert "Mainline" not in reference
