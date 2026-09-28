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
    # A client repo's user-facing task runs on design Claude even with Codex workers.
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
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


def test_3_a_failed_resume_keeps_its_session_and_two_in_a_row_start_fresh_saying_why(
        repo, gh, monkeypatch, tmp_path):
    log = _started(repo)
    assert repo.forge("work", FIX).returncode == 0
    first = _session(calls(log)[0], "--session-id")

    # Claude accepts the resume, then its turn fails: the round fails and the session is kept.
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    failed = repo.forge("work", FIX)
    monkeypatch.delenv("STUB_CLAUDE_EXIT")

    assert failed.returncode != 0
    [_, resumed] = calls(log)
    assert _session(resumed, "--resume") == first and EARLIER in resumed["brief"]
    assert FRESH not in failed.stdout

    # The next forge work resumes the same session again with the short prompt.
    again = repo.forge("work", FIX)

    assert again.returncode == 0, again.stdout + again.stderr
    [*_, resumed] = calls(log)
    assert _session(resumed, "--resume") == first and "--session-id" not in resumed["args"]
    assert EARLIER in resumed["brief"] and "# Worker brief" not in resumed["brief"]
    assert FRESH not in again.stdout

    # Two failed resumes in a row, here Claude having lost the session: the next round starts a
    # new session with the whole brief and says why.
    (repo.bin / "claude-sessions.json").unlink()
    assert repo.forge("work", FIX).returncode != 0
    assert repo.forge("work", FIX).returncode != 0
    assert [_session(call, "--resume") for call in calls(log)[-2:]] == [first, first]

    lost = repo.forge("work", FIX)

    assert lost.returncode == 0, lost.stdout + lost.stderr
    [*_, fresh] = calls(log)
    assert len(calls(log)) == 6 and "--resume" not in fresh["args"]
    second = _session(fresh, "--session-id")
    assert second != first
    assert "# Worker brief" in fresh["brief"] and EARLIER not in fresh["brief"]
    # The new session keeps the item's round count.
    assert fresh["brief"].startswith("Fix round 6 on Fix the login typo.")
    assert (f"{FRESH}Claude couldn't continue session {first} in two rounds in a row."
            in lost.stdout)

    # A success resets the count: one more failed resume keeps the new session.
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    assert repo.forge("work", FIX).returncode != 0
    monkeypatch.delenv("STUB_CLAUDE_EXIT")
    kept = repo.forge("work", FIX)

    assert kept.returncode == 0, kept.stdout + kept.stderr
    [*_, resumed] = calls(log)
    assert _session(resumed, "--resume") == second and FRESH not in kept.stdout

    # A checkout moved since its session started: the session is left alone and a new one starts.
    folder = Path(fresh["cwd"])
    moved = tmp_path / "moved-checkout"
    repo.git("worktree", "move", str(folder), str(moved))

    elsewhere = repo.forge("work", FIX)

    assert elsewhere.returncode == 0, elsewhere.stdout + elsewhere.stderr
    [*_, restarted] = calls(log)
    assert len(calls(log)) == 9 and "--resume" not in restarted["args"]
    assert _session(restarted, "--session-id") not in (first, second)
    assert Path(restarted["cwd"]).resolve() == moved.resolve()
    assert restarted["brief"].startswith("Fix round 9 on Fix the login typo.")
    assert "# Worker brief" in restarted["brief"]
    assert (f"{FRESH}its session was started in another checkout, {folder}"
            in elsewhere.stdout)


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
