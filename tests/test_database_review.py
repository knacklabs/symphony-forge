"""Database review rules reach clients and hold schema findings despite low model scores."""
from __future__ import annotations

import pytest

from test_close import CLEAN, GREEN, STORY_DOC, blocked, env  # noqa: F401 (fixture)
from test_score_notes import _client_repo as setup_client, _scored
from test_worker import calls, install_claude

STORY = "FORGE-DATABASE-1"

REVIEW_RULE = (
    "In an app with a database, report a table that this change adds, or a column, constraint, "
    "index or trigger on such a table, that breaks the database skill "
    "(.codex/skills/database/SKILL.md) as a P1 finding titled `Database: <the table or column>`. "
    "Report a Postgres extension that this change turns on and that is not on the skill's "
    "allowed list the same way, unless the app's constitution has a line "
    "\"Postgres extension <name>:\" with the owner's OK. A change to a table that the default "
    "branch already has is not a finding."
)
WORKER_RULE = (
    "In an app with a database, follow the database skill (.codex/skills/database/SKILL.md) "
    "for each table, column, index, constraint, migration or extension that you add. Existing "
    "tables stay as they are. A review holds new schema that breaks the skill."
)


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_6_reviews_hold_schema_that_breaks_the_skill(env, tmp_path, monkeypatch, adopted):
    # Audit: work must deliver the skill rule, and close must hold a low-scored database finding.
    # Omitting prompt delivery or the Database floor breaks this command-level contract.
    # Module tables coverage cannot catch this title or its new-table and extension exceptions.
    # Only third-party tools are faked; no production seam is needed.
    setup_client(env, tmp_path, adopted)
    env.checks(GREEN)
    repo = env.repo
    no_hooks = tmp_path / "fixture-no-hooks"
    no_hooks.mkdir(exist_ok=True)
    git = repo.git

    def fixture_git(*args, cwd=None):
        if args and args[0] in {"commit", "push"}:
            args = ("-c", f"core.hooksPath={no_hooks}", *args)
        return git(*args, cwd=cwd)

    with monkeypatch.context() as patch:
        patch.setattr(repo, "git", fixture_git)
        item, where = env.start_approved_task(STORY_DOC)
    log = install_claude(repo)
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert WORKER_RULE in " ".join(calls(log)[-1]["brief"].split())
    env.commit(where, "app.py", "print('invoice schema')\n", "Add invoices")
    title = "Database: Invoice.total"
    env.reviews(blocked(_scored("P1", title,
                               "Gain 2, Work 3, Harm 1\nInvoice.total uses an inexact float.")))
    closed = env.close(item)
    output = closed.stdout + closed.stderr
    assert closed.returncode == 1, output
    assert "The review left serious findings open" in output
    assert title in output
    assert "Gain 4, Work 2, Harm 1 (floor: database)" in output
    assert REVIEW_RULE in " ".join(env.prompt().split())

    env.commit(where, "app.py", "print('exact invoice total and currency')\n", "Use exact amounts")
    env.reviews(CLEAN)
    released = env.close(item)
    assert released.returncode == 0, released.stdout + released.stderr
