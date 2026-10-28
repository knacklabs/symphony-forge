"""Bound sign-off retries at the real decision command.

Test audit: protects reviewer input and the durable owner stop. The regression
is an empty-root retry or an unrestricted third review. Existing sign-off tests
cover individual full reviews. Only Autoreview is faked at its external edge;
the CLI, git snapshots, state and follow-up creation own the observed behavior.
"""
import json

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "client-sign-off-never-finishes-every-att"
pytestmark = pytest.mark.platform


def _report(priority):
    return {"report": {"review_status": "findings", "findings": [{
        "priority": priority, "title": "Order submission fails",
        "body": "Gain 5, Work 2, Harm 4\nThe normal order path fails.",
        "code_location": {"file_path": "app.py", "line": 1}}]}}


@pytest.mark.parametrize("setup,priority,choice", [
    (_client, "P1", "accept"), (_client, "P1", "more"),
    (_client, "P1", "split"), (_client, "P0", None),
    (_adopted_client, "P1", "accept"),
], ids=["new-accept", "new-more", "new-split", "new-critical", "adopted-accept"])
def test_signoff_reviews_changes_and_bounds_rounds(repo, tmp_path, monkeypatch, setup, priority, choice):
    fix, answers, queue = setup(repo, tmp_path, monkeypatch)
    if setup is _adopted_client:
        _request_build(repo, fix)
        (fix / "app.py").write_text("print('prototype')\n", encoding="utf-8")
        repo.git("add", "app.py", cwd=fix)
        repo.git("commit", "-q", "-m", "Build the adopted prototype", cwd=fix)
    page = _decision(fix, answers)
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}}, _report(priority)]))

    def accept(*args):
        return repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", *args, cwd=fix)

    first = accept()
    assert first.returncode == 1, first.stdout + first.stderr
    assert "Order submission fails" in first.stderr
    original = set((tmp_path / "reviewed-files.txt").read_text().splitlines())
    assert {"README.md", "forge.toml", "docs/product/BRIEF.md"} <= original
    (fix / "app.py").write_text("print('changed order path')\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=fix)
    repo.git("commit", "-q", "-m", "Repair the order path", cwd=fix)
    # The product edit also invalidates the separate canvas completeness check.
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}}, _report(priority)]))
    second = accept()
    assert second.returncode == 1, second.stdout + second.stderr
    assert set((tmp_path / "reviewed-files.txt").read_text().splitlines()) == {"app.py"}
    calls = queue.with_suffix(".calls.jsonl")
    prior = [json.loads(line) for line in calls.read_text().splitlines()]
    prompt = "\n".join(prior[-1]["prompt_files"].values())
    assert "Order submission fails" in prompt
    third = accept()
    assert third.returncode == 1, third.stdout + third.stderr
    if priority == "P0":
        assert "Order submission fails" in third.stderr
        assert "Next: fix the prototype" in third.stderr
        assert len(calls.read_text().splitlines()) == len(prior) + 1
        return
    assert "One more round, split or accept?" in third.stderr
    assert "--resolve" in third.stderr
    assert len(calls.read_text().splitlines()) == len(prior)
    resolved = accept("--resolve", choice, "--reason", "The owner chose this outcome")
    if choice == "more":
        assert len(calls.read_text().splitlines()) == len(prior) + 1
        assert "Order submission fails" in resolved.stderr
    else:
        assert resolved.returncode == 0, resolved.stdout + resolved.stderr
        assert "status: accepted" in page.read_text()
        assert len(calls.read_text().splitlines()) == len(prior)
        states = [json.loads(path.read_text()) for path in (fix / ".factory/fixes").glob("*.json")]
        assert any(entry["title"] == "Order submission fails" and entry["outcome"] == "follow-up"
                   for state in states for entry in state.get("known", []))
        if choice == "split":
            assert any("Order submission fails" in state.get("why", "") for state in states)
