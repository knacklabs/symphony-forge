"""Native handback restores committed settings without changing their bytes."""
import re

import pytest

from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_tools_session_hold import Session
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "FIX-WINDOWS-PLATFORM-SUBSET"


@pytest.mark.platform
@pytest.mark.parametrize("client", [False, True], indirect=True, ids=["new", "adopted"])
def test_4_handback_restores_committed_settings_with_their_original_bytes(client, monkeypatch, tmp_path):
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    client.git("switch", "-q", "fix/settings-setup")
    config = client.path / "forge.toml"
    original = (config.read_text("utf-8") + "# Main keeps CRLF\n").replace("\n", "\r\n").encode("utf-8")
    config.write_bytes(original)
    # This extends the client's pre-item setup, just like the client fixture itself.
    client.git("-c", f"core.hooksPath={(tmp_path / 'no-hooks').as_posix()}",
               "commit", "-qam", "Keep CRLF settings")
    client.git("switch", "-q", "main")
    client.git("merge", "-q", "--ff-only", "fix/settings-setup")
    _publish_default(client, client.git("remote", "get-url", "origin"))
    started = client.forge("fix", "start", "Correct spelling", "--done", "Correct the spelling",
                           "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = client.path.parent / f"{client.path.name}-fix-correct-spelling"
    # This covers native handback; installed SDK rounds restore settings through the driver.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "without-claude-sdk"))
    host = Session(client, tmp_path / "host", "claude-session")
    try:
        offered = host.forge("work", "correct-spelling")
        assert offered.returncode == 0, offered.stdout + offered.stderr
        number = re.search(r"--round (\d+)", offered.stdout)[1]
        # Native subagents can commit settings before handback enforces the worker boundary.
        (folder / "forge.toml").write_bytes(original + b"# Unauthorized setting\r\n")
        client.git("commit", "-qam", "Commit the worker edit", cwd=folder)

        returned = host.forge("handback", "correct-spelling", "--round", number,
                              "--subagent", "worker", "--text", "Committed.")
        assert returned.returncode == 0, returned.stdout + returned.stderr
        assert (folder / "forge.toml").read_bytes() == original
        assert client.git("status", "--porcelain", cwd=folder) == ""
    finally:
        host.close()
