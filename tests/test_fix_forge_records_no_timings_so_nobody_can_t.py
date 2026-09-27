"""Forge records the time spent in real work and close commands."""

import json
from datetime import datetime

from test_close import env  # noqa: F401
from test_worker import install_claude

STORY = "FIX-FORGE-RECORDS-NO-TIMINGS-SO-NOBODY-CAN-T"


def test_1_work_and_close_append_step_timings(env, monkeypatch):
    repo = env.repo
    install_claude(repo)
    config = repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8") +
                      'models.lite = { model = "sonnet", effort = "medium" }\n'
                      'models.review = { model = "gpt-6-astra", effort = "high" }\n', "utf-8")
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Set models")
    repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    timings = repo.path / ".git" / "forge" / "timings.jsonl"

    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stderr
    closed = repo.forge("close", item)
    assert closed.returncode == 0, closed.stderr

    lines = [json.loads(line) for line in timings.read_text("utf-8").splitlines()]
    assert [(line["item"], line["step"], line["outcome"]) for line in lines] == [
        (item, "worker round", "completed"), (item, "review", "clean"),
        (item, "CI wait", "passed")]
    assert [(line.get("model"), line.get("effort")) for line in lines] == [
        ("sonnet", "medium"), ("gpt-6-astra", "high"), (None, None)]
    for line in lines:
        datetime.fromisoformat(line["start"])
        assert line["seconds"] >= 0
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
