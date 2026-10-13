"""Every review finding and cold-read note carries Gain, Work and Harm, with the Harm floor.

Runs the real close, read and sign-off commands on a repo made by forge init and on the
earlier-release adopted fixture moved to this release. Only Autoreview, the cold reader and
GitHub are stubbed; they write the scored findings and notes.
"""
from __future__ import annotations

import json
import shutil
import sys

import pytest

from conftest import ROOT, _install
from test_close import CLEAN, blocked, env  # noqa: F401 (env is a fixture)
from test_proto_signoff import SOL_HIGH, _client, _decision
from test_setup import _fresh_client
from test_stop_default_answer import follow_ups, later
from test_hotspot_stop import rounds, seed
from test_story import DOC, READER, new_story

STORY = "FORGE-SCORE-1"


def _scored(priority: str, title: str, body: str, file: str = "app.py") -> dict:
    return {"title": title, "body": body, "priority": priority,
            "code_location": {"file_path": file, "line": 1}}


def _client_repo(env, tmp_path, previous: bool) -> None:
    """A client repo on this release: made by forge init, or adopted on an earlier release and
    moved to this one with forge sync."""
    repo = env.repo
    config = (repo.path / "forge.toml").read_text("utf-8")
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
    else:
        repo.path, made = _fresh_client(repo, env.gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    repo.git("switch", "-qc", "fix/upgrade")
    repo.write("forge.toml", config + 'models.grill.claude = { model = "opus", effort = "high" }\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
    no_hooks = f"core.hooksPath={tmp_path / 'no-hooks'}"
    repo.git("add", "-A")
    repo.git("-c", no_hooks, "commit", "-qm", "Move to this release")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/upgrade")
    repo.git("-c", no_hooks, "push", "-q", "origin", "main")


@pytest.mark.parametrize("case", ["init", "earlier-adoption-upgrade-sync", "sign-off", "narrowed"])
def test_1_every_note_and_finding_shows_scores_and_the_harm_floor(env, tmp_path, monkeypatch, case):
    repo = env.repo
    if case == "sign-off":
        (tmp_path / "sign-off").mkdir()
        fix, answers, queue = _client(repo, tmp_path / "sign-off", monkeypatch)
        _decision(fix, answers)
        # A score that is not one whole number from 1 to 5 makes the finding unreadable.
        queue.write_text(json.dumps([{"say": SOL_HIGH, "report": {"review_status": "findings", "findings": [
            _scored("P1", "Prototype fails", "Gain 3, Work 2, Harm 1.5\nDemo cannot finish")]}}]))
        unreadable = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert unreadable.returncode == 1
        assert "it wrote findings Forge cannot read" in unreadable.stderr
        queue.write_text(json.dumps([{"say": SOL_HIGH, "report": {"review_status": "findings", "findings": [
            _scored("P1", "Prototype fails", "Gain 3, Work 2, Harm 1\nDemo cannot finish")]}}]))
        refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert refused.returncode == 1
        assert "found a blocking issue: Prototype fails" in refused.stderr
        call = json.loads(queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()[-1])
        prompt = "\n\n".join(call["prompt_files"].values())
        assert "Gain <g>, Work <w>, Harm <h>" in prompt and "judgement, not measurement" in prompt
        return
    if case == "narrowed":  # a follow-up fix's name and summary leave the score line out
        seed(env, "src/a.py")
        item, where = env.start_fix()
        rounds(env, item, where, ["src/a.py"] * 2)
        env.commit(where, "app.py", "print(3)\n")
        env.reviews(blocked(_scored("P1", "Round 3 defect",
                                    "Gain 3, Work 2, Harm 1\nSaving drops the basket.", "src/a.py")))
        env.close(item)
        later(monkeypatch, 31)
        env.close(item)
        [branch] = follow_ups(env)
        subject = repo.git("log", "-1", "--format=%s", branch)
        assert "Round 3 defect" in subject
        assert "Gain" not in subject and "gain" not in branch
        return
    _client_repo(env, tmp_path, case != "init")

    # A review whose finding has no score line is not read; close's second attempt is.
    env.reviews(blocked(_scored("P1", "Saving drops the basket", "Evidence: app.py:1")),
                blocked(_scored("P1", "Saving drops the basket",
                                "Gain 3, Work 2, Harm 1\nRaise: Functional\nEvidence: app.py:1"),
                        _scored("P1", "Basket ids are guessable",
                                "Gain 3, Work 1, Harm 2\nRaise: Security\nAnyone can read a basket."),
                        _scored("P1", "The basket migration drops old rows",
                                "Gain 4, Work 3, Harm 1\nRaise: Functional\nOld baskets vanish."),
                        _scored("P1", "Saving overwrites another shopper's basket",
                                "Gain 3, Work 2, Harm 2\nRaise: Data loss\nTwo saves at once keep one.")))
    item, _ = env.start_fix()
    closed = env.close(item)
    out = closed.stdout + closed.stderr
    assert "it wrote findings Forge cannot read" in out
    assert len(env.review_calls()) == 2
    assert "Gain 3, Work 2, Harm 1\n" in closed.stdout
    assert "Gain 3, Work 1, Harm 4 (floor: security)" in closed.stdout
    assert "Gain 4, Work 3, Harm 4 (floor: migration)" in closed.stdout
    assert "Gain 3, Work 2, Harm 4 (floor: data loss)" in closed.stdout
    assert "Gain <g>, Work <w>, Harm <h>" in env.prompt()
    assert "judgement, not measurement" in env.prompt()

    # A cold-read note scored Harm 1 that names a migration is saved with the floor.
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    (repo.bin / "claude-says.md").write_text(
        "1. Blocking: Saved baskets need a migration of the old rows.\n"
        "   Raise: Plan gap\n   No task moves the old rows.\n   Gain 3, Work 2, Harm 1\n",
        encoding="utf-8")
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    notes = (shop / "plans/SHOP.read.md").read_text("utf-8")
    assert "   Gain 3, Work 2, Harm 4 (floor: migration)\n" in notes
    prompt = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]
    assert "Gain <g>, Work <w>, Harm <h>" in prompt and "judgement, not measurement" in prompt
