"""A new starter records admin actions and serves them only to its organisation's admins."""
import pytest

from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FORGE-DEFAULTS-1/HISTORY"
HISTORY_API_CASES = ("an invite and a role change write change history",)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_4_admin_actions_write_change_history(tmp_path_factory):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run change history against the live API")
    _require_cases(live_run(tmp_path_factory)["api"], HISTORY_API_CASES)
