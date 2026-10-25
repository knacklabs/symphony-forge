"""A new starter records admin actions and serves them only to its organisation's admins."""
import pytest

from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FORGE-DEFAULTS-1/HISTORY"
HISTORY_API_CASES = ("an invite and a role change write change history",)
PYTHON_HISTORY_API_CASES = ("test_an_invite_and_a_role_change_write_change_history",)
pytest_plugins = ("test_python_starter",)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_4_admin_actions_write_change_history(tmp_path_factory, request):
    # Audit: the live report must include the Python HTTP contract too. React coverage cannot
    # detect a missing Python history route or record. Reuse the real starter fixture and its
    # API report, with no production seam or second copy of the HTTP scenario.
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run change history against the live API")
    python_live = request.getfixturevalue("live_python_starter")
    _require_cases(python_live["api"], PYTHON_HISTORY_API_CASES)
    _require_cases(live_run(tmp_path_factory)["api"], HISTORY_API_CASES)
