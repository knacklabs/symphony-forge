"""A client receives the same app baseline in both agent hosts."""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

STORY = "FIX-APP-BASELINE"
ROOT = Path(__file__).resolve().parents[1]
BASELINE_SHA256 = "2f6876a725e67c0576437824ca67dc946d77a9566b4c312e6df764f5514e6d42"


def test_1_installed_sync_ships_app_baseline_to_both_agents(repo, tmp_path):
    # Pin the intended text so a shared source and package change cannot silently rewrite it.
    source = (ROOT / ".codex/skills/app-baseline/SKILL.md").read_text(
        encoding="utf-8").encode("utf-8")
    assert hashlib.sha256(source).hexdigest() == BASELINE_SHA256
    dist = tmp_path / "dist"
    subprocess.run(["uv", "build", "--wheel", "--sdist", "--out-dir", str(dist), str(ROOT)],
                   check=True, capture_output=True, text=True)

    repo.git("checkout", "-q", "-b", "fix/app-baseline")
    repo.write("forge.toml", 'version = "v1.2.1"\ntest = "true"\n')
    packages = (next(dist.glob("*.whl")), next(dist.glob("*.tar.gz")), ROOT)
    for kind, package in zip(("wheel", "sdist", "editable"), packages):
        env = tmp_path / kind
        subprocess.run(["uv", "venv", "--python", f"{sys.version_info.major}.{sys.version_info.minor}",
                        str(env)], check=True, capture_output=True, text=True)
        python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        forge = env / ("Scripts/forge.exe" if os.name == "nt" else "bin/forge")
        install = ["uv", "pip", "install", "--python", str(python), "--no-deps"]
        if kind == "editable":
            install.append("--editable")
        subprocess.run([*install, str(package)], check=True, capture_output=True, text=True)
        for host in (".claude", ".codex"):
            (repo.path / host / "skills/app-baseline/SKILL.md").unlink(missing_ok=True)
        synced = subprocess.run([str(forge), "sync"], cwd=repo.path,
                                capture_output=True, text=True)
        assert synced.returncode == 0, synced.stderr
        for host in (".claude", ".codex"):
            target = repo.path / host / "skills/app-baseline/SKILL.md"
            assert target.read_bytes() == source, (kind, host)
