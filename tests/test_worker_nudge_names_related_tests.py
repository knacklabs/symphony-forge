"""A worker asked to commit is told to run the change's related tests: forge.toml's fast_test with
{base} as the merge base with the default branch, not the whole suite CI runs."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from test_fix_claude_workers_start_a_fresh_session_eve import FIX
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "every-worker-round-runs-the-repo-s-whole"


def _commit_test_fixes(text):
    text = text.lower()
    assert text.index("commit your work") < text.index("run the change's related tests")
    assert text.index("run the change's related tests") < text.index("commit any fixes")


def _related_test_skills(client):
    for host in (".claude", ".codex"):
        skill = (client / host / "skills/test-audit/SKILL.md").read_text("utf-8")
        validation = " ".join(skill.split("## Validation\n")[1].split("## Landing")[0].split())
        assert "run the change's related tests" in validation
        assert "`fast_test` with `{base}` as the merge base with the default branch" in validation
        assert "`test` command when it has no `fast_test`" in validation
        assert "Run forge.toml's `test` command before you stop." not in validation
        _commit_test_fixes(validation)


def test_1_the_commit_nudge_names_the_fast_test_with_its_base(repo, monkeypatch):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             'workers = "claude"\ntest = "pytest -q"\n'
                             'fast_test = "pytest -q --since {base}"\n'
                             'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    base = repo.git("rev-parse", "HEAD")
    assert repo.forge("fix", "start", "Fix the login typo", "--done",
                      "The login page says Log in").returncode == 0
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "login.txt")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "2")

    built = repo.forge("work", FIX)

    assert built.returncode == 0, built.stdout + built.stderr
    nudged = calls(log)[1]
    assert f"Run the change's related tests (`pytest -q --since {base}`)" in nudged["brief"]
    _commit_test_fixes(nudged["brief"])

    monkeypatch.delenv("STUB_CLAUDE_LEAVE")
    monkeypatch.delenv("STUB_CLAUDE_COMMIT_FROM")
    again = repo.forge("work", FIX)
    assert again.returncode == 0, again.stdout + again.stderr
    continued = calls(log)[-1]
    assert "--resume" in continued["args"]
    assert f"Run the change's related tests (`pytest -q --since {base}`)" in continued["brief"]
    _commit_test_fixes(continued["brief"])


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
@pytest.mark.parametrize("fast", [False, True], ids=["test-fallback", "fast-test"])
def test_2_clients_receive_related_test_guidance_in_briefs_and_synced_skills(
        repo, gh, tmp_path, previous, fast):
    # Prompt bytes and synced guidance are the contract; Claude only records what Forge sends.
    # The old adoption is real release output from a text fixture, never current sync output.
    version = repo.forge("--version").stdout.split()[-1]
    if previous:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        _related_test_skills(client)
        repo.path = client
    repo.git("switch", "-q", "-c", "fix/test-guidance")
    config = (repo.path / "forge.toml").read_text("utf-8")
    config = config.replace('version = "v1.2.2"', f'version = "{version}"')
    config = config.replace('workers = "codex"', 'workers = "claude"').replace(
        'workers = "split"', 'workers = "claude"')
    if fast:
        config = 'fast_test = "pytest -q --since {base}"\n' + config
    repo.write("forge.toml", config)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A")
    # Seed a landed client setup, as the upgrade tests do; it has no active fix record yet.
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-q", "-m",
             "Upgrade worker guidance")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/test-guidance")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main")
    _related_test_skills(repo.path)
    log = install_claude(repo)
    started = repo.forge("fix", "start", "Fix the login typo", "--done", "The login page says Log in")
    assert started.returncode == 0, started.stdout + started.stderr
    built = repo.forge("work", FIX)
    assert built.returncode == 0, built.stdout + built.stderr
    brief = " ".join(calls(log)[0]["brief"].split())
    assert "run the change's related tests: forge.toml's `fast_test`" in brief
    assert "with `{base}` as the merge base with the default branch" in brief
    assert "`test` command when it has no `fast_test`" in brief
    _commit_test_fixes(brief.split("Use the test-audit skill", 1)[1])


@pytest.mark.parametrize("full,fast", [
    ("", 'fast_test = "pytest -q --since {base}"\n'),
    ('test = ""\n', 'fast_test = "pytest -q --since {base}"\n'),
    ("", ""),
], ids=["test-absent", "test-empty", "neither-command"])
def test_3_the_commit_nudge_resolves_fast_test_without_a_full_test(repo, monkeypatch, full, fast):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             'workers = "claude"\n' + full + fast +
                             'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Configure worker tests")
    repo.git("push", "-q", "origin", "main")
    base = repo.git("rev-parse", "HEAD")
    started = repo.forge("fix", "start", "Fix the login typo", "--done", "The login page says Log in")
    assert started.returncode == 0, started.stdout + started.stderr
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "login.txt")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "2")
    built = repo.forge("work", FIX)
    assert built.returncode == 0, built.stdout + built.stderr
    brief = calls(log)[1]["brief"]
    if fast:
        assert f"Run the change's related tests (`pytest -q --since {base}`)" in brief
    else:
        assert "Run the change's related tests in the foreground" in brief
        assert "(``)" not in brief
