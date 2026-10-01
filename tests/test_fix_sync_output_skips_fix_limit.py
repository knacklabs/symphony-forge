"""The fix-size limit doesn't count files whose content is exactly what forge sync writes; a hand
edit to one of them, and every other file, still counts."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from test_githooks import NEXT_PROMOTE, hooked, push, start_fix

STORY = "an-upgrade-fix-can-t-commit-without-the"


def git(folder: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True,
                          encoding="utf-8")


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
    settings = folder / ".claude/settings.json"
    data = json.loads(settings.read_text(encoding="utf-8"))
    data["permissions"]["deny"].append("Read(secrets/**)")
    settings.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for n in range(5):
        (folder / f"src/f{n}.py").parent.mkdir(exist_ok=True)
        (folder / f"src/f{n}.py").write_text("x = 1\n", encoding="utf-8")
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
