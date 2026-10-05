"""Worker briefs require the task's named tests, even for documentation."""
from test_worker import calls, install_claude

STORY = "FIX-WORKER-BRIEF-RULES"


def test_1_worker_brief_does_not_exempt_docs(repo):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "claude"\n'
                             'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")

    started = repo.forge("fix", "start", "Clarify worker tests", "--done", "Workers follow test rules")
    assert started.returncode == 0, started.stderr
    built = repo.forge("work", "clarify-worker-tests")
    assert built.returncode == 0, built.stderr
    brief = calls(log)[-1]["brief"]
    # The old brief exempted documentation changes; the task's Tests column now wins.
    assert "A change to documentation only needs no test." not in brief
    # Forge-source's command-only test policy now belongs to its own AGENTS.md; clients receive
    # the general requirement to add every test named in the task, even for documentation.
    assert "Add every test your task's Tests column names, even when the change is documentation only." in brief
