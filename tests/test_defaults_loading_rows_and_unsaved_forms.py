"""New starter apps show skeleton rows while lists load and ask before a form drops typed text."""
import pytest

from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FIX-TYPED-TEXT-IN-THE-INVITE-AND-ADD-AGENT-F"

# The Python starter copies this same React web, so the TypeScript run proves both.
LOADING_FLOW = "the projects, members and change history lists show skeleton rows while they load"
UNSAVED_FLOW = "the invite and add-agent forms ask before they close with unsaved text"


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_1_lists_show_skeleton_rows_while_loading(tmp_path_factory):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run the starter's browser flows")
    _require_cases(live_run(tmp_path_factory)["browser"], (LOADING_FLOW,))


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_2_invite_and_add_agent_forms_ask_before_closing_with_unsaved_text(tmp_path_factory):
    if not LIVE:
        pytest.skip("set FORGE_STARTER_LIVE=1 to run the starter's browser flows")
    _require_cases(live_run(tmp_path_factory)["browser"], (UNSAVED_FLOW,))
