"""A fix's pull request title is the whole first sentence of its why."""
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_close import CLEAN, env  # noqa: F401 - command-level fixture

STORY = "pr-title-whole-sentence"

LONG = ("Readers " + "cannot tell which step comes next " * 3).strip()


@pytest.mark.parametrize("client", ["new", "adopted on an earlier release"])
@pytest.mark.parametrize("why, title", [
    ("On Windows, forge merge run from inside a worktree fails. It removes its own folder.",
     "On Windows, forge merge run from inside a worktree fails"),
    ("Clients and this repo need v1.2.10 to get the fixes. Release it now.",
     "Clients and this repo need v1.2.10 to get the fixes"),
    (LONG + ". More detail.", LONG[:LONG.rindex(" ", 0, 71)]),
    ('The command prints "Failed." Retry it.', 'The command prints "Failed"'),
    ("Merges fail on the old release. v1.2.10 fixes it.", "Merges fail on the old release"),
])
def test_1_fix_title_is_the_whole_first_sentence(env, client, why, title):
    if client == "new":
        item, _ = env.start_fix(why=why)
    else:
        # The fix starts on the earlier release, then the repo upgrades and closes it.
        old = env.tmp / "old-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(env.repo.bin, "old-forge", FORGE_SHIM.format(
            python=sys.executable, src=(old / "src").as_posix()))
        current = (env.repo.path / "forge.toml").read_text("utf-8")
        settings = (ROOT / "tests/fixtures/adopted-v1.2.2/client/forge.toml").read_text("utf-8")
        env.commit(env.repo.path, "forge.toml", settings, "Use earlier Forge")
        env.repo.git("push", "-q", "origin", "main")
        started = subprocess.run([sys.executable, str(env.repo.bin / "old-forge"), "fix", "start",
                                  why, "--done", "The readme is tidy"],
                                 cwd=env.repo.path, capture_output=True, text=True, timeout=60)
        assert started.returncode == 0, started.stdout + started.stderr
        item = started.stdout.strip().rsplit("Next: forge work ", 1)[1].split()[0]
        where = env.repo.path.parent / f"{env.repo.path.name}-fix-{item}"
        env.commit(where, "forge.toml", current, "Upgrade Forge")
        synced = env.repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        env.repo.git("add", "-A", cwd=where)
        env.repo.git("commit", "-qm", "Sync Forge", cwd=where)
        env.commit(where, "app.py", "print('hello')\n", "Work")
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    create = env.gh_calls("pr", "create")[-1]
    assert create[create.index("--title") + 1] == title
