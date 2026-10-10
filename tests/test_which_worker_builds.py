"""forge.toml's workers says which tool builds what: codex, claude or split, through forge work
and forge next, with the stub Claude and the stub Codex app-server at their edges."""
from __future__ import annotations

import json
import os
import signal

import pytest

from test_codex_worker import QUIET, _codex_repo, _sent, _toml, sdk_data  # noqa: F401
from test_task import DOC, story
from test_worker import calls, install_claude

STORY = "FIX-WORKERS-SETTING"
CLAUDE_BUILD = {"build": {"model": "claude-sonnet-5", "effort": "medium"}}


def _workers(repo, folder, workers: str, models: dict | None = None) -> None:
    """Set the checkout's forge.toml to these workers, keeping the rest unless models are given."""
    config = folder / "forge.toml"
    text = config.read_text("utf-8")
    if models is not None:
        version = text.split('"', 2)[1]
        text = _toml(version, workers, models, "client")
    config.write_text(text.replace('workers = "codex"', f'workers = "{workers}"'),
                      encoding="utf-8")
    # Committed: a round that ends with changes uncommitted gets a second, commit-nudge turn.
    repo.git("commit", "-qam", f"Use {workers} workers", "--allow-empty", cwd=folder)


def _help(repo, workers: str, models: dict | None = None):
    started = repo.forge("task", "start", "BOARD/HELP")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = repo.path.parent / "repo-BOARD-HELP"
    _workers(repo, folder, workers, models)
    return folder


def test_1_workers_codex_builds_user_facing_and_plain_tasks_on_codex(repo, monkeypatch, sdk_data):
    _, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    page = repo.forge("work", "BOARD/PAGE")
    assert page.returncode == 0, page.stdout + page.stderr
    assert calls(claude_log) == []
    # User-facing work on Codex uses the design model's codex entry (its default here).
    assert _sent(codex_log, "thread/start")[-1]["config"] == {
        **QUIET, "features.multi_agent": True, "model": "gpt-6.1-sol", "model_reasoning_effort": "high",
        "agents.default_subagent_model": "gpt-6-luna",
        "agents.default_subagent_reasoning_effort": "max"}
    assert ("Building BOARD/PAGE with Codex (gpt-6.1-sol, high) because workers = codex, "
            "with the design model as it is user-facing") in page.stdout

    _help(repo, "codex")
    plain = repo.forge("work", "BOARD/HELP")
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert calls(claude_log) == []
    assert _sent(codex_log, "thread/start")[-1]["config"]["model"] == "gpt-6-sol"
    assert ("Building BOARD/HELP with Codex (gpt-6-sol, medium) because workers = codex"
            in plain.stdout)


def test_2_workers_split_builds_user_facing_on_claude_and_the_rest_on_codex(repo, monkeypatch,
                                                                          sdk_data):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    _workers(repo, folder, "split")
    page = repo.forge("work", "BOARD/PAGE")
    assert page.returncode == 0, page.stdout + page.stderr
    [call] = calls(claude_log)
    assert call["args"][:5] == ["-p", "--model", "claude-sonnet-5-5", "--effort", "xhigh"]
    assert _sent(codex_log, "turn/start") == []
    assert ("Building BOARD/PAGE with Claude (claude-sonnet-5-5, xhigh) because it is user-facing "
            "(workers = split)") in page.stdout

    _help(repo, "split")
    plain = repo.forge("work", "BOARD/HELP")
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert len(calls(claude_log)) == 1
    assert len(_sent(codex_log, "turn/start")) == 1
    assert ("Building BOARD/HELP with Codex (gpt-6-sol, medium) because it isn't user-facing "
            "(workers = split)") in plain.stdout


def test_3_workers_claude_builds_user_facing_and_plain_tasks_on_claude(repo, monkeypatch, sdk_data):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    _workers(repo, folder, "claude", CLAUDE_BUILD)
    page = repo.forge("work", "BOARD/PAGE")
    assert page.returncode == 0, page.stdout + page.stderr
    assert calls(claude_log)[-1]["args"][:5] == ["-p", "--model", "claude-sonnet-5-5",
                                                 "--effort", "xhigh"]
    assert ("Building BOARD/PAGE with Claude (claude-sonnet-5-5, xhigh) because workers = claude, "
            "with the design model as it is user-facing") in page.stdout

    _help(repo, "claude", CLAUDE_BUILD)
    plain = repo.forge("work", "BOARD/HELP")
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert calls(claude_log)[-1]["args"][:5] == ["-p", "--model", "claude-sonnet-5",
                                                 "--effort", "medium"]
    assert ("Building BOARD/HELP with Claude (claude-sonnet-5, medium) because workers = claude"
            in plain.stdout)
    assert _sent(codex_log, "turn/start") == []


