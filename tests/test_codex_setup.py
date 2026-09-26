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
from test_setup import _autoreview, _fresh_client, _stub_forge

STORY = "FORGE-WARM-1"
PIN = "0.156.1"
UNTRUSTED = "- Codex doesn't trust this project"
APPROVE = "- Note: when Codex asks you to approve Forge's hooks, approve them"

# Stub uv: logs each call. `venv` makes a real, empty environment with the standard library's venv
# (offline, nothing installed), and `pip install` writes a stand-in SDK into it: the modules and
# the two package versions that forge doctor's probe reads, a client with the approval handler
# Forge replaces, and the test's program standing in for the bundled Codex program.
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
    (site / "openai_codex").mkdir()
    (site / "openai_codex" / "__init__.py").write_text("", encoding="utf-8")
    (site / "openai_codex" / "client.py").write_text(
        "class CodexClient:\\n    def __init__(self):\\n        self._approval_handler = None\\n",
        encoding="utf-8")
    (site / "codex_cli_bin.py").write_text(
        "def bundled_codex_path(): return " + repr({program!r}) + "\\n", encoding="utf-8")
    for name in ("openai-codex", "openai-codex-cli-bin"):
        info = site / (name.replace("-", "_") + "-{pin}.dist-info")
        info.mkdir()
        (info / "METADATA").write_text("Name: " + name + "\\nVersion: {pin}\\n", encoding="utf-8")
