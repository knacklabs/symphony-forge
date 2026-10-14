"""A Not done finding blocks only on a Done-when line the change misses as written.

New and earlier-release clients get the rule in the guide sync writes and in close's review prompt.
"""
import shutil
from pathlib import Path

import pytest

from test_close import env  # noqa: F401

STORY = "review-blocks-on-done-when"
RULE = ("A `Not done` finding blocks only when it names a Done-when item the change misses as "
        "written. A case the Done-when does not name, such as another language, platform, shell, "
        "tool or folder layout, is a P2 `Follow-up: <the case>` finding")
STILL_BLOCKS = "a functional, security or data-loss defect on the changed code still blocks"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-on-v1.2.2"])
def test_1_unnamed_cases_are_follow_ups_and_defects_still_block(env, adopted):
    repo = env.repo
    if adopted:
        version = repo.forge("--version").stdout.split()[-1]
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        config = (repo.path / "forge.toml").read_text("utf-8")
        env.commit(repo.path, "forge.toml", config.replace('version = "v1.2.2"',
                   f'version = "{version}"').replace('workers = "codex"', 'workers = "claude"'),
                   "Adopt on the earlier release")
        repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".codex", ".claude"):
        guide = " ".join((where / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert RULE in guide and STILL_BLOCKS in guide, host
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-q", "-m", "Sync the guide", cwd=where)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    review = " ".join(env.prompt().split())
    assert RULE in review and STILL_BLOCKS in review
