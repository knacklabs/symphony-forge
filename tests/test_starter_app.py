"""Starter setup is opt-in, packaged, and leaves earlier apps alone."""
import re
import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path

import pytest

from test_setup import _fresh_client, _version
from test_doctor_fix_files import _land, _pin, _set, _start_fix
from test_worker import calls, install_claude

STORY = "FORGE-STARTER-1"
ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "src/forge/templates/starter"
COMMAND = "node scripts/test.mjs"


@pytest.mark.platform
@pytest.mark.parametrize("case", ["new", "wheel", "pyproject", "package.json", "adopted"])
def test_3_init_writes_the_starter_and_the_nx_pages(repo, gh, tmp_path, monkeypatch, case):
    # The real init owns copying; the wheel owns package inclusion, including dotfiles.
    paths = subprocess.run(
        ["git", "ls-files", "-z", "src/forge/templates/starter"], cwd=ROOT,
        capture_output=True, text=True, encoding="utf-8", check=True).stdout.rstrip("\0").split("\0")
    starter = [Path(path).relative_to("src/forge/templates/starter") for path in paths]
    if case == "wheel":
        built = subprocess.run(["uv", "build", "--wheel", "--out-dir", str(tmp_path / "dist")],
                               cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
        assert built.returncode == 0, built.stdout + built.stderr
        with zipfile.ZipFile(next((tmp_path / "dist").glob("*.whl"))) as wheel:
            for path in starter:
                assert wheel.read(f"forge/templates/starter/{path.as_posix()}") == (STARTER / path).read_bytes()
        return
    if case in ("pyproject", "package.json"):
        client, remote = tmp_path / "client", tmp_path / "client.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
        repo.git("remote", "add", "origin", str(remote), cwd=client)
        marker = "pyproject.toml" if case == "pyproject" else case
        (client / marker).write_text("{}\n", encoding="utf-8")
        before = repo.git("status", "--porcelain", "--ignored", "-uall", cwd=client)
        result = repo.forge("init", "--starter", cwd=client)
        assert result.returncode == 1, result.stdout + result.stderr
        assert marker in result.stdout + result.stderr
        assert repo.git("status", "--porcelain", "--ignored", "-uall", cwd=client) == before
        assert sorted(p.name for p in client.iterdir()) == [".git", marker]
        return
    if case == "new":
        client, result = _fresh_client(repo, gh, tmp_path, "--starter")
        assert result.returncode == 0, result.stdout + result.stderr
        [first] = repo.git("rev-list", "HEAD", cwd=client).splitlines()
        for path in starter:
            copied = subprocess.run(["git", "show", f"{first}:{path.as_posix()}"], cwd=client,
                                    capture_output=True, check=True).stdout
            assert copied == (STARTER / path).read_bytes(), path
        assert tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["test"] == COMMAND
    else:
        # Earlier adoption has app-owned deploy and test settings before the upgrade.
        shutil.copytree(ROOT / "tests/fixtures/doctor-v1.2.2", repo.path, dirs_exist_ok=True)
        repo.write("Dockerfile", "FROM node:24\n# Existing app\n")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Earlier adoption")
        before = repo.git("status", "--porcelain", "--ignored", "-uall")
        result = repo.forge("init", "--starter")
        assert result.returncode == 1, result.stdout + result.stderr
        assert "this repo already has commits" in (result.stdout + result.stderr).lower()
        assert repo.git("status", "--porcelain", "--ignored", "-uall") == before
        client = repo.path
        repo.git("push", "-q", "origin", "main")
        _land(repo, client, "Upgrade Forge", lambda folder: _set(
            folder, "forge.toml", _pin((folder / "forge.toml").read_text(encoding="utf-8"), _version(repo))))
        gh.respond("api", stdout="{}")
    client = _start_fix(repo, client, "Check starter guidance")
    settings = client / "forge.toml"
    settings.write_text(re.sub(r'workers = "[^"]+"', 'workers = "claude"', settings.read_text(encoding="utf-8")),
                        encoding="utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    if case == "adopted":
        assert (client / "Dockerfile").read_text(encoding="utf-8") == "FROM node:24\n# Existing app\n"
        assert tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["test"] == "npm test"
        for path in starter:
            if path.parts[0] in ("apps", "libs", "scripts") or path.name in (
                    "nx.json", "package.json", "package-lock.json", ".env.example"):
                assert not (client / path).exists(), path
    for host in (".claude", ".codex"):
        assert "forge init --starter" in (client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "--allow-empty", "-qm", "Current guidance", cwd=client)
    log = install_claude(repo)
    worked = repo.forge("work", "check-starter-guidance", cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = calls(log)[-1]["brief"]
    match = re.search(r"how-to.*?is in `([^`]+)`", brief, re.S)
    assert match, brief
    conventions = Path(match[1])
    stack = (conventions / "stack.md").read_text(encoding="utf-8")
    assert "Nx" in stack and "apps/web" in stack
    assert "React Router" in (conventions / "frontend.md").read_text(encoding="utf-8")
    keep = "An app set up before Nx keeps its npm workspaces and its Dockerfile."
    assert keep in stack
    for page in conventions.glob("*.md"):
        assert "npm workspaces" not in page.read_text(encoding="utf-8").replace(keep, ""), page
    assert COMMAND in (conventions / "testing.md").read_text(encoding="utf-8")
