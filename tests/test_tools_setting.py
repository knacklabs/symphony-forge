"""The tools setting overrides workers at the real work boundary."""
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_worker import calls, install_claude
from test_which_worker_builds import _help

STORY = "FORGE-TOOLS-1"


def test_1_tools_choose_one_tool_without_changing_the_work_process(repo, monkeypatch, sdk_data):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    # No tools key is both: retain workers, even from the other coordinating app.
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr
    assert len(_sent(codex_log, "turn/start")) == 1
    assert calls(claude_log) == []
    config = folder / "forge.toml"
    original = config.read_text("utf-8")
    config.write_text(original.replace('workers = "codex"', 'workers = "claude"\ntools = "gemini"'), encoding="utf-8")
    invalid = repo.forge("work", "BOARD/PAGE")
    assert invalid.returncode == 1
    assert "tools must be one of both, claude, codex" in invalid.stderr
    assert len(_sent(codex_log, "turn/start")) == 1
    config.write_text(original.replace('workers = "codex"', 'workers = "claude"\ntools = "codex"') +
                      '\n[models.design.codex]\nmodel = "gpt-6-nova"\neffort = "xhigh"\n', encoding="utf-8")
    repo.git("commit", "-qam", "Choose Codex", cwd=folder)
    chosen = repo.forge("work", "BOARD/PAGE")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    # The app-server accepts models on the conversation, rather than on turn/start.
    assert _sent(codex_log, "thread/resume")[-1]["config"]["model"] == "gpt-6-nova"
    assert calls(claude_log) == []
    plain_folder = _help(repo, "claude")
    plain_config = plain_folder / "forge.toml"
    plain_config.write_text(plain_config.read_text("utf-8").replace(
        'workers = "claude"', 'workers = "claude"\ntools = "codex"'), encoding="utf-8")
    repo.git("commit", "-qam", "Choose Codex for plain work", cwd=plain_folder)
    plain = repo.forge("work", "BOARD/HELP")
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert _sent(codex_log, "thread/start")[-1]["config"]["model"] == "gpt-6-sol"
    assert calls(claude_log) == []
    config.write_text(original.replace('workers = "codex"', 'workers = "split"\ntools = "claude"'), encoding="utf-8")
    repo.git("commit", "-qam", "Choose Claude", cwd=folder)
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    failed = repo.forge("work", "BOARD/PAGE")
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "exit code 3" in failed.stderr
    assert len(calls(claude_log)) == 1
    assert len(_sent(codex_log, "turn/start")) == 3
