"""The TypeScript starter supports one-company setup, invite-only accounts, and switching."""
import pytest

from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FORGE-SINGLECO-1"
SETUP_API_CASES = (
    "the setup command makes the company and its first admin",
)
INVITE_API_CASES = (
    "a one-company app refuses sign-up and still takes invites",
)
MANY_COMPANY_API_CASES = (
    "a one-company app becomes many-company by its setting alone",
    "defaults to many and accepts one or many",
    "rejects an unsupported value",
)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_2_setup_makes_the_company_and_its_first_admin(tmp_path_factory):
    # Audit: this requires the live API report to show successful setup, including duplicate and
    # invalid admin input. Existing many-company cases cannot catch a broken setup command. The
    # real Compose service, API, and database own the behavior; no production seam is needed.
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run one-company API checks")
    _require_cases(live_run(tmp_path_factory)["api"], SETUP_API_CASES)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_3_a_one_company_app_is_invite_only(tmp_path_factory):
    # This task owns the TypeScript API report. Python and browser report requirements belong to
    # their assigned tasks, which add their own names when those boundaries are ready.
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run one-company API checks")
    _require_cases(live_run(tmp_path_factory)["api"], INVITE_API_CASES)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_4_many_stays_the_default_and_the_switch_needs_no_migration(tmp_path_factory):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run one-company API checks")
    _require_cases(live_run(tmp_path_factory)["api"], MANY_COMPANY_API_CASES)
