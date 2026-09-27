"""The source checkout contains only state that the current Forge reads."""

import re
from pathlib import Path

STORY = "FIX-OLD-FORGE-RECORDS"
ROOT = Path(__file__).resolve().parents[1]


def test_1_only_current_forge_state_and_story_plans_remain(repo):
    assert repo.forge("--version").returncode == 0

    factory = {path.relative_to(ROOT).as_posix() for path in (ROOT / ".factory").rglob("*")
               if path.is_file()}
    assert all(re.fullmatch(
        r"\.factory/(?:stories/[A-Z][A-Z0-9-]*/(?:story\.json|tasks/[A-Z0-9-]+\.json)"
        r"|fixes/[^/]+\.json)", path) for path in factory), sorted(factory)

    plans = {path.relative_to(ROOT).as_posix() for path in (ROOT / "plans").rglob("*")
             if path.is_file()}
    assert all(re.fullmatch(r"plans/(?:[A-Z][A-Z0-9-]*(?:\.read)?\.md|roadmap\.json)",
                            path) for path in plans), sorted(plans)

    for old in ("WORKFLOW.md", ".review-notes.md", "projects", ".forge-migrate",
                ".claude/CLAUDE.md"):
        assert not (ROOT / old).exists(), old
