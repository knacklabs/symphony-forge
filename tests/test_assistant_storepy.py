"""The copied Python assistant removes expired chats and checkpoints."""

import shutil
from pathlib import Path

import pytest

from assistant_copy_python import copy_assistant_python
from test_agent_ready import _new_client
from test_starter_tree import LIVE, _require_cases, _run_live_starter

STORY = "FORGE-ASSIST-1-PYSTORE"


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_4_python_expired_chats_are_deleted(repo, gh, tmp_path, tmp_path_factory):
    # Audit: this protects the copied module's real Postgres retention path,
    # including checkpoint copies and activity updates. No other case owns
    # optional chat storage, and delete_expired(now) is the requested public API.
    client = _new_client(repo, gh, tmp_path, "python")
    assert not (client / "apps/api/app/assistant").exists()
    template = (
        Path(__file__).resolve().parents[1]
        / "src/forge/templates/skills/agents/assistant-module/python"
    )
    skill_copy = client / ".codex/skills/agents/assistant-module/python"
    shutil.copytree(template, skill_copy, dirs_exist_ok=True)
    copy_assistant_python(client)
    assert (client / "apps/api/app/assistant").is_dir()

    if not LIVE:
        return
    script = client / "scripts/test.mjs"
    text = script.read_text(encoding="utf-8")
    sync = "  run('uv', ['--directory', 'apps/api', 'sync', '--frozen']);"
    if text.count(sync) != 1:
        raise AssertionError(f"copy step did not match one lock command in {script}")
    script.write_text(
        text.replace(
            sync,
            "  run('uv', ['--directory', 'apps/api', 'lock']);\n" + sync,
        ),
        encoding="utf-8",
    )

    result = _run_live_starter(tmp_path_factory, [(client, Path("."))])
    _require_cases(
        result["api"],
        (
            "test_a_chat_31_days_after_its_last_message_is_deleted_with_its_checkpoints",
            "test_a_chat_29_days_after_its_last_message_stays",
            "test_a_new_message_moves_the_30_days",
        ),
    )
