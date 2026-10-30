"""Close preserves main's CRLF settings and the branch's complete version pin."""
import pytest

from test_close import env  # noqa: F401
from test_close_preserves_default_settings import _setup
from test_upgrade_command import Upgrade
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "FIX-WINDOWS-PLATFORM-SUBSET"


@pytest.mark.platform
@pytest.mark.parametrize("client", [False, True], indirect=True, ids=["new", "adopted"])
def test_3_close_keeps_main_settings_bytes_and_the_branch_pin(env, client, tmp_path):
    folder, original, incoming = _setup(env, client, tmp_path)
    incoming = incoming.replace("\n", "\r\n")
    Upgrade(env, tmp_path).on_main("forge.toml", incoming, "Keep CRLF settings")
    client.git("fetch", "-q", "origin", "main", cwd=folder)
    client.git("merge", "-q", "--no-commit", "origin/main", cwd=folder)
    # A worker left old settings in its merge. Close restores main and retains its pin.
    (folder / "forge.toml").write_bytes(original.encode("utf-8"))
    client.git("add", "forge.toml", cwd=folder)
    client.git("commit", "-qm", "Finish the worker merge", cwd=folder)

    closed = client.forge("close", "correct-spelling")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    expected = incoming.replace("# main pin", "# branch pin").encode("utf-8")
    assert (folder / "forge.toml").read_bytes() == expected
    assert client.git("status", "--porcelain", cwd=folder) == ""
