"""Names and first preview lines seen through Forge's work and read commands."""
from __future__ import annotations

from test_codex_worker import MODELS, _codex_repo, _sent, _toml
from test_codex_worker import sdk_data  # noqa: F401  (a fixture)

STORY = "FORGE-CHATVIEW-1"


def test_3_new_chats_get_short_names(repo, monkeypatch, sdk_data):
    _, calls = _codex_repo(repo, monkeypatch, sdk_data)
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _sent(calls, "thread/name/set")[-1]["name"] == "BOARD · The page"

    why = "Fix the login page title when customers enter their email address on mobile devices"
    started = repo.forge("fix", "start", why, "--done", "The title is readable")
    assert started.returncode == 0, started.stderr
    fix = started.stdout.rsplit("forge work ", 1)[-1].strip()
    assert repo.forge("work", fix).returncode == 0
    assert _sent(calls, "thread/name/set")[-1]["name"] == (
        "Fix · Fix the login page title when customers enter their…")

    story = repo.path.parent / "repo-story-BOARD"
    repo.git("worktree", "add", "-q", str(story), "story/BOARD")
    version = repo.forge("--version").stdout.split()[-1]
    (story / "forge.toml").write_text(_toml(version, "claude", {
        **MODELS, "grill.codex": {"model": "gpt-6-sol", "effort": "high"},
        "grill.claude": {"model": "opus", "effort": "high"}}), encoding="utf-8")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_THREAD_ID")
    read = repo.forge("read", "BOARD")
    assert read.returncode == 0, read.stdout + read.stderr
    assert _sent(calls, "thread/name/set")[-1]["name"] == "Read · BOARD"


def test_4_each_prompt_begins_with_its_round_summary(repo, monkeypatch, sdk_data):
    _, calls = _codex_repo(repo, monkeypatch, sdk_data)
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr
    assert _sent(calls, "turn/start")[-1]["input"][0]["text"].startswith(
        "Build The page for BOARD.\n")

    second = repo.forge("work", "BOARD/PAGE")
    assert second.returncode == 0, second.stdout + second.stderr
    assert _sent(calls, "turn/start")[-1]["input"][0]["text"].startswith(
        "Fix round 2 on The page.\n")

    record = repo.path / ".git/forge/threads/task/BOARD/PAGE.json"
    record.unlink()  # A later machine has the turn log but no conversation record.
    third = repo.forge("work", "BOARD/PAGE")
    assert third.returncode == 0, third.stdout + third.stderr
    assert _sent(calls, "turn/start")[-1]["input"][0]["text"].startswith(
        "Fix round 3 on The page.\n")

    why = "Fix the login typo"
    assert repo.forge("fix", "start", why, "--done", "The title is correct").returncode == 0
    fixed = repo.forge("work", "fix-the-login-typo")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    assert _sent(calls, "turn/start")[-1]["input"][0]["text"].startswith(
        "Fix: Fix the login typo.\n")
    next_fix = repo.forge("work", "fix-the-login-typo")
    assert next_fix.returncode == 0, next_fix.stdout + next_fix.stderr
    assert _sent(calls, "turn/start")[-1]["input"][0]["text"].startswith(
        "Fix round 2 on Fix the login typo.\n")

    story = repo.path.parent / "repo-story-BOARD"
    repo.git("worktree", "add", "-q", str(story), "story/BOARD")
    version = repo.forge("--version").stdout.split()[-1]
    (story / "forge.toml").write_text(_toml(version, "claude", {
        **MODELS, "grill.codex": {"model": "gpt-6-sol", "effort": "high"},
        "grill.claude": {"model": "opus", "effort": "high"}}), encoding="utf-8")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_THREAD_ID")
    read = repo.forge("read", "BOARD")
    assert read.returncode == 0, read.stdout + read.stderr
    assert _sent(calls, "turn/start")[-1]["input"][0]["text"].startswith(
        "Cold read of BOARD.\n")
