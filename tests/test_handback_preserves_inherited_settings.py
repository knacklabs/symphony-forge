"""Hand-back keeps inherited and merged settings while removing worker edits.

Audit: the merge-base guard discards an unmerged parent's settings. Real work
and handback commands own this boundary; the session shim only hosts them.
Existing native-work cases cover default settings, not stacked fixes.
"""
import re
from pathlib import Path

import pytest

from test_tools_session_hold import Session
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "keep-main-settings-on-handback"


@pytest.mark.parametrize("client, case", [
    pytest.param(False, case, id=f"new-{case}")
    for case in ("inherited", "merged", "edit-before-merge", "edit-after-merge")
] + [pytest.param(True, "edit-before-merge", id="adopted-merged")], indirect=["client"])
def test_1_handback_keeps_inherited_and_incoming_settings(client, monkeypatch, tmp_path, case):
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    client.git("switch", "-q", "fix/settings-setup")
    original = (client.path / "forge.toml").read_text("utf-8")
    original = re.sub(r"^fast_test = .*\n", "", original, flags=re.M)
    original = 'fast_test = "echo original"\n' + '# Separate settings\n' * 10 + original
    client.write("forge.toml", original)
    client.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qam", "Set test commands")
    client.git("switch", "-q", "main")
    client.git("merge", "-q", "--ff-only", "fix/settings-setup")
    remote = Path(client.git("remote", "get-url", "origin")).as_posix()
    _publish_default(client, remote)

    started = client.forge("fix", "start", "Parent settings", "--done", "Update forge.toml",
                           "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    parent = client.path.parent / f"{client.path.name}-fix-parent-settings"
    inherited = re.sub(r"^test = .*", 'test = "echo inherited"', original, flags=re.M)
    if inherited == original:
        inherited = original.replace('fast_test =', 'test = "echo inherited"\nfast_test =', 1)
    (parent / "forge.toml").write_text(inherited, "utf-8")
    client.git("commit", "-qam", "Set the parent test command", cwd=parent)
    started = client.forge("fix", "start", "Child product", "--done", "Product work is done",
                           "--kind", "mechanical", cwd=parent)
    assert started.returncode == 0, started.stdout + started.stderr
    child = client.path.parent / f"{client.path.name}-fix-child-product"
    # This contract needs native handback; installed SDK rounds use the driver instead.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "without-claude-sdk"))
    host = Session(client, tmp_path / "host", "claude-session")
    try:
        given = host.forge("work", "child-product", cwd=child)
        assert given.returncode == 0, given.stdout + given.stderr
        number = re.search(r"forge handback child-product --round (\d+)", given.stdout)[1]
        expected = inherited

        def worker_edit():
            settings = child / "forge.toml"
            settings.write_text(settings.read_text("utf-8").replace(
                'test = "echo inherited"', 'test = "echo worker"'), "utf-8")
            client.git("commit", "-qam", "Worker changes settings", cwd=child)

        if case == "edit-before-merge":
            worker_edit()
        if case != "inherited":
            client.git("switch", "-q", "fix/settings-setup")
            client.write("forge.toml", original.replace('echo original', 'echo default'))
            client.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qam",
                       "Change the default test picker")
            client.git("switch", "-q", "main")
            client.git("merge", "-q", "--ff-only", "fix/settings-setup")
            _publish_default(client, remote)
            client.git("fetch", "-q", "origin", "main", cwd=child)
            client.git("merge", "-q", "--no-edit", "origin/main", cwd=child)
            expected = inherited.replace('echo original', 'echo default')
        if case == "edit-after-merge":
            worker_edit()
        (child / "product.txt").write_text("Product work\n", "utf-8")
        client.git("add", "product.txt", cwd=child)
        client.git("commit", "-qm", "Finish product work", cwd=child)
        returned = host.forge("handback", "child-product", "--round", number,
                              "--subagent", "builder", "--text", "Done.", cwd=child)
        assert returned.returncode == 0, returned.stdout + returned.stderr
        assert (child / "forge.toml").read_text("utf-8") == expected
        assert (child / "product.txt").read_text("utf-8") == "Product work\n"
        assert client.git("status", "--porcelain", cwd=child) == ""
    finally:
        host.close()
