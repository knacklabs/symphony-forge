"""New apps and generated features give members view and create only."""
import re

import pytest

from test_feature_command import NOTES_LINE, SHELLS, _run_line, _written_paths
from test_setup import _fresh_client

STORY = "FORGE-ONEPLAN-1"


@pytest.mark.platform
@pytest.mark.parametrize("starter", ["typescript", "python"])
def test_5_members_get_view_and_create_by_default(repo, gh, tmp_path, starter):
    # Audit: init and feature must ship the agreed mapping. Copying the older mapping
    # grants edit; existing feature tests derive their expectations from that mapping.
    # This checks command output with no production seam. Earlier-adopted apps are
    # covered by test_feature_access.py::test_3's sync case.
    typescript = starter == "typescript"
    client, initialized = _fresh_client(
        repo, gh, tmp_path, "--starter", "react" if typescript else "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    built = _run_line(repo, client, SHELLS[0], NOTES_LINE)
    assert built.returncode == 0, built.stdout + built.stderr
    _written_paths(built, client)
    for plural in ("projects", "notes"):
        path = (f"libs/{plural}/server/src/{plural}.permissions.ts" if typescript
                else f"apps/api/app/{plural}/permissions.py")
        mapping = (client / path).read_text("utf-8")
        roles = dict(re.findall(r'''["']?(admin|member)["']?\s*:\s*\[([^\]]*)\]''', mapping))
        assert {role: re.findall(r'''["'](\w+)["']''', actions)
                for role, actions in roles.items()} == {
            "admin": ["view", "create", "edit", "delete", "restore"],
            "member": ["view", "create"],
        }
