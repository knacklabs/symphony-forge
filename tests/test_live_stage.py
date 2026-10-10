"""Live or prototype is one forge.toml setting, and every prototype rule reads it."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from test_close import CLEAN, GREEN, env  # noqa: F401  (env is a fixture)
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401  (sdk_data is a fixture)
from test_setup import _fresh_client
from test_story import DOC, GRILL, claude_plan, hook, ready, setup
from test_worker import calls, install_claude

STORY = "FORGE-LIVE-1"
GATE = ("Stories wait for the customer's sign-off. Build and demo the prototype first.\n"
        "Next: forge next\n")
SIGNOFF = '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n\n# The client signed off\n'


def _setup(repo, lines: str) -> None:
    """test_story's setup with the stub reader, then forge.toml with these lines."""
    setup(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\n{lines}{GRILL}')
    repo.git("commit", "-q", "-am", "Set the stage")
    repo.git("push", "-q", "origin", "main")


def _story(repo, key: str = "SHOP"):
    return repo.forge("story", "new", key, "Shoppers can save a basket")


@pytest.mark.parametrize("case, lines, gated", [
    ("prototype", 'repo = "client"\nstage = "prototype"\n', True),
    ("live", 'repo = "client"\nstage = "live"\n', False),
    ("unset", 'repo = "client"\n', False),  # a client repo without the setting counts as live
    ("forge-source", 'repo = "forge-source"\nstage = "prototype"\n', False),  # never Forge's own
    ("signed off", 'repo = "client"\nstage = "prototype"\n', False),
    ("other stage", 'repo = "client"\nstage = "beta"\n', True),
    ("init", "", False),
])
def test_1_live_or_prototype_is_one_setting(repo, gh, tmp_path, case, lines, gated):
    if case == "init":  # forge init in an empty repo starts a prototype
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        assert re.search(r'^stage = "prototype"$', (client / "forge.toml").read_text("utf-8"), re.M)
        return
    _setup(repo, lines)
    if case == "signed off":
        repo.write("docs/decisions/0001-client-signoff.md", SIGNOFF)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "The client signed off")
        repo.git("push", "-q", "origin", "main")
    made = _story(repo)
    if case == "other stage":
        assert made.returncode == 1
        assert made.stderr.startswith(
            "forge.toml is not usable: stage must be one of live, prototype.\n"), made.stderr
        return
    assert (made.returncode, made.stderr) == ((1, GATE) if gated else (0, "")), made.stderr


@pytest.mark.parametrize("rule", ["story and approval", "close and merge", "design routing"])
def test_2_live_repo_gets_no_prototype_rules(request, repo, rule):
    """In a live repo a story is created and approved, and no prototype rule applies."""
    if rule == "story and approval":
        _setup(repo, 'repo = "client"\nstage = "live"\n')
        ready(repo, "SHOP")  # the story gate lets it through with no sign-off on record
        assert "sign-off" not in repo.forge("next").stdout  # forge next's approval step
        recorded = hook(repo, claude_plan(request.getfixturevalue("claude_payload"), DOC))
        assert recorded.returncode == 0, recorded.stderr
        assert "Next: forge task start SHOP/SAVE" in repo.forge("next").stdout
        # The fix allowance: a fix starts with no prototype allowance.
        started = repo.forge("fix", "start", "Tidy the readme", "--done", "The readme is tidy")
        assert started.returncode == 0, started.stderr
        fix = Path(re.search(r" in (.+)\n", started.stdout)[1])
        assert "allow_large" not in json.loads(
            (fix / ".factory/fixes/tidy-the-readme.json").read_text("utf-8"))
        # forge next's prototype notices: no open sign-off topics.
        assert "Open before sign-off" not in repo.forge("next").stdout
    elif rule == "close and merge":
        forge = request.getfixturevalue("env")
        toml = forge.repo.path / "forge.toml"
        forge.commit(forge.repo.path, "forge.toml", toml.read_text("utf-8")
                     + 'repo = "client"\nstage = "live"\n'
                     + '[models.review]\nmodel = "gpt-6-astra"\neffort = "high"\n')
        forge.repo.git("push", "-q", "origin", "main")
        # Even a fix carrying the prototype allowance gets the full review in a live repo.
        item, where = forge.start_fix(allow_large="Prototype before sign-off")
        forge.open_pr("")
        forge.checks(GREEN)
        forge.reviews(CLEAN)
        closed = forge.close(item)
        assert closed.returncode == 0, closed.stderr
        [call] = forge.review_calls()
        options = dict(zip(call["args"][::2], call["args"][1::2]))
        assert (options["--engine"], options["--max-priority"]) == ("codex", "P3")
        assert "--model" not in options and "--thinking" not in options
        # The agent merge before sign-off: a human merges a live repo's pull requests.
        assert closed.stdout.splitlines()[-1] == (
            f"Ready: {item} has a clean review and green checks. A human merges its pull request.")
        denied = forge.repo.forge("merge", item, cwd=where)
        assert denied.returncode != 0
        assert 'forge merge is disabled by merge = "human"' in denied.stderr
    else:
        # _codex_repo's client forge.toml has no stage, so the repo is live.
        _, codex_log = _codex_repo(repo, request.getfixturevalue("monkeypatch"),
                                   request.getfixturevalue("sdk_data"), client=True)
        claude_log = install_claude(repo)
        assert repo.forge("fix", "start", "Fix the login typo", "--done", "It says Log in").returncode == 0
        state_file = repo.path.parent / "repo-fix-fix-the-login-typo/.factory/fixes/fix-the-login-typo.json"
        state = json.loads(state_file.read_text("utf-8"))
        assert "allow_large" not in state
        state["allow_large"] = "Prototype before sign-off"  # even a fix carrying the old allowance
        state_file.write_text(json.dumps(state), encoding="utf-8")
        worked = repo.forge("work", "fix-the-login-typo")
        assert worked.returncode == 0, worked.stdout + worked.stderr
        assert len(_sent(codex_log, "turn/start")) == 1  # the configured Codex worker, not design
        assert calls(claude_log) == []
