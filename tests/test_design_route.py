"""Design routing through the real forge work command and the third-party worker edges."""
from __future__ import annotations

import json
import os
import shutil

from test_codex_worker import _codex_repo, _sent, sdk_data
from test_worker import calls, install_claude

STORY = "FORGE-DESIGN-1"


def test_3_user_facing_task_uses_design_claude_even_with_codex_workers(repo, monkeypatch, sdk_data):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    # A client repo counts as live unless forge.toml says prototype.
    repo.write("forge.toml", (repo.path / "forge.toml").read_text("utf-8").replace(
        'repo = "client"', 'repo = "client"\nstage = "prototype"'))
    repo.git("commit", "-q", "-am", "Prototype stage")
    repo.git("push", "-q", "origin", "main")
    claude_log = install_claude(repo)
    result = repo.forge("work", "BOARD/PAGE")
    assert result.returncode == 0, result.stdout + result.stderr
    [call] = calls(claude_log)
    assert call["args"][:5] == ["-p", "--model", "claude-opus-5-5", "--effort", "high"]
    assert call["cwd"] == str(folder)
    assert "| PAGE | The page |" in call["brief"]
    assert _sent(codex_log, "turn/start") == []

    # Before sign-off, a new fix carries the prototype allowance and uses design Claude.
    assert repo.forge("fix", "start", "Fix the login typo", "--done", "It says Log in").returncode == 0
    prototype = repo.forge("work", "fix-the-login-typo")
    assert prototype.returncode == 0, prototype.stdout + prototype.stderr
    assert len(calls(claude_log)) == 2
    assert _sent(codex_log, "turn/start") == []

    fix = repo.path.parent / "repo-fix-fix-the-login-typo"
    state_file = fix / ".factory" / "fixes" / "fix-the-login-typo.json"
    state = json.loads(state_file.read_text("utf-8"))
    state["allow_large"] = "Other allowance"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    ordinary = repo.forge("work", "fix-the-login-typo")
    assert ordinary.returncode == 0, ordinary.stdout + ordinary.stderr
    assert len(_sent(codex_log, "turn/start")) == 1
    assert len(calls(claude_log)) == 2

    # Forge's own repository keeps its configured worker even for a user-facing row.
    config = folder / "forge.toml"
    config.write_text(config.read_text("utf-8").replace('repo = "client"',
                                                     'repo = "forge-source"'), encoding="utf-8")
    source = repo.forge("work", "BOARD/PAGE")
    assert source.returncode == 0, source.stdout + source.stderr
    assert len(_sent(codex_log, "turn/start")) == 2
    assert len(calls(claude_log)) == 2

    config.write_text(config.read_text("utf-8").replace('repo = "forge-source"',
                                                     'repo = "client"') +
                      '\n[models.design.claude]\nmodel = "custom-opus"\neffort = "high"\n',
                      encoding="utf-8")
    custom = repo.forge("work", "BOARD/PAGE")
    assert custom.returncode == 0, custom.stdout + custom.stderr
    assert calls(claude_log)[-1]["args"][:5] == ["-p", "--model", "custom-opus", "--effort", "high"]
    # The design round continues the session its first round started, so it gets the short prompt.
    assert "The earlier brief in this conversation still applies." in calls(claude_log)[-1]["brief"]
    assert "--resume" in calls(claude_log)[-1]["args"]
    assert len(_sent(codex_log, "turn/start")) == 2

    # A client story row without User-facing uses the configured Codex worker.
    started = repo.forge("task", "start", "BOARD/HELP")
    assert started.returncode == 0, started.stdout + started.stderr
    ordinary_task = repo.forge("work", "BOARD/HELP")
    assert ordinary_task.returncode == 0, ordinary_task.stdout + ordinary_task.stderr
    assert len(_sent(codex_log, "turn/start")) == 3
    assert len(calls(claude_log)) == 3

    # Design still uses its own Claude model when the repo chooses Claude for ordinary work.
    config.write_text(config.read_text("utf-8").replace('workers = "codex"',
                                                     'workers = "claude"'), encoding="utf-8")
    claude_worker = repo.forge("work", "BOARD/PAGE")
    assert claude_worker.returncode == 0, claude_worker.stdout + claude_worker.stderr
    assert calls(claude_log)[-1]["args"][:5] == ["-p", "--model", "custom-opus", "--effort", "high"]
    assert len(_sent(codex_log, "turn/start")) == 3


