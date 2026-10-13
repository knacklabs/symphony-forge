"""Command-level speed receipts and doctor verdicts."""
import json
from pathlib import Path
import re
import shutil
import sys

import pytest

from conftest import ROOT, _install, patient
from test_codex_fast_when_work_waits import _policy, _tiers
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_setup import _autoreview, _fresh_client, _stub_forge

STORY = "fast-mode-visible"


# From Claude Code, so these Codex workers run through the Codex kit.
@pytest.mark.usefixtures("claude_session")
@pytest.mark.parametrize("tiers, mode, receipt, received, said, doctor", [
    ([{"id": "priority", "name": "Fast"}], "needed", None, "priority",
     "Codex Fast: requested for this turn.",
     "the last codex turn ran with fast"),
    ([], "needed", None, "default",
     "Codex Fast: wanted, but gpt-6-sol doesn't offer it, so this turn requests normal speed.",
     "the last codex turn wanted fast, but gpt-6-sol doesn't offer it"),
    ([], "needed", "thread", "default",
     "Codex Fast: wanted, but gpt-6-sol doesn't offer it, so this turn requests normal speed.",
     "the last codex turn wanted fast, but gpt-6-sol doesn't offer it"),
    ([], "needed", "missing", None,
     "Codex Fast: wanted, but gpt-6-sol doesn't offer it, so this turn requests normal speed.",
     "the last codex turn wanted fast, but gpt-6-sol doesn't offer it"),
    ([{"id": "priority", "name": "Fast"}], "needed", "default", "default",
     "Codex Fast: requested for this turn.", "codex reported normal speed"),
    ([{"id": "priority", "name": "Fast"}], "needed", "other", "other",
     "Codex Fast: requested for this turn.", "codex reported a different speed"),
    ([{"id": "priority", "name": "Fast"}], "needed", "sibling", "priority",
     "Codex Fast: requested for this turn.", "the last codex turn ran with fast"),
    ([{"id": "priority", "name": "Fast"}], "needed", "missing", None,
     "Codex Fast: requested for this turn.", "codex did not report the last turn's speed"),
    ([{"id": "priority", "name": "Fast"}], "needed", 7, None,
     "Codex Fast: requested for this turn.", "codex did not report the last turn's speed"),
    ([{"id": "priority", "name": "Fast"}], "off", None, "default",
     "Codex speed: normal requested for this turn.", "the last codex turn ran at normal speed"),
])
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-release"])
def test_1_each_turn_says_and_records_whether_fast_ran(
        repo, monkeypatch, sdk_data, tiers, mode, receipt, received, said, doctor, adopted):
    # Old proof only checked text somewhere; receipts now cover each capacity retry as well.
    # The first line describes the request; only a receipt can confirm the speed afterward.
    _, calls = _codex_repo(repo, monkeypatch, sdk_data, client=True, start_task=False)
    if adopted:
        patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                                        dirs_exist_ok=True))
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(re.sub(r'^version = .*$', f'version = "{version}"',
                                 config.read_text("utf-8"), flags=re.M), "utf-8")
        repo.git("commit", "-qam", "Pin current Forge")
        repo.git("push", "-q", "origin", "main")
        said, doctor = (text.replace("gpt-6-sol", "gpt-6.1-sol") for text in (said, doctor))
    _tiers(repo, tiers, receipt)
    monkeypatch.setenv("STUB_CODEX_OVERLOADED", "1")
    monkeypatch.setenv("FORGE_CODEX_RETRY_WAIT", "0")
    started = repo.forge("fix", "start", "Fix the login typo", "--done", "It says Log in")
    assert started.returncode == 0, started.stdout + started.stderr
    if mode == "off":
        folder = repo.path.parent / f"{repo.path.name}-fix-fix-the-login-typo"
        _policy(repo, folder, mode)
    worked = repo.forge("work", "fix-the-login-typo")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    events = [json.loads(line) for line in
              (repo.path / ".git/forge/events.jsonl").read_text("utf-8").splitlines()]
    speeds = [row for row in events if row.get("turn") and "requested_tier" in row]
    assert len(speeds) == len(_sent(calls, "turn/start")) == 2
    assert len({row["turn"] for row in speeds}) == 2
    expected = "priority" if tiers and mode != "off" else "default"
    assert all(row["requested_tier"] == expected and row["tier"] == received for row in speeds)
    assert worked.stdout.splitlines()[0] == said
    checked = repo.forge("doctor")
    lines = [line.lower() for line in checked.stdout.splitlines() if "codex fast" in line.lower()]
    assert len(lines) == 1 and doctor in lines[0], checked.stdout
    assert checked.returncode == 1, checked.stdout


@pytest.mark.parametrize("history", [False, True])
def test_2_doctor_verdict_depends_on_problems_not_turn_history(
        repo, gh, tmp_path, monkeypatch, history):
    client, made = _fresh_client(repo, gh, tmp_path)
    assert made.returncode == 0, made.stderr
    gh.respond("auth", "status")
    _autoreview(tmp_path, monkeypatch)
    toml = client / "forge.toml"
    toml.write_text(toml.read_text("utf-8").replace('workers = "split"', 'workers = "claude"'),
                    "utf-8")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(client))}]\ntrust_level = "trusted"\n', "utf-8")
    _install(repo.bin, "claude", f"#!{sys.executable}\nprint('2.1.291 (Claude Code)')\n")
    _stub_forge(tmp_path, monkeypatch)
    if history:
        common = repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=client)
        events = Path(common) / "forge/events.jsonl"
        events.parent.mkdir(parents=True, exist_ok=True)
        patient(lambda: events.write_text(json.dumps({"event": "run end"}) + "\n", "utf-8"))
    healthy = repo.forge("doctor", cwd=client)
    assert healthy.returncode == 0, healthy.stdout + healthy.stderr
    gh.respond("auth", "status", exit=1)
    broken = repo.forge("doctor", cwd=client)
    assert broken.returncode == 1, broken.stdout + broken.stderr
    assert "gh is not signed in" in broken.stdout
