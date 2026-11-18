"""A resumed worker gets the full completion target and grep map for changed functions."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_fix_claude_workers_start_a_fresh_session_eve import _started
from test_worker import calls

STORY = "FIX-FULL-BRIEF-AND-PROOF"
FIX = "fix-the-login-typo"
DONE = "The login page says Log in"


@pytest.mark.parametrize("source, caller, test, original", [
    ("validator.py", "service.py", "tests/test_verify_credentials.py",
     "def verify_credentials():\n    return False\n"),
    ("validator.ts", "service.ts", "tests/credentials.spec.ts",
     "export const verify_credentials = (): boolean => {\n    return false;\n};\n"),
], ids=["python-function", "typed-typescript-arrow"])
def test_2_worker_round_brief_shows_done_when_and_changed_function_context(
        repo, source, caller, test, original):
    # The grep map must work for both Python and the typed TypeScript client stack.
    repo.write(source, original)
    repo.write(caller, "verify_credentials()\n")
    repo.write(test, "verify_credentials()\n")
    repo.git("add", source, caller, test)
    repo.git("commit", "-q", "-m", "Seed the sign-in check",
             "-m", "Proof list:\n- Sign-in check: manual check passed")
    repo.git("push", "-q", "origin", "main")

    log = _started(repo)
    first = repo.forge("work", FIX)
    assert first.returncode == 0, first.stdout + first.stderr
    folder = Path(calls(log)[-1]["cwd"])

    # The body-only edit must resolve to this function's caller and test.
    (folder / source).write_text(original.replace("False", "True").replace("false", "true"),
                                 encoding="utf-8")
    repo.git("add", source, cwd=folder)
    repo.git("commit", "-q", "-m", "Accept valid credentials", "-m",
             "Proof list:\n- Sign-in check: manual check passed", cwd=folder)

    resumed = repo.forge("work", FIX)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    brief = calls(log)[-1]["brief"]

    assert f"Done when: {DONE}" in brief
    assert "Complete the full Done-when for this item" in brief
    assert "verify_credentials" in brief
    assert caller in brief
    assert test in brief
