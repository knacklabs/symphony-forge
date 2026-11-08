"""An absent message leaves the same committed round available for handback."""
import json
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_setup import _fresh_client
from test_tools_session_hold import Session

STORY = "FIX-HANDBACK-MESSAGE"


@pytest.mark.platform
@pytest.mark.parametrize("history", ["new", "adopted"])
def test_1_empty_handback_preserves_round_for_message_retry(repo, gh, monkeypatch, tmp_path, history):
    # Test-audit: protect retry through the command and real host lifetime. The old
    # lifecycle test expected failure instead. No new production seam is needed.
    if history == "new":
        folder, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        repo.path = folder
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "without-sdk"))
    version = repo.forge("--version").stdout.split()[-1]
    repo.git("switch", "-qc", "fix/settings")
    repo.write("forge.toml", f'version = "{version}"\ntools = "claude"\nworkers = "claude"\n'
                             'test = "pytest -q"\ntest_place = "ci"\nchecks = ["tests"]\n')
    repo.write(".factory/fixes/settings.json", json.dumps({
        "kind": "fix", "branch": "fix/settings", "status": "working",
        "why": "Choose tools", "done_when": "forge.toml names the tools"}))
    assert repo.forge("sync").returncode == 0
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Choose tools")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/settings")
    _publish_default(repo, Path(repo.git("remote", "get-url", "origin")).as_posix())
    made = repo.forge("fix", "start", "Correct help words", "--done", "Help reads clearly",
                      "--slug", "help-words")
    assert made.returncode == 0, made.stdout + made.stderr
    host = Session(repo, tmp_path / "host", "claude-session")
    try:
        given = host.forge("work", "help-words")
        assert given.returncode == 0, given.stdout + given.stderr
        number = re.search(r"forge handback help-words --round (\d+)", given.stdout)[1]
        checkout = Path(re.search(r"background fixer subagent of this session, working in (.+)\.\n",
                                  given.stdout)[1])
        (checkout / "help.txt").write_text("Clear help.\n", "utf-8")
        repo.git("add", "help.txt", cwd=checkout)
        repo.git("commit", "-qm", "Correct help", cwd=checkout)
        head = repo.git("rev-parse", "HEAD", cwd=checkout)
        args = ("handback", "help-words", "--round", number, "--subagent", "worker-chat")
        events = repo.path / ".git/forge/events.jsonl"
        timings = repo.path / ".git/forge/timings.jsonl"
        before = events.read_bytes(), timings.read_bytes() if timings.exists() else b""
        for extra, message in [(("--text", "   "), ""), ((), "\n")]:
            empty = host.forge(*args, *extra, input=message)
            assert empty.returncode == 1
            assert "No message reached Forge" in empty.stderr
            assert (f'forge handback help-words --round {number} --subagent worker-chat '
                    '--text "<its last message>"') in empty.stderr
            assert "stdin" in empty.stderr and "forge work" not in empty.stderr
            assert (events.read_bytes(), timings.read_bytes() if timings.exists() else b"") == before
            assert f"Next: forge handback help-words --round {number}" in repo.forge("next").stdout
            assert repo.git("rev-parse", "HEAD", cwd=checkout) == head
        done = (host.forge(*args, "--text", "Committed the help.") if history == "new"
                else host.forge(*args, input="Committed the help."))
        assert done.returncode == 0, done.stdout + done.stderr
        assert "Next: forge close help-words" in repo.forge("next").stdout
        ends = [json.loads(line) for line in events.read_text("utf-8").splitlines()]
        assert [e["outcome"] for e in ends if e["event"] == "run end"
                and e["item"] == "help-words"] == ["completed"]
    finally:
        host.close()
