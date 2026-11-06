"""The copied Python assistant removes expired chats and checkpoints."""

import ast
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

    # The copied app still checks every table's schema. Extending that inventory
    # is a copy contract: without it the existing full-suite case rejects the
    # optional module's five tables. Keep every original starter entry too.
    inventories = []
    for path in (
        Path(__file__).resolve().parents[1]
        / "src/forge/templates/starter-python/apps/api/tests/test_module_schemas.py",
        client / "apps/api/tests/test_module_schemas.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        inventory = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "EXPECTED_TABLE_SCHEMAS"
                for target in node.targets
            )
        )
        inventories.append(ast.literal_eval(inventory))
    assert inventories[1] == (
        "assistant.chat",
        "assistant.checkpoint_blobs",
        "assistant.checkpoint_migrations",
        "assistant.checkpoint_writes",
        "assistant.checkpoints",
        *inventories[0],
    )

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
