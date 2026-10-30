"""Sources and needs reach new and earlier clients through real Forge commands.

Audit: missing render values, host copies or upgrade delivery must fail these
prompt contracts. Existing principles tests do not cover sources and needs.
Only external agents and GitHub are stubbed; no production seam is needed.
"""
import shutil
import subprocess
import sys

import pytest

import conftest
from conftest import ROOT, FORGE_SHIM, _install
from test_close import STORY_DOC, env  # noqa: F401
from test_setup import _fresh_client, _version
from test_story import READER, approved_constitution, new_story
from test_worker import calls, install_claude

STORY = "FORGE-ASKED-1"


def flat(text):
    return " ".join(text.split())


@pytest.fixture(params=[False, True], ids=["new-client", "adopted-v1.2.2"])
def client(env, request):
    repo = env.repo
    version = repo.forge("--version").stdout.split()[-1]
    if request.param:
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
    approved_constitution(repo)
    repo.git("push", "-q", "origin", "main")
    return env, request.param


def test_3_plans_name_a_source_or_a_need_for_each_item(client):
    env, _ = client
    shop = new_story(env.repo, "SHOP")
    synced = env.repo.forge("sync", cwd=shop)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    changes = flat((shop / "plans/SHOP.md").read_text("utf-8").split(
        "## What changes for you", 1)[1].split("##", 1)[0])
    assert "End each item with its source in plain words" in changes
    assert "(Needed by: the Customers screen)" in changes
    for host in (".claude", ".codex"):
        guide = flat((shop / host / "skills/forge/SKILL.md").read_text("utf-8"))
        assert "Name each screen, field, endpoint, tool and setting that the plan adds in one of these items" in guide
        assert "plan only the screens marked Build now" in guide


def test_4_additions_that_nothing_needs_get_a_not_needed_note(client):
    env, adopted = client
    repo = env.repo
    if not adopted:
        # Seed the approved story before sync installs the shared git hooks;
        # the approval fixture writes its sign-off and roadmap on main.
        source = "Shoppers can save a basket and come back to it. (Source: the owner's request, 27 Oct)"
        doc = STORY_DOC.replace("Shoppers can save a basket and come back to it.", source)
        assert source in doc
        item, _ = env.start_approved_task(doc)
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert "## What changes for you" in env.prompt()
        assert source in env.prompt()
    item, where = env.start_fix()
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-q", "-m", "Sync source guidance", cwd=where)
    log = install_claude(repo, worker=False)
    conftest._install(repo.bin, "claude", READER.format(python=sys.executable))
    env.commit(where, "docs/specs/basket.md", "# Basket\n\n## Why\n\nKeep a basket.\n")
    read = repo.forge("read", "basket", cwd=where)
    assert read.returncode == 0, read.stdout + read.stderr
    cold_read = flat(calls(log)[-1]["prompt"])
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    for prompt in (cold_read, flat(env.prompt())):
        boundary = prompt.split("## What counts", 1)[1].split("at the start of its evidence.", 1)[0]
        assert "- Not needed: a large addition that no source asks for and that no sourced item needs:" in boundary
        for phrase in ("a new table, background job, workflow or settings flag, or about 150 lines or more",
                       "docs/product/DISCOVERY.md", "docs/product/BRIEF.md", "docs/decisions/",
                       "a screen marked Build now at sign-off", "docs/product/CONSTITUTION.md",
                       "a fix's Why and Done-when line", "The canvas is not a source"):
            assert phrase in boundary, phrase
        for phrase in ("Not needed: <what was added>",
                       "which sources and sourced items you checked and found silent",
                       "name its source or the sourced item that needs it",
                       "remove it and add one line for it to `plans/ideas.md`",
                       "Deleting beats fixing", "say that it is large and why",
                       "A smaller addition is advice", "never against the canvas"):
            assert phrase in prompt, phrase


@pytest.mark.parametrize("previous", [False, True], ids=["new init", "previous release"])
def test_5_useful_extras_go_to_the_idea_list(repo, gh, tmp_path, previous):
    log = install_claude(repo)
    if not previous:
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        started = repo.forge("fix", "start", "Check idea guidance", "--done",
                             "Agents receive idea guidance", "--kind", "mechanical", cwd=client)
        assert started.returncode == 0, started.stdout + started.stderr
        client = tmp_path / "client-fix-check-idea-guidance"
        item = "check-idea-guidance"
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
    text = config.read_text("utf-8").replace('version = "v1.2.2"', f'version = "{_version(repo)}"')
    text = text.replace('workers = "split"', 'workers = "claude"').replace(
        'workers = "codex"', 'workers = "claude"')
    config.write_text(text, "utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", "Use current client guidance", cwd=client)
    worked = repo.forge("work", item, cwd=client)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = flat(calls(log)[-1]["brief"])
    for phrase in ("build nothing for it", "plans/ideas.md", "the sourced item that needs it>",
                   "Only what is needed", "Build nothing beyond them just in case"):
        assert phrase in brief, phrase
    for host in (".claude", ".codex"):
        folder = client / host / "skills/forge"
        guide = flat((folder / "SKILL.md").read_text("utf-8"))
        assert "add one line `- <YYYY-MM-DD>: <the idea>` to `plans/ideas.md`" in guide
        assert "`Not needed: <what>` on a large addition" in guide
        assert "Only what is needed" in (folder / "standards.md").read_text("utf-8")