def test_4_forge_next_shows_the_worker_beside_each_ready_task(repo, monkeypatch, sdk_data):
    folder, _ = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    # PAGE is started, so make a ready task user-facing too.
    story(repo, doc=DOC.replace("| `tests/test_api.py` | none | no |",
                                "| `tests/test_api.py` | none | yes |"))
    # forge next finds the story where it has landed, and tasks start from there.
    repo.git("merge", "-q", "--no-edit", "story/BOARD")
    repo.git("push", "-q", "origin", "main")
    config = repo.path / "forge.toml"
    for workers, style, plain in (("codex", "Codex", "Codex"), ("split", "Claude", "Codex"),
                                  ("claude", "Claude", "Claude")):
        before = config.read_text("utf-8")
        config.write_text(before.replace('workers = "codex"', f'workers = "{workers}"'),
                          encoding="utf-8")
        repo.git("commit", "-qam", f"Use {workers} workers", "--allow-empty")
        repo.git("push", "-q", "origin", "main")
        shown = repo.forge("next").stdout
        assert f"Next: forge task start BOARD/API  # {style} builds it" in shown, shown
        assert f"Next: forge task start BOARD/HELP  # {plain} builds it" in shown, shown
        config.write_text(before, encoding="utf-8")
        repo.git("commit", "-qam", "Back to codex workers", "--allow-empty")
        repo.git("push", "-q", "origin", "main")

    # Run from PAGE's checkout set to Claude, forge next still names the worker the default
    # branch's settings give a task started from there: Codex.
    _workers(repo, folder, "claude")
    shown = repo.forge("next", cwd=folder).stdout
    assert "Next: forge task start BOARD/HELP  # Codex builds it" in shown, shown


def test_5_a_family_switch_between_rounds_starts_fresh_with_the_brief_and_findings(
        repo, monkeypatch, sdk_data):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    _workers(repo, folder, "split")
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr
    assert len(calls(claude_log)) == 1

    state_file = folder / ".factory" / "stories" / "BOARD" / "tasks" / "PAGE.json"
    state = json.loads(state_file.read_text("utf-8"))
    state["review"] = {"status": "blocked", "findings": [
        {"priority": "P1", "title": "Board misses a story", "body": "List every story.",
         "file": "web/board.py", "line": 1}]}
    state_file.write_text(json.dumps(state), encoding="utf-8")

    # Claude to Codex: a new Codex conversation with the whole brief and the finding.
    (folder / "forge.toml").write_text((folder / "forge.toml").read_text("utf-8").replace(
        'workers = "split"', 'workers = "codex"'), encoding="utf-8")
    repo.git("commit", "-qam", "Switch workers", cwd=folder)
    to_codex = repo.forge("work", "BOARD/PAGE")
    assert to_codex.returncode == 0, to_codex.stdout + to_codex.stderr
    assert ("Starting a new Codex conversation, because its last round ran on Claude"
            in to_codex.stdout)
    assert _sent(codex_log, "thread/resume") == []
    [turn] = _sent(codex_log, "turn/start")
    sent = turn["input"][0]["text"]
    assert "## Tests first" in sent and "Board misses a story" in sent

    # Codex back to Claude: Claude's earlier session is not resumed; a new one gets it all.
    (folder / "forge.toml").write_text((folder / "forge.toml").read_text("utf-8").replace(
        'workers = "codex"', 'workers = "split"'), encoding="utf-8")
    repo.git("commit", "-qam", "Switch workers", cwd=folder)
    to_claude = repo.forge("work", "BOARD/PAGE")
    assert to_claude.returncode == 0, to_claude.stdout + to_claude.stderr
    assert ("Starting a new Claude session with the whole brief, because its last round ran on "
            "Codex") in to_claude.stdout
    last = calls(claude_log)[-1]
    assert "--resume" not in last["args"] and "--session-id" in last["args"]
    assert "## Tests first" in last["brief"] and "Board misses a story" in last["brief"]


def test_6_workers_claude_never_falls_back_to_codex(repo, monkeypatch, sdk_data):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    _workers(repo, folder, "claude")
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    failed = repo.forge("work", "BOARD/PAGE")
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "exit code 3" in failed.stderr
    assert "fell back to Codex" not in failed.stdout
    assert len(calls(claude_log)) == 1
    assert _sent(codex_log, "turn/start") == []


def test_7_the_launch_line_names_the_default_models_a_worker_runs_with(repo, monkeypatch,
                                                                     sdk_data):
    # Earlier settings name only gpt models: omitted Claude entries now use Sonnet at xhigh.
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    _help(repo, "claude")
    plain = repo.forge("work", "BOARD/HELP")
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert calls(claude_log)[-1]["args"][:5] == ["-p", "--model", "claude-sonnet-5-5",
                                                 "--effort", "xhigh"]
    assert ("Building BOARD/HELP with Claude (claude-sonnet-5-5, xhigh) because workers = claude"
            in plain.stdout)

    # Codex with no models at all runs, and names, Forge's Codex default.
    help_folder = repo.path.parent / "repo-BOARD-HELP"
    _workers(repo, help_folder, "codex", {})
    again = repo.forge("work", "BOARD/HELP")
    assert again.returncode == 0, again.stdout + again.stderr
    assert _sent(codex_log, "thread/start")[-1]["config"] == {
        **QUIET, "features.multi_agent": True, "model": "gpt-6.1-sol", "model_reasoning_effort": "medium"}
    assert ("Building BOARD/HELP with Codex (gpt-6.1-sol, medium) because workers = codex"
            in again.stdout)


