"""Known findings need a repair review, not omission from another review.

Audit: close owns the saved outcome and chat message. Existing close cases do
not carry an open sign-off finding into a different review. A clean unrelated
review must not close it; a repair review must still close its own findings.
Only external review and GitHub responses are faked; no production seam is added.
"""
import json
import shutil

import pytest

from conftest import ROOT
from test_close import CLEAN, blocked, env, finding  # noqa: F401

STORY = "known-issue-fixed-means-repaired"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_only_a_repair_review_closes_its_own_findings(env, adopted):
    version = env.repo.forge("--version").stdout.split()[-1]
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", env.repo.path, dirs_exist_ok=True)
        env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8"),
                   "Adopt an earlier release")
        env.repo.git("switch", "-q", "-c", "fix/refresh-adapters")
        settings = env.repo.path / "forge.toml"
        settings.write_text(settings.read_text("utf-8").replace('version = "v1.2.2"',
                                                               f'version = "{version}"'), "utf-8")
        synced = env.repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        # Fixture refresh stands in for an earlier upgrade, before this fix starts.
        env.repo.git("config", "core.hooksPath", (env.tmp / "no-hooks").as_posix())
        env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8"),
                   "Refresh the adapters")
        env.repo.git("switch", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/refresh-adapters")
        env.repo.git("push", "-q", "origin", "main")
    known = [{"title": "Production storage is missing", "file": "app.py", "line": 1,
              "outcome": "open", "reason": "", "round": 1, "area": "app.py"},
             {"title": "Earlier repair", "file": "app.py", "line": 1,
              "outcome": "fixed in round 2", "reason": "", "round": 1, "area": "app.py"}]
    item, where = env.start_fix(known=known)
    env.reviews(blocked(finding("P0", "Greeting crashes")))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert "Greeting crashes" in first.stdout, first.stdout + first.stderr
    path = where / ".factory/fixes/tidy-readme.json"
    state = json.loads(path.read_text("utf-8"))
    assert state["known"][0]["outcome"] == "open"
    env.commit(where, "app.py", "print('repaired greeting')\n", "Repair the greeting")
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    outcomes = {entry["title"]: entry["outcome"] for entry in json.loads(path.read_text("utf-8"))["known"]}
    assert outcomes["Production storage is missing"] == "open"
    assert outcomes["Greeting crashes"].startswith("fixed in round ")
    assert outcomes["Earlier repair"] == "fixed in round 2"


def test_2_claude_fix_does_not_link_a_stale_codex_chat(env):
    item, _ = env.start_fix(worker="claude")
    git = env.repo.git("rev-parse", "--git-common-dir")
    folder = (env.repo.path / git).resolve() / "forge/threads/fix"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{item}.json").write_text(json.dumps({"conversation": "old-codex-chat"}), "utf-8")
    env.gh.respond("pr", "view", "fix/tidy-readme", "--json", "number,url,headRefName",
                   exit=1, stderr="Codex chat link must not be requested")
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Could not link the pull request in its Codex chat" not in closed.stdout
    assert not any(call[:3] == ["pr", "view", "fix/tidy-readme"] and
                   "number,url,headRefName" in call for call in env.gh.calls())
