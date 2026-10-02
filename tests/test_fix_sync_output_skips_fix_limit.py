"""The fix-size limit doesn't count test files or files whose content is exactly what forge sync
writes; a hand edit to a synced file, and every other code file, still counts."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from test_close import env  # noqa: F401 (the shared fixture)
from test_githooks import NEXT_PROMOTE, commit, hooked, push, start_fix

STORY = "an-upgrade-fix-can-t-commit-without-the"


def git(folder: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True,
                          encoding="utf-8")


def hand_edit(folder: Path) -> None:
    """A deny rule added by hand to the synced settings, plus five ordinary code files."""
    settings = folder / ".claude/settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["permissions"].setdefault("deny", []).append("Read(secrets/**)")
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for n in range(5):
        (folder / f"src/f{n}.py").parent.mkdir(exist_ok=True)
        (folder / f"src/f{n}.py").write_text("x = 1\n", encoding="utf-8")


def synced_fix(repo) -> tuple[str, Path]:
    """A fix that runs forge sync over a repo whose own settings and AGENTS.md predate it."""
    fix, folder = start_fix(repo, "Upgrade Forge")
    synced = repo.forge("sync", cwd=folder)
    assert synced.returncode == 0, synced.stderr
    return fix, folder


def test_1_upgrade_fix_of_only_sync_output_commits_and_pushes_without_an_allowance(repo):
    # The repo's own content in files sync merges: sync's output over it is what doesn't count.
    repo.write(".claude/settings.json", json.dumps({"permissions": {"deny": ["Read(.env)"]}}))
    repo.write("AGENTS.md", "# House rules\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "The repo's own settings")
    hooked(repo)

    fix, folder = synced_fix(repo)
    git(folder, "add", "-A")
    staged = git(folder, "diff", "--cached", "--name-only").stdout.split()
    assert len([path for path in staged if not path.endswith(".md")]) > 5
    committed = git(folder, "commit", "-q", "-m", "Upgrade Forge")
    assert committed.returncode == 0, committed.stderr
    pushed = push(folder, f"fix/{fix}")
    assert pushed.returncode == 0, pushed.stderr

    # The same output plus a hand edit beyond it: the edited file counts, the rest still don't.
    fix, folder = synced_fix(repo)
    hand_edit(folder)
    git(folder, "add", "-A")
    over = git(folder, "commit", "-q", "-m", "Upgrade Forge and more")
    assert over.returncode != 0
    assert over.stderr == (
        f"Fix {fix} changes 6 code files, over the limit of 5, so it has to become a story, unless "
        "the human allows it with forge fix allow-large.\n" + NEXT_PROMOTE.format(fix=fix))

    # Close pushes the fix; pushing the same commit made with --no-verify is refused alike.
    assert git(folder, "commit", "-q", "--no-verify", "-m", "Upgrade Forge and more").returncode == 0
    refused = push(folder, f"fix/{fix}")
    assert refused.returncode != 0
    assert f"Fix {fix} changes 6 code files, over the limit of 5" in refused.stderr


def test_2_upgrade_fix_of_only_sync_output_closes_and_a_hand_edit_is_counted_by_the_check(env):
    def pr_check(where: Path, branch: str):
        return env.repo.forge("hook", "pr-check", "--base", env.repo.git("rev-parse", "main"),
                              "--head", env.repo.git("rev-parse", "HEAD", cwd=where),
                              "--branch", branch)

    item, where = env.start_fix()
    assert env.repo.forge("sync", cwd=where).returncode == 0
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("commit", "-q", "-m", "Sync Forge's files", cwd=where)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    checked = pr_check(where, "fix/tidy-readme")
    assert (checked.returncode, checked.stdout) == (
        0, "forge-pr-check passed for fix/tidy-readme.\n"), checked.stderr

    # A machine without Forge's hooks commits the same output plus a hand edit; the check counts it.
    item, where = env.start("hand-edit", "fix/hand-edit", ".factory/fixes/hand-edit.json",
                            {"kind": "fix", "why": "Tighten settings", "done_when": "Tighter"}, {})
    assert env.repo.forge("sync", cwd=where).returncode == 0
    hand_edit(where)
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("commit", "-q", "--no-verify", "-m", "Sync and more", cwd=where)
    refused = pr_check(where, "fix/hand-edit")
    assert refused.returncode != 0
    assert refused.stderr.startswith(
        "The fix on fix/hand-edit changes 6 code files, over the limit of 5, and has no "
        "allow-large reason.\n"), refused.stderr


def test_3_fix_with_four_source_and_three_test_files_commits_without_an_allowance(repo):
    hooked(repo)
    _, folder = start_fix(repo, "Fix the login typo")
    committed = commit(folder, *(f"src/f{n}.py" for n in range(4)), "tests/test_login.py",
                       "src/login.test.ts", "pkg/users_test.py")
    assert committed.returncode == 0, committed.stderr
