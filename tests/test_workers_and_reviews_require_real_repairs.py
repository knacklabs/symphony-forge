"""Init and sync deliver repair rules to workers and reviewers at their command boundaries."""
import shutil
from pathlib import Path

import pytest

from test_close import GREEN, env  # noqa: F401
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "ROOT-CAUSE-AND-NO-TEST-GAMING"


# Prompt content is the public contract here. Missing shipped guidance is the regression;
# existing distribution tests cover other rules, not these two. No production seam is needed.
# External worker/reviewer stubs capture requests, but do not decide their content.
@pytest.mark.parametrize("adopted", [False, True], ids=["init", "sync-from-v1.2.2"])
@pytest.mark.parametrize("rule, worker_phrases, review_phrase", [
    ("root cause", (
        "Reproduce the bug before you change the code.",
        "Find the first place the code goes wrong.",
        "Fix it in the shared function that every affected caller uses.",
        "Check sibling callers for the same fault.",
        "A guard is a fix only when it handles a valid state.",
    ), "Report a fix that hides a symptom and leaves the root cause in place."),
    ("no test-gaming", (
        "Do not hard-code expected values to make tests pass.",
        "Do not add a branch that detects a test.",
        "Do not add a silent default that hides a broken rule.",
    ), "Report code that only makes tests pass:"),
])
def test_1_workers_and_reviews_receive_real_repair_rules(
        env, tmp_path, adopted, rule, worker_phrases, review_phrase):
    repo = env.repo
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        client = repo.path
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        client, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Adopt on the earlier release")
        assert 'version = "v1.2.2"' in (client / "forge.toml").read_text("utf-8")
    else:
        client, initialized = _fresh_client(repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    config = (f'version = "{version}"\nworkers = "claude"\n'
              'test = "echo ok"\nchecks = ["tests", "forge-pr-check"]\n'
              'models.lite = { model = "sonnet", effort = "medium" }\n')
    if adopted:
        env.commit(client, "forge.toml", config, "Use the current release")
        repo.git("push", "-q", "origin", "main", cwd=client)

    started = repo.forge("fix", "start", "Repair the greeting", "--done",
                         "The greeting works", "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    where = client.parent / f"{client.name}-fix-repair-the-greeting"
    if not adopted:
        env.commit(where, "forge.toml", config, "Configure the test client")
    if adopted:
        synced = repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("add", "-A", cwd=where)
        repo.git("commit", "-q", "-m", "Sync current rules", cwd=where)
    log = install_claude(repo)
    worked = repo.forge("work", "repair-the-greeting", cwd=where)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    for phrase in worker_phrases:
        assert phrase in brief, (rule, phrase)
    if rule == "root cause":
        for host in (".claude", ".codex"):
            standards = " ".join((where / host / "skills/forge/standards.md").read_text(
                "utf-8").split())
            for phrase in worker_phrases:
                assert phrase in standards, (host, phrase)

    env.commit(where, "app.py", "print('hello')\n", "Repair the greeting")
    env.checks(GREEN)  # Init configures protection through the same external GitHub stub.
    closed = repo.forge("close", "repair-the-greeting", cwd=where)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    review = " ".join(env.prompt().split())
    assert review_phrase in review
    if rule == "no test-gaming":
        for phrase in ("hard-coded expected values", "a branch that detects a test",
                       "a silent default that hides a broken rule"):
            assert phrase in review
