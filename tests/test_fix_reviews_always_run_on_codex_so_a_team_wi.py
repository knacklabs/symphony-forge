"""A team with only Claude Code installed can close work: the review runs on Claude."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from test_close import PIN, ROOT, env  # noqa: F401  (env is a fixture)
from test_setup import _executable, _fresh_client

STORY = "reviews-always-run-on-codex-so-a-team-wi"


def _claude_only(tmp_path: Path, monkeypatch, bin_dir: Path, helper: str = "") -> None:
    """No codex command anywhere on PATH, and a home whose Claude skills folder holds the
    Autoreview helper (a stub that records its calls when given)."""
    for name in ("codex", "codex.cmd"):
        (bin_dir / name).unlink(missing_ok=True)
    tools = tmp_path / "tools"  # git stays reachable when it shares a folder with codex
    tools.mkdir()
    (tools / Path(shutil.which("git")).name).symlink_to(shutil.which("git"))
    monkeypatch.setenv("PATH", os.pathsep.join(
        [str(tools), *(folder for folder in os.environ["PATH"].split(os.pathsep)
                       if not shutil.which("codex", path=folder))]))
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.delenv("AUTOREVIEW", raising=False)
    home = tmp_path / "home"
    skill = home / ".claude" / "skills" / "autoreview"
    (skill / "scripts").mkdir(parents=True)
    (skill / "scripts" / "autoreview").write_text(helper, encoding="utf-8")
    (skill / ".upstream-sha").write_text(PIN + "\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


def test_1_close_without_codex_reviews_with_claude_on_autoreviews_defaults(
        env, tmp_path, monkeypatch):
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + '\n[models.review]\nmodel = "gpt-6-sol"\neffort = "xhigh"\n'
               + '\n[models.grill.claude]\nmodel = "opus"\neffort = "high"\n')
    env.repo.git("push", "-q", "origin", "main")
    _claude_only(tmp_path, monkeypatch, env.repo.bin,
                 (ROOT / "tests" / "stubs" / "autoreview").read_text("utf-8"))
    # close still reaches the gh stub (gh.CMD on Windows)
    assert Path(shutil.which("gh")).parent == env.repo.bin
    item, _ = env.start_fix()
    env.open_pr("Readme greets new readers")

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    [call] = env.review_calls()  # the helper found under ~/.claude/skills ran
    options = dict(zip(call["args"][::2], call["args"][1::2]))
    assert options["--engine"] == "claude"
    assert "--model" not in options and "--thinking" not in options
    assert "--codex-bin" not in call["args"]


def test_2_doctor_accepts_a_claude_only_setup(repo, gh, tmp_path, monkeypatch):
    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    toml = client / "forge.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace(
        'workers = "split"', 'workers = "claude"', 1), encoding="utf-8")
    gh.respond("auth", "status")
    _claude_only(tmp_path, monkeypatch, repo.bin)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-codex"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")  # run from Claude Code, as a Claude-only team does
    _executable(repo.bin / "claude", "#!/bin/sh\n")
    if os.name == "nt":
        (repo.bin / "claude.cmd").write_text("@exit /b 0\n", encoding="utf-8")

    done = repo.forge("doctor", cwd=client)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Autoreview" not in done.stdout
    assert "checks out" in done.stdout
