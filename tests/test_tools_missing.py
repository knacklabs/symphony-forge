"""Missing selected tools refuse before work changes; doctor repairs reachable SDKs."""
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install, patient
from test_close import env  # noqa: F401
from test_codex_setup import PIN, UV_STUB
from test_story import approved_constitution, new_story

STORY = "FORGE-TOOLS-1"
CLAUDE_PIN = "0.2.161"


def _hide(repo, names):
    # Discovery is the OS edge. Never expose the developer's installed tools.
    shim = repo.bin / "forge"
    original = shim.read_text("utf-8")
    shim.write_text(original.replace("from forge.cli import main",
        "import shutil\n_original_which = shutil.which\n"
        f"shutil.which = lambda name, *a, **k: None if name in {names!r} else _original_which(name, *a, **k)\n"
        "from forge.cli import main"), encoding="utf-8")


@pytest.mark.platform
@pytest.mark.parametrize("case,tool", [
    ("review", "claude"), ("review", "codex"), ("review-override", "codex"),
    ("work", "claude"), ("work", "codex"), ("read", "claude"), ("read", "codex"),
    ("doctor", "claude"), ("doctor", "codex"), ("doctor-both", "both"),
    ("doctor-adopted", "claude"), ("doctor-kit-codex", "both"),
])
def test_8_missing_tools_stop_plainly_and_doctor_repairs_them(env, tmp_path, monkeypatch, case, tool):
    repo = env.repo
    if case == "doctor-adopted":
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                                         repo.path, dirs_exist_ok=True))
        version = repo.forge("--version").stdout.split()[-1]
        repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n')
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier release")
    config = repo.path / "forge.toml"
    env.commit(repo.path, "forge.toml", config.read_text("utf-8") + f'\ntools = "{tool}"\n')
    repo.git("push", "-q", "origin", "main")
    monkeypatch.setenv("CLAUDECODE" if tool == "codex" else "CODEX_THREAD_ID", "test-session")
    monkeypatch.delenv("CODEX_THREAD_ID" if tool == "codex" else "CLAUDECODE", raising=False)
    data = Path(os.environ["XDG_DATA_HOME"])
    claude = data / "forge/claude-sdk" / f"claude-agent-sdk-{CLAUDE_PIN}"
    codex = data / "forge/codex-sdk" / f"openai-codex-{PIN}"
    if case.startswith("doctor"):
        _install(repo.bin, "codex", f'#!{sys.executable}\nimport sys\n'
                 f'print("codex-cli {PIN}" if sys.argv[1:] == ["--version"] else "Logged in using ChatGPT")\n')
        # The SDK supplies its own program. Keep a standalone program absent
        # through repair so doctor's recovery works for SDK-only kit runs too.
        if tool == "both":
            _hide(repo, ["codex"] if case == "doctor-kit-codex" else ["claude"])
        (claude / "forge-sdk-ready").unlink(missing_ok=True)
        (codex / "forge-sdk-ready").unlink(missing_ok=True)
        if tool != "both":
            _hide(repo, [tool])
            missing = repo.forge("doctor")
            assert f"{tool} is not installed or not on PATH." in missing.stdout
            assert ("npm install -g @openai/codex" if tool == "codex" else
                    "npm install -g @anthropic-ai/claude-code") in missing.stdout
        checked = repo.forge("doctor")
        label = "Claude Agent SDK" if tool == "claude" else "Codex SDK"
        assert label in checked.stdout, checked.stdout + checked.stderr
        if tool == "both":
            assert "Claude Agent SDK" in checked.stdout
        uv = UV_STUB.format(python=sys.executable, program=str(repo.bin / "codex"), pin=PIN)
        # The package manager supplies the SDK's public module and distribution metadata.
        claude_install = '''elif args[-1].startswith("claude-agent-sdk=="):
    site = pathlib.Path(subprocess.run([args[args.index("--python") + 1], "-c",
        "import sysconfig; print(sysconfig.get_path('purelib'))"],
        capture_output=True, text=True, check=True).stdout.strip())
    (site / "claude_agent_sdk.py").write_text("class ClaudeAgentOptions:\\n    def __init__(self, **kwargs): pass\\nasync def query(): pass\\n", encoding="utf-8")
    info = site / "claude_agent_sdk-0.2.161.dist-info"
    info.mkdir()
    (info / "METADATA").write_text("Name: claude-agent-sdk\\nVersion: 0.2.161\\n", encoding="utf-8")
else:
    site ='''
        _install(repo.bin, "uv", uv.replace("else:\n    site =", claude_install))
        fixed = repo.forge("doctor", "--fix")
        assert f"Installed the {label}" in fixed.stdout, fixed.stdout + fixed.stderr
        again = repo.forge("doctor")
        assert label not in again.stdout, again.stdout + again.stderr
        if tool == "both":
            assert "Claude Agent SDK" not in again.stdout, again.stdout + again.stderr
        requests = [json.loads(line) for line in (repo.bin / "uv-calls.jsonl").read_text("utf-8").splitlines()]
        package = f"claude-agent-sdk=={CLAUDE_PIN}" if tool == "claude" else f"openai-codex=={PIN}"
        assert any(call[-1] == package for call in requests)
        if tool == "both":
            assert any(call[-1] == f"claude-agent-sdk=={CLAUDE_PIN}" for call in requests)
        return
    if case == "read":
        approved_constitution(repo)
        folder = new_story(repo, "SHOP")
        item, command = "SHOP", "read"
        state_file = folder / "plans/SHOP.md"
    else:
        item, folder = env.start_fix()
        command = "close" if case.startswith("review") else "work"
        state_file = folder / f".factory/fixes/{item}.json"
    if command == "close":
        # Refuse before close merges incoming main.
        env.commit(repo.path, "incoming.txt", "Default branch moved\n")
        repo.git("push", "-q", "origin", "main")
        program = "missing-codex" if case == "review-override" else tool
        if case == "review-override":
            monkeypatch.setenv("CODEX_BIN", program)
        _hide(repo, [program])
        name = "Claude Code" if tool == "claude" else "Codex"
    else:
        (claude / "forge-sdk-ready" if tool == "claude" else codex / "forge-sdk-ready").unlink(missing_ok=True)
        name = "Claude Agent SDK" if tool == "claude" else "Codex SDK"
    before, state = repo.git("rev-parse", "HEAD", cwd=folder), state_file.read_bytes()
    result = repo.forge(command, item, cwd=folder)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == (f"forge.toml's tools is {tool}, so this runs on {name}, which isn't installed. "
                             "Forge won't use the other tool instead.\nNext: forge doctor --fix\n")
    assert repo.git("rev-parse", "HEAD", cwd=folder) == before
    assert state_file.read_bytes() == state
    assert repo.git("status", "--porcelain", cwd=folder) == ""
    for log in ("claude-sdk-calls.jsonl", "codex-app-server.jsonl", "codex-calls.jsonl"):
        assert not (repo.bin / log).exists()
    assert env.review_calls() == []
    if command == "close":
        assert not (folder / "incoming.txt").exists()
