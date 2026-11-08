"""An absent message leaves the same committed round available for handback."""
import json
import os
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT, _install
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_setup import _fresh_client
from test_tools_session_hold import Session

STORY = "FIX-HANDBACK-MESSAGE"


@pytest.mark.platform
@pytest.mark.parametrize("history", ["new", "adopted"])
@pytest.mark.parametrize("tool", ["claude", "codex"])
def test_1_empty_handback_preserves_round_for_message_retry(repo, gh, monkeypatch, tmp_path,
                                                          history, tool):
    # Test-audit: protect retry through both real coordinating sessions. Losing
    # the held round breaks next and retry. Assert commands, not private records.
    if history == "new":
        folder, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        repo.path = folder
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    if tool == "claude":
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
    else:
        monkeypatch.delenv("CLAUDECODE", raising=False)
        monkeypatch.setenv("CODEX_THREAD_ID", "handback-session")
        _install(repo.bin, "codex-app-server", (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
        monkeypatch.setenv("CODEX_BIN", str(repo.bin / (
            "codex-app-server.cmd" if os.name == "nt" else "codex-app-server")))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "without-sdk"))
    version = repo.forge("--version").stdout.split()[-1]
    repo.git("switch", "-qc", "fix/settings")
    # This test needs a native handoff; normal-speed workers use the app server.
    native = 'codex_fast = "needed"\n' if tool == "codex" else ""
    repo.write("forge.toml", f'version = "{version}"\ntools = "{tool}"\nworkers = "{tool}"\n'
                             f'{native}'
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
    checkout = next(Path(line[9:]) for line in repo.git("worktree", "list", "--porcelain").splitlines()
                    if line.startswith("worktree ") and line.endswith("help-words"))
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(checkout))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    host = Session(repo, tmp_path / "host", tool + "-session")
    try:
        given = host.forge("work", "help-words")
        assert given.returncode == 0, given.stdout + given.stderr
        number = re.search(r"forge handback help-words --round (\d+)", given.stdout)[1]
        assert str(checkout.resolve().as_posix()) in given.stdout
        (checkout / "help.txt").write_text("Clear help.\n", "utf-8")
        repo.git("add", "help.txt", cwd=checkout)
        repo.git("commit", "-qm", "Correct help", cwd=checkout)
        head = repo.git("rev-parse", "HEAD", cwd=checkout)
        args = ("handback", "help-words", "--round", number, "--subagent", "worker-chat")
        for extra, message in [(("--text", "   "), ""), ((), "\n")]:
            empty = host.forge(*args, *extra, input=message)
            assert empty.returncode == 1
            assert "No message reached Forge" in empty.stderr
            assert (f'forge handback help-words --round {number} --subagent worker-chat '
                    '--text "<its last message>"') in empty.stderr
            assert "stdin" in empty.stderr and "forge work" not in empty.stderr
            shown = repo.forge("next")
            assert shown.returncode == 0, shown.stdout + shown.stderr
            assert f"Next: forge handback help-words --round {number}" in shown.stdout
            assert "Next: forge work help-words" not in shown.stdout
            assert repo.git("rev-parse", "HEAD", cwd=checkout) == head
        done = (host.forge(*args, "--text", "Committed the help.") if history == "new"
                else host.forge(*args, input="Committed the help."))
        assert done.returncode == 0, done.stdout + done.stderr
        assert "Next: forge close help-words" in repo.forge("next").stdout
    finally:
        host.close()
