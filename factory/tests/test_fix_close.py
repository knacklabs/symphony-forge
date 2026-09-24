"""End-to-end orchestration for one-command Lite fixes."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

from test_gates import HARNESS, git, head, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from factory_lib import append_ledger_record, evidence_path, head_sha  # noqa: E402
from forge_cli import fix, quickfix, review  # noqa: E402


def _open_lite(repo: Path, window_id: str) -> dict:
    git(repo, "config", "user.email", "test@knacklabs.dev")
    git(repo, "config", "user.name", "Gate Tests")
    window = {
        "id": window_id,
        "profile": "lite",
        "by": "test author",
        "reason": "bounded fix test",
        "started_at": "2026-09-24T00:00:00Z",
        "max_files": 5,
        "files": [],
        "harness_source": False,
        "base_sha": head(repo),
    }
    active = repo / ".factory" / "quickfix.json"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(json.dumps(window) + "\n", encoding="utf-8")
    append_ledger_record(
        quickfix.ledger_path(repo), {"event": "open", **window},
        f"open-{window_id}",
    )
    return window


def _mock_review(monkeypatch, *, blocking=None, non_blocking=None):
    calls = []

    def fake_review(base: Path, **kwargs):
        calls.append((base, kwargs))
        active = quickfix.load_active(base)
        commit = head_sha(base)
        for aspect in review.LENSES:
            artifact = {
                "review_base_sha": active["base_sha"],
                "commit": commit,
                "score": 10,
                "blocking_findings": blocking if aspect == "quality" else [],
                "non_blocking_findings": (
                    non_blocking if aspect == "quality" else []
                ),
            }
            path = evidence_path(base, None, f"reviews/{aspect}.json", for_write=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(artifact) + "\n", encoding="utf-8")

    monkeypatch.setattr(review, "review_lite", fake_review)
    return calls


def _mock_worker(monkeypatch, *, writes=True):
    calls = []

    def fake_launch(base: Path, **kwargs):
        calls.append((base, kwargs))
        if writes:
            product = base / "src" / "fix.py"
            product.parent.mkdir(parents=True, exist_ok=True)
            product.write_text("fixed = True\n", encoding="utf-8")
        return {"launch_status": "succeeded"}

    monkeypatch.setattr(fix, "launch_companion", fake_launch)
    return calls


def _invoke_close(repo: Path, description: str = "Repair Lite path") -> None:
    fix.cmd_fix(argparse.Namespace(
        description=description, repo=str(repo), close=True,
        resume_close=False, window_id=None,
    ))


def _prepare_sync(monkeypatch):
    monkeypatch.setenv("FORGE_COORDINATOR", "claude")
    monkeypatch.setattr(fix, "mode_run_config", lambda *_args: ("model", "max", 5))


def test_fix_close_commits_reviews_closes_and_commits_only_window_records(
        repo, monkeypatch, capsys):
    window_id = "Q-0227-clean"
    _open_lite(repo, window_id)
    foreign_window_id = "Q-0227-cleanup"
    foreign_record = append_ledger_record(
        quickfix.ledger_path(repo), {"event": "done", "id": foreign_window_id},
        f"done-{foreign_window_id}",
    )
    _prepare_sync(monkeypatch)
    workers = _mock_worker(monkeypatch)
    reviews = _mock_review(monkeypatch, non_blocking=[{
        "summary": "Minor follow-up",
    }])

    factory_side_effect = repo / ".factory" / "worker-side-effect.json"
    plan_side_effect = repo / "plans" / "worker-side-effect.md"
    factory_side_effect.write_text("leave staged\n", encoding="utf-8")
    plan_side_effect.parent.mkdir(parents=True, exist_ok=True)
    plan_side_effect.write_text("leave staged\n", encoding="utf-8")
    git(repo, "add", "-f", "--", ".factory/worker-side-effect.json",
        "plans/worker-side-effect.md")
    original = head(repo)

    _invoke_close(repo)

    output = capsys.readouterr().out
    assert "accepted; log with `forge defer add` if they matter" in output
    assert workers and len(workers) == 1
    assert reviews == [(repo, {})]
    assert not quickfix.load_active(repo)
    assert head(repo) != original

    product_commit = git(repo, "rev-parse", "HEAD^")
    assert git(repo, "show", "-s", "--format=%s", product_commit) == "Repair Lite path"
    assert f"Ticket: {window_id}" in git(repo, "show", "-s", "--format=%B", product_commit)
    assert git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r",
               product_commit) == "src/fix.py"

    record_paths = set(git(repo, "diff-tree", "--no-commit-id", "--name-only",
                           "-r", "HEAD").splitlines())
    assert len(record_paths) == 2
    assert all(path.startswith("plans/quickfixes/") and window_id in path
               for path in record_paths)
    assert foreign_record.relative_to(repo).as_posix() not in record_paths
    record_message = git(repo, "show", "-s", "--format=%B", "HEAD")
    assert f"Ticket: {window_id}" in record_message
    assert set(git(repo, "diff", "--cached", "--name-only").splitlines()) == {
        ".factory/worker-side-effect.json", "plans/worker-side-effect.md",
    }


@pytest.mark.parametrize("first_sentence", [
    "Repair Lite path.",
    "Repair " + "x" * 100 + ".",
])
def test_fix_close_uses_short_subject_and_preserves_description(
        repo, monkeypatch, first_sentence):
    window_id = "Q-0227-description"
    _open_lite(repo, window_id)
    _prepare_sync(monkeypatch)
    _mock_worker(monkeypatch)
    _mock_review(monkeypatch)
    prefix = (
        first_sentence + "\nSecond sentence explains the change. "
        "Third sentence adds details "
    )
    description = prefix + "z" * (399 - len(prefix)) + "."
    assert len(description) == 400

    _invoke_close(repo, description)

    product_commit = git(repo, "rev-parse", "HEAD^")
    subject = git(repo, "show", "-s", "--format=%s", product_commit)
    message = git(repo, "show", "-s", "--format=%B", product_commit)
    expected = (first_sentence[:69] + "..." if len(first_sentence) > 72
                else first_sentence)
    assert subject == expected
    assert len(subject) <= 72
    assert message.index(description) < message.index(f"Ticket: {window_id}")


def test_fix_close_blocking_review_leaves_window_open(repo, monkeypatch, capsys):
    window_id = "Q-0227-blocked"
    _open_lite(repo, window_id)
    _prepare_sync(monkeypatch)
    _mock_worker(monkeypatch)
    reviews = _mock_review(monkeypatch, blocking=[{
        "summary": "Fix round required",
    }])
    original = head(repo)

    _invoke_close(repo)

    output = capsys.readouterr().out
    assert "Fix round required" in output
    assert f"window {window_id} remains open" in output
    assert quickfix.load_active(repo)["id"] == window_id
    assert reviews == [(repo, {})]
    assert head(repo) != original
    assert git(repo, "show", "-s", "--format=%s", "HEAD") == "Repair Lite path"
    assert f"Ticket: {window_id}" in git(repo, "show", "-s", "--format=%B", "HEAD")
    assert not any(event.get("event") == "done" and event.get("id") == window_id
                   for event in quickfix.load_events(repo))


def test_fix_close_resume_reviews_and_closes_previously_committed_changes(
        repo, monkeypatch, capsys):
    window_id = "Q-0227-review-retry"
    _open_lite(repo, window_id)
    _prepare_sync(monkeypatch)
    workers = _mock_worker(monkeypatch)
    complete_review_calls = _mock_review(monkeypatch)
    complete_review = review.review_lite
    review_attempts = []

    def incomplete_first_review(base: Path, **kwargs):
        review_attempts.append((base, kwargs))
        if len(review_attempts) > 1:
            complete_review(base, **kwargs)

    monkeypatch.setattr(review, "review_lite", incomplete_first_review)
    original = head(repo)

    with pytest.raises(SystemExit):
        _invoke_close(repo)
    assert "Lite review needs current complete artifacts" in capsys.readouterr().out

    product_commit = head(repo)
    assert product_commit != original
    assert quickfix.load_active(repo)["id"] == window_id
    assert git(repo, "show", "-s", "--format=%s", product_commit) == "Repair Lite path"
    assert git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r",
               product_commit) == "src/fix.py"

    fix.cmd_fix(argparse.Namespace(
        description="Repair Lite path", repo=str(repo), close=True,
        resume_close=True, window_id=window_id,
    ))

    assert workers and len(workers) == 1
    assert review_attempts == [(repo, {}), (repo, {})]
    assert complete_review_calls == [(repo, {})]
    assert not quickfix.load_active(repo)
    assert git(repo, "rev-parse", "HEAD^") == product_commit
    assert git(repo, "rev-parse", "HEAD^^") == original
    assert git(repo, "log", "--format=%s", f"{original}..HEAD").splitlines().count(
        "Repair Lite path") == 1


def test_fix_close_with_no_product_change_does_not_commit_or_review(
        repo, monkeypatch, capsys):
    window_id = "Q-0227-empty"
    _open_lite(repo, window_id)
    _prepare_sync(monkeypatch)
    _mock_worker(monkeypatch, writes=False)
    monkeypatch.setattr(
        review, "review_lite",
        lambda *_args, **_kwargs: pytest.fail("review ran without product changes"),
    )
    original = head(repo)

    _invoke_close(repo)

    assert "No product changes to commit" in capsys.readouterr().out
    assert quickfix.load_active(repo)["id"] == window_id
    assert head(repo) == original


def test_native_fix_close_prints_and_honors_resume_after_worker_returns(
        repo, monkeypatch, capsys):
    window_id = "Q-0227-native"
    _open_lite(repo, window_id)
    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    monkeypatch.setattr(fix, "mode_run_config", lambda *_args: ("model", "max", 5))
    monkeypatch.setattr(fix, "launch_companion", lambda *_args, **_kwargs: {
        "action": "spawn_agent", "transport": "host-native",
    })
    original = head(repo)

    _invoke_close(repo)

    output = capsys.readouterr().out
    assert "--close --resume-close" in output
    assert f"--window-id {window_id}" in output
    assert quickfix.load_active(repo)["id"] == window_id
    assert head(repo) == original

    product = repo / "src" / "fix.py"
    product.parent.mkdir(parents=True, exist_ok=True)
    product.write_text("fixed = True\n", encoding="utf-8")
    reviews = _mock_review(monkeypatch)
    fix.cmd_fix(argparse.Namespace(
        description="Repair Lite path", repo=str(repo), close=True,
        resume_close=True, window_id=window_id,
    ))
    capsys.readouterr()

    assert reviews == [(repo, {})]
    assert not quickfix.load_active(repo)
