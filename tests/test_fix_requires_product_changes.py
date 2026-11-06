"""Interrupted builds must not merge Forge records as a completed fix.

Audit: real commands and git own the refusal and merge. A thread-only commit
bypasses the old state-file check. Existing empty-fix tests do not cover it.
Only GitHub and the review tool are fake; no production test seam is needed.
"""
import re
import sys

import pytest

from test_app_constitution import _fixture_git
from conftest import GH_STUB, _install
from test_close import GREEN
from test_board_dependency_timelines import _client, _land_fixture
from test_land import GH, ITEM, URL, _fix, env, land  # noqa: F401

STORY = "FIX-REQUIRE-PRODUCT-CHANGES"


@pytest.mark.parametrize("history,command,change", [
    ("new", "close", None),
    ("new", "land", None),
    ("adopted-v1.2.2", "land", None),
    ("new", "land", "app.py"),
    ("new", "land", "docs/repair.md"),
])
def test_1_records_only_fixes_refuse_but_code_and_docs_merge(land, tmp_path, history, command, change):
    env = land
    _client(env.repo, env.gh, tmp_path, history)
    _install(env.repo.bin, "gh", GH.format(
        python=sys.executable, remote=env.repo.git("remote", "get-url", "origin"), url=URL)
        + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    config = env.repo.path / "forge.toml"
    config.write_text('merge = "agent"\n' + re.sub(
        r'^merge = .*\n', '', config.read_text("utf-8"), flags=re.MULTILINE), encoding="utf-8")
    env.repo.git("add", "forge.toml")
    _fixture_git(env.repo, tmp_path, "commit", "-qm", "Enable agent merges")
    _land_fixture(env.repo)
    env.checks(GREEN)
    where = _fix(env, "working", changes={
        ".factory/threads/fix/tidy-readme.json": '{"thread": "interrupted"}\n',
        "plans/spotted/tidy-readme.json": '{"items": []}\n',
    })
    if change:
        env.commit(where, change, "# Repair\n")
    elif history == "new":
        (where / "unfinished-test.py").write_text("# Uncommitted work\n", encoding="utf-8")

    done = env.repo.forge(command, ITEM)

    if change:
        assert done.returncode == 0, done.stdout + done.stderr
        assert len(env.gh_calls("pr", "merge")) == 1
    else:
        assert done.returncode != 0, done.stdout + done.stderr
        assert "The build round did not finish." in done.stderr
        assert f"forge work {ITEM}" in done.stderr
        if history == "new":
            assert "unfinished-test.py" in done.stderr
        assert not env.gh_calls("pr", "merge")
        assert not env.review_calls()
