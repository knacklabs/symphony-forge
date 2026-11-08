"""Repos without a speed setting request normal Codex turns."""
import os
from pathlib import Path
import re
import shutil

import pytest

from conftest import ROOT, patient
from test_codex_fast_when_work_waits import _tiers
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_tools_session_hold import Session

STORY = "FIX-CODEX-FAST-OFF-BY-DEFAULT"
pytestmark = pytest.mark.usefixtures("claude_session")


@pytest.mark.parametrize("adopted, coordinator", [
    (False, "claude"), (True, "claude"), (False, "codex"), (True, "codex"),
], ids=["new", "earlier-adopted", "new-codex", "earlier-adopted-codex"])
def test_1_no_setting_requests_normal_speed_for_fixes_and_repair_rounds(
        repo, monkeypatch, sdk_data, tmp_path, adopted, coordinator):
    # Omission must mean normal speed, even for fixes and repair rounds.
    # Existing coverage assumes needed by default; the stub only reports requests.
    # Real init/sync/work commands own the policy, with no production test seam.
    _, calls = _codex_repo(repo, monkeypatch, sdk_data, client=True, start_task=False)
    if adopted:
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                                       repo.path, dirs_exist_ok=True))
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(re.sub(r'^version = .*$', f'version = "{version}"',
                                 config.read_text("utf-8"), flags=re.M), "utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade earlier adoption")
        repo.git("push", "-q", "origin", "main")
    assert "codex_fast" not in (repo.path / "forge.toml").read_text("utf-8")
    _tiers(repo, [{"id": "priority", "name": "Fast"}])
    started = repo.forge("fix", "start", "Correct the login label", "--done", "It says Log in")
    assert started.returncode == 0, started.stdout + started.stderr
    if adopted:
        folder = repo.path.parent / f"{repo.path.name}-fix-correct-the-login-label"
        synced = repo.forge("sync", cwd=folder)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-qm", "Refresh earlier adoption", cwd=folder)
    # A Codex coordinator can have Fast on. Its native children inherit that tier,
    # so only a worker whose own turn requests normal speed can honor omission.
    host = None
    if coordinator == "codex":
        monkeypatch.delenv("CLAUDECODE")
        monkeypatch.setenv("CODEX_THREAD_ID", "fast-coordinator")
        config = Path(os.environ["CODEX_HOME"]) / "config.toml"
        config.write_text('service_tier = "priority"\n' + config.read_text("utf-8"), "utf-8")
        host = Session(repo, tmp_path / "host", "codex-session")
    try:
        for _ in range(2):
            worked = (host or repo).forge("work", "correct-the-login-label")
            assert worked.returncode == 0, worked.stdout + worked.stderr
            assert "subagent of this session" not in worked.stdout
            assert _sent(calls, "turn/start")[-1].get("serviceTierForTurn") == "default"
    finally:
        if host:
            host.close()