"""


def _program(path: Path, line: str) -> None:
    """The stand-in bundled Codex program: it runs one line, in sh (cmd on Windows)."""
    path.write_text(f"@{line}\n" if os.name == "nt" else f"#!/bin/sh\n{line}\n", encoding="utf-8")
    path.chmod(0o755)


def _workers(top: Path, kind: str) -> None:
    toml = top / "forge.toml"
    toml.write_text(re.sub(r'workers = "\w+"', f'workers = "{kind}"',
                           toml.read_text(encoding="utf-8")), encoding="utf-8")


def test_11_codex_doctor(repo, gh, tmp_path, monkeypatch):
    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    gh.respond("auth", "status")
    _autoreview(tmp_path, monkeypatch)
    codex_home = tmp_path / "codex"  # the user's Codex config, which records trusted projects
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    # The one required UI skill, where each worker reads skills; test_29 covers its absence.
    claude_home = tmp_path / "claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    for home in (codex_home, claude_home):
        (home / "skills" / "impeccable").mkdir(parents=True)
        (home / "skills" / "impeccable" / "SKILL.md").write_text("impeccable\n", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))  # never the real SDK environment
    env = tmp_path / "data" / "forge" / "codex-sdk" / f"openai-codex-{PIN}"
    program = tmp_path / ("bundled-codex.cmd" if os.name == "nt" else "bundled-codex")
    _program(program, f"echo codex-cli {PIN}")
    hooks = _stub_forge(tmp_path, monkeypatch)
    _workers(client, "codex")

    def trust(level: str) -> None:
        (codex_home / "config.toml").write_text(
            f'[projects.{json.dumps(str(client))}]\ntrust_level = "{level}"\n', encoding="utf-8")

    # No SDK, a project Codex's config doesn't list, and no uv anywhere on PATH, even on a machine
    # that has it: --fix installs nothing and doctor gives its rows. The hook health check still
    # runs, and the note says to approve Forge's hooks.
    path = os.environ["PATH"]
    monkeypatch.setenv("PATH", os.pathsep.join(
        folder for folder in path.split(os.pathsep) if not shutil.which("uv", path=folder)))
    first = repo.forge("doctor", "--fix", cwd=client)
    assert first.returncode == 1
    assert "Installing" not in first.stdout and "Traceback" not in first.stderr
    assert first.stderr.startswith("forge doctor found 3 problem(s)"), first.stderr
    for row in ("- uv is not installed or not on PATH.\n  Fix: ",
                f"- The Codex SDK {PIN} isn't installed in {env}.\n  Fix: forge doctor --fix\n",
                UNTRUSTED, APPROVE):
        assert row in first.stdout, first.stdout
    assert not env.exists()
    assert hooks.read_text(encoding="utf-8").count('"hook_event_name"') == 6
    monkeypatch.setenv("PATH", path)
    _install(repo.bin, "uv", UV_STUB.format(python=sys.executable, pin=PIN, program=str(program)))

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

    # A wrong SDK version fails, and so does a bundled Codex program that says another version or
    # exits non-zero, and an SDK client with no approval handler for Forge to replace.
    metadata = next(env.rglob("openai_codex-*.dist-info")) / "METADATA"
    metadata.write_text("Name: openai-codex\nVersion: 0.150.0\n", encoding="utf-8")
    wrong_sdk = repo.forge("doctor", cwd=client)
    metadata.write_text(f"Name: openai-codex\nVersion: {PIN}\n", encoding="utf-8")
    _program(program, "echo codex-cli 0.150.0")
    wrong_program = repo.forge("doctor", cwd=client)
    _program(program, "exit 3")
    failing_program = repo.forge("doctor", cwd=client)
    _program(program, f"echo codex-cli {PIN}")
    sdk_client = next(env.rglob("openai_codex/client.py"))
    handler = sdk_client.read_text(encoding="utf-8")
    sdk_client.write_text("class CodexClient:\n    pass\n", encoding="utf-8")
    moved_handler = repo.forge("doctor", cwd=client)
    sdk_client.write_text(handler, encoding="utf-8")
    for done, said in (
            (wrong_sdk, f"openai-codex 0.150.0, openai-codex-cli-bin {PIN}, codex-cli {PIN}"),
            (wrong_program, f"openai-codex {PIN}, openai-codex-cli-bin {PIN}, codex-cli 0.150.0"),
            (failing_program, "returned non-zero exit status 3."),
            (moved_handler, "the SDK client has no _approval_handler for Forge to replace")):
        assert done.returncode == 1
        assert (f"- The Codex SDK in {env} should be openai-codex {PIN}, openai-codex-cli-bin "
                f"{PIN}, codex-cli {PIN}, but its Python says: ") in done.stdout, done.stdout
        assert f"{said}\n  Fix: forge doctor --fix\n" in done.stdout, done.stdout

    # A project marked untrusted fails doctor, and forge work refuses to start Codex in it before
    # it records any status. A task worktree gets its trusted main repo's trust.
    worktree = tmp_path / "client-task"
    repo.git("worktree", "add", "-q", "-b", "task/SHOP-CART", str(worktree), cwd=client)
    _workers(worktree, "codex")  # forge init wrote the [models] table
    trust("untrusted")
    untrusted = repo.forge("doctor", cwd=client)
    assert untrusted.returncode == 1 and UNTRUSTED in untrusted.stdout
    head = repo.git("rev-parse", "HEAD", cwd=worktree)
    refused = repo.forge("work", "SHOP/CART", cwd=worktree)
    assert refused.stderr == ("Codex doesn't trust this project, so it would skip Forge's hooks; "
                              "Forge starts no Codex worker here.\nNext: forge doctor\n")
    assert repo.git("rev-parse", "HEAD", cwd=worktree) == head
    trust("trusted")
    in_worktree = repo.forge("doctor", cwd=worktree)
    assert in_worktree.returncode == 0, in_worktree.stdout + in_worktree.stderr

    # Claude workers: no Codex rows and no approval note, even with no SDK and no trust entry, and
    # --fix installs nothing.
    shutil.rmtree(env)
    (codex_home / "config.toml").unlink()
    _workers(client, "claude")
    _install(repo.bin, "claude", "#!/bin/sh\n")
    claude = repo.forge("doctor", "--fix", cwd=client)
    assert claude.returncode == 0, claude.stdout + claude.stderr
    assert "Codex SDK" not in claude.stdout and APPROVE not in claude.stdout
    # Outside a Forge project it refuses as ever, before installing anything.
    outside = repo.forge("doctor", "--fix")
    assert outside.stderr == "This repo has no forge.toml.\nNext: forge init\n"
    assert not env.exists()
    assert len((repo.bin / "uv-calls.jsonl").read_text(encoding="utf-8").splitlines()) == 2

    # Under Claude Code the cold read runs on Codex, so with Claude workers doctor checks the SDK
    # and --fix installs it; trust stays advice.
    monkeypatch.setenv("CLAUDECODE", "1")
    reader = repo.forge("doctor", cwd=client)
    assert reader.returncode == 1
    assert f"- The Codex SDK {PIN} isn't installed in {env}.\n  Fix: forge doctor --fix\n" in (
        reader.stdout)
    fixed = repo.forge("doctor", "--fix", cwd=client)
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    assert (env / "forge-sdk-ready").read_text(encoding="utf-8") == f"{PIN}\n"
