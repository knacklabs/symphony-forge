"""Close preserves forge.autoreview output across retries and skips record-only diffs."""
import json
from pathlib import Path

import pytest

from test_board_dependency_timelines import _client, _land_fixture
from test_close import env, report, run  # noqa: F401

STORY = "FIX-RECORDS-ONLY-REVIEW"


@pytest.mark.parametrize(("history", "planning_record"), [
    ("new", False), ("new", True), ("adopted-v1.2.2", True)])
def test_1_close_records_a_clean_review_when_main_already_has_the_product_change(
        env, tmp_path, history, planning_record):
    # Audit: real close and git merge. Only GitHub and Autoreview are fake.
    # A model call on an empty product diff is the regression; CI must still gate close.
    _client(env.repo, env.gh, tmp_path, history)
    item, where = env.start_fix()
    env.start("land-product", "fix/land-product", ".factory/fixes/land-product.json",
              {"kind": "fix", "why": "Land the product change", "done_when": "The product changes"},
              {"app.py": "print('hello')\n"})
    env.repo.git("merge", "-q", "--ff-only", "fix/land-product")
    _land_fixture(env.repo)
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    if planning_record:
        env.commit(where, "plans/spotted/tidy-readme.json", json.dumps({"items": []}),
                   "Record a follow-up")
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
    expected = [".factory/fixes/tidy-readme.json"]
    if planning_record:
        expected.append("plans/spotted/tidy-readme.json")
    assert env.repo.git("diff", "--name-only", "origin/main...HEAD", cwd=where).splitlines() == expected


@pytest.mark.parametrize(("history", "change", "retry_report"), [
    ("new", "README.md", True), ("new", "app.py", True),
    ("new", "app.py", False), ("adopted-v1.2.2", "README.md", True)])
def test_2_close_shows_preserved_output_for_unreadable_findings(
        env, tmp_path, history, change, retry_report):
    # Audit: docs and code both need review. The external tool alone supplies malformed
    # findings; Forge must preserve them after its temporary review tree disappears,
    # including when a failed retry writes no replacement report.
    _client(env.repo, env.gh, tmp_path, history)
    item, _ = env.start_fix({change: "Product change\n"})
    raw = report({"title": "Unreadable finding", "priority": "P1"})
    malformed = {"exit": 0, "report": raw}
    retry = malformed if retry_report else {
        "exit": 3, "report": None, "say": "codex: the model is unavailable"}
    env.reviews(malformed, retry)

    closed = env.close(item)

    assert closed.returncode != 0
    assert len(env.review_calls()) == 2
    assert "it wrote findings Forge cannot read" in closed.stderr
    if not retry_report:
        assert "codex: the model is unavailable" in closed.stderr
    assert "forge doctor" not in closed.stderr
    line = next(line for line in closed.stderr.splitlines() if line.startswith("Raw Autoreview output: "))
    saved = Path(line.removeprefix("Raw Autoreview output: "))
    assert saved.is_file()
    assert json.loads(saved.read_text("utf-8")) == raw
    assert f"forge close {item}" in closed.stderr
