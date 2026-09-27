"""Worker defaults in repos set up by forge init."""
from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

STORY = "FIX-NEW-REPOS-GET-CLAUDE-AS-THEIR-WORKER-BY"


def _new_repo(repo, gh, tmp_path: Path, forge_toml: str = "") -> Path:
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    if forge_toml:
        (client / "forge.toml").write_text(forge_toml, encoding="utf-8")
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    return client


def test_1_forge_init_writes_codex_workers(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)

    result = repo.forge("init", cwd=client)

    assert result.returncode == 0, result.stderr
    assert tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["workers"] == "codex"


def test_2_forge_toml_defaults_to_codex_workers(repo, gh, tmp_path, monkeypatch):
    client = _new_repo(repo, gh, tmp_path)
    result = repo.forge("init", cwd=client)
    assert result.returncode == 0, result.stderr
    path = client / "forge.toml"
    path.write_text("\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                              if not line.startswith("workers = ")) + "\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "untrusted-codex"))

    doctor = repo.forge("doctor", cwd=client)

    assert "Codex doesn't trust this project" in doctor.stdout


def test_3_forge_init_preserves_explicit_workers(repo, gh, tmp_path):
    version = repo.forge("--version").stdout.split()[-1]
    client = _new_repo(repo, gh, tmp_path, f'version = "{version}"\nworkers = "claude"\n')

    result = repo.forge("init", cwd=client)

    assert result.returncode == 0, result.stderr
    assert tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["workers"] == "claude"
