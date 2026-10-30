"""Close leaves equivalent settings alone, including Windows checkout bytes.

Audit: existing close-settings tests cover real changes and pin comments, but
not committed CRLF or a missing final newline. Real close owns the outcome;
only external review and GitHub are faked, with no new production seam.
"""
import pytest

from test_close import env  # noqa: F401
from test_close_preserves_default_settings import MESSAGE, _setup
from test_upgrade_command import Upgrade
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

pytestmark = pytest.mark.platform

STORY = "windows-test-fixes-2"


@pytest.mark.parametrize("client, ending, pin", [
    pytest.param(False, "\r\n", False, id="new-crlf"),
    pytest.param(False, "\r\n", True, id="new-crlf-pin"),
    pytest.param(False, "", False, id="new-no-final-newline"),
    pytest.param(True, "\r\n", True, id="adopted-crlf-pin"),
], indirect=["client"])
def test_1_close_leaves_equivalent_settings_and_the_branch_pin_untouched(
        env, client, tmp_path, ending, pin):
    folder, _, incoming = _setup(env, client, tmp_path)
    if pin:
        version = client.forge("--version").stdout.split()[-1]
        Upgrade(env, tmp_path).on_main(
            "forge.toml", incoming.replace(f'version = "{version}"', 'version = "v1.2.2"'))
        client.git("fetch", "-q", "origin", "main", cwd=folder)
    client.git("merge", "-q", "--no-commit", "origin/main", cwd=folder)
    # Store Windows bytes even on Unix, without checkout conversion hiding them.
    client.git("config", "core.autocrlf", "false", cwd=folder)
    text = incoming.replace('# main pin', '# branch pin') if pin else incoming
    content = (text.replace("\n", ending) if ending else text.rstrip("\n")).encode("utf-8")
    path = folder / "forge.toml"
    path.write_bytes(content)
    if pin:
        # A genuine version difference also needs the generated files for this
        # release, just like a real upgrade; do not bypass close's sync gate.
        synced = client.forge("sync", cwd=folder)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    client.git("add", "-A", cwd=folder)
    client.git("commit", "-qm", "Keep checkout formatting", cwd=folder)
    before = client.git("rev-parse", "HEAD", cwd=folder)

    closed = client.forge("close", "correct-spelling")

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    assert MESSAGE not in closed.stdout
    assert path.read_bytes() == content
    assert client.git("log", "--format=%H", f"{before}..HEAD", "--", "forge.toml", cwd=folder) == ""
    assert client.git("status", "--porcelain", cwd=folder) == ""
