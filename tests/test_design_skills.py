"""Client init and upgrade deliver licensed design tools; Forge keeps its own tools."""
import os
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_setup import _fresh_client, _version

STORY = "FORGE-NOSCREENS-1"


# Gate: delivered paths, licences, mode and app preservation are the public contract.
# Missing ships discovery, packaging or executable mode is the credible regression.
# Existing inventories lack old adoption, doctor and mode; no test seam is needed.
# Installer transport has its independent owner in test_sales_install.
@pytest.mark.parametrize("case", ["new init", "previous release", "forge repo"])
def test_8_a_client_repo_gets_the_design_skills_and_the_installers_install_them(repo, gh, tmp_path, case):
    if case == "forge repo":
        repo.git("checkout", "-q", "-b", "fix/design-skills")
        repo.write("forge.toml", f'version = "{_version(repo)}"\nrepo = "forge-source"\ntest = "true"\n')
        client = repo.path
    elif case == "new init":
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        old = tmp_path / "previous-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(python=sys.executable, src=str(old / "src")))
        gh.respond("api", stdout="{}")
        made = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init",
                               "--test", "echo ok", "--checks", "tests",
                               "--interfaces", "api/routes/**", "--approver", "Owner",
                               "--merger", "Owner"], cwd=repo.path, capture_output=True, text=True)
        assert made.returncode == 0, made.stdout + made.stderr
        client = repo.path.parent / "repo-fix-adopt-forge"
        config = client / "forge.toml"
        config.write_text(config.read_text(encoding="utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), encoding="utf-8")
        for rel in ("apps/web/package.json", "apps/web/keep.tsx", "libs/example/keep.py"):
            target = client / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('{}\n' if rel.endswith('.json') else '# Keep client code\n', encoding="utf-8")
    before = {p.relative_to(client): p.read_bytes() for folder in ("apps", "libs")
              for p in (client / folder).rglob("*") if p.is_file()}
    if case != "new init":
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    assert before == {p.relative_to(client): p.read_bytes() for folder in ("apps", "libs")
                      for p in (client / folder).rglob("*") if p.is_file()}
    for host in (".claude", ".codex"):
        for name in ("impeccable", "emil-design-eng"):
            folder = client / host / "skills" / name
            if case == "forge repo":
                assert not folder.exists()
                continue
            for filename in ("SKILL.md", "LICENSE"):
                assert (folder / filename).is_file(), (case, host, name, filename)
            source = ROOT / "src/forge/templates/skills" / name
            expected = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
            assert expected == {p.relative_to(folder): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        if case != "forge repo" and os.name != "nt":
            assert os.access(client / host / "skills/impeccable/scripts/impeccable", os.X_OK)
        if case == "new init":
            # Init commits the pinned Windows launcher too, without Git changing its CRLF bytes.
            launcher = "skills/impeccable/scripts/impeccable.cmd"
            committed = subprocess.run(["git", "show", f"HEAD:{host}/{launcher}"], cwd=client,
                                       check=True, capture_output=True)
            assert committed.stdout == (ROOT / "src/forge/templates" / launcher).read_bytes()
    if case != "forge repo":
        web = client / "apps/web/package.json"
        web.parent.mkdir(parents=True, exist_ok=True)
        if not web.exists():
            web.write_text('{}\n', encoding="utf-8")
        checked = repo.forge("doctor", cwd=client)
        assert checked.returncode in (0, 1) and checked.stdout, checked.stdout + checked.stderr
        assert "Traceback" not in checked.stderr, checked.stderr
        assert "is required for UI work but isn't installed" not in checked.stdout, checked.stdout
