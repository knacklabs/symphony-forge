"""Fresh and resumed workers receive the two-round cold-read stop rule."""
STORY = "three-rounds-ask"

import pytest

from test_close import env  # noqa: F401
from test_worker import calls, install_claude

pytestmark = pytest.mark.platform


def test_4_fresh_and_resumed_workers_wait_for_both_read_and_review_choices(env):
    item, _ = env.start_fix()
    log = install_claude(env.repo)
    for _ in range(2):
        result = env.repo.forge("work", item)
        assert result.returncode == 0, result.stdout + result.stderr
        brief = " ".join(calls(log)[-1]["brief"].split())
        assert "round two" in brief and "P0" in brief
        assert "forge read" in brief and "<accept|more|split>" in brief
    assert calls(log)[-1]["options"]["resume"]
