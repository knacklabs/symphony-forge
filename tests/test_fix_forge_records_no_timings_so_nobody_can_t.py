"""Forge records the time spent in real work and close commands."""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from test_close import CLEAN, FAILED, blocked, env, finding, run  # noqa: F401
from test_codex_worker import _codex_repo, _toml, sdk_data  # noqa: F401
from test_worker import install_claude

STORY = "FIX-FORGE-RECORDS-NO-TIMINGS-SO-NOBODY-CAN-T"


def delay_tool(path: Path, report: str = "") -> None:
    original = path.with_name(path.name + "-original")
    path.rename(original)
    script = (f"#!{sys.executable}\nimport os, sys, time\ntime.sleep(0.2)\n"
              + (f"print({report!r}, flush=True)\n" if report else "")
              + f"os.execv(sys.executable, [sys.executable, {str(original)!r}, *sys.argv[1:]])\n")
    path.write_text(script, "utf-8")
    path.chmod(0o755)


@pytest.mark.parametrize("scenario,review_model", [
    ("clean_default", "gpt-6-sol"),
    ("clean_override", "gpt-6-astra"),
    ("claude_failed", None),
    ("codex", None),
    ("blocked", None),
    ("review_failed", None),
    ("ci_failed", None),
])
def test_1_work_and_close_append_step_timings(env, request, monkeypatch, scenario, review_model):
    repo = env.repo
    if scenario == "codex":
        _codex_rounds(repo, monkeypatch, request.getfixturevalue("sdk_data"))
        return
    if scenario in ("blocked", "review_failed", "ci_failed"):
        _failed_close(env, scenario)
        return

    install_claude(repo)
    config = repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8") +
                      'models.lite = { model = "sonnet", effort = "medium" }\n'
                      + ('models.review = { model = "gpt-6-astra" }\n'
                         if scenario == "clean_override" else ""), "utf-8")
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Set models")
    repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    timings = repo.path / ".git" / "forge" / "timings.jsonl"
    if scenario == "claude_failed":
        monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
        work_start = datetime.now(timezone.utc)
        failed = repo.forge("work", item)
        work_end = datetime.now(timezone.utc)
        assert failed.returncode != 0
        assert "The worker stopped with exit code 3" in failed.stderr
        [line] = [json.loads(text) for text in timings.read_text("utf-8").splitlines()]
        assert (line["item"], line["step"], line["outcome"], line["model"], line["effort"]) == (
            item, "worker round", "failed", "sonnet", "medium")
        assert work_start - timedelta(seconds=1) <= datetime.fromisoformat(line["start"]) <= work_end
        assert 0 <= line["seconds"] <= (work_end - work_start).total_seconds()
        return
    delay_tool(repo.bin / "claude")
    delay_tool(repo.bin / "gh")
    delay_tool(Path(os.environ["AUTOREVIEW"]),
               f"model: {review_model}\nthinking: high")

    work_start = datetime.now(timezone.utc)
    worked = repo.forge("work", item)
    work_end = datetime.now(timezone.utc)
    assert worked.returncode == 0, worked.stderr
    close_start = datetime.now(timezone.utc)
    closed = repo.forge("close", item)
    close_end = datetime.now(timezone.utc)
    assert closed.returncode == 0, closed.stderr

    lines = [json.loads(line) for line in timings.read_text("utf-8").splitlines()]
    # Close now also records its test stage, even when no command is configured. The worker,
    # review and CI durations retain the original contract; a skipped stage has no minimum.
    assert [(line["item"], line["step"], line["outcome"]) for line in lines] == [
        (item, "worker round", "completed"), (item, "test run", "skipped"), (item, "review", "clean"),
        (item, "CI wait", "passed")]
    assert [(line.get("model"), line.get("effort")) for line in lines] == [
        ("sonnet", "medium"), (None, None), (review_model, "high"), (None, None)]
    for line, earliest, latest in zip(lines, [work_start, close_start, close_start, close_start],
                                      [work_end, close_end, close_end, close_end]):
        assert earliest - timedelta(seconds=1) <= datetime.fromisoformat(line["start"]) <= latest
        assert (0 if line["step"] == "test run" else 0.15) <= line["seconds"] <= (
            latest - earliest).total_seconds()
    assert not repo.git("status", "--porcelain", cwd=repo.path)


def _codex_rounds(repo, monkeypatch, sdk_data):
    folder, _ = _codex_repo(repo, monkeypatch, sdk_data)
    item = "BOARD/PAGE"
    timings = repo.path / ".git" / "forge" / "timings.jsonl"

    first = repo.forge("work", item)
    assert first.returncode == 0, first.stderr
    version = repo.forge("--version").stdout.split()[-1]
    (folder / "forge.toml").write_text(_toml(version, "codex", {
        "build": {"model": "gpt-6-sol", "effort": "medium"},
        "fix": {"model": "gpt-6-luna", "effort": "high"}}), "utf-8")
    repo.git("add", "forge.toml", cwd=folder)
    repo.git("commit", "-q", "-m", "Configure the next worker round", cwd=folder)
    second = repo.forge("work", item)
    assert second.returncode == 0, second.stderr
    monkeypatch.setenv("STUB_CODEX_STATUS", "failed")
    third = repo.forge("work", item)
    assert third.returncode != 0

    lines = [json.loads(line) for line in timings.read_text("utf-8").splitlines()]
    assert [(line["item"], line["step"], line["outcome"], line["model"], line["effort"])
            for line in lines] == [
                (item, "worker round", "completed", "gpt-6-sol", "medium"),
                (item, "worker round", "completed", "gpt-6-luna", "high"),
                (item, "worker round", "failed", "gpt-6-luna", "high")]


def _failed_close(env, failure):
    if failure == "blocked":
        env.reviews(blocked(finding("P1", "Missing greeting")))
        expected = [("review", "blocked")]
    elif failure == "review_failed":
        env.reviews(FAILED)
        expected = [("review", "failed")]
    else:
        env.reviews(CLEAN)
        env.checks([run("tests", "failure"), run("forge-pr-check")])
        expected = [("review", "clean"), ("CI wait", "failed")]
    item, _ = env.start_fix()
    timings = env.repo.path / ".git" / "forge" / "timings.jsonl"

    closed = env.close(item)
    assert closed.returncode != 0
    lines = [json.loads(line) for line in timings.read_text("utf-8").splitlines()]
    assert [(line["item"], line["step"], line["outcome"]) for line in lines] == [
        (item, step, outcome) for step, outcome in [("test run", "skipped"), *expected]]


def test_2_timing_write_failure_does_not_fail_work(env):
    repo = env.repo
    install_claude(repo)
    config = repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8") +
                      'models.lite = { model = "sonnet", effort = "medium" }\n'
                      'models.review = { model = "gpt-6-astra", effort = "high" }\n', "utf-8")
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Set model")
    repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    (repo.path / ".git" / "forge" / "timings.jsonl").mkdir(parents=True)
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stderr
    closed = repo.forge("close", item)
    assert closed.returncode == 0, closed.stderr
