"""Claude's SDK boundary owns external worker sessions and process-tree lifetime.

The stub implements only Anthropic's edge. Forge chooses the options, remembers
the session, selects each brief and stops the real driver and its child.
"""
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import alive, person  # noqa: F401 (human stop fixture)
from test_setup import _fresh_client
from test_task import story
from test_tools_session_hold import Session
from test_worker import calls, install_claude

STORY = "FORGE-TOOLS-1"
ITEM = "keep-claude-worker-context"
PIN = "0.2.161"


@pytest.mark.parametrize("history", ["new", "adopted"])
@pytest.mark.parametrize("regression", ["bundled-cli", "design-preflight"])
def test_6_claude_workers_use_resumable_sdk_turns_and_stop_their_tree(
        repo, gh, monkeypatch, tmp_path, person, history, regression):
    version = repo.forge("--version").stdout.split()[-1]
    settings = (f'version = "{version}"\nrepo = "client"\n'
                'tools = "both"\nworkers = "claude"\ntest = "git status --porcelain"\n'
                'models.lite = { model = "sonnet", effort = "medium" }\n')
    if history == "new":
        client = tmp_path / "client"
        client.mkdir()
        (client / "forge.toml").write_text(settings, encoding="utf-8")
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.write("forge.toml", settings)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Configure Claude client")
        repo.git("push", "-q", "origin", "main")
    # The CLI remains installed, but workers must never use its headless transport.
    cli_log = install_claude(repo, worker=False)
    started = repo.forge("fix", "start", "Keep Claude worker context", "--done",
                         "Claude workers keep their conversation and stop with their children")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = repo.path.parent / f"{repo.path.name}-fix-{ITEM}"
    synced = repo.forge("sync", cwd=folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    if repo.git("status", "--porcelain", cwd=folder):
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-qm", "Sync client adapters", cwd=folder)
    sdk_log = repo.bin / "claude-sdk-calls.jsonl"
    sessions = repo.bin / "claude-sdk-sessions.json"
    monkeypatch.delenv("CLAUDECODE", raising=False)
    host = Session(repo, tmp_path / "host", "codex-session")
    held = None
    release = tmp_path / "release-sdk"
    marker = tmp_path / "sdk-process-tree.json"
    try:
        sdk_env = Path(os.environ["XDG_DATA_HOME"]) / "forge/claude-sdk" / f"claude-agent-sdk-{PIN}"
        ready = sdk_env / "forge-sdk-ready"
        ready.unlink()
        head = repo.git("rev-parse", "HEAD", cwd=folder)
        state = (folder / f".factory/fixes/{ITEM}.json").read_bytes()
        refused = host.forge("work", ITEM)
        assert refused.returncode == 1, refused.stdout + refused.stderr
        assert f"The Claude Agent SDK {PIN} isn't installed" in refused.stderr
        assert "forge doctor --fix" in refused.stderr
        assert repo.git("rev-parse", "HEAD", cwd=folder) == head
        assert repo.git("status", "--porcelain", cwd=folder) == ""
        assert (folder / f".factory/fixes/{ITEM}.json").read_bytes() == state
        assert calls(sdk_log) == []

        # Replace uv at its package-install edge, while creating a real isolated
        # interpreter. Forge must choose the version and write its ready marker.
        _install(repo.bin, "uv", f'''#!{sys.executable}
import json, pathlib, subprocess, sys
args = sys.argv[1:]
with (pathlib.Path(__file__).resolve().parent / "uv-sdk-calls.jsonl").open("a", encoding="utf-8") as out:
    out.write(json.dumps(args) + "\\n")
if args[:3] == ["venv", "--python", "3.11"]:
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", args[-1]], check=True)
elif args[:3] != ["pip", "install", "--python"] or args[-1] != "claude-agent-sdk=={PIN}":
    sys.exit(1)
''')
        repaired = host.forge("doctor", "--fix", cwd=folder)
        assert f"Installed the Claude Agent SDK {PIN}" in repaired.stdout, repaired.stdout + repaired.stderr
        assert ready.read_text("utf-8").strip() == PIN
        requests = [json.loads(line) for line in
                    (repo.bin / "uv-sdk-calls.jsonl").read_text("utf-8").splitlines()]
        assert ["venv", "--python", "3.11", str(sdk_env)] in requests
        sdk_python = sdk_env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        assert ["pip", "install", "--python", str(sdk_python), f"claude-agent-sdk=={PIN}"] in requests
        checked = host.forge("doctor", cwd=folder)
        assert "Claude Agent SDK" not in checked.stdout + checked.stderr

        if regression == "design-preflight":
            story(repo)
            started_design = repo.forge("task", "start", "BOARD/PAGE")
            assert started_design.returncode == 0, started_design.stdout + started_design.stderr
            design = repo.path.parent / f"{repo.path.name}-BOARD-PAGE"
            config = design / "forge.toml"
            config.write_text(config.read_text("utf-8").replace('workers = "claude"',
                              'workers = "split"') +
                              '\n[models.design.claude]\nmodel = "sonnet"\neffort = "medium"\n'
                              '\n[models.design.codex]\nmodel = "gpt-6-sol"\neffort = "high"\n',
                              encoding="utf-8")
            repo.git("commit", "-qam", "Choose split workers", cwd=design)
            before = repo.git("rev-parse", "HEAD", cwd=design)
            design_state = design / ".factory/stories/BOARD/tasks/PAGE.json"
            state_before = design_state.read_bytes()
            ready.unlink()
            try:
                missing = host.forge("work", "BOARD/PAGE")
                assert missing.returncode == 1, missing.stdout + missing.stderr
                assert f"The Claude Agent SDK {PIN} isn't installed" in missing.stderr
                assert "forge doctor --fix" in missing.stderr
                assert repo.git("rev-parse", "HEAD", cwd=design) == before
                assert repo.git("status", "--porcelain", cwd=design) == ""
                assert design_state.read_bytes() == state_before
                assert calls(sdk_log) == []
                assert not (repo.bin / "codex-app-server.jsonl").exists()
                assert "Claude failed this design round" not in missing.stdout + missing.stderr
            finally:
                ready.write_text(PIN + "\n", encoding="utf-8")

        edge = repo.bin / "claude_agent_sdk/__init__.py"
        edge.write_text(edge.read_text("utf-8").replace(
            '"input_tokens": 10, "output_tokens": 5',
            '"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 3, '
            '"cache_creation_input_tokens": 2, "future_usage": 900').replace(
            '{"session_id": session, "model": options.model}',
            '{"session_id": session, "model": options.model, "future_init": "ignored"}').replace(
            '[TextBlock("SDK worker output")]',
            '[TextBlock("SDK worker output"), ToolUseBlock("read-1", "Read", '
            '{"file_path": "app.py"})]'), encoding="utf-8")
        # The SDK driver writes UTF-8 even when its Python inherits a legacy pipe encoding.
        monkeypatch.setenv("PYTHONIOENCODING", "ascii")
        response = "stub claude: built it — नमस्ते café"
        monkeypatch.setenv("STUB_CLAUDE_RESULT", response)
        if regression == "bundled-cli":
            # Only command discovery changes: the SDK and its bundled program
            # remain installed. No separate Claude executable is required.
            launcher = repo.bin / "forge"
            launcher.write_text(launcher.read_text("utf-8").replace(
                "from forge.cli import main",
                "import shutil\n"
                "_which = shutil.which\n"
                "shutil.which = lambda name, *args, **kwargs: None if name == 'claude' else _which(name, *args, **kwargs)\n"
                "from forge.cli import main"), encoding="utf-8")
        first = host.forge("work", ITEM)
        assert first.returncode == 0, first.stdout + first.stderr
        [fresh] = calls(sdk_log)
        assert Path(fresh["cwd"]).resolve() == folder.resolve()
        assert "# Worker brief" in fresh["prompt"]
        assert "Claude workers keep their conversation" in fresh["prompt"]
        assert fresh["options"]["model"] == "sonnet"
        assert fresh["options"]["effort"] == "medium"
        assert fresh["options"]["permission_mode"] == "bypassPermissions"
        assert fresh["options"]["cli_path"] is None  # SDK resolves its bundled native program.
        assert fresh["options"]["env"]["FORGE_WORKER"] == "1"
        assert fresh["options"]["system_prompt"] == {"type": "preset", "preset": "claude_code"}
        assert fresh["options"]["setting_sources"] == ["user", "project", "local"]
        assert not fresh["options"].get("resume")
        assert fresh["worker"] == "1"
        assert str(ROOT / "src/forge/templates/conventions") in fresh["options"]["add_dirs"]
        assert "stub claude: built it" in first.stdout
        assert response in first.stdout
        log = repo.path / f".git/forge/work-{ITEM}.log"
        messages = [json.loads(line) for line in log.read_text("utf-8").splitlines()
                    if line.startswith("{")]
        init, assistant, result = messages
        assert (init["type"], init["subtype"], init["model"]) == ("system", "init", "sonnet")
        assert init["future_init"] == "ignored"
        assert assistant["type"] == "assistant" and assistant["message"]["model"] == "sonnet"
        assert assistant["message"]["content"] == [
            {"type": "text", "text": "SDK worker output"},
            {"type": "tool_use", "id": "read-1", "name": "Read", "input": {"file_path": "app.py"}}]
        assert result["type"] == "result" and result["num_turns"] == 1
        assert result["session_id"] == fresh["session_id"]
        assert result["usage"] == {"input_tokens": 10, "output_tokens": 5,
                                   "cache_read_input_tokens": 3, "cache_creation_input_tokens": 2,
                                   "future_usage": 900}

        second = host.forge("work", ITEM)
        assert second.returncode == 0, second.stdout + second.stderr
        fresh, resumed = calls(sdk_log)
        session = resumed["options"]["resume"]
        assert session and session in json.loads(sessions.read_text("utf-8"))
        assert "The earlier brief in this conversation still applies." in resumed["prompt"]
        assert "# Worker brief" not in resumed["prompt"]

        # Anthropic loses the session; Forge must reject only that resume and use
        # a fresh conversation with the full brief in the same work command.
        sessions.unlink()
        recovered = host.forge("work", ITEM)
        assert recovered.returncode == 0, recovered.stdout + recovered.stderr
        _, _, rejected, replacement = calls(sdk_log)
        assert rejected["options"]["resume"] == session
        assert not replacement["options"].get("resume")
        assert "# Worker brief" in replacement["prompt"]
        assert "Claude workers keep their conversation" in replacement["prompt"]
        assert "Starting a new Claude session with the whole brief" in recovered.stdout

        monkeypatch.setenv("STUB_CLAUDE_SDK_HOLD", str(release))
        monkeypatch.setenv("STUB_CLAUDE_SDK_STARTED", str(marker))
        held = host.start("work", ITEM)
        _until(lambda: marker.exists() or held.done(), "the SDK driver and child to start")
        assert not held.done(), held.result().stdout if held.done() else ""
        tree = json.loads(marker.read_text("utf-8"))
        assert alive(tree["driver"]) and alive(tree["child"])
        stopped = host.forge("stop", ITEM)
        assert stopped.returncode == 0, stopped.stdout + stopped.stderr
        _until(lambda: not alive(tree["driver"]) and not alive(tree["child"]),
               "stop to end the SDK driver and child")
        ended = held.result(timeout=30)
        assert ended.returncode != 0, ended.stdout + ended.stderr
        assert not any("-p" in call["args"] for call in calls(cli_log))
    finally:
        release.touch()
        try:
            if held is not None:
                held.result(timeout=30)
        finally:
            host.close()
