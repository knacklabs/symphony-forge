"""A queued nightly runs the commit that triggered it.

Test-audit: Protect scheduled full-run selection at the real Forge command
boundary. A branch that moves while Actions queues the run must not reject the
event commit or test the newer main commit. Existing full-run tests cover the
manual latest-main requirement, but not this scheduled race. Use real Git and
the configured pytest command; the harness stubs only GitHub's edge.
"""
import json
import sys
from pathlib import Path

import pytest


STORY = "fewer-main-runs"


@pytest.mark.platform
def test_6_queued_nightly_tests_its_checked_out_commit(repo, monkeypatch):
    repo.git("switch", "main")
    tests = repo.path / "tests"
    tests.mkdir(exist_ok=True)
    (tests / "test_queued_full_run.py").write_text(
        "from pathlib import Path\n\n"
        "def test_record_checked_out_marker():\n"
        "    Path('run-receipt').write_text(Path('suite-marker').read_text('utf-8'), encoding='utf-8')\n",
        encoding="utf-8")
    (repo.path / "suite-marker").write_text("event commit\n", encoding="utf-8")
    ignored = repo.path / ".gitignore"
    existing = ignored.read_text("utf-8") if ignored.exists() else ""
    ignored.write_text(existing + "\n__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    command = (f'"{Path(sys.executable).as_posix()}" -m pytest '
               "tests/test_queued_full_run.py -q")
    (repo.path / "forge.toml").write_text(
        f'version = "{version}"\nrepo = "forge-source"\n'
        'checks = []\ntest_place = "ci"\n'
        f"test = {json.dumps(command)}\n",
        encoding="utf-8")

    repo.git("add", ".gitignore", "forge.toml", "suite-marker", "tests/test_queued_full_run.py")
    repo.git("commit", "-q", "-m", "Prepare scheduled full-run test")
    repo.git("push", "-q", "origin", "HEAD:main")
    event_commit = repo.git("rev-parse", "HEAD")
    (repo.path / "suite-marker").write_text("new main commit\n", encoding="utf-8")
    repo.git("add", "suite-marker")
    repo.git("commit", "-q", "-m", "Advance main while nightly waits")
    latest_main = repo.git("rev-parse", "HEAD")
    repo.git("push", "-q", "origin", "HEAD:main")
    repo.git("checkout", "-q", "--detach", event_commit)
    assert repo.git("rev-parse", "HEAD") == event_commit
    assert latest_main != event_commit

    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/project")
    monkeypatch.setenv("FORGE_GROUP", "1")
    monkeypatch.setenv("FORGE_GROUPS", "1")
    scheduled = repo.forge("test", "--full")

    assert scheduled.returncode == 0, scheduled.stdout + scheduled.stderr
    assert (repo.path / "run-receipt").read_text("utf-8") == "event commit\n"

    (repo.path / "run-receipt").unlink()
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    manual = repo.forge("test", "--full")
    assert manual.returncode == 1
    assert manual.stderr == (
        "The full run must use the latest commit on main. Next: git switch main && git pull, "
        "then forge test --full.\n")
    assert not (repo.path / "run-receipt").exists()
