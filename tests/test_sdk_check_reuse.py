"""Work reuses the SDK probe until its installation marker changes."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, ROOT, _install, patient
from test_codex_setup import _workers
from test_codex_worker import PIN, sdk_data  # noqa: F401
from test_setup import _fresh_client, _version

STORY = "cache-sdk-check"


@pytest.mark.parametrize("setup", ["new", "earlier-adopted"])
def test_1_work_reuses_sdk_check_until_ready_marker_changes(
        repo, gh, tmp_path, monkeypatch, sdk_data, claude_session, setup):
    # Real work commands and SDK; count --version at the bundled Codex program's edge.
    # Previously every work command ran this probe, even for an unchanged install.
    if setup == "new":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        made = repo.forge("fix", "start", "Reuse the SDK check", "--done",
                          "Work reuses the SDK check", cwd=client)
        item = "reuse-the-sdk-check"
        client = Path(made.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    else:
        old = tmp_path / "previous-release"
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old))
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(
            python=sys.executable, src=str(old / "src")))
        gh.respond("api", stdout="{}")
        made = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init",
                               "--test", "echo ok", "--checks", "tests",
                               "--interfaces", "api/routes/**", "--approver", "Owner",
                               "--merger", "Owner"], cwd=repo.path,
                              capture_output=True, text=True, encoding="utf-8", timeout=120)
        client = repo.path.parent / "repo-fix-adopt-forge"
        item = "adopt-forge"
        config = client / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), "utf-8")
    assert made.returncode == 0, made.stdout + made.stderr
    _workers(client, "codex")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Use Codex workers", cwd=client)
    common = Path(repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=client)).parent
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(common))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    data = tmp_path / "sdk-data"
    relative = Path("forge/codex-sdk") / f"openai-codex-{PIN}"
    patient(lambda: shutil.copytree(sdk_data / relative, data / relative, symlinks=os.name != "nt"))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    probes = tmp_path / "probes"
    program = (ROOT / "tests/stubs/codex-app-server").read_text("utf-8")
    program = program.replace('VERSION = ',
        'if "--version" in sys.argv:\n'
        f'    with open({json.dumps(str(probes))}, "a", encoding="utf-8") as out:\n'
        '        out.write("probe\\n")\n\nVERSION = ', 1)
    _install(repo.bin, "codex-app-server", program)
    monkeypatch.setenv("CODEX_BIN", str(repo.bin / (
        "codex-app-server.cmd" if os.name == "nt" else "codex-app-server")))
    marker = data / relative / "forge-sdk-ready"

    def work():
        done = repo.forge("work", item, cwd=client)
        assert done.returncode == 0, done.stdout + done.stderr

    work()
    work()
    assert probes.read_text("utf-8").splitlines() == ["probe"]
    stamp = marker.stat().st_mtime_ns
    os.utime(marker, ns=(stamp + 2_000_000_000, stamp + 2_000_000_000))
    work()
    assert probes.read_text("utf-8").splitlines() == ["probe", "probe"]
    # A missing ready marker must never reuse the previous success.
    marker.unlink()
    missing = repo.forge("work", item, cwd=client)
    assert missing.returncode == 1 and "isn't installed" in missing.stderr
    marker.write_text(PIN + "\n", "utf-8")
    work()
    assert probes.read_text("utf-8").splitlines() == ["probe"] * 3
