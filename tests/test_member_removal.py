"""New TypeScript apps remove members and old apps keep their code on sync."""

import pytest

from test_mcp import _adopted_files_after_sync
from test_setup import _fresh_client
from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FORGE-MAIL-1/REMOVE"
REMOVAL_API_CASE = "an admin removes a member, who is signed out at once"


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "earlier adopted"])
def test_1_an_admin_removes_a_member(repo, gh, tmp_path, tmp_path_factory, starter):
    # Audit: the live API case owns immediate loss of access and its removal side effects; this
    # test also protects starter init and the earlier-adopted upgrade boundary. Without it, a new
    # app can omit the route or sync can overwrite existing app code. No production seam is used.
    if starter == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        assert after == before
        return

    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert (client / "libs/auth/server/src/members.controller.ts").is_file()
    if LIVE:
        _require_cases(live_run(tmp_path_factory)["api"], (REMOVAL_API_CASE,))
