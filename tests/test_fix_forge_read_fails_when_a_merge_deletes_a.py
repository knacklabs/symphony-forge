"""Command-level regression for forge read racing a merge that deletes a branch."""
import hashlib
import json
import shutil
import sys

from conftest import _install

from test_story import DOC, setup, worktree

STORY = "FIX-FORGE-READ-FAILS-WHEN-A-MERGE-DELETES-A"

# git that deletes task/BASKET-AAA the moment forge lists files inside it, then runs the real git.
GIT_WRAPPER = """#!{python}
import subprocess, sys
args = sys.argv[1:]
if args[:1] == ["ls-tree"] and "task/BASKET-AAA" in args:
    subprocess.run([{git!r}, "branch", "-D", "task/BASKET-AAA"], capture_output=True)
sys.exit(subprocess.run([{git!r}, *args]).returncode)
"""


def test_1_read_skips_a_branch_deleted_between_listing_and_lookup(repo):
    setup(repo)
    assert repo.forge("fix", "start", "Recover the saved basket", "--done", "Saved baskets return").returncode == 0
    fix = worktree(repo, "fix/recover-the-saved-basket")
    body = "# Basket spec\n\n## Why\n\nA saved basket gets lost.\n\n## Roadmap\n\n- BASKET: Recover baskets\n"
    digest = hashlib.sha256(body.encode()).hexdigest()
    path = fix / "docs/specs/baskets.md"
    path.parent.mkdir(parents=True)
    path.write_text(f'---\nstatus: confirmed\nconfirmed_hash: "{digest}"\n---\n{body}', encoding="utf-8")
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-q", "-m", "Confirm the basket spec", cwd=fix)
    made = repo.forge("story", "new", "BASKET", "Recover baskets", "--from-fix", "recover-the-saved-basket")
    assert made.returncode == 0, made.stderr
    (worktree(repo, "story/BASKET") / "plans/BASKET.md").write_text(DOC, encoding="utf-8")
    # A branch listed first vanishes the moment forge looks inside it, as when a merge deletes it.
    repo.git("branch", "task/BASKET-AAA")
    _install(repo.bin, "git", GIT_WRAPPER.format(python=sys.executable, git=shutil.which("git")))
    read = repo.forge("read", "BASKET")
    assert read.returncode == 0, read.stderr
    assert "task/BASKET-AAA" not in repo.git("branch", "--list", "task/BASKET-AAA")
    prompt = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]
    assert "A saved basket gets lost." in prompt
