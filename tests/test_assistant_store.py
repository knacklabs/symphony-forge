"""The copied TypeScript assistant erases inactive chats and checkpoint copies."""
import json
import shutil
from pathlib import Path

import pytest

from assistant_copy import copy_assistant
from test_agent_ready import _new_client
from test_starter_tree import LIVE, _require_cases, _run_live_starter

STORY = "FORGE-ASSIST-1"


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_4_expired_chats_are_deleted(repo, gh, tmp_path, tmp_path_factory):
    # Audit: retention includes the owner row, checkpoint blobs and pending writes.
    # A wrong cutoff, missing checkpoint erase or stale activity time breaks it.
    # No existing case owns optional chat retention. The requested public cleanup
    # method accepts time in production, so no production test seam is needed.
    client = _new_client(repo, gh, tmp_path)
    assert not (client / "libs/assistant").exists()
    # GUIDE owns delivery through init/sync. Stage this part's source template
    # so its storage proof can run before GUIDE ships, without a production seam.
    shutil.copytree(
        Path(__file__).resolve().parents[1]
        / "src/forge/templates/skills/agents/assistant-module/typescript",
        client / ".codex/skills/agents/assistant-module/typescript",
        dirs_exist_ok=True,
    )
    copy_assistant(client)
    if not LIVE:
        return

    # Run the copied module's API cases, with the existing build, browser checks,
    # isolated host configuration and process cleanup. TSCHAT owns all-API proof.
    package = client / "package.json"
    data = json.loads(package.read_text(encoding="utf-8"))
    data["scripts"]["test:api"] += " apps/api/test/assistant-chats.e2e-spec.ts"
    package.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    script = client / "scripts/test.mjs"
    script.write_text(script.read_text(encoding="utf-8").replace(
        "['pnpm', 'install', '--frozen-lockfile']", "['pnpm', 'install']",
    ), encoding="utf-8")
    result = _run_live_starter(tmp_path_factory, [(client, Path('.'))])
    _require_cases(result["api"], (
        "a chat 31 days after its last message is deleted with its checkpoints",
        "a chat 29 days after its last message stays",
        "a new message moves the 30 days",
    ))
