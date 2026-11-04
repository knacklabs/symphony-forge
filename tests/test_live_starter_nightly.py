"""Forge's live starter checks have a nightly home outside generated CI."""
from pathlib import Path
import re

STORY = "FIX-WINDOWS-AND-LIVE-TESTS-NIGHTLY"
ROOT = Path(__file__).resolve().parents[1]


def test_1_live_starter_checks_run_nightly_outside_the_full_suite():
    # Config boundary: losing the schedule or invite job silently loses live proof.
    # Other tests own starter behavior, not CI dispatch. No production seam is needed.
    smoke = (ROOT / ".github/workflows/starter-smoke.yml").read_text("utf-8")
    assert re.search(r"^  schedule:\n    - cron: '.+'$", smoke, re.M)
    job = re.search(r"^  organisation-invites-smoke:\n(.*?)(?=^  \S|\Z)",
                    smoke, re.M | re.S)[1]
    assert "FORGE_STARTER_LIVE: '1'" in job
    assert ("tests/test_defaults_organisations.py::"
            "test_2_admins_invite_by_email_and_members_cannot_change_roles_or_invite") in job
    full = (ROOT / ".github/workflows/forge.yml").read_text("utf-8")
    assert "FORGE_STARTER_LIVE" not in full
    assert "timeout-minutes: 60" in full
