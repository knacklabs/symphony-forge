"""A new starter writes one private error report for an API or UI crash."""
import pytest

from test_python_starter import live_python_starter  # noqa: F401 - registers the Python smoke fixture
from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FORGE-DEFAULTS-1"
API_REPORT_CASES = (
    "accepts a public report without its page query or fragment",
    "an API crash writes one error report",
)
PYTHON_API_REPORT_CASES = (
    "an_api_crash_writes_one_error_report",
    "accepts_a_public_web_error_report_and_logs_only_its_safe_fields",
)
UI_REPORT_FLOW = "a UI crash writes one error report"


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_5_a_ui_crash_and_an_api_crash_each_write_one_error_report(tmp_path_factory, request):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run the API and browser error-report flows")

    starter = live_run(tmp_path_factory)
    _require_cases(starter["api"], API_REPORT_CASES)
    _require_cases(starter["browser"], (UI_REPORT_FLOW,))

    python_starter = request.getfixturevalue("live_python_starter")
    _require_cases(python_starter["api"], PYTHON_API_REPORT_CASES)
    _require_cases(python_starter["browser"], (UI_REPORT_FLOW,))
