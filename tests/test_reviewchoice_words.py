"""Delivered guidance and absent-key defaults on new and earlier-adopted clients.

Test audit: missing synced guidance, inserted config keys, or a one-round default
would violate these independent delivery and upgrade contracts. Explicit round
values and skip execution belong to the sibling tests; these tests own only
delivery, byte preservation and the absent-key path. Existing command fixtures
and external-tool stubs need no production seam. Prompt text is the product here.
"""
import json
import sys

import pytest

from conftest import ROOT, _install
from test_close import blocked, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_readloop_gates import say
from test_story import DOC, READER, approved_constitution, new_story
from test_two_round_limit import note
from test_worker import calls, install_claude

STORY = "FORGE-REVIEWCHOICE-1"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption-sync"])
def test_4_synced_guide_and_worker_brief_describe_person_requested_skip(env, adopted):
    client(env, adopted)
    for host in (".codex", ".claude"):
        guide = " ".join((env.repo.path / host / "skills/forge/SKILL.md")
                         .read_text("utf-8").split())
        for text in ('--no-review --by "<name>" --reason "<why>"',
                     "only when a person asks", "cold_read_rounds", "task_review_rounds"):
            assert text in guide

    # Select the existing SDK capture so this checks the brief actually sent to a worker.
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    config = config.replace('workers = "codex"', 'workers = "claude"')
    config = config.replace('workers = "split"', 'workers = "claude"')
    env.commit(env.repo.path, "forge.toml", config)
    env.repo.git("push", "-q", "origin", "main")
    log = install_claude(env.repo)
    item, _ = env.start_fix()
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert "Only use the model-review skip when a person asks" in brief
    assert "no earlier review blocked the item" in brief
    assert "task_review_rounds" in brief


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption-sync"])
def test_5_init_and_upgrade_keep_settings_and_two_round_defaults(env, adopted):
    client(env, adopted)
    config = env.repo.path / "forge.toml"
    content = config.read_bytes().replace(b"\r\n", b"\n")
    if adopted:
        previous = (ROOT / "tests/fixtures/adopted-v1.2.2/client/forge.toml").read_bytes().replace(b"\r\n", b"\n")
        version = env.repo.forge("--version").stdout.split()[-1].encode()
        assert content == previous.replace(b'"v1.2.2"', b'"' + version + b'"')
    for key in (b"cold_read_rounds", b"task_review_rounds"):
        assert key not in content

    env.reviews(blocked(note("P1", "Saving loses quantities")))
    item, _ = env.start_task()
    closed = env.close(item)
    output = closed.stdout + closed.stderr
    assert closed.returncode == 1, output
    assert "The review left serious findings open" in output
    assert "One more round, split or accept?" not in output
    assert "reached the round limit" not in output

    # A separate plan exercises the cold-read default without an explicit setting.
    approved_constitution(env.repo)
    env.commit(env.repo.path, "plans/roadmap.json", json.dumps({"items": [{"key": "READ"}]}))
    settings = config.read_text("utf-8")
    if "models.grill.claude" not in settings:
        settings = 'models.grill.claude = { model = "opus", effort = "high" }\n' + settings
    settings = settings.replace('workers = "codex"', 'workers = "claude"')
    settings = settings.replace('workers = "split"', 'workers = "claude"')
    settings = settings.replace('stage = "prototype"', 'stage = "live"')
    env.commit(env.repo.path, "forge.toml", settings)
    env.repo.git("push", "-q", "origin", "main")
    where = new_story(env.repo, "READ")
    (where / "plans/READ.md").write_text(DOC, encoding="utf-8")
    _install(env.repo.bin, "claude", READER.format(python=sys.executable))
    say(env.repo, "1. Blocking: Saving loses its recovery point.\n"
        "   Case: normal use - A shopper returns and loses saved work.\n"
        "   Gain 4, Work 1, Harm 2\n")
    first = env.repo.forge("read", "READ", cwd=where)
    assert first.returncode == 0, first.stdout + first.stderr
    assert "Wrote round 1 of the cold read" in first.stdout
    assert "One more round, split or accept?" not in first.stdout + first.stderr
