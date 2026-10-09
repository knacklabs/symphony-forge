"""A roadmap item a new spec replaces is retired with `forge roadmap retire`, not deleted by hand."""
from __future__ import annotations

import hashlib
import json
import subprocess

STORY = "roadmap-items-a-new-spec-replaces-can-on"

DISCOVER = "No story or fix is in progress and the roadmap is empty, so start with discovery, as "


def _item(key: str, status: str, order: int, **more: str) -> dict:
    return {"key": key, "title": f"The {key} story", "spec": "docs/specs/old-way.md",
            "status": status, "order": order, **more}


def _ok(done) -> str:
    assert done.returncode == 0, done.stderr
    return done.stdout


def _refused(done, problem: str, next_step: str) -> None:
    assert (done.returncode, done.stderr) == (1, f"{problem}\nNext: {next_step}\n")


def _roadmap(repo) -> list[dict]:
    return json.loads((repo.path / "plans/roadmap.json").read_text(encoding="utf-8"))["items"]


def _on_main(repo, items: list[dict]) -> None:
    repo.write("plans/roadmap.json", json.dumps({"generated_by": "human", "items": items}, indent=2))
    repo.write("docs/specs/new-way.md", "# The new way\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Plan so far")
    repo.git("push", "-q", "origin", "main")


def _fix(repo) -> None:
    """A fix branch Forge started, the lane every roadmap change ships through."""
    repo.git("checkout", "-q", "-b", "fix/new-way")
    repo.write(".factory/fixes/new-way.json", json.dumps({
        "kind": "fix", "why": "The new way replaces the old one", "done_when": "It is retired",
        "branch": "fix/new-way", "status": "started", "touches": 0,
        "steps": [{"step": "start", "at": "2026-09-25T10:00:00+00:00"}]}, indent=2))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Start the fix")


def _board(repo) -> str:
    out = repo.path.parent / "board.html"
    _ok(repo.forge("board", "--out", str(out)))
    return out.read_text(encoding="utf-8")


def test_1_retiring_a_pending_item_marks_it_superseded_by_the_new_spec(repo):
    _on_main(repo, [_item("OLD-1", "pending", 1), _item("KEEP-1", "pending", 2)])
    _fix(repo)
    assert "The OLD-1 story" in _board(repo)

    assert _ok(repo.forge("roadmap", "retire", "OLD-1", "--by", "new-way")) == (
        "OLD-1 is retired on plans/roadmap.json, superseded by docs/specs/new-way.md.\n")

    assert _roadmap(repo) == [_item("OLD-1", "superseded", 1, superseded_by="docs/specs/new-way.md"),
                              _item("KEEP-1", "pending", 2)]
    assert repo.git("log", "-1", "--format=%s") == (
        "Retire OLD-1 from the roadmap; the new-way spec replaces it")
    assert repo.git("show", "--name-only", "--format=", "HEAD") == "plans/roadmap.json"
    assert repo.git("status", "--porcelain") == ""
    board = _board(repo)
    assert "The OLD-1 story" not in board and "The KEEP-1 story" in board


def test_2_retiring_refuses_an_unknown_key_a_started_or_done_item_and_a_missing_spec(repo):
    _on_main(repo, [_item("OLD-1", "pending", 1), _item("DONE-1", "done", 2),
                    _item("BUSY-1", "pending", 3)])
    repo.git("branch", "story/BUSY-1")  # forge story new started it on its own branch
    _fix(repo)
    head = repo.git("rev-parse", "HEAD")

    _refused(repo.forge("roadmap", "retire", "NOPE-1", "--by", "new-way"),
             "NOPE-1 is not on the roadmap (plans/roadmap.json).",
             "forge roadmap retire <KEY> --by new-way")
    _refused(repo.forge("roadmap", "retire", "DONE-1", "--by", "new-way"),
             "DONE-1 is done, and only a pending roadmap item can be retired.", "forge next")
    _refused(repo.forge("roadmap", "retire", "BUSY-1", "--by", "new-way"),
             "BUSY-1 is started, and only a pending roadmap item can be retired.", "forge next")
    _refused(repo.forge("roadmap", "retire", "OLD-1", "--by", "gone"),
             "docs/specs/gone.md does not exist; write the spec there first.", "forge spec save gone")

    assert repo.git("rev-parse", "HEAD") == head
    assert repo.git("status", "--porcelain") == ""


