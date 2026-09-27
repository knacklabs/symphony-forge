STORY = "FORGE-TRIM-1"

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    ".claude/skills/forge/fde.md": ".codex/skills/forge/fde.md",
    ".codex/skills/forge/fde.md": ".codex/skills/forge/fde.md",
    ".claude/skills/test-audit/SKILL.md": ".codex/skills/test-audit/SKILL.md",
    ".codex/skills/test-audit/SKILL.md": ".codex/skills/test-audit/SKILL.md",
    ".claude/skills/test-audit/NOTICE.md": ".codex/skills/test-audit/NOTICE.md",
    ".codex/skills/test-audit/NOTICE.md": ".codex/skills/test-audit/NOTICE.md",
    ".claude/skills/remote-approval/SKILL.md": ".claude/skills/remote-approval/SKILL.md",
}
OLD_COPIES = (
    "src/forge/templates/fde.md",
    "src/forge/templates/skills/test-audit/SKILL.md",
    "src/forge/templates/skills/test-audit/NOTICE.md",
    "src/forge/templates/skills/remote-approval/SKILL.md",
)


def test_2_sync_ships_one_source_copy_in_wheel_sdist_and_editable(repo, tmp_path):
    assert all(not (ROOT / rel).exists() for rel in OLD_COPIES)
    expected = {target: (ROOT / source).read_text(encoding="utf-8").encode("utf-8")
                for target, source in SOURCES.items()}
    dist = tmp_path / "dist"
    subprocess.run(["uv", "build", "--wheel", "--sdist", "--out-dir", str(dist), str(ROOT)],
                   check=True, capture_output=True, text=True)

    repo.git("checkout", "-q", "-b", "fix/skills")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "true"\n'
               'checks = ["tests", "forge-pr-check"]\n')
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
        for target in SOURCES:
            (repo.path / target).unlink(missing_ok=True)
        synced = subprocess.run([str(forge), "sync"], cwd=repo.path,
                                capture_output=True, text=True)
        assert synced.returncode == 0, synced.stderr
        assert {target: (repo.path / target).read_bytes() for target in SOURCES} == expected
