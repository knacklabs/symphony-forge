"""During an upgrade the default branch still carries the Codex hooks an earlier Forge release
wrote, and Codex reads the main checkout's hooks for every worktree. Forge recognizes each earlier
release's hooks as its own, so the upgrade's Codex worker starts with no review in Codex's /hooks.

The stub app-server lists the main checkout's .codex/hooks.json as Codex's hooks/list does."""
from __future__ import annotations

STORY = "old-hooks-are-forge"

import json
import shutil

import pytest

from conftest import ROOT
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401
from test_codex_turns_trust_forge_hooks import _listed, _trusted

ADOPTED = ROOT / "tests/fixtures/adopted-v1.2.2/client"
LAUNCHER = '. "$(git rev-parse --show-toplevel)/.forge/hooks.sh" && '


def _before_the_launcher(text: str) -> str:
    """The v1.0 to v1.2.1 hooks: the v1.2.2 ones without the launcher they source."""
    data = json.loads(text)
    for groups in data["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                assert LAUNCHER in hook["command"]
                hook["command"] = hook["command"].replace(LAUNCHER, "")
    return json.dumps(data, indent=2) + "\n"


@pytest.mark.parametrize("earlier", ["v1.2.1", "v1.2.2"])
def test_1_the_worker_starts_with_an_earlier_release_s_hooks_on_the_default_branch(
        repo, monkeypatch, sdk_data, claude_session, earlier):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    # The default branch as a client adopted on the earlier release has it.
    hooks_file = repo.path / ".codex" / "hooks.json"
    hooks_file.parent.mkdir(exist_ok=True)
    shutil.copyfile(ADOPTED / ".codex" / "hooks.json", hooks_file)
    if earlier == "v1.2.1":
        hooks_file.write_text(_before_the_launcher(hooks_file.read_text("utf-8")), "utf-8")
    repo.git("add", str(hooks_file))
    repo.git("commit", "-q", "-m", f"Forge {earlier}'s hooks")
    repo.git("push", "-q", "origin", "main")
    monkeypatch.setenv("STUB_CODEX_HOOK_TRUST", "modified")  # as after the upgrade changed them

    built = repo.forge("work", "BOARD/PAGE")

    assert built.returncode == 0, built.stdout + built.stderr
    assert {hook["sourcePath"] for hook in _listed(calls)} == {str(hooks_file)}
    assert {hook["eventName"] for hook in _listed(calls)} == {
        "sessionStart", "preCompact", "preToolUse", "postToolUse"}
    [start] = _sent(calls, "thread/start")
    assert start["config"]["hooks"] == _trusted(calls)
    assert len(_sent(calls, "turn/start")) == 1
    assert folder.is_dir()
