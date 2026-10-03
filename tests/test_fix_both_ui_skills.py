"""Forge delivers the two-skill UI contract to workers and reviewers."""

import json
import os

from test_close import env  # noqa: F401 (pytest fixture)
from test_setup import _autoreview, _executable, _fresh_client, _stub_forge
from test_worker import calls, install_claude

STORY = "FIX-BOTH-UI-SKILLS"


def flat(text):
    return " ".join(text.split())


def test_1_sync_delivers_both_ui_skills_and_motion_resolutions(env):
    repo = env.repo
    repo.git("checkout", "-q", "-b", "fix/ui-skill-guidance")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    for host in (".claude", ".codex"):
        standard = flat((repo.path / host / "skills/forge/standards.md").read_text("utf-8"))
        assert "impeccable and emil-design-eng are required for every UI" in standard
        assert "prototypes included" in standard
        assert "one batched inspection" in standard
        assert "under 300 ms" in standard
        assert "@starting-style" in standard
        assert "cubic-bezier(0.23, 1, 0.32, 1)" in standard


def test_2_worker_and_review_get_both_ui_skills_and_blocking_checks(env):
    repo = env.repo
    config = repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8") +
                      'models.lite = { model = "sonnet", effort = "medium" }\n', "utf-8")
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin worker model")
    repo.git("push", "-q", "origin", "main")
    log = install_claude(repo)
    item, _ = env.start_fix()
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stderr
    brief = flat(calls(log)[-1]["brief"])
    assert "impeccable and emil-design-eng are required for every UI" in brief
    assert "prototypes included" in brief
    assert "one batched inspection" in brief
    assert "Invoke emil-design-eng with a specific task" in brief

    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    review = flat(env.prompt())
    assert "impeccable and emil-design-eng are required for every UI" in review
    assert "prototypes included" in review
    assert "one batched inspection" in review
    assert "P1 `Not done`" in review
    assert "failed emil-design-eng checklist item" in review
    assert "not a `Simpler:` finding" in review


def test_3_doctor_requires_both_ui_skills_where_the_worker_reads_them(repo, gh, tmp_path,
                                                                       monkeypatch):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stderr
    config = client / "forge.toml"
    config.write_text(config.read_text("utf-8").replace('workers = "split"',
                                                       'workers = "claude"', 1), "utf-8")
    gh.respond("auth", "status")
    _autoreview(tmp_path, monkeypatch)
    _stub_forge(tmp_path, monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(client))}]\ntrust_level = "trusted"\n', "utf-8")
    _executable(repo.bin / "claude", "#!/bin/sh\n")
    if os.name == "nt":
        (repo.bin / "claude.cmd").write_text("@exit /b 0\n", encoding="utf-8")
    skills = home / ".claude" / "skills"
    (skills / "impeccable").mkdir(parents=True)
    (skills / "impeccable" / "SKILL.md").write_text("impeccable\n", "utf-8")
    # Doctor checks UI skills only when the client has a frontend.
    (client / "web").mkdir()
    (client / "web" / "package.json").write_text('{"name":"web"}\n', encoding="utf-8")

    missing = repo.forge("doctor", cwd=client)
    assert missing.returncode == 1
    assert ("emil-design-eng is required for UI work but isn't installed where the claude "
            "worker reads skills.\n  Fix: ") in missing.stdout
    assert "impeccable is required" not in missing.stdout

    (skills / "emil-design-eng").mkdir()
    (skills / "emil-design-eng" / "SKILL.md").write_text("emil-design-eng\n", "utf-8")
    ready = repo.forge("doctor", cwd=client)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    assert ready.stdout.startswith("Everything checks out")
