"""forge-pr-check keeps a clean light review when the check's event base is older."""
from __future__ import annotations

from test_close import env  # noqa: F401 (env is the shared fixture)

STORY = "FIX-DOCS-ONLY-LIGHT-REVIEW-OLDER-BASE"


def test_1_docs_only_light_review_passes_with_older_event_base(env):
    item, where = env.start_fix({"README.md": "Hello\n"})
    old_base = env.repo.git("rev-parse", "HEAD")
    assert env.close(item).returncode == 0
    # The default branch gets code, and the fix branch merges it after the review.
    env.commit(env.repo.path, "app.py", "value = 1\n", "Unrelated code")
    env.repo.git("push", "-q", "origin", "main")
    env.repo.git("fetch", "-q", "origin", cwd=where)
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    done = env.repo.forge("hook", "pr-check", "--base", old_base, "--branch", "fix/tidy-readme",
                          "--head", env.repo.git("rev-parse", "HEAD", cwd=where))
    assert done.returncode == 0, done.stderr


def test_2_default_branch_functional_check_does_not_stale_the_review(env):
    item, where = env.start_fix({"README.md": "Hello\n"})
    old_base = env.repo.git("rev-parse", "HEAD")
    assert env.close(item).returncode == 0
    env.commit(env.repo.path, "app.py", "value = 1\n",
               "Other work\n\nFunctional check: opened the app and saw it work.")
    env.repo.git("push", "-q", "origin", "main")
    env.repo.git("fetch", "-q", "origin", cwd=where)
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    done = env.repo.forge("hook", "pr-check", "--base", old_base, "--branch", "fix/tidy-readme",
                          "--head", env.repo.git("rev-parse", "HEAD", cwd=where))
    assert done.returncode == 0, done.stderr


def test_3_signoff_on_default_branch_stales_a_docs_only_prototype_review(env):
    env.repo.write("forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
                   + 'repo = "client"\nstage = "prototype"\n')
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Set client policy")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({"README.md": "Hello\n"}, allow_large="Prototype before sign-off")
    assert env.close(item).returncode == 0
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    check = ["hook", "pr-check", "--branch", "fix/tidy-readme", "--head", head]
    assert env.repo.forge(*check, "--base", env.repo.git("rev-parse", "HEAD")).returncode == 0
    env.commit(env.repo.path, "docs/decisions/0001-client-signoff.md",
               '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n', "Accept client sign-off")
    env.repo.git("push", "-q", "origin", "main")
    stale = env.repo.forge(*check, "--base", env.repo.git("rev-parse", "HEAD"))
    assert stale.returncode == 1 and "out of date" in stale.stderr, stale.stdout + stale.stderr
