"""New starter apps remove members and old apps keep their code on sync."""

import json

import pytest

from test_setup import _fresh_client
from test_starter_tree import LIVE, _require_cases, live_python_run, live_run

STORY = "FORGE-MAIL-1/REMOVE"
REMOVAL_API_CASE = "an admin removes a member, who is signed out at once"


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python"])
def test_1_an_admin_removes_a_member(repo, gh, tmp_path, tmp_path_factory, starter):
    # Screen removal leaves the API behavior in place. The live API report owns immediate loss of
    # access and its side effects; the new-app check ensures each starter keeps that API route.
    client, initialized = _fresh_client(
        repo, gh, tmp_path, "--starter", "python" if starter == "python" else "react"
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    if starter == "python":
        # Audit: init must ship the public Python API contract; a stale generated schema
        # is independent of live route behavior, and TS coverage cannot catch it. No seam.
        schema = json.loads((client / "libs/shared/api-types/openapi.json").read_text("utf-8"))
        assert "delete" in schema["paths"]["/api/v1/members/{account_id}"]
    else:
        assert (client / "libs/auth/server/src/members.controller.ts").is_file()
    if LIVE:
        run = live_python_run(tmp_path_factory) if starter == "python" else live_run(tmp_path_factory)
        case = "test_an_admin_removes_a_member_who_is_signed_out_at_once" if starter == "python" else REMOVAL_API_CASE
        _require_cases(run["api"], (case,))
