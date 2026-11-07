"""Init and upgrade deliver the early full-run instructions.

The guide is the agent's public contract: a missing dispatch instruction leaves
proof until tag push. Existing full-run tests own the proof gate, not when the
agent starts it. Real init/sync delivery needs no production test seam.
"""
from test_mod_guide import guide_files  # noqa: F401

STORY = "start-full-run-early"


def test_1_full_run_starts_after_last_product_merge_before_notes(guide_files):
    for path in guide_files:
        guide = " ".join(path.read_text(encoding="utf-8").split())
        assert "After the last product merge for a release or sign-off, start the full run at once" in guide
        assert "gh workflow run forge.yml --ref <default>" in guide
        assert "Prepare the release or sign-off notes while it runs, then follow that same run" in guide
        assert "A green full run on the latest default-branch commit is required before pushing a release tag" in guide
