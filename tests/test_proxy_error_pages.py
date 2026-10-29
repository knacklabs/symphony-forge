"""A starter web app reads a proxy's non-JSON error page as its normal request error, with the status."""
import pytest

from test_starter_tree import LIVE, _require_cases, live_run

STORY = "the-web-api-client-reads-every-reply-as"
PROXY_ERROR_FLOW = "a proxy error page reads as the normal request error with its status"


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_1_a_non_json_reply_raises_the_normal_request_error_with_its_status(tmp_path_factory):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run the starter's browser flows")
    _require_cases(live_run(tmp_path_factory)["browser"], (PROXY_ERROR_FLOW,))
