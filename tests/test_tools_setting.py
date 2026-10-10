"""The tools setting overrides workers at the real work boundary."""
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT, patient
from test_close import env  # noqa: F401
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_setup import _fresh_client, _stub_forge
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
    # A source repo's unused workers value must not change its design model either.
    config.write_text(config.read_text("utf-8").replace('repo = "client"', 'repo = "forge-source"'),
                      encoding="utf-8")
    repo.git("commit", "-qam", "Choose one tool in a source repo", cwd=folder)
    source = repo.forge("work", "BOARD/PAGE")
    assert source.returncode == 0, source.stdout + source.stderr
    assert _sent(codex_log, "thread/resume")[-1]["config"]["model"] == "gpt-6-nova"
    assert calls(claude_log) == []
    config.write_text(original.replace('workers = "codex"', 'workers = "split"\ntools = "claude"'), encoding="utf-8")
    repo.git("commit", "-qam", "Choose Claude", cwd=folder)
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    failed = repo.forge("work", "BOARD/PAGE")
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "exit code 3" in failed.stderr
    assert len(calls(claude_log)) == 1
    assert len(_sent(codex_log, "turn/start")) == 4


@pytest.mark.parametrize("tools,workers", [("claude", "codex"), ("codex", "claude")])
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-release"])
def test_10_doctor_checks_the_selected_tool_instead_of_workers(env, tmp_path, monkeypatch,
                                                             tools, workers, adopted):
    repo = env.repo
    if adopted:
        client = repo.path
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client,
                                         dirs_exist_ok=True))
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-qm", "Adopt earlier Forge", cwd=client)
        config = client / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(re.sub(r'^version = .*$', f'version = "{version}"',
                                 config.read_text("utf-8"), flags=re.M), "utf-8")
        repo.git("commit", "-qam", "Pin current Forge", cwd=client)
        repo.git("push", "-q", "origin", "main", cwd=client)
    else:
        client, initialized = _fresh_client(repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    started = repo.forge("fix", "start", "Choose tools", "--done", "Doctor checks chosen tool",
                         cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    client = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    config = client / "forge.toml"
    config.write_text(re.sub(r'^workers = .*$', f'workers = "{workers}"\ntools = "{tools}"',
                             config.read_text("utf-8"), flags=re.M), "utf-8")
    (client / "web").mkdir()
    (client / "web/package.json").write_text('{"name":"web"}\n', "utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Choose one tool", cwd=client)
    before = config.read_bytes()
    env.gh.respond("auth", "status")
    home = tmp_path / "doctor-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / ".claude"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / "data"))
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    # Both CLIs are installed. Missing SDK, trust and UI skills belong only to the chosen tool.
    if tools == "claude":
        for name in ("impeccable", "emil-design-eng"):
            skill = home / ".claude/skills" / name / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(f"{name}\n", "utf-8")
    _stub_forge(tmp_path, monkeypatch)
    checked = repo.forge("doctor", cwd=client)
    assert config.read_bytes() == before
    if tools == "claude":
        assert checked.returncode == 0, checked.stdout + checked.stderr
        assert "Codex SDK" not in checked.stdout
        assert "trust_level" not in checked.stdout
        assert "worker reads skills" not in checked.stdout
    else:
        assert checked.returncode == 1, checked.stdout + checked.stderr
        assert "forge doctor found 4 problem(s)" in checked.stderr, checked.stdout + checked.stderr
        assert "Codex SDK" in checked.stdout
        assert "Codex doesn't trust this project" in checked.stdout
        for name in ("impeccable", "emil-design-eng"):
            assert f"{name} is required for UI work but isn't installed where the codex worker reads skills." in checked.stdout
        assert "claude worker reads skills" not in checked.stdout
