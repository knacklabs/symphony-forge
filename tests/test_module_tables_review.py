"""Reviews and cold reads hold new queries across module table ownership."""
from __future__ import annotations

import json

import pytest

from test_close import CLEAN, GREEN, STORY_DOC, blocked, body, env  # noqa: F401 (fixture)
from test_proto_signoff import SOL_HIGH, _client, _decision
from test_score_bar import _read_prompt, _says
from test_score_notes import _client_repo as setup_client, _scored
from test_story import DOC, new_story
from test_worker import calls, install_claude


REVIEW_RULE = (
    "In an app with a database, report a query that this change adds in one module on a table "
    "another module owns as a P1 finding titled `Module tables: <the query>`. A module owns the "
    "tables in its own schema file; in an app without one schema file per module, it owns the "
    "tables that only its code writes. Other modules reach those tables only through its public "
    "service. A query the default branch already has is not a finding, and neither is app code "
    "outside the modules, such as the demo-data loader."
)
WORKER_RULE = (
    "In an app with modules, use another module only through its public service, and never query "
    "a table it owns. The tests' module-boundary lint fails an import across modules, and a review "
    "holds a new query on another module's tables."
)
READ_RULE = (
    "In a client app, report a plan whose part has one module query a table another module owns "
    "as a note titled `Module tables: <the part>`."
)
SIGNOFF_RULE = (
    "Report a query in one module on a table another module owns as a P1 finding titled "
    "`Module tables: <the query>`."
)


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_3_reviews_and_reads_hold_a_query_on_another_modules_tables(env, tmp_path, monkeypatch, adopted):
    # Test-audit: commands own prompt delivery and the hold, including low model scores.
    # Existing floor tests cover other titles, so miss this rule being absent or unscored.
    # Only external tools are faked; no production seam is needed.
    original = env.repo.path
    setup_client(env, tmp_path, adopted)
    env.checks(GREEN)
    repo = env.repo
    # A part's first review returns the serious-finding message. A fix instead reaches
    # its one-round owner-choice stop; that policy has its own command coverage.
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
    env.commit(where, "app.py", "print('module change')\n", "Change a module")
    title = "Module tables: ProjectsService reads Session"
    issue = _scored("P1", title, "Gain 2, Work 3, Harm 1\nProjects reads the sign-in table.")
    env.reviews(blocked(issue))
    closed = env.close(item)
    output = closed.stdout + closed.stderr
    assert closed.returncode == 1, output
    assert "The review left serious findings open" in output
    assert title in output
    assert "Gain 4, Work 2, Harm 1 (floor: module tables)" in output
    assert REVIEW_RULE in " ".join(env.prompt().split())

    _says(repo, "1. Blocking: Module tables: The plan has projects read Session\n"
                "   Case: normal use - projects loads a session.\n"
                "   Gain 2, Work 1, Harm 1\n"
                "2. Advisory: Module tables: A rare query\n"
                "   Case: rare\n   Gain 2, Work 1, Harm 1\n")
    shop = new_story(repo, "MODULES")
    (shop / "plans/MODULES.md").write_text(DOC, encoding="utf-8")
    read = repo.forge("read", "MODULES")
    assert read.returncode == 0, read.stdout + read.stderr
    assert READ_RULE in " ".join(_read_prompt(repo).split())
    notes = (shop / "plans/MODULES.read.md").read_text("utf-8")
    held = notes.split("1. Blocking:", 1)[1].split("2. Advisory:", 1)[0]
    assert "Gain 4, Work 1, Harm 1 (floor: module tables)" in held
    assert "below the bar" not in held
    assert "passed: no\n" in notes
    assert "Disposition: keep - below the bar (follow-up)" in notes
    assert "give finding 1" in repo.forge("next").stdout

    # Later findings keep their scores; fixing the current query releases normal close.
    env.reviews(blocked(_scored("P2", "Later: " + title,
                                "Gain 2, Work 3, Harm 1\nAnother part owns this query.")))
    env.commit(where, "app.py", "print('public service')\n", "Use the public service")
    released = env.close(item)
    assert released.returncode == 0, released.stdout + released.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    assert "Later: " + title + " (app.py:1): Gain 2, Work 3, Harm 1" in published

    # Sign-off uses the same path for both adoption histories. Use the untouched fixture repo.
    if not adopted:
        repo.path = original
        signoff = tmp_path / "sign-off"
        signoff.mkdir()
        fix, answers, queue = _client(repo, signoff, monkeypatch)
        _decision(fix, answers)
        queue.write_text(json.dumps([
            {**CLEAN, "say": SOL_HIGH},
            {**blocked(issue), "say": SOL_HIGH},
        ]), encoding="utf-8")
        accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert accepted.returncode == 1, accepted.stdout + accepted.stderr
        assert f"found a blocking issue: {title}" in accepted.stderr
        reviews = [json.loads(line) for line in
                   queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
        prompt = "\n\n".join(reviews[-1]["prompt_files"].values())
        assert SIGNOFF_RULE in " ".join(prompt.split())
