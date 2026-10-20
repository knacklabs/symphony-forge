"""A split transfers open review findings to one linked fix for new and upgraded clients."""
STORY = "split-creates-follow-up"

import json
import shutil
from pathlib import Path

import pytest

from test_close import GREEN, STORY_DOC, blocked, env, finding  # noqa: F401
from test_hotspot_stop import saved, seed
from test_setup import _fresh_client


@pytest.mark.parametrize("previous,kind", [(False, "fix"), (False, "task"),
                                          (True, "fix"), (True, "task")],
                         ids=["init-fix", "init-part", "upgrade-fix", "upgrade-part"])
def test_1_split_moves_every_open_finding_to_one_linked_fix(env, tmp_path, previous, kind):
    if previous:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        env.repo.path, dirs_exist_ok=True)
        env.repo.git("add", "-A")
        env.repo.git("commit", "-q", "-m", "Adopt the earlier release")
        env.repo.git("checkout", "-q", "-b", "fix/upgrade-client")
        version = env.repo.forge("--version").stdout.split()[-1]
        config = (env.repo.path / "forge.toml").read_text("utf-8")
        env.commit(env.repo.path, "forge.toml", config.replace('version = "v1.2.2"',
                                                             f'version = "{version}"'))
        synced = env.repo.forge("sync")
        assert synced.returncode == 0, synced.stderr
        env.repo.git("config", "core.hooksPath", (tmp_path / "setup-hooks").as_posix())
        env.repo.git("add", "-A")
        env.repo.git("commit", "-q", "-m", "Upgrade Forge")
        env.repo.git("checkout", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/upgrade-client")
        env.repo.git("push", "-q", "origin", "main")
    else:
        client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        env.repo.path = client
    # These helpers prepare and merge the client's mainline history.
    env.repo.git("config", "core.hooksPath", (tmp_path / "setup-hooks").as_posix())
    env.checks(GREEN)
    seed(env, "src/a.py")
    seed(env, "src/safe.py")
    item, where = env.start_approved_task(STORY_DOC) if kind == "task" else env.start_fix()
    safe = finding("P1", "Proven safe", "src/safe.py")
    # A fix's first P0 asks the owner; a part retains its three-round stop and prior dismissal.
    last_round = 3 if kind == "task" else 1
    for number in range(1, last_round + 1):
        env.commit(where, "src/a.py", f"pass  # round {number}\n")
        env.commit(where, "app.py", f"print({number})\n")
        # P1s no longer reach this stop after round two; retain open P0s for the split.
        defects = [finding("P0", f"Round {number} defect", "src/a.py")]
        if number == last_round:
            defects.append(finding("P0", "Second split defect", "app.py"))
        env.reviews(blocked(*defects, *([safe] if kind == "task" else [])))
        held = env.close(item)
        assert held.returncode == 1, held.stdout + held.stderr
        if number == 1 and kind == "task":
            dismissed = env.close(item, "--dismiss", "2", "--because", "src/safe.py:1 This case is safe")
            assert dismissed.returncode == 1, dismissed.stdout + dismissed.stderr
    assert "Ask the human" in held.stderr, held.stdout + held.stderr
    branches = set(env.repo.git("branch", "--format=%(refname:short)").splitlines())
    split = env.close(item, "--resolve", "split", "--reason", "Move both defects to one fix")
    assert split.returncode == 0, split.stdout + split.stderr
    created = set(env.repo.git("branch", "--format=%(refname:short)").splitlines()) - branches
    assert len(created) == 1, split.stdout + split.stderr
    branch = created.pop()
    assert branch.startswith("fix/")
    name = branch.removeprefix("fix/")
    follow_up = json.loads(env.repo.git("show", f"{branch}:.factory/fixes/{name}.json"))
    for field in ("why", "done_when"):
        for title, location in ((f"Round {last_round} defect", "src/a.py:1"),
                                ("Second split defect", "app.py:1")):
            assert title in follow_up[field] and location in follow_up[field]
        assert "Proven safe" not in follow_up[field]
    assert follow_up["stacked_on"] == item
    assert saved(where, item)["stop"]["fixes"] == [name]
    assert name in split.stdout
    # The original item resumes without a new review or the transferred findings.
    before = len(env.review_calls())
    resumed = env.close(item)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert "Ready:" in resumed.stdout
    assert len(env.review_calls()) == before
    # Later edits require review. A settled split finding cannot block it again.
    env.commit(where, "other.py", "print('later work')\n")
    resumed = env.close(item)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert len(env.review_calls()) == before + 1
    assert len(set(env.repo.git("branch", "--format=%(refname:short)").splitlines()) - branches) == 1
