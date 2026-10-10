"""Split workers in Forge's source repo honor its user-facing rows and model overrides."""
from conftest import ROOT
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_worker import calls, install_claude

STORY = "workers-split"


def test_1_user_facing_source_task_uses_opus_medium_and_plain_task_uses_codex(
        repo, monkeypatch, sdk_data, request):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data)
    text = (ROOT / "forge.toml").read_text("utf-8")
    (folder / "forge.toml").write_text(text, encoding="utf-8")
    repo.git("commit", "-qam", "Use this repo's settings", cwd=folder)
    claude_log = install_claude(repo)

    page = repo.forge("work", "BOARD/PAGE")

    assert page.returncode == 0, page.stdout + page.stderr
    [call] = calls(claude_log)
    assert call["args"][:5] == ["-p", "--model", "claude-opus-5-5", "--effort", "medium"]
    assert _sent(codex_log, "turn/start") == []

    started = repo.forge("task", "start", "BOARD/HELP")
    assert started.returncode == 0, started.stdout + started.stderr
    help_folder = repo.path.parent / f"{repo.path.name}-BOARD-HELP"
    (help_folder / "forge.toml").write_text(text, encoding="utf-8")
    repo.git("commit", "-qam", "Use this repo's settings", cwd=help_folder)
    request.getfixturevalue("claude_session")
    plain = repo.forge("work", "BOARD/HELP")
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert len(calls(claude_log)) == 1
    [codex] = _sent(codex_log, "thread/start")
    assert codex["config"]["model"] == "gpt-6.1-sol"
    assert codex["config"]["model_reasoning_effort"] == "medium"
