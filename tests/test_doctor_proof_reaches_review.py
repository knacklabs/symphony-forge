"""Doctor's generated fix supplies evidence to its first close review."""
import json
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

import conftest
from test_close import GREEN, body, env  # noqa: F401
from test_doctor_fix_files import _fixes, _folder_of, _land, _old_hosts, _pin, _set
from test_setup import _fresh_client

STORY = "FIX-DOCTOR-PROOF"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_doctor_fix_commit_proof_reaches_first_close_review(env, monkeypatch, adopted):
    repo = env.repo
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        client = repo.path
        shutil.copytree(conftest.ROOT / "tests/fixtures/doctor-v1.2.2", client,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
        repo.git("push", "-q", "origin", "main")
    else:
        client, initialized = _fresh_client(repo, env.gh, env.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.path = client
    command = f'"{Path(sys.executable).as_posix()}" -c "print(\'client checks passed\')"'
    settings = _pin((client / "forge.toml").read_text("utf-8"), version)
    config = tomllib.loads(settings)
    for key in ("test", "fast_test"):
        if key in config:
            settings = settings.replace(f'{key} = {json.dumps(config[key])}',
                                        f'{key} = {json.dumps(command)}')
    if "test" not in config:
        settings += f'\ntest = {json.dumps(command)}\n'
    _land(repo, client, "Set the current release and client check",
          lambda folder: _set(folder, "forge.toml", settings))
    if not adopted:
        _old_hosts(repo, client)
    monkeypatch.setenv("XDG_DATA_HOME", str(env.tmp / "data"))
    monkeypatch.setenv("CODEX_HOME", str(env.tmp / "codex-home"))
    conftest._install(repo.bin, "uv", f"#!{sys.executable}\nimport sys\nsys.exit(1)\n")
    env.gh.respond("auth", "status")
    env.checks(GREEN)

    repaired = repo.forge("doctor", "--fix")
    assert "- Fixed: wrote" in repaired.stdout, repaired.stdout + repaired.stderr
    branch, = _fixes(repo, client)
    name = branch.removeprefix("fix/")
    folder = _folder_of(repo, client, branch)
    message = repo.git("log", "-1", "--format=%B", branch)
    assert "\nProof list:\n" in message
    proof = message[message.index("Proof list:"):]
    assert "The files match what forge sync writes for the pinned Forge" in proof
    assert f"Forge {version}'s forge sync" in proof
    written = repo.git("show", "--format=", "--name-only", branch).splitlines()
    assert written
    for rel in written:
        assert rel in proof
    assert f"forge close {name}" in proof and "test run" in proof
    checked = repo.forge("doctor", cwd=folder)
    assert "differs from what forge sync writes" not in checked.stdout

    closed = repo.forge("close", name)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 1
    assert proof in env.prompt()
    # Proof is available at launch; completed test output is reported when close joins tests.
    assert "Tests are running alongside this review" in env.prompt()
    assert "client checks passed" in closed.stdout
    assert "exited with status 0" in closed.stdout
    assert proof in body(env.gh_calls("pr", "create")[-1])
