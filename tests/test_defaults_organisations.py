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
PYTHON_INVITE_API_CASES = (
    "test_an_admin_invites_a_person_by_email_who_joins_the_organisation",
    "test_a_member_cannot_invite_people_or_change_roles",
    "test_an_admin_changes_another_members_role_but_not_their_own",
    "test_an_admin_cannot_change_the_role_of_another_organisations_account",
    "test_an_invite_link_works_once_and_only_for_its_email",
    "test_production_refuses_an_invite_without_a_mail_provider",
)
INVITE_API_CASES = (
    "an admin invites a person by email who joins the organisation",
    "a member cannot invite people or change roles",
    "an admin changes another member's role but not their own",
    "an admin cannot change the role of another organisation's account",
    "an invite link works once and only for its email",
    "production refuses an invite without a mail provider",
)
MEMBERS_FLOW = "only an admin sees the invite and role controls"
JOIN_FLOW = "an admin invites a person who joins and sees the same projects"
pytest_plugins = ("test_python_starter",)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_1_one_organisations_records_never_reach_another(tmp_path_factory):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run organisation isolation against the live API")
    _require_cases(live_run(tmp_path_factory)["api"], ORGANISATION_API_CASES)


@pytest.mark.platform
@pytest.mark.timeout(3600)
def test_2_admins_invite_by_email_and_members_cannot_change_roles_or_invite(
    tmp_path_factory, request
):
    # Audit: this checks the invite contract names in each starter's real API test report. The
    # React checks alone cannot detect a missing Python HTTP case; both harnesses use live apps
    # and databases, with only mail represented by the starter's logged test link.
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run organisation invites against the live API")
    python_live = request.getfixturevalue("live_python_starter")
    _require_cases(python_live["api"], PYTHON_INVITE_API_CASES)
    _require_cases(python_live["browser"], (MEMBERS_FLOW, JOIN_FLOW))
    react_live = live_run(tmp_path_factory)
    _require_cases(react_live["api"], INVITE_API_CASES)
    _require_cases(react_live["browser"], (MEMBERS_FLOW, JOIN_FLOW))
