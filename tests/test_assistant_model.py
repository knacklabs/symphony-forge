"""The TypeScript assistant model and spend cap ship as a copied module."""
import json
import shutil
from pathlib import Path

import pytest

from assistant_copy import copy_assistant
from test_assistant_chats import _run_assistant_app
from test_agent_ready import _new_client
from test_starter_tree import LIVE, _require_cases

STORY = "FORGE-ASSIST-1"


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_5_the_key_and_cap_come_from_settings(repo, gh, tmp_path, tmp_path_factory, monkeypatch):
    # Audit: protects the copied module's four model files and app-owned API test.
    # It fails if a file is omitted from the template or the README copy steps.
    # The store test checks chats only; this uses the copy path with no seam.
    client = _new_client(repo, gh, tmp_path)
    source = (
        Path(__file__).resolve().parents[1]
        / "src/forge/templates/skills/agents/assistant-module/typescript"
    )
    shutil.copytree(
        source,
        client / ".codex/skills/agents/assistant-module/typescript",
        dirs_exist_ok=True,
    )
    copy_assistant(client)

    required = (
        Path("libs/assistant/server/src/assistant.model.ts"),
        Path("libs/assistant/server/src/assistant.usage.ts"),
        Path("libs/assistant/server/src/assistant.prompt.ts"),
        Path("libs/assistant/server/src/assistant.guard.ts"),
        Path("apps/api/test/assistant-model.e2e-spec.ts"),
    )
    for path in required:
        assert (client / path).is_file(), f"copied assistant module is missing {path}"

    if not LIVE:
        return

    package = client / "package.json"
    data = json.loads(package.read_text(encoding="utf-8"))
    data["scripts"]["test:api"] += " apps/api/test/assistant-model.e2e-spec.ts"
    package.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    result = _run_assistant_app(client, tmp_path_factory, monkeypatch)
    _require_cases(result["api"], (
        "only the model file reads the provider key and the module contains no key",
        "missing required settings stop startup with a plain message",
        "the model uses the configured provider, key and address",
        "monthly spend stops at the cap and last month does not count",
        "the prompt stays within its UTF-8 byte budget and has a version",
        "the secret check finds labelled secrets and valid cards but not plain text",
    ))
