"""Worker briefs carry the two test rules that prevent failed fix rounds."""
from test_worker import calls, install_claude

STORY = "FIX-WORKER-BRIEF-RULES"


def test_1_worker_brief_does_not_exempt_docs_and_runs_forge(repo):
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
    assert ("In a repo whose tests run Forge (forge-source), a test runs the forge command "
            "and never imports forge.") in brief
