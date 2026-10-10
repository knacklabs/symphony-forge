"""Workers wait for a review-loop choice only after close holds the loop."""
import re
import shutil
import sys

import pytest

from conftest import FORGE_SHIM, ROOT, _install
from test_close import env  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item
from test_worker import calls, install_claude

STORY = "worker-no-idle-choice"


@pytest.mark.parametrize("previous", [False, True], ids=["init", "previous-adoption-sync"])
def test_1_workers_fix_each_round_unless_close_has_stopped_the_review_loop(env, tmp_path, previous):
    item, where = client_item(env, tmp_path, previous)
    config = (where / "forge.toml").read_text("utf-8")
    env.commit(where, "forge.toml", config.replace('workers = "codex"',
                                                  'workers = "claude"').replace(
        'workers = "split"', 'workers = "claude"'))
    log = install_claude(env.repo)
    command = env.repo.bin / "forge"
    current_command = command.read_text("utf-8")
    if previous:
        # Start a real session with the earlier prompt bytes, retaining host tracking.
        old_src = tmp_path / "before-choice-clarification"
        shutil.copytree(ROOT / "src/forge", old_src / "src/forge",
                        ignore=shutil.ignore_patterns("__pycache__"))
        for rel in (".codex/skills/app-baseline/SKILL.md",
                    ".codex/skills/test-audit/SKILL.md", ".codex/skills/test-audit/NOTICE.md",
                    ".codex/skills/forge/fde.md", ".claude/skills/remote-approval/SKILL.md"):
            (old_src / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, old_src / rel)
        shutil.copyfile(ROOT / "tests/fixtures/worker-brief-before-delegation.md",
                        old_src / "src/forge/templates/brief.md")
        worker = old_src / "src/forge/worker.py"
        old_rule = (ROOT / "tests/fixtures/worker-review-loop-before-choice-clarification.txt").read_text(
            "utf-8")
        worker.write_text(re.sub(r"REVIEW_LOOP = \(.*?\)\n", lambda _: old_rule,
                                 worker.read_text("utf-8"), count=1, flags=re.S), encoding="utf-8")
        _install(env.repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=str(old_src / "src")))
    try:
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
    finally:
        command.write_text(current_command, encoding="utf-8")
    # The old unconditional wait made each finding look like a fresh choice.
    # This is a delivered prompt contract; the host stub only captures its input.
    rule = ("Wait for a recorded choice only after close has stopped the review loop. "
            "Otherwise, fix the findings in this round, including new findings after a recorded "
            "narrow or split; do not ask for another choice unless close stops the loop again.")
    first = calls(log)[-1]
    assert (rule in " ".join(first["brief"].split())) == (not previous)
    if previous:
        synced = env.repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    resumed = env.repo.forge("work", item)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    call = calls(log)[-1]
    assert "--resume" in call["args"]
    assert (call["args"][call["args"].index("--resume") + 1]
            == first["args"][first["args"].index("--session-id") + 1])
    assert "The earlier brief in this conversation still applies." in call["brief"]
    assert rule in " ".join(call["brief"].split())
