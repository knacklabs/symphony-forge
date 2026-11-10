"""With workers = claude, Forge's source repo builds every task on Claude: user-facing rows keep
the design model, plain tasks use the build model. The owner moved it from split on 10 Nov 2026."""
from conftest import ROOT
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_worker import calls, install_claude

STORY = "workers-split"


def test_1_user_facing_source_task_uses_sonnet_high_and_plain_task_uses_sonnet_low(
        repo, monkeypatch, sdk_data):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data)
    text = (ROOT / "forge.toml").read_text("utf-8")
    (folder / "forge.toml").write_text(text, encoding="utf-8")
    repo.git("commit", "-qam", "Use this repo's settings", cwd=folder)
    claude_log = install_claude(repo)

    page = repo.forge("work", "BOARD/PAGE")

    assert page.returncode == 0, page.stdout + page.stderr
    [call] = calls(claude_log)
    assert (call["options"]["model"], call["options"]["effort"]) == ("claude-sonnet-5-5", "high")
    assert _sent(codex_log, "turn/start") == []

    started = repo.forge("task", "start", "BOARD/HELP")
    assert started.returncode == 0, started.stdout + started.stderr
    help_folder = repo.path.parent / f"{repo.path.name}-BOARD-HELP"
    (help_folder / "forge.toml").write_text(text, encoding="utf-8")
    repo.git("commit", "-qam", "Use this repo's settings", cwd=help_folder)
    plain = repo.forge("work", "BOARD/HELP")
    assert plain.returncode == 0, plain.stdout + plain.stderr
    second = calls(claude_log)[-1]
    assert (second["options"]["model"], second["options"]["effort"]) == ("claude-sonnet-5-5", "low")
    assert len(calls(claude_log)) == 2
    assert _sent(codex_log, "thread/start") == []
