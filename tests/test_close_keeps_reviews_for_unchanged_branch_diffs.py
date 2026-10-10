"""Close keeps clean review decisions across an unchanged branch diff.

Open findings also require unchanged reviewed files before numbered dismissals can be used.

The real close command owns review reuse and dismissals; only Autoreview and GitHub are faked.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, ROOT
from test_close import CLEAN, GREEN, blocked, body, env, finding  # noqa: F401
from test_setup import _fresh_client

STORY = "after-forge-close-merges-the-latest-defa"


def client(env, previous):
    if previous:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        env.repo.path, dirs_exist_ok=True)
        env.repo.git("switch", "-q", "-c", "fix/upgrade-client")
        env.repo.git("add", "-A")
        env.repo.git("commit", "-q", "-m", "Adopted on the previous release")
        version = env.repo.forge("--version").stdout.split()[-1]
        config = (env.repo.path / "forge.toml").read_text()
        env.repo.write("forge.toml", config.replace('"v1.2.2"', f'"{version}"'))
        env.repo.write(".factory/fixes/upgrade-client.json",
                       '{"kind":"fix","branch":"fix/upgrade-client","status":"working"}')
        synced = env.repo.forge("sync")
        assert synced.returncode == 0, synced.stderr
        env.repo.git("add", "-A")
        env.repo.git("commit", "-q", "-m", "Upgrade the adopted client")
        env.repo.git("switch", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/upgrade-client")
        # Seed the fixture remote without asking an installed client hook to push main.
        remote = env.repo.git("remote", "get-url", "origin")
        env.repo.git("fetch", "-q", str(env.repo.path), "main:main", cwd=Path(remote))
    else:
        folder, initialized = _fresh_client(env.repo, env.gh, env.tmp)
        assert initialized.returncode == 0, initialized.stderr
        env.repo.path = folder
    # A separate clone represents other work landing on main; its git hooks are local, as usual.
    writer = env.tmp / "main-writer"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(writer))
    env.repo.path = writer
    # Init's generic GitHub API response must not mask the check responses.
    env.checks(GREEN)


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
@pytest.mark.parametrize("dismiss_before_merge", [False, True], ids=["same-command", "saved"])
def test_1_close_keeps_review_and_dismissals_when_main_moves(env, previous, dismiss_before_merge):
    client(env, previous)
    env.commit(env.repo.path, "NEWS.md", "Old news\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.reviews(blocked(finding("P1", "Greeting is missing", "NEWS.md")))
    first = env.close(item)
    assert first.returncode == 1, first.stderr
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)
    dismissal = ("--dismiss", "1", "--because", "app.py:1 the greeting is here")
    if dismiss_before_merge:
        dismissed = env.close(item, *dismissal)
        assert dismissed.returncode == 0, dismissed.stderr
    before = env.repo.git("diff", "--raw", "--no-abbrev", "-z", "origin/main...HEAD",
                          "--", "app.py", cwd=where)
    # Changing display preferences cannot change what the branch itself changed.
    env.repo.git("config", "diff.noprefix", "true", cwd=where)
    moved = env.commit(env.repo.path, "NEWS.md", "New news\n")
    env.repo.git("push", "-q", "origin", "main")
    closed = env.close(item, *(() if dismiss_before_merge else dismissal))
    if not dismiss_before_merge:
        # The old contract reused open findings despite changes to their cited file. Close now
        # reviews that file first; dismissals already saved on a clean review still survive.
        assert closed.returncode == 1, closed.stdout + closed.stderr
        assert closed.stderr.splitlines() == [
            "The branch changed since the review those finding numbers came from.",
            f"Next: forge close {item}",
        ]
        assert len(env.review_calls()) == 1
        refreshed = env.close(item)
        assert refreshed.returncode == 1, refreshed.stdout + refreshed.stderr
        assert "The review left serious findings open:" in refreshed.stderr
        closed = env.close(item, *dismissal)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    env.repo.git("merge-base", "--is-ancestor", moved, "HEAD", cwd=where)
    assert env.repo.git("diff", "--raw", "--no-abbrev", "-z", "origin/main...HEAD",
                        "--", "app.py", cwd=where) == before
    reviews = 1 if dismiss_before_merge else 2
    assert len(env.review_calls()) == reviews
    assert "dismissed because app.py:1 the greeting is here" in body(env.gh_calls("pr", "edit")[-1])
    # The persisted decision must also survive another close after the merge.
    again = env.close(item)
    assert again.returncode == 0, again.stderr
    assert len(env.review_calls()) == reviews


def test_2_close_reviews_again_when_main_changes_the_branch_diff(env):
    base = "old\n" + "pass\n" * 20 + "tail\n"
    env.commit(env.repo.path, "app.py", base)
    env.repo.git("push", "-q", "origin", "main")
    changed = base.replace("old", "new").replace("tail", "branch")
    item, where = env.start_fix(changes={"app.py": changed})
    env.reviews(CLEAN)
    assert env.close(item).returncode == 0
    before = env.repo.git("diff", "origin/main...HEAD", "--", "app.py", cwd=where)
    # Main absorbs one of the branch's changes. The final file is identical, but the reviewed
    # diff is smaller: the old contents-only contract reused a review that no longer covered it.
    env.commit(env.repo.path, "app.py", base.replace("old", "new"))
    env.repo.git("push", "-q", "origin", "main")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert (where / "app.py").read_text() == changed
    assert env.repo.git("diff", "origin/main...HEAD", "--", "app.py", cwd=where) != before
    assert len(env.review_calls()) == 2


@pytest.mark.parametrize("review_before_fix", [False, True], ids=["new-review", "existing-review"])
def test_3_default_branch_checker_accepts_new_and_reused_reviews(env, review_before_fix):
    # CI installs Forge from the PR base. Pin its actual checker and fingerprint owner, so the
    # current close command cannot silently change the required check's record contract.
    source = env.tmp / "base-src"
    shutil.copytree(ROOT / "src/forge", source / "forge", ignore=shutil.ignore_patterns("__pycache__"))
    fixture = ROOT / "tests/fixtures/pr-check-before-branch-diff"
    for name in ("close.py", "checks.py", "review.py", "prcheck.py", "templates/review.md"):
        shutil.copy(fixture / name, source / "forge" / name)
    command = env.tmp / "base-forge"
    command.write_text(FORGE_SHIM.format(python=sys.executable, src=str(source)), encoding="utf-8")

    def base_forge(*args):
        return subprocess.run([sys.executable, str(command), *args], cwd=env.repo.path,
                              input="", capture_output=True, text=True, timeout=60)

    close = (lambda item, *args: base_forge("close", item, *args)) if review_before_fix else env.close
    env.commit(env.repo.path, "NEWS.md", "Old news\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.reviews(blocked(finding("P1", "Greeting is missing", "NEWS.md")))
    assert close(item).returncode == 1
    dismissed = close(item, "--dismiss", "1", "--because", "app.py:1 the greeting is here")
    assert dismissed.returncode == 0, dismissed.stderr
    for after_merge in (False, True):
        if after_merge:
            env.commit(env.repo.path, "NEWS.md", "New news\n")
            env.repo.git("push", "-q", "origin", "main")
            closed = env.close(item)
            assert closed.returncode == 0, closed.stderr
            assert len(env.review_calls()) == 1
        checked = base_forge(
             "hook", "pr-check", "--base",
             env.repo.git("rev-parse", "HEAD"), "--head",
             env.repo.git("rev-parse", "HEAD", cwd=where), "--branch", "fix/tidy-readme")
        assert checked.returncode == 0, checked.stdout + checked.stderr
        assert "forge-pr-check passed for fix/tidy-readme." in checked.stdout


def test_4_diff_order_preferences_do_not_invalidate_same_command_dismissals(env):
    item, where = env.start_fix(changes={"app.py": "print('hello')\n", "other.py": "pass\n"})
    env.reviews(blocked(finding("P1", "Greeting is missing")))
    assert env.close(item).returncode == 1
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)
    order = env.tmp / "diff-order"
    order.write_text("other.py\napp.py\n", encoding="utf-8")
    env.repo.git("config", "diff.orderFile", str(order), cwd=where)
    moved = env.commit(env.repo.path, "NEWS.md", "New news\n")
    env.repo.git("push", "-q", "origin", "main")
    closed = env.close(item, "--dismiss", "1", "--because", "app.py:1 the greeting is here")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    env.repo.git("merge-base", "--is-ancestor", moved, "HEAD", cwd=where)
    assert len(env.review_calls()) == 1
    assert "dismissed because app.py:1 the greeting is here" in body(env.gh_calls("pr", "edit")[-1])
