"""A new starter keeps project data inside its organisation."""
import pytest

from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FORGE-DEFAULTS-1"
ORGANISATION_API_CASES = (
    "organisation isolation: another organisation gets 404 and the project stays unchanged",
    "a new account is the only admin of its own organisation",
)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_1_one_organisations_records_never_reach_another(tmp_path_factory):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run organisation isolation against the live API")
    _require_cases(live_run(tmp_path_factory)["api"], ORGANISATION_API_CASES)
