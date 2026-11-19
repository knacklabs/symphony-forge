"""A resumed task keeps the story-level file rule after a Forge upgrade.

Test-audit:
1. The observable contract is that a resumed `forge work` sends the story-file protection in its
   short continuation brief, so an older saved conversation receives the current rule.
2. A regression is that the full template gains the rule but the continuation brief omits it.
3. The full-template check does not cover a saved Claude session resumed through `forge work`; this
   command-level test reaches that delivery path.
4. The test seeds a pre-upgrade saved session only as setup, then checks the real command's captured
   prompt. It needs no production test seam.
"""
import json
from pathlib import Path

import pytest

from test_close import STORY_DOC, env  # noqa: F401
from test_worker import calls, install_claude

pytestmark = pytest.mark.platform
STORY = "FIX-TASK-START-WRONG-BASE"


def test_4_resumed_worker_receives_story_file_rule_after_upgrade(env):
    item, tree = env.start_approved_task(STORY_DOC)
    log = install_claude(env.repo)

    # This saved Claude session began with the pre-upgrade brief, which did not have the rule.
    common = Path(env.repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=tree))
    head = env.repo.git("rev-parse", "HEAD", cwd=tree)
    session = common / "forge" / "threads" / "task" / Path(item).with_suffix(".json")
    session.parent.mkdir(parents=True, exist_ok=True)
    session.write_text(json.dumps({"claude": {"id": "old-saved-session", "checkout": str(tree),
                                                "start": head, "head": head, "rounds": 1}}),
                       encoding="utf-8")
    (env.repo.bin / "claude-sdk-sessions.json").write_text(
        json.dumps({"old-saved-session": str(tree)}), encoding="utf-8")

    resumed = env.repo.forge("work", item, cwd=tree)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    prompt = calls(log)[-1]["brief"]
    assert "The earlier brief in this conversation still applies." in prompt
    assert "Never delete story-level files, such as design images, to keep a part narrow." in prompt
