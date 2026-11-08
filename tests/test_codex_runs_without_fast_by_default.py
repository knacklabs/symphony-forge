"""Repos without a speed setting request normal Codex turns."""
import json
import os
from pathlib import Path
import re
import shutil
import sys

import pytest

from conftest import ROOT, _install, patient
from test_codex_fast_when_work_waits import _tiers
from test_codex_setup import PIN, _signed_in_codex
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_tools_missing import _hide
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
    if coordinator == "codex":
        config = repo.path / "forge.toml"
        config.write_text('tools = "codex"\n' + config.read_text("utf-8"), "utf-8")
        repo.git("commit", "-qam", "Use only Codex")
        repo.git("push", "-q", "origin", "main")
    assert "codex_fast" not in (repo.path / "forge.toml").read_text("utf-8")
    _tiers(repo, [{"id": "priority", "name": "Fast"}])
    started = repo.forge("fix", "start", "Correct the login label", "--done", "It says Log in")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = repo.path.parent / f"{repo.path.name}-fix-correct-the-login-label"
    if adopted:
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
        _signed_in_codex(repo)
        _hide(repo, ["claude"])
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "empty-data"))
        # Only the package manager is fake: it installs the cached real SDK.
        # Doctor must choose to install it without Claude, and work must use it.
        donor = next((sdk_data / "forge/codex-sdk" / f"openai-codex-{PIN}").rglob("site-packages"))
        _install(repo.bin, "uv", f'''#!{sys.executable}
import json, pathlib, shutil, subprocess, sys
args = sys.argv[1:]
with open(pathlib.Path(__file__).resolve().parent / "uv-calls.jsonl", "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
if args[0] == "venv":
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", args[-1]], check=True)
elif args[:2] == ["pip", "install"]:
    python = args[args.index("--python") + 1]
    target = subprocess.run([python, "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
                            capture_output=True, text=True, check=True).stdout.strip()
    shutil.copytree({json.dumps(donor.as_posix())}, target, dirs_exist_ok=True)
''')
        host = Session(repo, tmp_path / "host", "codex-session")
    try:
        if host:
            blocked = host.forge("work", "correct-the-login-label")
            assert blocked.returncode == 1 and "Codex SDK" in blocked.stderr, blocked.stderr
            assert "Next: forge doctor --fix" in blocked.stderr
            checked = host.forge("doctor", cwd=folder)
            assert f"The Codex SDK {PIN} isn't installed" in checked.stdout, checked.stdout
            repaired = host.forge("doctor", "--fix", cwd=folder)
            assert f"Installed the Codex SDK {PIN}" in repaired.stdout, repaired.stdout + repaired.stderr
            assert "Installing the Claude Agent SDK" not in repaired.stdout
            requests = [json.loads(line) for line in
                        (repo.bin / "uv-calls.jsonl").read_text("utf-8").splitlines()]
            assert [call[-1] for call in requests if call[:2] == ["pip", "install"]] == [
                f"openai-codex=={PIN}"]
        for _ in range(2):
            worked = (host or repo).forge("work", "correct-the-login-label")
            assert worked.returncode == 0, worked.stdout + worked.stderr
            assert "subagent of this session" not in worked.stdout
            assert _sent(calls, "turn/start")[-1].get("serviceTierForTurn") == "default"
    finally:
        if host:
            host.close()
