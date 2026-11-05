"""History attribution ships in new apps; sync preserves earlier app code."""
import pytest

from test_agent_ready import _new_client
from test_mcp import _adopted_files_after_sync
from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FORGE-ASSIST-1"


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "earlier adopted"])
def test_3_history_shows_the_agent(repo, gh, tmp_path, starter, tmp_path_factory):
    # Audit: init/sync own delivery and preservation; the real API/database case owns
    # list and CSV attribution. Existing agent-ready tests prove storage only.
    # No production seam is added; record through the existing public service.
    if starter == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        assert after == before
        return
    client = _new_client(repo, gh, tmp_path)
    assert (client / "apps/api/test/history.e2e-spec.ts").is_file()
    if LIVE:
        _require_cases(live_run(tmp_path_factory)["api"], (
            'the history list carries viaAgent; the CSV Who column shows the email followed by ", via the assistant"; a change with no agent shows the email only',
        ))
