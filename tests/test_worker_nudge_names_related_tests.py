"""Workers formerly received the raw test command; every round now uses forge test
so the shared machine lane also covers their related tests."""
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
        assert "follow `forge.toml`'s `test_place`" in validation.lower()
        assert "in local mode" in validation.lower()
        assert "run the change's related tests through `forge test`" in validation.lower()
        assert "in ci mode" in validation.lower()
        assert "do not run them here" in validation.lower()
        assert "run `forge test` only for a test you are writing" in validation.lower()
        assert "run the change's related tests" in validation
        assert "through `forge test`" in validation
        assert "`fast_test`, or `test` when none is set" in validation
        assert "Run forge.toml's `test` command before you stop." not in validation
        _commit_test_fixes(validation)

        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        refresh = guide.split("## Refresh dependencies", 1)[1].split("## Planning a story", 1)[0]
        assert "follow the repo's `test_place`" in refresh.lower()
        assert "local mode" in refresh.lower()
        assert "run the related tests through `forge test`" in refresh.lower()
        assert "ci mode" in refresh.lower()
        assert "do not run them here" in refresh.lower()


def test_1_the_commit_nudge_and_continued_round_use_the_test_lane(repo, monkeypatch):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             'workers = "claude"\ntest = "pytest -q"\n'
                             'fast_test = "pytest -q --since {base}"\n'
                             'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    assert repo.forge("fix", "start", "Fix the login typo", "--done",
                      "The login page says Log in").returncode == 0
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "login.txt")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "2")

    built = repo.forge("work", FIX)

    assert built.returncode == 0, built.stdout + built.stderr
    nudged = calls(log)[1]
    assert "run the change's related tests through `forge test`" in nudged["brief"].lower()
    _commit_test_fixes(nudged["brief"])

    monkeypatch.delenv("STUB_CLAUDE_LEAVE")
    monkeypatch.delenv("STUB_CLAUDE_COMMIT_FROM")
    again = repo.forge("work", FIX)
    assert again.returncode == 0, again.stdout + again.stderr
    continued = calls(log)[-1]
    assert bool(continued["options"].get("resume"))
    assert "run the change's related tests through `forge test`" in continued["brief"].lower()
    _commit_test_fixes(continued["brief"])


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
def test_2_clients_receive_related_test_guidance_in_briefs_and_synced_skills(
        repo, gh, tmp_path, previous):
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
    started = repo.forge("fix", "start", "Fix the login typo", "--done", "The login page says Log in",
                         "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    built = repo.forge("work", FIX)
    assert built.returncode == 0, built.stdout + built.stderr
    brief = " ".join(calls(log)[0]["brief"].split()).lower()
    assert ("the pull request's ci runs the change's related tests, lint and type checks, "
            "so do not run them here; run `forge test` only for a test you are writing, "
            "to watch it fail.") in brief
    assert "run the change's related tests through `forge test` in the foreground" not in brief


@pytest.mark.parametrize("full,fast", [
    ("", 'fast_test = "pytest -q --since {base}"\n'),
    ('test = ""\n', 'fast_test = "pytest -q --since {base}"\n'),
    ("", ""),
], ids=["test-absent", "test-empty", "neither-command"])
def test_3_the_commit_nudge_uses_the_lane_even_without_a_test_command(repo, monkeypatch, full, fast):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             'workers = "claude"\n' + full + fast +
                             'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Configure worker tests")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Fix the login typo", "--done", "The login page says Log in")
    assert started.returncode == 0, started.stdout + started.stderr
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "login.txt")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "2")
    built = repo.forge("work", FIX)
    assert built.returncode == 0, built.stdout + built.stderr
    brief = calls(log)[1]["brief"]
    assert "run the change's related tests through `forge test`" in brief.lower()
