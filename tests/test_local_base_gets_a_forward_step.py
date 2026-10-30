"""A local-only base leads to close, then a real dependent task start.

The command boundary owns this regression: existing local-base coverage rules
out restarting the base but does not require an actionable replacement step.
Real Git rejects the initial publication; only GitHub and review are faked.
"""
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_stack_start import configured, refuses_without_start, start

STORY = "stack-circular-next"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "upgraded-client"])
def test_1_local_base_gets_a_step_that_unblocks_its_dependent(env, previous):
    repo = configured(env, previous)
    remote = Path(repo.git("remote", "get-url", "origin"))
    hook = remote / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    parent, result = start(repo, "A")
    hook.unlink()
    assert "the work stays local" in result.stderr
    assert repo.git("branch", "-r", "--list", "origin/task/STACK-A") == ""
    env.commit(parent, "app.py", "A_VALUE = 1\n")

    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert ("STACK/B waits for STACK/A to publish reviewed changes.\n"
            "Next: forge close STACK/A") in shown.stdout, shown.stdout
    refuses_without_start(repo, "B",
                          "STACK/B waits for STACK/A to publish reviewed changes.",
                          "forge close STACK/A")

    # Follow the printed command. Close publishes and reviews the local base,
    # so the dependent can start from that reviewed work without a merge.
    env.open_pr("")
    closed = env.close("STACK/A")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    shown = repo.forge("next")
    assert "Next: forge task start STACK/B" in shown.stdout, shown.stdout + shown.stderr
    upper, _ = start(repo, "B")
    assert (upper / "app.py").read_text("utf-8") == "A_VALUE = 1\n"
