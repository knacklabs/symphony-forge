"""Synced clients get bounded review, cold-read and worker instructions from Forge."""
import shutil
import sys
from pathlib import Path

import pytest

import conftest
from test_close import env  # noqa: F401
from test_story import READER
from test_worker import calls, install_claude

STORY = "FIX-THE-RULES-THAT-STOP-REVIEWS-AND-PLAN-REA"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-on-v1.2.2"])
def test_1_sync_delivers_bounded_review_cold_read_and_worker_rules(env, adopted):
    repo = env.repo
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Adopt on the earlier release")
        config = (repo.path / "forge.toml").read_text("utf-8")
        config = config.replace('version = "v1.2.2"', f'version = "{version}"')
        config = config.replace('workers = "codex"', 'workers = "claude"')
        config = config.replace('[models.lite]\nmodel = "gpt-6.1-sol"',
                                '[models.lite]\nmodel = "sonnet"')
        config = config.replace('subagents = "gpt-6-luna"\nsubagent_effort = "max"\n', "")
    else:
        config = ((repo.path / "forge.toml").read_text("utf-8")
                  + 'repo = "client"\nstage = "live"\n'
                  + 'models.lite = { model = "sonnet", effort = "medium" }\n'
                  + 'models.grill.claude = { model = "opus", effort = "high" }\n')
    env.commit(repo.path, "forge.toml", config, "Use the installed Forge")
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert (where / "forge.toml").read_text("utf-8") == config
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-q", "-m", "Sync the client instructions", cwd=where)

    log = install_claude(repo)
    worked = repo.forge("work", item, cwd=where)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert "One command-level test per rule is enough." in brief

    conftest._install(repo.bin, "claude", READER.format(python=sys.executable))
    env.commit(where, "docs/specs/basket.md", "# Basket\n\n## Why\n\nKeep a basket.\n")
    read = repo.forge("read", "basket", cwd=where)
    assert read.returncode == 0, read.stdout + read.stderr
    cold_read = " ".join(calls(log)[-1]["prompt"].split())
    assert "Prefer one blunt fail-closed rule with one test over listing every case." in cold_read
    assert "Leave out, unless it falls under Security or Data loss" in cold_read
    assert "a window under a second" in cold_read
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    review = " ".join(env.prompt().split())
    assert ("- a rare combination that needs an unusual sequence: a crash or interrupt at a "
            "precise moment, a window under a second") in review
    assert "- a case a fail-closed rule in the change already covers;" in review
    assert ("extra test variations (one command-level test per rule is enough), unless the "
            "finding names a concrete scenario the current tests would pass while the code is "
            "broken") in review
