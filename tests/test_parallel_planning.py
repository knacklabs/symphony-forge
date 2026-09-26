"""Plans aim for parallel work: the skill, the story template and the cold read say so, and
forge next tells the coordinator to start the ready parts together."""
from __future__ import annotations

import json

from test_discovery import HOSTS, _client
from test_phases import _flat
from test_story import DOC, claude_plan, hook, new_story, ready, setup

STORY = "PARALLEL-PLANNING"
SPLIT_BY_FILES = ("split tasks so each owns its files; shared lines (command table, guide list, "
                  "registry) go to one task or a small last wiring task; after only when a task "
                  "needs another task's code")


def test_1_the_skill_says_to_split_by_files_and_start_ready_work_together(repo, gh, tmp_path):
    client = _client(repo, gh, tmp_path)
    for host in HOSTS:
        skill = _flat((client / host / "skills/forge/SKILL.md").read_text("utf-8"))
        planning = skill.split("## Planning a story")[1].split(" ## ")[0]
        for rule in ("split tasks so each owns its files", "a command-table row, a guide list or a "
                     "registry", "goes to one task, or to a small last wiring task",
                     "Use After only when a task needs another task's code"):
            assert rule in planning, rule
        assert ("Start every task and fix `forge next` lists as ready at once, and close each as "
                "its worker finishes") in skill


def test_2_the_story_template_and_cold_read_say_to_split_by_files(repo):
    setup(repo)
    shop = new_story(repo, "SHOP")
    guidance = _flat((shop / "plans" / "SHOP.md").read_text("utf-8").split("## Tasks")[1])
    assert SPLIT_BY_FILES in guidance.lower()

    (shop / "plans" / "SHOP.md").write_text(DOC, encoding="utf-8")
    (repo.bin / "claude-says.md").write_text("No findings.\n", encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    prompt = _flat(json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8")
                              .splitlines()[-1])["prompt"])
    assert ("Flag every After link or shared Scope entry that exists only because of a shared "
            "line (a command-table row, a guide list, a registry), and name the split: the shared "
            "line to one task or a small last wiring task") in prompt


def test_3_forge_next_says_to_start_the_ready_parts_together(repo, claude_payload):
    setup(repo)
    parallel = DOC.replace("`tests/test_page.py` | SAVE |", "`tests/test_page.py` | none |")
    shop = ready(repo, "SHOP", parallel)
    assert hook(repo, claude_plan(claude_payload, parallel, cwd=shop)).returncode == 0
    assert repo.forge("next").stdout.splitlines()[:3] == [
        "2 parts of Shoppers can save a basket can start now; start them together.",
        "Next: forge task start SHOP/SAVE", "Next: forge task start SHOP/SHOW"]
