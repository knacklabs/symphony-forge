"""A Claude worker's fix round continues the session its first round started, like a Codex worker's
conversation, and starts fresh with the whole brief, saying why, when it can't."""
from __future__ import annotations

import uuid
from pathlib import Path

from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401 (sdk_data is a fixture)
from test_worker import calls, install_claude

STORY = "claude-workers-start-a-fresh-session-eve"
FIX = "fix-the-login-typo"
EARLIER = "The earlier brief in this conversation still applies."
FRESH = "Starting a new Claude session with the whole brief, because "


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
    assert FRESH not in again.stdout


def test_2_a_design_claude_worker_continues_its_session_with_the_short_prompt(
        repo, monkeypatch, sdk_data):
    # A client repo's user-facing task runs on design Claude with split workers (once "even with
    # Codex workers"; workers = codex now builds it on Codex).
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    config = folder / "forge.toml"
    config.write_text(config.read_text("utf-8").replace('workers = "codex"', 'workers = "split"'),
                      encoding="utf-8")
    # Committed: a round that ends with changes uncommitted gets a second, commit-nudge turn.
    repo.git("commit", "-qam", "Use split workers", cwd=folder)
    log = install_claude(repo)

    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr
    [built] = calls(log)
    session = _session(built, "--session-id")
    assert "# Worker brief" in built["brief"] and "| PAGE | The page |" in built["brief"]

    again = repo.forge("work", "BOARD/PAGE", "--note", "Make the heading bigger.")

    assert again.returncode == 0, again.stdout + again.stderr
    [_, fixed] = calls(log)
    assert _session(fixed, "--resume") == session and "--session-id" not in fixed["args"]
    assert fixed["cwd"] == str(folder) and fixed["args"][:3] == ["-p", "--model", "claude-opus-5-5"]
    assert EARLIER in fixed["brief"] and "Make the heading bigger." in fixed["brief"]
    assert "# Worker brief" not in fixed["brief"]
    assert FRESH not in again.stdout
    assert _sent(codex_log, "turn/start") == []


def test_3_a_resume_claude_rejects_starts_fresh_in_the_same_round_saying_why(repo, gh, tmp_path):
    log = _started(repo)
    assert repo.forge("work", FIX).returncode == 0
    first = _session(calls(log)[0], "--session-id")
    # Claude has lost the session, as after its own history was cleared.
    (repo.bin / "claude-sessions.json").unlink()

    lost = repo.forge("work", FIX)

    # The same forge work starts a new session with the whole brief and says why.
    assert lost.returncode == 0, lost.stdout + lost.stderr
    [_, rejected, fresh] = calls(log)
    assert _session(rejected, "--resume") == first
    assert "--resume" not in fresh["args"]
    second = _session(fresh, "--session-id")
    assert second != first
    assert "# Worker brief" in fresh["brief"] and EARLIER not in fresh["brief"]
    assert fresh["brief"].startswith("Fix round 2 on Fix the login typo.")
    assert f"{FRESH}Claude no longer has session {first}." in lost.stdout

    # The next round continues the new session with the short prompt.
    kept = repo.forge("work", FIX)

    assert kept.returncode == 0, kept.stdout + kept.stderr
    [*_, resumed] = calls(log)
    assert len(calls(log)) == 4 and _session(resumed, "--resume") == second
    assert resumed["brief"].startswith("Fix round 3 on Fix the login typo.")
    assert EARLIER in resumed["brief"] and FRESH not in kept.stdout

    # A checkout moved since its session started: the session is left alone and a new one starts.
    folder = Path(fresh["cwd"])
    moved = tmp_path / "moved-checkout"
    repo.git("worktree", "move", str(folder), str(moved))

    elsewhere = repo.forge("work", FIX)

    assert elsewhere.returncode == 0, elsewhere.stdout + elsewhere.stderr
    [*_, restarted] = calls(log)
    assert len(calls(log)) == 5 and "--resume" not in restarted["args"]
    assert _session(restarted, "--session-id") not in (first, second)
    assert Path(restarted["cwd"]).resolve() == moved.resolve()
    assert restarted["brief"].startswith("Fix round 4 on Fix the login typo.")
    assert "# Worker brief" in restarted["brief"]
    assert (f"{FRESH}its session was started in another checkout, {folder}"
            in elsewhere.stdout)


def test_5_failed_turns_in_a_session_claude_still_has_keep_that_session(repo, gh, monkeypatch):
    log = _started(repo)
    assert repo.forge("work", FIX).returncode == 0
    first = _session(calls(log)[0], "--session-id")

    # Claude accepts the resume twice and both turns fail: each round fails and keeps the session.
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    for _ in range(2):
        failed = repo.forge("work", FIX)
        assert failed.returncode != 0
        assert FRESH not in failed.stdout
    monkeypatch.delenv("STUB_CLAUDE_EXIT")
    assert [_session(call, "--resume") for call in calls(log)[1:]] == [first, first]

    # The third round still continues the same session with the short prompt.
    again = repo.forge("work", FIX)

    assert again.returncode == 0, again.stdout + again.stderr
    [*_, resumed] = calls(log)
    assert len(calls(log)) == 4
    assert _session(resumed, "--resume") == first and "--session-id" not in resumed["args"]
    assert EARLIER in resumed["brief"] and "# Worker brief" not in resumed["brief"]
    assert FRESH not in again.stdout


def test_4_a_round_without_forge_s_local_session_record_starts_fresh_and_says_so(repo, gh):
    log = _started(repo)
    assert repo.forge("work", FIX).returncode == 0
    # The item's committed state shows a round ran, but this machine has no record of its session,
    # as on another machine or after .git/forge was cleared.
    (repo.path / ".git" / "forge" / "threads" / "fix" / f"{FIX}.json").unlink()

    again = repo.forge("work", FIX)

    assert again.returncode == 0, again.stdout + again.stderr
    [first, fresh] = calls(log)
    assert "--resume" not in fresh["args"]
    assert _session(fresh, "--session-id") != _session(first, "--session-id")
    assert "# Worker brief" in fresh["brief"] and EARLIER not in fresh["brief"]
    assert (f"{FRESH}Forge has no record of its Claude session on this machine."
            in again.stdout)
