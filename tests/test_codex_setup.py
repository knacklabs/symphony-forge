"""Codex workers' setup: forge doctor checks the pinned Codex SDK and the project's trust, and
forge doctor --fix installs the SDK.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path

from conftest import _install
from test_setup import _fresh_client, _stub_forge

STORY = "FORGE-WARM-1"
PIN = "0.156.1"
UNTRUSTED = "- Codex doesn't trust this project"
APPROVE = "- Note: when Codex asks you to approve Forge's hooks, approve them"

# Stub uv: logs each call. `venv` makes a real, empty environment with the standard library's venv
# (offline, nothing installed), and `pip install` writes a stand-in SDK into it: the two modules
# and the two package versions that forge doctor's probe reads.
UV_STUB = """#!{python}
import json, pathlib, subprocess, sys
args = sys.argv[1:]
with open(pathlib.Path(__file__).resolve().parent / "uv-calls.jsonl", "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\\n")
if args[0] == "venv":
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", args[-1]], check=True)
else:
    site = pathlib.Path(subprocess.run(
        [args[args.index("--python") + 1], "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        capture_output=True, text=True, check=True).stdout.strip())
    (site / "openai_codex.py").write_text("", encoding="utf-8")
    (site / "codex_cli_bin.py").write_text("def bundled_codex_path(): pass\\n", encoding="utf-8")
    for name in ("openai-codex", "openai-codex-cli-bin"):
        info = site / (name.replace("-", "_") + "-{pin}.dist-info")
        info.mkdir()
        (info / "METADATA").write_text("Name: " + name + "\\nVersion: {pin}\\n", encoding="utf-8")
"""


def _workers(top: Path, kind: str) -> None:
    toml = top / "forge.toml"
    toml.write_text(re.sub(r'workers = "\w+"', f'workers = "{kind}"',
                           toml.read_text(encoding="utf-8")), encoding="utf-8")


def test_11_codex_doctor(repo, gh, tmp_path, monkeypatch):
    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    gh.respond("auth", "status")
    codex_home = tmp_path / "codex"  # the user's Codex config, which records trusted projects
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))  # never the real SDK environment
    env = tmp_path / "data" / "forge" / "codex-sdk" / f"openai-codex-{PIN}"
    _install(repo.bin, "uv", UV_STUB.format(python=sys.executable, pin=PIN))
    hooks = _stub_forge(tmp_path, monkeypatch)
    _workers(client, "codex")

    def trust(level: str) -> None:
        (codex_home / "config.toml").write_text(
            f'[projects.{json.dumps(str(client))}]\ntrust_level = "{level}"\n', encoding="utf-8")

    # No SDK and a project Codex's config doesn't list: two failing rows. The hook health check
    # still runs, and the note says to approve Forge's hooks.
    first = repo.forge("doctor", cwd=client)
    assert first.returncode == 1
    assert (f"- The Codex SDK {PIN} isn't installed in {env}.\n  Fix: forge doctor --fix\n"
            in first.stdout), first.stdout
    assert UNTRUSTED in first.stdout and APPROVE in first.stdout
    assert hooks.read_text(encoding="utf-8").count('"hook_event_name"') == 6

    # --fix installs the pinned SDK with uv into a fresh environment, marks it ready and checks.
    trust("trusted")
    fixed = repo.forge("doctor", "--fix", cwd=client)
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    assert "Everything checks out" in fixed.stdout
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    calls = (repo.bin / "uv-calls.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(call) for call in calls] == [
        ["venv", "--python", "3.11", str(env)],
        ["pip", "install", "--python", str(python), f"openai-codex=={PIN}"]]
    assert (env / "forge-sdk-ready").read_text(encoding="utf-8") == f"{PIN}\n"

    # The wrong SDK version fails.
    metadata = next(env.rglob("openai_codex-*.dist-info")) / "METADATA"
    metadata.write_text("Name: openai-codex\nVersion: 0.150.0\n", encoding="utf-8")
    wrong = repo.forge("doctor", cwd=client)
    assert wrong.returncode == 1
    assert (f"should be openai-codex {PIN}, openai-codex-cli-bin {PIN}, but its Python says: "
            f"openai-codex 0.150.0, openai-codex-cli-bin {PIN}") in wrong.stdout, wrong.stdout
    metadata.write_text(f"Name: openai-codex\nVersion: {PIN}\n", encoding="utf-8")

    # A project marked untrusted fails; a task worktree gets its trusted main repo's trust.
    trust("untrusted")
    untrusted = repo.forge("doctor", cwd=client)
    assert untrusted.returncode == 1 and UNTRUSTED in untrusted.stdout
    trust("trusted")
    worktree = tmp_path / "client-task"
    repo.git("worktree", "add", "-q", "-b", "task/SHOP-CART", str(worktree), cwd=client)
    _workers(worktree, "codex")
    in_worktree = repo.forge("doctor", cwd=worktree)
    assert in_worktree.returncode == 0, in_worktree.stdout + in_worktree.stderr

    # Claude workers: no Codex rows and no approval note, even with no SDK and no trust entry.
    shutil.rmtree(env)
    (codex_home / "config.toml").unlink()
    _workers(client, "claude")
    _install(repo.bin, "claude", "#!/bin/sh\n")
    claude = repo.forge("doctor", cwd=client)
    assert claude.returncode == 0, claude.stdout + claude.stderr
    assert "Codex SDK" not in claude.stdout and APPROVE not in claude.stdout
