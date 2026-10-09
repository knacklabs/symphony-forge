"""Design model settings written by Forge and accepted in a client repo."""
from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

STORY = "FORGE-DESIGN-1"


def test_2_forge_init_writes_design_models(repo, gh, tmp_path: Path) -> None:
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')

    result = repo.forge("init", cwd=client)

    assert result.returncode == 0, result.stderr
    models = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["models"]
    assert models["design"] == {
        "claude": {"model": "claude-opus-5-5", "effort": "high"},
        "codex": {"model": "gpt-6.1-sol", "effort": "high"},
    }
    # Forge's source repo can override these client defaults; its settings test owns that contract.
    toml = repo.write("forge.toml", 'version = "v1.1.0"\n'
                      '[models.design.claude]\nmodel = "custom-claude"\neffort = "high"\n'
                      '[models.design.codex]\nmodel = "custom-codex"\neffort = "high"\n')

    configured = repo.forge("doctor")
    toml.write_text('version = "v1.1.0"\n', encoding="utf-8")
    older = repo.forge("doctor")
    toml.write_text('version = "v1.1.0"\n[models.design.claude]\neffort = "high"\n',
                    encoding="utf-8")
    malformed = repo.forge("doctor")

    assert "[models] table is not usable" not in configured.stdout + configured.stderr
    assert "[models] table is not usable" not in older.stdout + older.stderr
    assert "models.design.claude has no model" in malformed.stdout + malformed.stderr
