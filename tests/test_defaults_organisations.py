"""A new starter scopes project data and protects organisation invites and roles."""
import pytest

from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FORGE-DEFAULTS-1"
ORGANISATION_API_CASES = (
    "organisation isolation: another organisation gets 404 and the project stays unchanged",
    "a new account is the only admin of its own organisation",
)
PYTHON_ORGANISATION_API_CASES = (
    "test_organisation_isolation_returns_404_and_leaves_the_project_unchanged",
    "test_a_new_account_is_the_only_admin_of_its_organisation",
)
INVITE_API_CASES = (
    "an admin invites a person by email who joins the organisation",
    "a member cannot invite people or change roles",
    "an admin changes another member's role but not their own",
    "an admin cannot change the role of another organisation's account",
    "an invite link works once and only for its email",
    "production refuses an invite without a mail provider",
)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_1_one_organisations_records_never_reach_another(tmp_path_factory):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run organisation isolation against the live API")
    _require_cases(live_run(tmp_path_factory)["api"], ORGANISATION_API_CASES)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_2_admins_invite_by_email_and_members_cannot_change_roles_or_invite(tmp_path_factory):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run organisation invites against the live API")
    _require_cases(live_run(tmp_path_factory)["api"], INVITE_API_CASES)
