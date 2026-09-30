"""forge sync pre-allows Claude's tools in .claude/settings.json, since Claude ignores a repo-level
bypass mode, and keeps the deny hook in front of them."""
from __future__ import annotations

import json
import subprocess

from test_setup import _on_a_branch_with_forge_toml

STORY = "claude-code-sessions-in-client-repos-ask"
TOOLS = ["Bash", "Edit", "Write", "WebFetch", "WebSearch"]


def test_1_sync_merges_the_allow_list_keeps_the_client_s_own_and_blocks_first(repo, claude_payload):
    _on_a_branch_with_forge_toml(repo)
    repo.write(".claude/settings.json", json.dumps({
        "model": "opus",
        "permissions": {"allow": ["Bash(ls)", "Edit"], "deny": ["Read(./.env)"],
                        "defaultMode": "acceptEdits"}}))

    first = repo.forge("sync")
    assert first.returncode == 0, first.stderr
    path = repo.path / ".claude/settings.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    # The client's entries and settings stay, in their order; each tool is allowed once.
    assert settings["model"] == "opus"
    assert settings["permissions"] == {
        "allow": ["Bash(ls)", "Edit", "Bash", "Write", "WebFetch", "WebSearch"],
        "deny": ["Read(./.env)"], "defaultMode": "acceptEdits"}

    synced = path.read_text(encoding="utf-8")
    second = repo.forge("sync")
    assert second.returncode == 0, second.stderr
    assert path.read_text(encoding="utf-8") == synced
    assert "Wrote .claude/settings.json" not in second.stdout

    # The deny hook still guards every Bash command, so a destructive one is blocked before
    # the allow list is consulted.
    [guard] = [hook["command"] for group in settings["hooks"]["PreToolUse"]
               if group.get("matcher") == "Bash" for hook in group["hooks"]]
    payload = claude_payload("PreToolUse", "Bash", {"command": "rm -rf build"})
    blocked = subprocess.run(guard, shell=True, cwd=repo.path, input=json.dumps(payload),
                             capture_output=True, text=True, timeout=60)
    assert blocked.returncode == 2 and blocked.stderr.startswith('Forge blocks "')


def test_2_sync_allows_the_tools_in_a_repo_with_no_settings(repo):
    _on_a_branch_with_forge_toml(repo)
    assert repo.forge("sync").returncode == 0
    settings = json.loads((repo.path / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["permissions"] == {"allow": TOOLS}
