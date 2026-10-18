"""Close reviews product changes and preserves unreadable reviewer output."""
import json
from pathlib import Path

import pytest

from test_board_dependency_timelines import _client, _land_fixture
from test_close import env, report, run  # noqa: F401

STORY = "FIX-RECORDS-ONLY-REVIEW"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_close_records_a_clean_review_when_main_already_has_the_product_change(env, tmp_path, history):
    # Audit: real close and git merge. Only GitHub and Autoreview are fake.
    # A model call on an empty product diff is the regression; CI must still gate close.
    _client(env.repo, env.gh, tmp_path, history)
    item, where = env.start_fix()
    env.commit(env.repo.path, "app.py", "print('hello')\n", "Land the product change")
    _land_fixture(env.repo)
    env.reviews({"exit": 0, "report": {"findings": ["unreadable"]}})
    env.checks([run("tests", "failure"), run("forge-pr-check")])

    closed = env.close(item)

    assert "nothing to review: only Forge's records changed" in closed.stdout
    assert not env.review_calls()
    assert closed.returncode != 0
    assert "Checks failed on the pull request: tests." in closed.stderr
    # A second close must reuse the clean review rather than call a model.
    env.checks([run("tests"), run("forge-pr-check")])
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert not env.review_calls()
    assert "Ready" in closed.stdout
    assert env.repo.git("diff", "--name-only", "origin/main...HEAD", cwd=where).splitlines() == [
        ".factory/fixes/tidy-readme.json"]


@pytest.mark.parametrize(("history", "change"), [
    ("new", "README.md"), ("new", "app.py"), ("adopted-v1.2.2", "README.md")])
def test_2_close_shows_preserved_output_for_unreadable_findings(env, tmp_path, history, change):
    # Audit: docs and code both need review. The external tool alone supplies malformed
    # findings; Forge must preserve them after its temporary review tree disappears.
    _client(env.repo, env.gh, tmp_path, history)
    item, _ = env.start_fix({change: "Product change\n"})
    raw = report({"title": "Unreadable finding", "priority": "P1"})
    env.reviews({"exit": 0, "report": raw})

    closed = env.close(item)

    assert closed.returncode != 0
    assert len(env.review_calls()) == 2
    assert "it wrote findings Forge cannot read" in closed.stderr
    assert "forge doctor" not in closed.stderr
    line = next(line for line in closed.stderr.splitlines() if line.startswith("Raw Autoreview output: "))
    saved = Path(line.removeprefix("Raw Autoreview output: "))
    assert saved.is_file()
    assert json.loads(saved.read_text("utf-8")) == raw
    assert f"forge close {item}" in closed.stderr
