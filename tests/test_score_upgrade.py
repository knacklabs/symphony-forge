"""A repo that upgrades mid-change keeps the unscored reads and reviews its earlier release saved
holding work back until their next round scores them; a new repo scores from its first round.

Runs the real forge command: the earlier release's (v1.2.10, the last without scores) on the
adopted fixture to save a blocked read and a blocked review, then this release's after the
upgrade. Only Autoreview, the cold reader and GitHub are stubbed.
"""
from __future__ import annotations

import shutil
import subprocess
import tarfile

import pytest

from conftest import ROOT
from test_close import CLEAN, GREEN, blocked, env  # noqa: F401 (env is a fixture)
from test_score_bar import _client_on_this_release, _says
from test_score_notes import _scored
from test_story import DOC, new_story

STORY = "FORGE-SCORE-1"
EARLIER = "v1.2.10"


def _on_release(repo, tmp_path, release: str | None) -> None:
    """Point the forge command at an earlier release's source, or back at this checkout's."""
    shim, here, old = repo.bin / "forge", repr(str(ROOT / "src")), tmp_path / EARLIER
    if release and not old.exists():
        archive = subprocess.run(["git", "-C", str(ROOT), "archive", release, "src", ".codex/skills",
                                  ".claude/skills"],
                                 capture_output=True, check=True).stdout
        old.mkdir()
        (tmp_path / "src.tar").write_bytes(archive)
        with tarfile.open(tmp_path / "src.tar") as tar:
            tar.extractall(old, filter="data")
    there = repr(str(old / "src"))
    text = shim.read_text("utf-8")
    shim.write_text(text.replace(here, there) if release else text.replace(there, here), "utf-8")


def _move_to(repo, tmp_path, config: str, version: str, branch: str) -> None:
    no_hooks = f"core.hooksPath={tmp_path / 'no-hooks'}"
    repo.git("switch", "-qc", branch)
    repo.write("forge.toml", config.replace(config.split('"')[1], version, 1))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.write("plans/roadmap.json", '{"items": [{"key": "SHOP"}]}')
    repo.git("add", "-A")
    repo.git("-c", no_hooks, "commit", "-qm", f"Move to {version}")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", branch)
    repo.git("-c", no_hooks, "push", "-q", "origin", "main")


@pytest.mark.parametrize("case", ["init", "earlier-adoption-upgrade-sync"])
def test_6_saved_unscored_notes_hold_until_scored_and_the_readme_explains_the_bar(env, tmp_path, case):
    repo = env.repo
    if case != "init":
        # The earlier release, on a repo adopted before it, saves a blocked read and review.
        config = (repo.path / "forge.toml").read_text("utf-8")
        current = config.split('"')[1]
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt an earlier release")
        _on_release(repo, tmp_path, EARLIER)
        assert repo.forge("--version").stdout.split()[-1].endswith(EARLIER[1:])
        _move_to(repo, tmp_path, config, EARLIER, "fix/earlier")
        env.checks(GREEN)
        _says(repo, "1. Blocking: Saving requires an account but sign-in is out of scope.\n")
        shop = new_story(repo, "SHOP")
        (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
        assert repo.forge("read", "SHOP").returncode == 0
        item, where = env.start_fix()
        env.reviews(blocked({"title": "Saved serious finding", "body": "Evidence", "priority": "P1",
                             "code_location": {"file_path": "app.py", "line": 1}}))
        saved = env.close(item)
        assert saved.returncode == 1, saved.stdout + saved.stderr

        # Upgrade to this release in the middle of both: the saved results still hold work.
        _on_release(repo, tmp_path, None)
        _move_to(repo, tmp_path, config + 'models.grill.claude = { model = "opus", effort = "high" }\n',
                 current, "fix/upgrade")
        assert "finding 1" in repo.forge("next").stdout
        # Explicitly adopt the upgrade on this active branch: close now leaves a clean
        # unrelated main move alone instead of bringing in its release pin and generated files.
        repo.git("fetch", "-q", "origin", cwd=where)
        repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
        before = len(env.review_calls())
        env.reviews(CLEAN)  # a new review would pass: only the saved one can hold close
        held = env.close(item)
        assert held.returncode == 1, held.stdout + held.stderr
        assert "Saved serious finding" in held.stderr
        assert len(env.review_calls()) == before
        notes = shop / "plans/SHOP.read.md"
        notes.write_text(notes.read_text("utf-8").rstrip() + "\n   Disposition: keep because sign-in is "
                         "out of scope\n", encoding="utf-8")
        env.commit(where, "app.py", "print('saved the note')\n")
    else:
        _client_on_this_release(env, tmp_path, case)
        shop = new_story(repo, "SHOP")
        (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
        notes = shop / "plans/SHOP.read.md"
        item, _ = env.start_fix()

    # The next round scores: a note labelled blocking but below the bar passes the read.
    _says(repo, "2. Blocking: The title could be shorter.\n   Raise: Plan gap\n   Gain 2, Work 1, Harm 1\n")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    assert "passed: yes\n" in notes.read_text("utf-8")
    assert "forge read SHOP" not in repo.forge("next").stdout
    # And a P1 below the bar no longer holds the change.
    env.reviews(blocked(_scored("P1", "The button label is long", "Gain 2, Work 1, Harm 1\nRaise: Functional")))
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout

    readme = (ROOT / "README.md").read_text("utf-8").split("## How Forge weighs a note", 1)[1]
    readme = readme.split("\n## ", 1)[0]
    for text in ("**Gain**", "**Work**", "**Harm**", "| Harm 4 or 5, or Gain 5 |",
                 "| Gain 4, or Gain 3 with Harm 3, and Work 1 or 2 |",
                 "| Gain 4, or Gain 3 with Harm 3, and Work 3 or more |",
                 "| Other Gain 3 notes |",
                 "| Gain 1 or 2 |", "breaks Go repos", "Harm 4 (floor: migration)",
                 "This sentence in the plan is not clear"):
        assert text in readme
