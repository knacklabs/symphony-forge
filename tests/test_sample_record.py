"""Accepted sign-off records need no second review or test run.

Audit: real close, merge, next and Git hooks own this contract. Omitting the
sign-off decision from records-only changes starts an unwanted reviewer.
Existing bookkeeping tests do not cover this decision or its merge. Only
GitHub and Autoreview are fake; no production seam is needed.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_app_constitution import _fixture_git
from test_board_dependency_timelines import _client
from test_close import CLEAN, GREEN, env  # noqa: F401
from test_merge_command import _merge_at_github

STORY = "FORGE-SAMPLE-1"


@pytest.mark.parametrize("history,app_change", [
    ("new", False), ("new", True), ("adopted-v1.2.2", False),
], ids=["new client", "new client with app change", "earlier adopted"])
def test_3_the_signoff_record_merges_alone_without_review_or_tests(
        env, tmp_path, history, app_change):
    repo = env.repo
    _client(repo, env.gh, tmp_path, history)
    # No sample-data switch: the record-only rule applies to every prototype.
    marker = tmp_path / "test-ran"
    code = f"from pathlib import Path; Path({marker.as_posix()!r}).write_text('ran')"
    command = f"{json.dumps(Path(sys.executable).as_posix())} -c {json.dumps(code)}"
    config = repo.path / "forge.toml"
    version = repo.forge("--version").stdout.split()[-1]
    config.write_text(f'version = "{version}"\nrepo = "client"\nstage = "prototype"\n'
                      f'test = {json.dumps(command)}\ntest_place = "local"\n', encoding="utf-8")
    repo.git("add", "forge.toml")
    _fixture_git(repo, tmp_path, "commit", "-qm", "Configure prototype proof")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    changes = {
        "docs/decisions/0001-client-signoff.md":
            '---\nstatus: accepted\nconfirmed_by: "Sam Lee"\n---\n\n# Client sign-off\n',
        ".factory/client-signoff.json": json.dumps({"review": {"findings": []}}),
    }
    if app_change:
        changes["app.py"] = "print('changed demo')\n"
    item, where = env.start_fix(changes)
    env.reviews(CLEAN)
    env.open_pr("")
    env.checks(GREEN)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    if app_change:
        assert "nothing to review" not in closed.stdout
        assert env.review_calls()
        assert marker.exists()
        return
    assert "nothing to review: only Forge's records changed" in closed.stdout
    assert not env.review_calls()
    assert not marker.exists()

    pushed = subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=where,
                            capture_output=True, text=True, encoding="utf-8")
    assert pushed.returncode != 0
    assert "main changes only through a merged pull request" in pushed.stderr
    committed = subprocess.run(["git", "commit", "--allow-empty", "-m", "Direct commit"],
                               cwd=repo.path, capture_output=True, text=True, encoding="utf-8")
    assert committed.returncode != 0
    assert "Forge changes nothing on main" in committed.stderr

    # The GitHub edge squashes the published branch into the bare remote.
    origin = Path(repo.git("remote", "get-url", "origin"))
    merge_area = tmp_path / "record-merge"
    merge_area.mkdir()
    shutil.move(str(origin), merge_area / "remote.git")
    repo.git("remote", "set-url", "origin", str(merge_area / "remote.git"))
    env.tmp = merge_area
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main",
        "headRefName": "fix/tidy-readme", "headRefOid": repo.git("rev-parse", "HEAD", cwd=where),
        "title": "Record client sign-off", "isDraft": False, "body": ""}))
    _merge_at_github(env)
    merged = repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert repo.git("show", "origin/main:docs/decisions/0001-client-signoff.md") == changes[
        "docs/decisions/0001-client-signoff.md"].strip()
    assert not marker.exists()
    repo.git("pull", "--ff-only", "origin", "main")
    following = repo.forge("next")
    assert following.returncode == 0, following.stderr
    assert "prototype" not in following.stdout.splitlines()[0].lower()
