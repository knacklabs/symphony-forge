"""Both client starters support one-company setup, invite-only accounts, and switching."""
import pytest

from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FORGE-SINGLECO-1"
pytest_plugins = ("test_python_starter",)
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
@pytest.mark.timeout(3600)
def test_2_setup_makes_the_company_and_its_first_admin(tmp_path_factory, request):
    # Audit: this requires the live API report to show successful setup, including duplicate and
    # invalid admin input. Existing many-company cases cannot catch a broken setup command. The
    # real Compose service, API, and database own the behavior; no production seam is needed.
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run one-company API checks")
    _require_cases(request.getfixturevalue("live_python_starter")["api"], (
        "test_the_setup_command_makes_the_company_and_its_first_admin",
    ))
    _require_cases(live_run(tmp_path_factory)["api"], SETUP_API_CASES)


@pytest.mark.platform
@pytest.mark.timeout(3600)
def test_3_a_one_company_app_is_invite_only(tmp_path_factory, request):
    # Both live API reports own this contract. The web task adds the browser requirements.
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run one-company API checks")
    _require_cases(request.getfixturevalue("live_python_starter")["api"], (
        "test_a_one_company_app_refuses_sign_up_and_still_takes_invites",
    ))
    _require_cases(live_run(tmp_path_factory)["api"], INVITE_API_CASES)


@pytest.mark.platform
@pytest.mark.timeout(3600)
def test_4_many_stays_the_default_and_the_switch_needs_no_migration(tmp_path_factory, request):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run one-company API checks")
    _require_cases(request.getfixturevalue("live_python_starter")["api"], (
        "test_a_one_company_app_becomes_many_company_by_its_setting_alone",
        "test_defaults_to_many_and_accepts_one_or_many",
        "test_rejects_an_unsupported_companies_setting",
    ))
    _require_cases(live_run(tmp_path_factory)["api"], MANY_COMPANY_API_CASES)
