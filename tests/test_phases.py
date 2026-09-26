"""The phase texts: the story template, the cold read, the worker brief and the review instructions.

Each test is named test_<criterion>_<rule> after the spec's acceptance criterion it proves.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from test_close import STORY_DOC, env, finding, report  # noqa: F401 (env is a fixture)
from test_githooks import commit
from test_setup import _fresh_client
from test_story import DOC, new_story, setup
from test_worker import calls, install_claude


def _flat(text: str) -> str:
    """The text with every run of whitespace as one space, so line wraps don't matter."""
    return " ".join(text.split())


def test_33_new_moving_parts_line(env):
    repo = env.repo
    # The template from forge story new ends its Tasks section with the line.
    env.commit(repo.path, "plans/roadmap.json", json.dumps({"items": [{"key": "CART"}]}))
    repo.git("push", "-q", "origin", "main")
    made = repo.forge("story", "new", "CART", "Shoppers share a cart")
    assert made.returncode == 0, made.stderr
    tasks = repo.git("show", "story/CART:plans/CART.md").split("\n## Tasks\n")[1].split("\n## ")[0]
    assert tasks.strip().splitlines()[-1] == "New moving parts: none"

    # The worker brief and the review instructions both carry the story's line.
    line = "New moving parts: a nightly clean-up job (Done when 1)"
    env.commit(repo.path, "plans/SHOP.md", STORY_DOC.replace("New moving parts: none", line))
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_task()
    log = install_claude(repo)
    assert repo.forge("work", item).returncode == 0
    assert line in calls(log)[-1]["brief"]
    assert env.close(item).returncode == 0
    assert line in env.prompt()

    # forge-pr-check fails a pull request whose story doc has lost the line.
    doc = (where / "plans" / "SHOP.md").read_text("utf-8")
    env.commit(where, "plans/SHOP.md", doc.replace(f"{line}\n", ""))
    checked = repo.forge("hook", "pr-check", "--base", repo.git("rev-parse", "origin/main"),
                         "--head", "HEAD", "--branch", "task/SHOP-T1", cwd=where)
    assert checked.returncode == 1
    assert checked.stderr.splitlines()[0] == (
        'The story doc plans/SHOP.md is malformed: its Tasks section has no "New moving parts:" '
        "line.")


def test_34_simpler_rule(env):
    # The helper drops a finding pinned to a file the branch didn't change and calls the review
    # incomplete; Forge keeps the finding, so this unnamed moving part still blocks close.
    unnamed = finding("P1", "Simpler: drop the new job queue, do the work in the request",
                      "jobs.py", 3)
    env.reviews({"exit": 2, "say": "autoreview incomplete", "report": {
        **report(), "findings": [], "scope_rejected_findings": [unnamed],
        "review_status": "incomplete", "overall_correctness": "patch is incorrect"}})
    done = env.close(env.start_task()[0])

    prompt = _flat(env.prompt())
    for rule in (
            "report it as a P2 finding titled `Simpler: <what to cut> → <what replaces it>`",
            "make it P1 when the diff adds a new dependency, service, datastore, queue, background "
            "job or abstraction layer that the New moving parts line above doesn't name",
            "structure the standards page requires for a concern the diff really has (a provider "
            "for an external service, typed request and response types for an endpoint) is not a "
            "finding",
            'validation, authorization, secrets handling, data-loss protection and accessibility '
            'are never "simpler": a missing one is its own P1 finding',
            # The reviewer reads the whole checkout, and pins each finding where Forge sees it.
            "the standard note that the sandbox is empty does not apply to this run",
            "Pin every finding to a line in a file this branch changes"):
        assert rule in prompt, rule
    assert done.returncode == 1 and len(env.review_calls()) == 1
    assert done.stderr.splitlines()[-2] == (
        "The review left serious findings open: finding 1 (Simpler: drop the new job queue, do "
        "the work in the request).")


def test_35_simple_enough_cold_read(repo):
    setup(repo)
    shop = new_story(repo, "SHOP")
    (shop / "plans" / "SHOP.md").write_text(DOC, encoding="utf-8")
    (repo.bin / "claude-says.md").write_text("1. One task would do.\n", encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0

    prompt = _flat(json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8")
                              .splitlines()[-1])["prompt"])
    for check in (
            "Anything that maps to nothing gets `Cut or defer: <item>`",
            "Each entry in `New moving parts` needs its \"Done when\" item and a reason the lower "
            "rungs won't do",
            "`Simpler: <part> → <lower rung>`",
            'When a smaller shape would deliver the same "Done when", name it',
            "`Split: <task> → <two tasks>`",
            "Flag any one-way step (deleting data, a destructive migration, a new vendor) that "
            "isn't listed under Risks",
            "Never propose dropping validation, security, data-loss protection or accessibility"):
        assert check in prompt, check
    notes = (shop / "plans" / "SHOP.read.md").read_text("utf-8")
    for disposition in ("`Disposition: cut`", "`Disposition: defer`",
                        "`Disposition: keep <one-line reason>`"):
        assert disposition in notes


def test_37_one_ui_skill(env):
    # A user-facing task's brief and its review name motion only for a Done-when item needing it.
    log = install_claude(env.repo)
    item = env.start_task("T2", {"show.py": "print('basket')\n"})[0]
    assert env.repo.forge("work", item).returncode == 0
    assert env.close(item).returncode == 0
    for text in (_flat(calls(log)[-1]["brief"]), _flat(env.prompt())):
        assert "impeccable is the one" in text
        motion = [s for s in re.split(r"(?<=\.) ", text) if re.search(r"motion|animat", s, re.I)]
        assert motion, "no sentence names motion"
        for sentence in motion:
            assert "only when a Done-when item needs motion" in sentence, sentence


def test_40_interfaces(repo, gh, tmp_path, env):
    # With interfaces listed, a fix's review has no Promote instruction; with none, it does.
    item, where = env.start_fix()
    assert env.close(item).returncode == 0
    assert "Promote:" not in env.prompt()
    toml = (where / "forge.toml").read_text("utf-8")
    env.commit(where, "forge.toml", toml.replace('interfaces = ["**/routes/**"]', "interfaces = []"))
    env.close(item)
    assert ("Report any change to an interface (an API route, a database schema or migration, a "
            "command table or a config schema) as a P1 finding titled `Promote: <the interface>`"
            ) in _flat(env.prompt())

    # forge init writes the stack's default interfaces: a fix that changes one is refused.
    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    started = repo.forge("fix", "start", "Tidy the orders code", "--done", "It reads well",
                         cwd=client)
    assert started.returncode == 0, started.stderr
    fix = started.stdout.split()[2]
    folder = Path(started.stdout.splitlines()[0].split(" in ", 1)[1])
    for path in ("apps/api/src/orders/orders.controller.ts", "apps/api/prisma/schema.prisma",
                 "apps/api/prisma/migrations/20260926_init/migration.sql",
                 "apps/api/src/config.schema.ts", "src/cli.py"):
        refused = commit(folder, path)
        assert refused.returncode != 0 and f"Fix {fix} changes the interface {path}," in (
            refused.stderr), refused.stderr
        repo.git("reset", "-q", cwd=folder)
        (folder / path).unlink()
    assert commit(folder, "apps/api/src/orders/orders.service.ts").returncode == 0
