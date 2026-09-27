"""Forge records the time spent in real work and close commands."""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
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


@pytest.mark.parametrize("review_config,review_model", [
    ("", "gpt-6-sol"),
    ('models.review = { model = "gpt-6-astra" }\n', "gpt-6-astra"),
])
def test_1_work_and_close_append_step_timings(env, monkeypatch, review_config, review_model):
    repo = env.repo
    install_claude(repo)
    config = repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8") +
                      'models.lite = { model = "sonnet", effort = "medium" }\n'
                      + review_config, "utf-8")
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Set models")
    repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    timings = repo.path / ".git" / "forge" / "timings.jsonl"
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
    assert [(line["item"], line["step"], line["outcome"]) for line in lines] == [
        (item, "worker round", "completed"), (item, "review", "clean"),
        (item, "CI wait", "passed")]
    assert [(line.get("model"), line.get("effort")) for line in lines] == [
        ("sonnet", "medium"), (review_model, "high"), (None, None)]
    for line, earliest, latest in zip(lines, [work_start, close_start, close_start],
                                      [work_end, close_end, close_end]):
        assert earliest - timedelta(seconds=1) <= datetime.fromisoformat(line["start"]) <= latest
        assert 0.15 <= line["seconds"] <= (latest - earliest).total_seconds()
    assert not repo.git("status", "--porcelain", cwd=repo.path)

    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    failed = repo.forge("work", item)
    assert failed.returncode != 0
    assert json.loads(timings.read_text("utf-8").splitlines()[-1])["outcome"] == "failed"


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
