"""Python history attribution ships in new apps; sync preserves earlier app code."""
import json

import pytest

from test_agent_ready import _new_client
from test_mcp import _adopted_files_after_sync
from test_starter_tree import LIVE, _require_cases, live_python_run

STORY = "FORGE-ASSIST-1/HISTVIAPY"


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["python", "earlier adopted"])
def test_3_history_shows_the_agent(repo, gh, tmp_path, starter, tmp_path_factory):
    # Audit: init/sync own delivery and preservation; real API/Postgres owns list
    # and CSV attribution. OpenAPI independently guards the generated client
    # contract, read from the contract the live smoke run makes (no contract is committed,
    # so outside LIVE this test no longer checks it). Existing agent-ready tests prove
    # storage only. No new seam.
    if starter == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        assert after == before
        return
    client = _new_client(repo, gh, tmp_path, "python")
    assert not (client / "libs/shared/api-types/openapi.json").exists()
    if LIVE:
        document = live_python_run(tmp_path_factory)["contract"]
        field = document["components"]["schemas"]["HistoryEntry"]["properties"]["viaAgent"]
        assert {option["type"] for option in field["anyOf"]} == {"string", "null"}
        _require_cases(live_python_run(tmp_path_factory)["api"], (
            "test_history_list_and_csv_show_the_agent_that_acts_for_a_person",
        ))