def test_4_missing_or_cleanly_failed_claude_falls_back_to_sol_and_resumes(repo, monkeypatch,
                                                                            sdk_data):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    config = folder / "forge.toml"
    config.write_text(config.read_text("utf-8") +
                      '\n[models.design.codex]\nmodel = "gpt-6-nova"\neffort = "xhigh"\n',
                      encoding="utf-8")
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    clean = repo.forge("work", "BOARD/PAGE")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "fell back to Codex" in clean.stdout and "exit code 3" in clean.stdout
    [claude_call] = calls(claude_log)
    [first] = _sent(codex_log, "thread/start")
    assert first["config"] == {"model": "gpt-6-nova", "model_reasoning_effort": "xhigh"}
    assert first["approvalPolicy"] == "never"
    [turn] = _sent(codex_log, "turn/start")
    assert turn["input"][0]["text"] == claude_call["brief"]
    log = (repo.path / ".git" / "forge" / "work-BOARD-PAGE.log").read_text("utf-8")
    assert "fell back to Codex" in log and "exit code 3" in log

    # A later missing Claude command uses the design defaults without Build/Fix models.
    version = repo.forge("--version").stdout.split()[-1]
    config.write_text(
        f'version = "{version}"\nrepo = "client"\nworkers = "codex"\n', encoding="utf-8")
    os.unlink(repo.bin / "claude")
    if os.name == "nt":
        os.unlink(repo.bin / "claude.cmd")
    git_dir = os.path.dirname(shutil.which("git"))
    monkeypatch.setenv("PATH", os.pathsep.join((str(repo.bin), git_dir, os.defpath)))
    missing = repo.forge("work", "BOARD/PAGE")
    assert missing.returncode == 0, missing.stdout + missing.stderr
    assert "fell back to Codex" in missing.stdout and "missing" in missing.stdout
    assert _sent(codex_log, "thread/start")[-1]["config"] == {
        "model": "gpt-6.1-sol", "model_reasoning_effort": "high"}
    install_claude(repo)
    assert len(calls(claude_log)) == 1
    assert len(_sent(codex_log, "thread/resume")) == 1
    assert len(_sent(codex_log, "turn/start")) == 2

    # If Claude leaves a file behind, the same failure must stay with Claude.
    script = repo.bin / "claude"
    original = script.read_text("utf-8")
    script.write_text(original.replace('print("stub claude: built it")',
                                       'pathlib.Path("worker-change.txt").write_text("changed")\n'
                                       'print("stub claude: built it")'), encoding="utf-8")
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    failed = repo.forge("work", "BOARD/PAGE")
    assert failed.returncode == 1
    assert "exit code 3" in failed.stderr
    assert "fell back to Codex" not in failed.stdout
    assert (folder / "worker-change.txt").read_text("utf-8") == "changed"
    assert len(calls(claude_log)) == 2
    assert len(_sent(codex_log, "turn/start")) == 2

    script.write_text(original.replace('print("stub claude: built it")',
                                       'import subprocess\n'
                                       'pathlib.Path("README.md").write_text("staged change")\n'
                                       'subprocess.run(["git", "add", "README.md"], check=True)\n'
                                       'print("stub claude: built it")'), encoding="utf-8")
    staged = repo.forge("work", "BOARD/PAGE")
    assert staged.returncode == 1 and "exit code 3" in staged.stderr
    assert repo.git("diff", "--cached", "--name-only", cwd=folder) == "README.md"
    assert len(_sent(codex_log, "turn/start")) == 2
