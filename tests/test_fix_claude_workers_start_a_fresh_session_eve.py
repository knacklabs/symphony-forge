"""A Claude worker's fix round continues the session its first round started, like a Codex worker's
conversation, and starts fresh with the whole brief, saying why, when it can't."""
from __future__ import annotations

import uuid
from pathlib import Path

from test_worker import calls, install_claude

STORY = "claude-workers-start-a-fresh-session-eve"
FIX = "fix-the-login-typo"
EARLIER = "The earlier brief in this conversation still applies."


def _started(repo) -> Path:
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             'workers = "claude"\ntest = "pytest -q"\n'
                             'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Fix the login typo", "--done", "The login page says Log in")
    assert started.returncode == 0, started.stderr
    return log


def _session(call: dict, flag: str) -> str:
    return str(uuid.UUID(call["args"][call["args"].index(flag) + 1]))


def test_1_a_claude_fix_round_continues_its_session_with_the_short_prompt(repo, gh):
    log = _started(repo)

    first = repo.forge("work", FIX)
    assert first.returncode == 0, first.stdout + first.stderr
    [built] = calls(log)
    session = _session(built, "--session-id")
    assert "--resume" not in built["args"]
    assert "# Worker brief" in built["brief"] and "Why: Fix the login typo" in built["brief"]

    again = repo.forge("work", FIX, "--note", "Use the word Log in, not Login.")

    assert again.returncode == 0, again.stdout + again.stderr
    [_, fixed] = calls(log)
    assert _session(fixed, "--resume") == session and "--session-id" not in fixed["args"]
    assert fixed["cwd"] == built["cwd"]
    brief = fixed["brief"]
    assert EARLIER in brief and "Use the word Log in, not Login." in brief
    assert "# Worker brief" not in brief and "## Standards" not in brief
    assert "## Since your last turn" in brief
    assert "Starting a new Claude session" not in again.stdout


def test_2_a_session_claude_cant_continue_starts_fresh_with_the_whole_brief_and_says_why(
        repo, gh, tmp_path):
    log = _started(repo)
    assert repo.forge("work", FIX).returncode == 0
    first = _session(calls(log)[0], "--session-id")
    # Claude has lost the session, as when its history was cleared.
    (repo.bin / "claude-sessions.json").unlink()

    lost = repo.forge("work", FIX)

    assert lost.returncode == 0, lost.stdout + lost.stderr
    [_, resumed, fresh] = calls(log)
    assert _session(resumed, "--resume") == first
    second = _session(fresh, "--session-id")
    assert second != first and "--resume" not in fresh["args"]
    assert "# Worker brief" in fresh["brief"] and EARLIER not in fresh["brief"]
    assert ("Starting a new Claude session with the whole brief, because Claude couldn't "
            f"continue session {first}: No conversation found with session ID: {first}") in lost.stdout

    # A checkout moved since its session started: the session is left alone and a new one starts.
    folder = Path(fresh["cwd"])
    moved = tmp_path / "moved-checkout"
    repo.git("worktree", "move", str(folder), str(moved))

    elsewhere = repo.forge("work", FIX)

    assert elsewhere.returncode == 0, elsewhere.stdout + elsewhere.stderr
    [*_, restarted] = calls(log)
    assert len(calls(log)) == 4 and "--resume" not in restarted["args"]
    assert _session(restarted, "--session-id") not in (first, second)
    assert Path(restarted["cwd"]).resolve() == moved.resolve()
    assert "# Worker brief" in restarted["brief"]
    assert ("Starting a new Claude session with the whole brief, because its session was started "
            f"in another checkout, {folder}") in elsewhere.stdout
