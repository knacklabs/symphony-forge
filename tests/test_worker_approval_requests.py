"""Worker permission requests reach Forge rather than an automatic refusal."""
import json
import os
import re
import shutil
import sys

import pytest

from conftest import REAL_CODEX_HOME
from test_codex_smoke import ENV, PIN, WAIT
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401

STORY = "codex-builders-must-write-a-failing-test"


def test_1_worker_requests_use_forges_accepting_reviewer(repo, monkeypatch, sdk_data, claude_session):
    _folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    # First build and resumed fix rounds must both let commands such as forge test ask
    # Forge's accepting handler. "never" refuses escalation before that handler runs;
    # auto_review delegates the choice to another model instead of Forge.
    for _ in range(2):
        built = repo.forge("work", "BOARD/PAGE")
        assert built.returncode == 0, built.stdout + built.stderr
    fixed = repo.forge("fix", "start", "Allow the test command", "--done", "Tests can run")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    built = repo.forge("work", "allow-the-test-command")
    assert built.returncode == 0, built.stdout + built.stderr
    for method in ("thread/start", "thread/resume", "turn/start"):
        sent = _sent(calls, method)
        assert sent, method
        for params in sent:
            assert params["approvalPolicy"] == "on-request"
            assert params["approvalsReviewer"] == "user"


@pytest.mark.timeout(WAIT)
@pytest.mark.skipif(os.environ.get("FORGE_LIVE_CODEX") != "1" or not (ENV / "forge-sdk-ready").is_file(),
                    reason=f"calls a real Codex model: needs FORGE_LIVE_CODEX=1 and SDK {PIN}")
def test_2_builder_runs_forge_test_and_observes_its_failure(
        repo, monkeypatch, isolated_codex_home, claude_session):
    # This is the execution proof; the protocol test above cannot prove that Codex
    # actually runs a command. Use the installed SDK and program, never the app-server stub.
    shutil.copyfile(REAL_CODEX_HOME / "auth.json", isolated_codex_home / "auth.json")
    (isolated_codex_home / "auth.json").chmod(0o600)
    (isolated_codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(ENV.parents[2]))
    version = repo.forge("--version").stdout.split()[-1]
    test_command = f'"{sys.executable}" -m pytest test_red.py -q'
    repo.write("forge.toml", f'version = "{version}"\nworkers = "codex"\n'
               f'test = {json.dumps(test_command)}\n'
               '[models.lite.codex]\nmodel = "gpt-6-sol"\neffort = "low"\n')
    repo.write("test_red.py", 'def test_intentional_failure():\n'
               '    assert False, "worker observed the real failing regression"\n')
    repo.write(".gitignore", "__pycache__/\n.pytest_cache/\n")
    repo.git("add", ".")
    repo.git("commit", "-qm", "Prepare the intentional failing regression")
    repo.git("push", "-q", "origin", "main")
    fixed = repo.forge("fix", "start", "Observe the failing regression", "--done",
                       "The worker observes the intentional test failure")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    built = repo.forge("work", "observe-the-failing-regression", "--note",
                       "This is an intentional failing-test fixture. Run exactly forge test "
                       "in your checkout with the command tool, with sandbox_permissions set to "
                       "require_escalated so Forge must answer the permission request. "
                       "Use a non-login shell so the test PATH is preserved. "
                       "Observe the assertion failure, then stop. Do not fix the test, edit "
                       "files, commit, or run any other test command. The expected failure "
                       "is the result we need.", timeout=WAIT)
    assert built.returncode == 0, built.stdout + built.stderr
    log = (repo.path / ".git" / "forge" /
           "work-observe-the-failing-regression.log").read_text(encoding="utf-8")
    assert "Accepted Codex's request item/commandExecution/requestApproval" in log, log
    assert re.search(r"\$ [^\n]*forge test[^\n]*\(failed\)", log), log
    assert "worker observed the real failing regression" in log, log
    assert "1 failed" in log, log
