"""New and previously adopted clients receive Windows guidance without new settings."""
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_setup import _fresh_client, _version
from test_worker import calls, install_claude

STORY = "workers-build-on-macos-or-linux-so-windo"


@pytest.mark.parametrize("setup", ["new", "previous-release adoption"])
def test_1_sync_and_worker_brief_carry_the_windows_checklist(repo, gh, tmp_path, monkeypatch, setup):
    # This guards delivery of the checklist, not whether a model follows it. The only fake
    # is Claude at its process boundary; Forge generates and sends the actual brief.
    log = install_claude(repo)
    if setup == "new":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        made = repo.forge("fix", "start", "Check Windows guidance", "--done",
                          "Workers receive the Windows checklist", cwd=client)
        client = tmp_path / "client-fix-check-windows-guidance"
        item = "check-windows-guidance"
    else:
        old = tmp_path / "previous-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(
            python=sys.executable, src=str(old / "src")))
        gh.respond("api", stdout="{}")
        made = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init",
                               "--test", "echo ok", "--checks", "tests",
                               "--interfaces", "api/routes/**", "--approver", "Owner",
                               "--merger", "Owner"], cwd=repo.path,
                              capture_output=True, text=True)
        client = repo.path.parent / "repo-fix-adopt-forge"
        item = "adopt-forge"
        assert "Windows checklist" not in (
            client / ".codex/skills/forge/standards.md").read_text(encoding="utf-8")
    assert made.returncode == 0, made.stdout + made.stderr
    config = client / "forge.toml"
    text = config.read_text(encoding="utf-8")
    text = text.replace('version = "v1.2.2"', f'version = "{_version(repo)}"')
    text = text.replace('workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"')
    config.write_text(text, encoding="utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert config.read_text(encoding="utf-8") == text
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Configure Windows guidance", cwd=client)
    built = repo.forge("work", item, cwd=client)
    assert built.returncode == 0, built.stdout + built.stderr
    brief = calls(log)[-1]["brief"].split("## Standards")[0]
    pages = [brief, *((client / host / "skills/forge/standards.md").read_text(
        encoding="utf-8") for host in (".claude", ".codex"))]
    for page in pages:
        flat = " ".join(page.split())
        for rule in (
            "Windows checklist",
            "A path written into a file or compared as text goes through `json.dumps` or `as_posix`",
            "Tests never assume a drive letter or a '/' separator",
            "File operations in tests use the repo's lock-safe helpers where it has them",
        ):
            assert rule in flat, rule
