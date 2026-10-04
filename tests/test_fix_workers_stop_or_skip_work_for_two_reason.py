"""Workers receive required tests and evidence-based failure guidance through forge work."""

from test_worker import calls, install_claude

STORY = "FIX-WORKERS-STOP-OR-SKIP-WORK-FOR-TWO-REASON"


def test_1_worker_brief_requires_named_tests_and_keeps_flaky_failures_unresolved(repo):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n'
               'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")

    started = repo.forge("fix", "start", "Clarify worker test guidance",
                         "--done", "Workers receive both test rules")
    assert started.returncode == 0, started.stderr
    worked = repo.forge("work", "clarify-worker-test-guidance")
    assert worked.returncode == 0, worked.stderr
    brief = calls(log)[-1]["brief"]
    tests_first = brief.split("## Tests first\n", 1)[1].split("\n## ", 1)[0]
    assert "Add every test your task's Tests column names, even when the change is documentation only." in tests_first
    # An isolated pass used to excuse a suite failure as machine load. It now establishes
    # intermittency only; the worker reports both results and leaves the failure unresolved.
    assert ("A test that fails in the suite but passes alone is flaky; its failure stays unresolved.\n"
            "Report both results without guessing the cause.") in tests_first
