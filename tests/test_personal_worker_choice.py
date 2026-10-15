"""A developer's own forge.local.toml, beside the main checkout's forge.toml and ignored by git,
chooses tools, workers and models for that clone only; every other key stays repo-only."""
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT, patient
from test_close import env  # noqa: F401
from test_codex_worker import _codex_repo, sdk_data  # noqa: F401
from test_setup import _fresh_client, _stub_forge
from test_worker import calls, install_claude

STORY = "personal-worker-choice"
LOCAL = 'workers = "claude"\n\n[models.build]\nmodel = "claude-sonnet-5"\neffort = "medium"\n'


def test_1_each_clone_chooses_its_own_worker_with_no_tracked_change(repo, monkeypatch, sdk_data):
    page, _ = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    repo.git("merge", "-q", "--no-edit", "story/BOARD")
    repo.git("push", "-q", "origin", "main")
    other = repo.path.parent / "other"
    repo.git("clone", "-q", str(repo.path.parent / "remote.git"), str(other))
    (repo.path / "forge.local.toml").write_text(LOCAL, "utf-8")
    # This clone and its task worktree build on Claude; the other clone keeps forge.toml's Codex.
    for folder in (repo.path, page):
        shown = repo.forge("next", cwd=folder).stdout
        assert ("Next: forge task start BOARD/HELP  # Claude builds it "
                "(forge.local.toml: workers = claude, models.build; forge.toml: tools = both)") in shown, shown
    shown = repo.forge("next", cwd=other).stdout
    assert "Next: forge task start BOARD/HELP  # Codex builds it\n" in shown, shown
    # A models-only file keeps forge.toml's worker and names its own models.
    (other / "forge.local.toml").write_text('[models.build]\nmodel = "gpt-6-nova"\neffort = "low"\n', "utf-8")
    shown = repo.forge("next", cwd=other).stdout
    assert ("Next: forge task start BOARD/HELP  # Codex builds it "
            "(forge.local.toml: models.build; forge.toml: tools = both, workers = codex)") in shown, shown
    # A local tools = "both" is named too, beside forge.toml's workers and models.
    (other / "forge.local.toml").write_text('tools = "both"\n', "utf-8")
    shown = repo.forge("next", cwd=other).stdout
    assert ("Next: forge task start BOARD/HELP  # Codex builds it "
            "(forge.local.toml: tools = both; forge.toml: workers = codex, models.build)") in shown, shown
    # A local models table replaces the whole kind: with no entry for Codex, Codex runs on
    # Forge's built-in default, not on forge.toml's build entry.
    (other / "forge.local.toml").write_text(
        '[models.build.claude]\nmodel = "claude-sonnet-5"\neffort = "low"\n', "utf-8")
    shown = repo.forge("next", cwd=other).stdout
    assert ("Next: forge task start BOARD/HELP  # Codex builds it "
            "(forge.toml: tools = both, workers = codex; built-in default: models.build)") in shown, shown

    claude_log = install_claude(repo)
    started = repo.forge("task", "start", "BOARD/HELP")
    assert started.returncode == 0, started.stdout + started.stderr
    built = repo.forge("work", "BOARD/HELP")
    assert built.returncode == 0, built.stdout + built.stderr
    assert (calls(claude_log)[-1]["options"]["model"], calls(claude_log)[-1]["options"]["effort"]) == ("claude-sonnet-5", "medium")
    assert ("Building BOARD/HELP with Claude (claude-sonnet-5, medium) because workers = claude; "
            "forge.local.toml: workers = claude, models.build; forge.toml: tools = both") in built.stdout
    # A local tools choice overrides forge.toml's Codex workers too. forge.toml has only Codex
    # models, so Claude's come from Forge's built-in default.
    (repo.path / "forge.local.toml").write_text('tools = "claude"\n', "utf-8")
    started = repo.forge("task", "start", "BOARD/API")
    assert started.returncode == 0, started.stdout + started.stderr
    built = repo.forge("work", "BOARD/API")
    assert built.returncode == 0, built.stdout + built.stderr
    assert len(calls(claude_log)) == 2
    assert ("because tools = claude; forge.local.toml: tools = claude; forge.toml: workers = codex; "
            "built-in default: models.build") in built.stdout, built.stdout
    # A started fix's forge work line names its worker and sources too.
    fixed = repo.forge("fix", "start", "Tidy the readme", "--done", "The readme is tidy")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    name = fixed.stdout.split()[2]
    shown = repo.forge("next").stdout
    assert (f"Next: forge work {name}  # Claude builds it (forge.local.toml: tools = claude; "
            "forge.toml: workers = codex; built-in default: models.lite)") in shown, shown
    # A prototype fix is design work, so forge next previews the worker forge work picks for it.
    config = repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8").replace('repo = "client"', 'repo = "client"\nstage = "prototype"'),
                      "utf-8")
    repo.git("commit", "-qam", "Back to the prototype stage")
    repo.git("push", "-q", "origin", "main")
    (repo.path / "forge.local.toml").write_text('workers = "split"\n', "utf-8")
    fixed = repo.forge("fix", "start", "Show the demo", "--done", "The demo shows")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    name = fixed.stdout.split()[2]
    shown = repo.forge("next").stdout
    assert (f"Next: forge work {name}  # Claude builds it (forge.local.toml: workers = split; "
            "forge.toml: tools = both; built-in default: models.design)") in shown, shown
    for folder in (repo.path, page, other):
        assert repo.git("status", "--porcelain", "--untracked-files=no", cwd=folder) == ""