def test_3_forge_next_no_longer_offers_a_retired_item(repo):
    _on_main(repo, [_item("OLD-1", "pending", 1)])
    assert _ok(repo.forge("next")).splitlines()[:2] == [
        "No story or fix is in progress.",
        'Next: forge story new <KEY> "<title>" for an item on plans/roadmap.json']

    _fix(repo)
    _ok(repo.forge("roadmap", "retire", "OLD-1", "--by", "new-way"))
    # The fix lands: only its roadmap change reaches main.
    repo.git("checkout", "-q", "main")
    repo.git("checkout", "fix/new-way", "--", "plans/roadmap.json")
    repo.git("commit", "-q", "-m", "Retire OLD-1")
    repo.git("push", "-q", "origin", "main")
    repo.git("branch", "-q", "-D", "fix/new-way")

    assert _ok(repo.forge("next")).startswith(DISCOVER)


def _git(repo, *args: str) -> subprocess.CompletedProcess[str]:
    # These branches aren't Forge's, so its commit hook would refuse them; the merge rule doesn't.
    return subprocess.run(["git", "-c", "core.hooksPath=no-hooks", *args], cwd=repo.path,
                          capture_output=True, text=True, encoding="utf-8")


def _commit(repo, items: list[dict], message: str) -> None:
    repo.write("plans/roadmap.json", json.dumps({"items": items}, indent=2) + "\n")
    assert _git(repo, "commit", "-q", "-am", message).returncode == 0


def test_4_the_roadmap_merge_rule_conflicts_on_competing_statuses(repo):
    repo.git("checkout", "-q", "-b", "fix/roadmap")
    repo.write("forge.toml", 'version = "v1.2.6"\ntest = "echo ok"\n'
                             'checks = ["tests", "forge-pr-check"]\n')
    repo.write("plans/roadmap.json", json.dumps({"items": [_item("OLD-1", "pending", 1)]}) + "\n")
    _ok(repo.forge("sync"))
    repo.git("add", "-A")
    assert _git(repo, "commit", "-q", "-m", "Synced").returncode == 0
    repo.git("branch", "starts")
    repo.git("checkout", "-q", "-b", "retires")
    retired = _item("OLD-1", "superseded", 1, superseded_by="docs/specs/new-way.md")
    _commit(repo, [retired], "Retire")
    repo.git("checkout", "-q", "starts")
    _commit(repo, [_item("OLD-1", "started", 1)], "Start")
    repo.git("branch", "starts-again")
    repo.git("branch", "retires-again", "retires")

    # The old rule picked superseded; competing status edits now require a decision.
    for ours, theirs in (("retires", "starts"), ("starts-again", "retires-again")):
        repo.git("checkout", "-q", ours)
        before = _roadmap(repo)
        merged = _git(repo, "merge", "-q", "--no-edit", theirs)
        assert merged.returncode != 0, merged.stdout + merged.stderr
        assert "plans/roadmap.json" in repo.git("diff", "--name-only", "--diff-filter=U")
        assert _roadmap(repo) == before, ours
        repo.git("merge", "--abort")


def test_5_a_retired_story_counts_as_finished_for_its_spec_check_back(repo, monkeypatch):
    body = ("\n# Invoices by email\n\n## Success measure\n\n- Metric: invoices paid on time.\n"
            "- Baseline: 40%.\n- Target: 70%.\n- Check date: 2026-10-01\n")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    repo.write("docs/specs/old-way.md", f"---\ntitle: Invoices by email\nstatus: confirmed\nconfirmed_hash: {digest}\n---\n{body}")
    repo.write(".factory/stories/DONE-1/story.json", '{"title": "DONE-1", "status": "done"}\n')
    _on_main(repo, [_item("DONE-1", "done", 1),
                    _item("OLD-1", "superseded", 2, superseded_by="docs/specs/new-way.md")])
    monkeypatch.setenv("FORGE_NOW", "2026-10-02T09:00:00+00:00")

    assert _ok(repo.forge("next")).splitlines()[0] == (
        "Every story from the Invoices by email spec is done and its check date has passed; "
        "measure invoices paid on time.")
