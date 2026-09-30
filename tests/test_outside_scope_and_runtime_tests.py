"""Workers change the outside-Scope files a change needs and name them; only runtime behaviour
needs an end-to-end test; new test files are named for the behaviour they prove."""

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
    item, _ = env.start_task()
    assert env.close(item).returncode == 0
    scope = flat(env.prompt().split("## Scope", 1)[1].split("\n## ", 1)[0])
    assert "Report only the files outside Scope that the work doesn't need" in scope
    assert "Check the worker's handoff names each such file and why" in scope


def test_3_brief_asks_end_to_end_only_for_runtime_behaviour(repo):
    tests_first = flat(brief_of(repo).split("## Tests first\n", 1)[1].split("\n## ", 1)[0])
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
