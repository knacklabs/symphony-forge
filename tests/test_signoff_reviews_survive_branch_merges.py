"""Concurrent sign-off reviews remain visible after Forge reconciles their record.

Test audit: the contract is the next real sign-off command receiving both independent
review histories. A merge that keeps only one parent's rounds loses the other finding;
existing sign-off tests use one checkout. Git and Forge commands are real, with only
Autoreview responses replaced at its external boundary. No production seam is needed.
"""
import json

import pytest

from test_proto_signoff import SOL_HIGH, _client, _decision

STORY = "record-merge-conflicts"
pytestmark = pytest.mark.platform


def _finding(title):
    return {
        "priority": "P0",
        "title": title,
        "body": "Gain 5, Work 2, Harm 4\nThe order can be lost.",
        "code_location": {"file_path": "app.py", "line": 1},
    }


def _report(*findings):
    return {"review_status": "findings", "findings": list(findings)}


def _accept(repo, checkout, queue, report):
    queue.write_text(json.dumps([{"say": SOL_HIGH, "report": report}]), encoding="utf-8")
    return repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=checkout)


def _calls(queue):
    calls = queue.with_suffix(".calls.jsonl")
    return [json.loads(line) for line in calls.read_text("utf-8").splitlines()] if calls.exists() else []


def test_5_signoff_keeps_both_machine_reviews_after_a_branch_merge(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path / "signoff", monkeypatch)
    page = _decision(fix, answers)
    repo.git("add", page.relative_to(fix).as_posix(), cwd=fix)
    repo.git("commit", "-qm", "Prepare client sign-off", cwd=fix)
    synced = repo.forge("sync", cwd=fix)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=fix)
    if repo.git("diff", "--cached", "--name-only", cwd=fix):
        repo.git("commit", "-qm", "Install sign-off merge rule", cwd=fix)

    branch = repo.git("branch", "--show-current", cwd=fix)
    remote = repo.git("remote", "get-url", "origin", cwd=fix)
    repo.git("push", "-q", "-u", "origin", branch, cwd=fix)
    peer = tmp_path / "sign-off-peer"
    repo.git("clone", "-q", "--branch", branch, remote, str(peer), cwd=fix)

    first_title = "First machine found a data-loss risk"
    first = _accept(repo, fix, queue, _report(_finding(first_title)))
    assert first.returncode != 0
    assert first_title in first.stderr

    second_title = "Second machine found an access risk"
    second = _accept(repo, peer, queue, _report(_finding(second_title)))
    assert second.returncode != 0
    assert second_title in second.stderr
    peer_branch = f"{branch}-peer"
    repo.git("push", "-q", "origin", f"HEAD:refs/heads/{peer_branch}", cwd=peer)

    repo.git("fetch", "-q", "origin", cwd=fix)
    repo.git("merge", "--no-edit", f"origin/{peer_branch}", cwd=fix)

    before = len(_calls(queue))
    accepted = _accept(repo, fix, queue, {"review_status": "scoped-clean", "findings": []})
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    later_calls = _calls(queue)[before:]
    prompt = "\n".join(text for call in later_calls
                       for text in call["prompt_files"].values())
    assert first_title in prompt
    assert second_title in prompt
    assert "fixed: absent from a later review" not in prompt
