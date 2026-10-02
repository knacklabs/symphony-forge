"""forge.toml's workers says which tool builds what: codex, claude or split, through forge work
and forge next, with the stub Claude and the stub Codex app-server at their edges."""
from __future__ import annotations

import json

from test_codex_worker import _codex_repo, _sent, _toml, sdk_data  # noqa: F401
from test_task import DOC, story
from test_worker import calls, install_claude

STORY = "FIX-WORKERS-SETTING"
CLAUDE_BUILD = {"build": {"model": "claude-sonnet-5", "effort": "medium"}}


def _workers(folder, workers: str, models: dict | None = None) -> None:
    """Set the checkout's forge.toml to these workers, keeping the rest unless models are given."""
    config = folder / "forge.toml"
    text = config.read_text("utf-8")
    if models is not None:
        version = text.split('"', 2)[1]
        text = _toml(version, workers, models, "client")
    config.write_text(text.replace('workers = "codex"', f'workers = "{workers}"'),
                      encoding="utf-8")


def _help(repo, workers: str, models: dict | None = None):
    started = repo.forge("task", "start", "BOARD/HELP")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = repo.path.parent / "repo-BOARD-HELP"
    _workers(folder, workers, models)
    return folder


def test_1_workers_codex_builds_user_facing_and_plain_tasks_on_codex(repo, monkeypatch, sdk_data):
    _, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    page = repo.forge("work", "BOARD/PAGE")
    assert page.returncode == 0, page.stdout + page.stderr
    assert calls(claude_log) == []
    # User-facing work on Codex uses the design model's codex entry (its default here).
    assert _sent(codex_log, "thread/start")[-1]["config"] == {
        "model": "gpt-6.1-sol", "model_reasoning_effort": "high"}
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
    _workers(folder, "split")
    page = repo.forge("work", "BOARD/PAGE")
    assert page.returncode == 0, page.stdout + page.stderr
    [call] = calls(claude_log)
    assert call["args"][:5] == ["-p", "--model", "claude-opus-5-5", "--effort", "high"]
    assert _sent(codex_log, "turn/start") == []
    assert ("Building BOARD/PAGE with Claude (claude-opus-5-5, high) because it is user-facing "
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
    _workers(folder, "claude", CLAUDE_BUILD)
    page = repo.forge("work", "BOARD/PAGE")
    assert page.returncode == 0, page.stdout + page.stderr
    assert calls(claude_log)[-1]["args"][:5] == ["-p", "--model", "claude-opus-5-5",
                                                 "--effort", "high"]
    assert ("Building BOARD/PAGE with Claude (claude-opus-5-5, high) because workers = claude, "
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
    _codex_repo(repo, monkeypatch, sdk_data, client=True)
    # PAGE is started, so make a ready task user-facing too.
    story(repo, doc=DOC.replace("| `tests/test_api.py` | none | no |",
                                "| `tests/test_api.py` | none | yes |"))
    # forge next finds the story where it has landed.
    repo.git("merge", "-q", "--no-edit", "story/BOARD")
    repo.git("push", "-q", "origin", "main")
    config = repo.path / "forge.toml"
    for workers, style, plain in (("codex", "Codex", "Codex"), ("split", "Claude", "Codex"),
                                  ("claude", "Claude", "Claude")):
        config.write_text(config.read_text("utf-8").replace('workers = "codex"',
                                                            f'workers = "{workers}"'),
                          encoding="utf-8")
        shown = repo.forge("next").stdout
        assert f"Next: forge task start BOARD/API  # {style} builds it" in shown, shown
        assert f"Next: forge task start BOARD/HELP  # {plain} builds it" in shown, shown
        config.write_text(config.read_text("utf-8").replace(f'workers = "{workers}"',
                                                            'workers = "codex"'),
                          encoding="utf-8")


def test_5_a_family_switch_between_rounds_starts_fresh_with_the_brief_and_findings(
        repo, monkeypatch, sdk_data):
    folder, codex_log = _codex_repo(repo, monkeypatch, sdk_data, client=True)
    claude_log = install_claude(repo)
    _workers(folder, "split")
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
    to_claude = repo.forge("work", "BOARD/PAGE")
    assert to_claude.returncode == 0, to_claude.stdout + to_claude.stderr
    assert ("Starting a new Claude session with the whole brief, because its last round ran on "
            "Codex") in to_claude.stdout
    last = calls(claude_log)[-1]
    assert "--resume" not in last["args"] and "--session-id" in last["args"]
    assert "## Tests first" in last["brief"] and "Board misses a story" in last["brief"]
