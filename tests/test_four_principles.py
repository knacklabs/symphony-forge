"""The principles reach new and earlier clients through the real Forge commands.

Audit: missing host/upgrade delivery breaks the prompt contract; the score case
guards advice blocking work or Security being waived. Existing guidance and score
tests do not cover these principles together. Only external agents and GitHub are
stubbed. No production seam is needed; prompt bytes are the delivery contract.
"""
import shutil
import subprocess
import sys

import pytest

import conftest
from conftest import ROOT, FORGE_SHIM, _install
from test_close import blocked, body, env  # noqa: F401
from test_score_notes import _scored
from test_setup import _fresh_client, _version
from test_story import READER
from test_worker import calls, install_claude

STORY = "FORGE-ASKED-1"


def flat(text):
    return " ".join(text.split())


@pytest.mark.parametrize("previous", [False, True], ids=["new init", "previous release"])
def test_1_the_principles_reach_the_guide_and_the_worker(repo, gh, tmp_path, previous):
    log = install_claude(repo)
    if not previous:
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        started = repo.forge("fix", "start", "Check principles", "--done",
                             "Agents receive the principles", "--kind", "mechanical", cwd=client)
        assert started.returncode == 0, started.stdout + started.stderr
        client = tmp_path / "client-fix-check-principles"
        item = "check-principles"
    else:
        old = tmp_path / "previous-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(
            python=sys.executable, src=str(old / "src")))
        gh.respond("api", stdout="{}")
        made = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init",
                               "--test", "echo ok", "--checks", "tests",
                               "--interfaces", "api/routes/**", "--approver", "Owner",
                               "--merger", "Owner"], cwd=repo.path, capture_output=True, text=True)
        assert made.returncode == 0, made.stdout + made.stderr
        client = tmp_path / "repo-fix-adopt-forge"
        item = "adopt-forge"
    config = client / "forge.toml"
    text = config.read_text("utf-8").replace('version = "v1.2.2"',
                                            f'version = "{_version(repo)}"')
    text = text.replace('workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"')
    config.write_text(text, "utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use the current client guidance", cwd=client)
    worked = repo.forge("work", item, cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    for host in (".claude", ".codex"):
        guide = flat((client / host / "skills/forge/SKILL.md").read_text("utf-8"))
        for phrase in ("## Principles", "Add work only when F x H >= 2 x C. F, for the first 1,000 users",
                       "Copy `## Principles` into every app's constitution word for word",
                       "Do not add it to an approved constitution"):
            assert phrase in guide, (host, phrase)
    brief = flat(calls(log)[-1]["brief"])
    for phrase in ("why deleting code or a step does not solve it", "its F x H and 2 x C",
                   "Rules are stated, not policed", "3 a P0", "1 rare, 2 weekly, 3 daily",
                   "1 for 20 lines or fewer with no model call or user step",
                   "2 for up to about 150 lines or one model call or user step",
                   "3 for more, or a new table, job, workflow or flag"):
        assert phrase in brief, phrase
    if previous:
        assert not (client / "docs/product/CONSTITUTION.md").exists()


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_2_added_work_is_weighed_against_its_cost(env, adopted):
    repo = env.repo
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
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
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-q", "-m", "Sync the client instructions", cwd=where)
    log = install_claude(repo, worker=False)
    conftest._install(repo.bin, "claude", READER.format(python=sys.executable))
    env.commit(where, "docs/specs/basket.md", "# Basket\n\n## Why\n\nKeep a basket.\n")
    read = repo.forge("read", "basket", cwd=where)
    assert read.returncode == 0, read.stdout + read.stderr
    cold_read = flat(calls(log)[-1]["prompt"])
    env.reviews(blocked(_scored("P1", "Retry an unusual failure",
                               "Gain 2, Work 2, Harm 1\nRaise: Functional\n"
                               "Adds work: a retry; F 1 x H 1 = 1; 2 x C = 4")))
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    for prompt in (cold_read, flat(env.prompt())):
        for phrase in ("Four principles govern every change.",
                       "Adds work: <what>; F <f> x H <h> = <p>; 2 x C = <c>",
                       "When p is less than 2 x C, score its Gain 2 or less",
                       "a cold read keeps it with its disposition in the read notes",
                       "A check that a Done-when item promises is not added work",
                       "Rules are stated, not policed", "3 a P0"):
            assert phrase in prompt, phrase
    # Known limits are listed as Lived with in the pull request, not in stdout.
    recorded = body(env.gh_calls("pr", "edit")[-1])
    lived_with = recorded.split("Lived with:", 1)[1].split("</details>", 1)[0]
    assert "Retry an unusual failure" in lived_with
    # The same cost never waives the independent Security Harm floor.
    env.commit(where, "app.py", "print('hello again')\n")
    env.reviews(blocked(_scored("P1", "Protect the retry credential",
                               "Gain 2, Work 2, Harm 4\nRaise: Security\n"
                               "Adds work: a retry; F 1 x H 1 = 1; 2 x C = 4")))
    refused = env.close(item)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "Protect the retry credential" in refused.stdout + refused.stderr