def test_8_a_fallback_after_a_claude_round_starts_codex_fresh_with_the_brief_and_findings(
        repo, monkeypatch, sdk_data):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    # A Codex round, then a Claude round under split.
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    _workers(repo, folder, "split")
    on_claude = repo.forge("work", "BOARD/PAGE")
    assert on_claude.returncode == 0, on_claude.stdout + on_claude.stderr
    assert len(calls(claude_log)) == 1

    state_file = folder / ".factory" / "stories" / "BOARD" / "tasks" / "PAGE.json"
    state = json.loads(state_file.read_text("utf-8"))
    state["review"] = {"status": "blocked", "findings": [
        {"priority": "P1", "title": "Board misses a story", "body": "List every story.",
         "file": "web/board.py", "line": 1}]}
    state_file.write_text(json.dumps(state), encoding="utf-8")
    repo.git("commit", "-qam", "Review findings", cwd=folder)

    # Claude fails cleanly, so split falls back to Codex: a new conversation, not the first one.
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    fell = repo.forge("work", "BOARD/PAGE")
    assert fell.returncode == 0, fell.stdout + fell.stderr
    assert "fell back to Codex" in fell.stdout
    assert ("Starting a new Codex conversation, because its last round ran on Claude"
            in fell.stdout)
    assert _sent(codex_log, "thread/resume") == []
    assert len(_sent(codex_log, "thread/start")) == 2
    sent = _sent(codex_log, "turn/start")[-1]["input"][0]["text"]
    assert "## Tests first" in sent and "Board misses a story" in sent


@pytest.mark.skipif(os.name == "nt", reason="no Ctrl-C to send a process there")
def test_10_a_codex_start_cut_short_after_a_claude_round_leaves_the_retry_fresh(
        repo, monkeypatch, sdk_data):
    from test_codex_record import _held

    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    # A Codex round, then a Claude round.
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    _workers(repo, folder, "split")
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert len(calls(claude_log)) == 1

    # Back on Codex, the app-server never finishes starting; the round is stopped before any
    # conversation exists, as a start that times out is.
    (folder / "forge.toml").write_text((folder / "forge.toml").read_text("utf-8").replace(
        'workers = "split"', 'workers = "codex"'), encoding="utf-8")
    repo.git("commit", "-qam", "Back to Codex", cwd=folder)
    record = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD" / "PAGE.json"
    work, _, _ = _held(repo, codex_log, record, "stall")
    work.send_signal(signal.SIGINT)
    work.communicate(timeout=60)

    # The retry starts a new conversation with the whole brief, not the first Codex one.
    retry = repo.forge("work", "BOARD/PAGE")
    assert retry.returncode == 0, retry.stdout + retry.stderr
    assert _sent(codex_log, "thread/resume") == []
    assert len(_sent(codex_log, "thread/start")) == 2
    assert "## Tests first" in _sent(codex_log, "turn/start")[-1]["input"][0]["text"]


def test_9_forge_next_names_the_default_branch_s_worker_for_a_task_after_another_story(
        repo, claude_payload):
    from test_after_another_story_task import _plans
    from test_story import worktree

    _plans(repo, claude_payload, "TURN-1/T4")
    # The story branch says Claude; the default branch keeps Codex (no workers line).
    shop = worktree(repo, "story/SHOP")
    config = shop / "forge.toml"
    config.write_text(config.read_text("utf-8") + 'workers = "claude"\n', encoding="utf-8")
    repo.git("commit", "-qam", "Claude workers for SHOP", cwd=shop)
    assert repo.forge("task", "start", "TURN-1/T4").returncode == 0
    turn = worktree(repo, "task/TURN-1-T4")
    (turn / "src").mkdir()
    (turn / "src" / "turn.py").write_text("TURNS = 1\n", encoding="utf-8")
    repo.git("add", "-A", cwd=turn)
    repo.git("commit", "-q", "-m", "Save turns", cwd=turn)
    repo.git("merge", "-q", "--no-ff", "-m", "Save turns (#1)", "task/TURN-1-T4")
    repo.git("push", "-q", "origin", "main")

    # SAVE comes after another story's task, so task start branches it from the default branch.
    shown = repo.forge("next").stdout
    assert "Next: forge task start SHOP/SAVE  # Codex builds it" in shown, shown
    assert repo.forge("task", "start", "SHOP/SAVE").returncode == 0
    started = worktree(repo, "task/SHOP-SAVE")
    assert 'workers = "claude"' not in (started / "forge.toml").read_text("utf-8")
