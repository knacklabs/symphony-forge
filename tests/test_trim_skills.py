STORY = "FORGE-TRIM-1"

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    ".claude/skills/forge/fde.md": ".codex/skills/forge/fde.md",
    ".codex/skills/forge/fde.md": ".codex/skills/forge/fde.md",
    ".claude/skills/test-audit/SKILL.md": ".codex/skills/test-audit/SKILL.md",
    ".codex/skills/test-audit/SKILL.md": ".codex/skills/test-audit/SKILL.md",
    ".claude/skills/test-audit/NOTICE.md": ".codex/skills/test-audit/NOTICE.md",
    ".codex/skills/test-audit/NOTICE.md": ".codex/skills/test-audit/NOTICE.md",
    ".claude/skills/remote-approval/SKILL.md": ".claude/skills/remote-approval/SKILL.md",
    # FORGE-READLOOP-1 adds the Forge skill, so a package missing its reader steps fails here.
    ".claude/skills/forge/SKILL.md": "src/forge/templates/skill.md",
    ".codex/skills/forge/SKILL.md": "src/forge/templates/skill.md",
}
# SHA-256 of the four package copies before the trim, with LF endings as sync writes.
# The test-audit pin leaves CI-mode repair tests to the builder and wider checks to CI.
# The FDE pin includes the app constitution's date, time zone, currency and number defaults.
# It also includes the approved built-in labels for organisations, invites, formats, deletion and CSV.
# The FDE labels recognize both the TypeScript and Python starter organisation folders.
# The approved guide uses INR, defers unbuilt parts and names Mainline error-log alerts.
# Current-source equality alone would miss a shared change across all three installs.
PRE_TRIM_SHA256 = {
    ".codex/skills/forge/fde.md": "304d2a1cf91f5e40c289af47c566f9a9d055bb609c2e0528f4288818fd4e2fcf",
    ".codex/skills/test-audit/SKILL.md": "7684c6c1d5e43fd06365feb5d50d69c9591f03163de457b8dd811a334b2590bc",
    ".codex/skills/test-audit/NOTICE.md": "05713febd8aeaca480afdc78074c66544635517e1868d3a59d7fe1cb54d70149",
    ".claude/skills/remote-approval/SKILL.md": "f3d334b989b73b65f6255d874592c052db96089df476dd1f0c9efa1d95ce8e01",
}
OLD_COPIES = (
    "src/forge/templates/fde.md",
    "src/forge/templates/skills/test-audit/SKILL.md",
    "src/forge/templates/skills/test-audit/NOTICE.md",
    "src/forge/templates/skills/remote-approval/SKILL.md",
)
# Preserve the existing distribution boundary: wheels, source archives and editable installs
# must now include all of the pinned design skill support files as well.
SOURCES.update({f"{host}/skills/{path.relative_to(ROOT / 'src/forge/templates/skills').as_posix()}":
                path.relative_to(ROOT).as_posix()
                for name in ("impeccable", "emil-design-eng")
                for path in (ROOT / "src/forge/templates/skills" / name).rglob("*") if path.is_file()
                for host in (".claude", ".codex")})


@pytest.mark.platform
def test_2_sync_ships_one_source_copy_in_wheel_sdist_and_editable(repo, tmp_path):
    assert all(not (ROOT / rel).exists() for rel in OLD_COPIES)
    # Existing skills use LF; the pinned Windows launcher keeps its upstream CRLF bytes.
    originals = {source: ((ROOT / source).read_bytes() if source.endswith("/impeccable.cmd") else
                          (ROOT / source).read_text(encoding="utf-8").encode("utf-8"))
                 for source in set(SOURCES.values())}
    assert {source: hashlib.sha256(originals[source]).hexdigest()
            for source in PRE_TRIM_SHA256} == PRE_TRIM_SHA256
    expected = {target: originals[source] for target, source in SOURCES.items()}
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
