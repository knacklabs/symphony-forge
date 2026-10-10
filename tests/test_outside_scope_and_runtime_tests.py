"""Workers change the outside-Scope files a change needs and name them; only runtime behaviour
needs an end-to-end test; new test files are named for the behaviour they prove."""

import re
from pathlib import Path

from test_close import env  # noqa: F401
from test_worker import calls, install_claude

STORY = "FIX-WORKERS-STOP-AND-ASK-BEFORE-EVERY-FILE-O"


def flat(text: str) -> str:
    return " ".join(text.split())


def brief_of(repo) -> str:
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n'
               'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Greet readers", "--done", "The readme greets readers")
    assert started.returncode == 0, started.stderr
    worked = repo.forge("work", "greet-readers")
    assert worked.returncode == 0, worked.stderr
    return calls(log)[-1]["brief"]


def test_1_worker_changes_needed_outside_scope_files_and_names_them(repo):
    brief = brief_of(repo)
    rules = flat(brief.split("# Worker brief", 1)[1].split("\n## ", 1)[0])
    assert ("You may change a file outside your Scope that the change needs, such as a caller, "
            "a type or an existing test it breaks; name each such file and why in your handoff."
            ) in rules
    assert ("Stop only for a one-way step, a security question, a new moving part, or Done-when "
            "items that contradict each other") in rules
    assert "path outside" not in flat(brief.split("## Standards", 1)[0])
    assert "path outside your Scope" not in flat(brief)


def test_2_review_reports_only_outside_scope_files_the_work_does_not_need(env):
    env.repo.write("tests/test_old.py", "def test_old():\n    assert True\n")
    env.repo.git("add", "tests")
    env.repo.git("commit", "-q", "-m", "Add an existing test")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_task(changes={"app.py": "print('saved')\n",
                                      "tests/test_old.py": "def test_old():\n    assert False\n"})
    assert env.close(item).returncode == 0
    scope = flat(env.prompt().split("## Scope", 1)[1].split("\n## ", 1)[0])
    # Every changed file outside Scope and Tests is listed, a changed existing test included, so
    # the reviewer judges whether the work needed it.
    assert "- tests/test_old.py" in scope
    assert "Report only the files outside Scope that the work doesn't need" in scope
    # Close never passes the worker's handoff, so the reviewer is not told to check it.
    assert "handoff" not in scope


def test_3_brief_asks_end_to_end_only_for_runtime_behaviour(repo):
    brief = brief_of(repo)
    tests_first = flat(brief.split("## Tests first\n", 1)[1].split("\n## ", 1)[0])
    # The testing how-to the brief points to follows the same rule.
    folder = re.search(r"default client stack is in `([^`]+)`", brief)[1]
    testing = flat((Path(folder) / "testing.md").read_text(encoding="utf-8"))
    for rule in ("Every Done-when item needs an end-to-end test through the real entry point when "
                 "it changes runtime behaviour",
                 "An item with no UI gets a Supertest test through HTTP",
                 "Every user-facing Done-when item gets one Playwright test"):
        start = testing.index(rule)
        assert "when it changes runtime behaviour" in testing[start:testing.index(".", start + len(rule))], rule
    assert "one per Done-when item, not one per function" in testing
    assert testing.count("proven by the check the item names") >= 2
    assert ("Every Done-when item needs an end-to-end test through the real entry point when it "
            "changes runtime behaviour") in tests_first
    assert ("Settings, docs, deletions and test-only items are proven by the check the item names."
            ) in tests_first


def test_4_review_asks_end_to_end_only_for_runtime_behaviour(env):
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    audit = flat(env.prompt().split("## Test audit", 1)[1].split("\n## ", 1)[0])
    assert ("Every Done-when item needs an end-to-end test through the real entry point when it "
            "changes runtime behaviour") in audit
    assert ("Settings, docs, deletions and test-only items are proven by the check the item names."
            ) in audit


def test_5_brief_names_new_test_files_after_their_behaviour(repo):
    tests_first = flat(brief_of(repo).split("## Tests first\n", 1)[1].split("\n## ", 1)[0])
    assert ("Name a new test file after the behaviour it proves, never after the fix's slug."
            ) in tests_first


# A sentence that asks for a test for each or every item, with no runtime-behaviour condition and
# no named check as the alternative.
PER_ITEM = re.compile(r"\b(each|every)\b[^.]*\bitems?\b|\bitems?\b[^.]*\bbecomes? a test\b", re.I)
TEST = re.compile(r"\b(tests?|Playwright|Supertest)\b(?! names)")
NAMED_CHECK = re.compile(r"check (the item|it) names|test or check")


def per_item_test_demands(name: str, text: str) -> list[str]:
    sentences = re.split(r"(?<=[.;:])\s+", flat(text))
    return [f"{name}: {s}" for s in sentences if PER_ITEM.search(s) and TEST.search(s)
            and "runtime behaviour" not in s and not NAMED_CHECK.search(s)]


def test_6_no_worker_guidance_demands_a_test_for_every_item_regardless_of_runtime_behaviour(repo):
    brief = brief_of(repo)
    folder = Path(re.search(r"default client stack is in `([^`]+)`", brief)[1])
    repo.git("checkout", "-q", "-b", "fix/sync-skill")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    texts = {"brief": brief,
             **{f"conventions/{p.name}": p.read_text(encoding="utf-8")
                for p in sorted(folder.glob("*.md"))},
             **{f"{host}/{name}": (repo.path / host / "skills/forge" / name).read_text("utf-8")
                for host in (".claude", ".codex") for name in ("SKILL.md", "standards.md")}}
    assert "## Standards" in brief and len(texts) > 10
    found = [line for name, text in texts.items() for line in per_item_test_demands(name, text)]
    assert found == [], "\n".join(found)


def test_7_no_review_demands_a_test_for_every_item_regardless_of_runtime_behaviour(env):
    fix, _ = env.start_fix()
    assert env.close(fix).returncode == 0
    texts = {"fix review": env.prompt()}
    task, _ = env.start_task()
    assert env.close(task).returncode == 0
    texts["task review"] = env.prompt()
    found = [line for name, text in texts.items() for line in per_item_test_demands(name, text)]
    assert found == [], "\n".join(found)