def test_2_a_shared_setting_in_the_local_file_is_refused(repo, monkeypatch, sdk_data):
    _codex_repo(repo, monkeypatch, sdk_data, client=True, start_task=False)
    (repo.path / "forge.local.toml").write_text('workers = "claude"\nmerge = "agent"\n', "utf-8")
    refused = repo.forge("task", "start", "BOARD/PAGE")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert ("forge.local.toml can't set merge: it holds only tools, workers and [models] tables, "
            "so settings the team shares stay in forge.toml.\n"
            "Next: move merge to forge.toml in a fix, or take it out of forge.local.toml") in refused.stderr
    # A key it may hold, with a value Forge can't use, is refused too.
    (repo.path / "forge.local.toml").write_text('workers = "gemini"\n', "utf-8")
    refused = repo.forge("task", "start", "BOARD/PAGE")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert ("forge.local.toml is not usable: workers must be one of claude, codex, split.\n"
            "Next: ask your agent to fix forge.local.toml") in refused.stderr


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-release"])
def test_3_new_and_upgraded_repos_ignore_the_local_file_and_doctor_names_its_settings(
        env, tmp_path, monkeypatch, adopted):
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
        # init's own first commit ignores the file.
        assert "forge.local.toml" in repo.git("show", "HEAD:.gitignore", cwd=client).splitlines()
    main = client
    started = repo.forge("fix", "start", "Choose my worker", "--done", "My file is ignored", cwd=main)
    assert started.returncode == 0, started.stdout + started.stderr
    client = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "forge.local.toml" in (client / ".gitignore").read_text("utf-8").splitlines()
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Ignore my settings", "--allow-empty", cwd=client)
    (main / "forge.local.toml").write_text(
        'tools = "claude"\n' + LOCAL + '\n[models.fix.codex]\nmodel = "gpt-6-sol"\neffort = "low"\n'
        'subagents = "gpt-6-luna"\nsubagent_effort = "max"\n', "utf-8")
    roles = (client / ".claude/agents/worker.md").read_bytes()
    assert repo.forge("sync", cwd=client).returncode == 0
    # Personal models never reach the committed subagent roles.
    assert (client / ".claude/agents/worker.md").read_bytes() == roles
    (client / "forge.local.toml").write_text("", "utf-8")
    assert repo.git("check-ignore", "forge.local.toml", cwd=client) == "forge.local.toml"
    (client / "forge.local.toml").unlink()

    env.gh.respond("auth", "status")
    home = tmp_path / "doctor-home"
    for name in ("impeccable", "emil-design-eng"):
        skill = home / ".claude/skills" / name / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(f"{name}\n", "utf-8")
    for variable, value in (("HOME", home), ("USERPROFILE", home), ("CODEX_HOME", home / ".codex"),
                            ("CLAUDE_CONFIG_DIR", home / ".claude"), ("XDG_DATA_HOME", home / "data")):
        monkeypatch.setenv(variable, str(value))
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    _stub_forge(tmp_path, monkeypatch)
    checked = repo.forge("doctor", cwd=client)
    assert ("- Note: forge.local.toml overrides tools = claude, workers = claude, "
            "models.build (model claude-sonnet-5, effort medium), models.fix.codex (model gpt-6-sol, "
            "effort low, subagents gpt-6-luna, subagent_effort max)."
            ) in checked.stdout, checked.stdout + checked.stderr
