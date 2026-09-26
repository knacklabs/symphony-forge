"""Forge's contracts: refusals, third-party tools, both hosts, plain English, pull requests only, and
state only (spec criteria 3, 6, 7, 8, 9 and 25).

Each test is named test_<criterion>_<rule> after the spec's acceptance criterion it proves.
"""
from __future__ import annotations

import ast
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

import conftest
from test_approval import _digest
from test_board import seen as page_text
from test_close import PIN, body, env, finding, report, run  # noqa: F401 (env is a fixture)
from test_setup import _executable, _hook_commands, _version
from test_story import DOC, READER, claude_plan, codex_question, ready, setup, worktree
from test_codex_worker import _codex_repo, sdk_data  # noqa: F401 (sdk_data is a fixture)
from test_walkthrough import DOC as CART_DOC
from test_walkthrough import walk, with_models
from test_worker import calls, install_claude

STORY = "FORGE-NEXT-1"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "forge"


# --- criterion 3: every refusal is tested ---------------------------------------------------

# A refusal no cheap test can trigger, and why, in plain words.
UNTRIGGERED = {
    "cli.not_built": "every command in the table is built now, so nothing prints it; it guards a "
                     "command added to the table before its code",
}


def _refusals() -> dict[str, tuple[str, str]]:
    """Every refusal in src/forge's refusal tables, by module.key: (problem, next command)."""
    found = {}
    for path in sorted(SOURCE.glob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and [getattr(t, "id", "") for t in node.targets] == [
                    "REFUSALS"]:
                for key, value in zip(node.value.keys, node.value.values):
                    found[f"{path.stem}.{key.value}"] = ast.literal_eval(value)
    return found


def _expected() -> list[str]:
    """Every text the tests expect: each string, and each f-string with its values left out."""
    texts = []
    for path in (ROOT / "tests").glob("test_*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                texts.append(node.value)
            elif isinstance(node, ast.JoinedStr):
                texts.append("\0".join(part.value for part in node.values
                                       if isinstance(part, ast.Constant)))
    return texts


def _parts(template: str) -> list[str]:
    return [part for part in (piece.strip(" \"'") for piece in re.split(r"\{[^}]*\}", template))
            if part]


def _bad_hook_input(repo, gh, tmp_path, monkeypatch, request):
    return (("hook", "approval"), None, "not json",
            "The hook input is not a JSON object.\nNext: forge doctor\n")


def _approval(repo, **fields) -> str:
    """A Claude Code ExitPlanMode payload with these fields."""
    return json.dumps({"session_id": "s1", "tool_use_id": "t1", "cwd": str(repo.path),
                       "hook_event_name": "PostToolUse", "tool_name": "ExitPlanMode",
                       "tool_input": {"plan": DOC}, **fields})


def _approval_outside_the_contract(repo, gh, tmp_path, monkeypatch, request):
    return (("hook", "approval"), None, _approval(repo, tool_response={"accepted": True}),
            "The approval doesn't match the approval contract, so nothing was recorded.\n"
            "Next: forge next\n")


def _approval_with_no_session(repo, gh, tmp_path, monkeypatch, request):
    return (("hook", "approval"), None,
            _approval(repo, session_id="", tool_response={"plan": DOC, "isAgent": False}),
            "The approval has no session or event id to guard against a replay, so nothing was "
            "recorded.\nNext: forge next\n")


def _codex_sdk_install_fails(repo, gh, tmp_path, monkeypatch, request):
    repo.write("forge.toml", f'version = "{_version(repo)}"\nworkers = "codex"\n')
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    conftest._install(repo.bin, "uv", f"#!{sys.executable}\nimport sys\n"
                                      "sys.stderr.write('uv: the network is down\\n')\nsys.exit(1)\n")
    return (("doctor", "--fix"), None, "",
            "uv venv failed while installing the Codex SDK: uv: the network is down\n"
            "Next: forge doctor --fix\n")


def _init_with_commits(repo, gh, tmp_path, monkeypatch, request):
    return (("init",), None, "",
            "forge init sets up a new repo, and this one already has commits; a repo with the "
            "copied-in Forge moves over with forge migrate.\nNext: forge migrate\n")


def _init_without_origin(repo, gh, tmp_path, monkeypatch, request):
    fresh = tmp_path / "fresh"
    repo.git("init", "-q", "-b", "main", str(fresh))
    return (("init",), fresh, "",
            "This repo has no origin remote, so Forge can't push the first commit or protect the "
            "default branch.\nNext: gh repo create <name> --private --source . --remote origin\n")


def _protection_fails(repo, gh, tmp_path, monkeypatch, request):
    client, remote = tmp_path / "client", tmp_path / "client.git"
    repo.git("init", "-q", "--bare", "-b", "main", str(remote))
    repo.git("init", "-q", "-b", "main", str(client))
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    gh.respond("api", exit=1)
    # The branch has no rule yet, so reading it works; setting Forge's rule fails.
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    return (("init",), client, "", re.compile(
        r"Branch protection on main was not set: gh exited with code 1\.\n"
        r"Next: gh api --method PUT 'repos/\{owner\}/\{repo\}/branches/main/protection' "
        r"--input \S+branch-protection\.json'?\n"))


def _not_a_repo(repo, gh, tmp_path, monkeypatch, request):
    (tmp_path / "nowhere").mkdir()
    return (("next",), tmp_path / "nowhere", "",
            "This folder is not inside a git repository.\nNext: cd <your repo>\n")


def _unknown_setting(repo, gh, tmp_path, monkeypatch, request):
    repo.write("forge.toml", 'version = "v1.0.0"\ncolour = "blue"\n')
    return (("sync",), None, "",
            "forge.toml is not usable: 'colour' is not a forge.toml key.\nNext: forge doctor\n")


def _roadmap_without_items(repo, gh, tmp_path, monkeypatch, request):
    repo.write("plans/roadmap.json", "[]\n")
    return (("story", "new", "SHOP", "Shoppers can save a basket"), None, "",
            "plans/roadmap.json is not usable: it needs an items list where every item has a key.\n"
            "Next: git checkout -- plans/roadmap.json\n")


def _not_an_item(repo, gh, tmp_path, monkeypatch, request):
    return (("work", "Not An Item"), None, "",
            "'Not An Item' is not a story key, a KEY/TASK task or a fix name.\nNext: forge next\n")


def _unreadable_state(repo, gh, tmp_path, monkeypatch, request):
    repo.write(".factory/fixes/tidy.json", "not json\n")
    return (("close", "tidy"), None, "",
            ".factory/fixes/tidy.json is not usable: Expecting value: line 1 column 1 (char 0).\n"
            "Next: git checkout -- .factory/fixes/tidy.json\n")


def _lower_case_key(repo, gh, tmp_path, monkeypatch, request):
    return (("story", "new", "shop", "Shoppers can save a basket"), None, "",
            "'shop' is not a story key; a key is capital letters, digits and hyphens.\n"
            'Next: forge story new <KEY> "<title>"\n')


def _no_title(repo, gh, tmp_path, monkeypatch, request):
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
    return (("story", "new", "SHOP"), None, "",
            'A new story needs a plain-English title.\nNext: forge story new SHOP "<title>"\n')


def _no_story(repo, gh, tmp_path, monkeypatch, request):
    return (("read", "SHOP"), None, "",
            'There is no story SHOP here.\nNext: forge story new SHOP "<title>"\n')


def _no_spec(repo, gh, tmp_path, monkeypatch, request):
    return (("read", "saved-baskets"), None, "",
            "docs/specs/saved-baskets.md does not exist.\nNext: forge spec save saved-baskets\n")


def _reader_fails(repo, gh, tmp_path, monkeypatch, request):
    setup(repo)
    assert repo.forge("story", "new", "SHOP", "Shoppers can save a basket").returncode == 0
    (worktree(repo, "story/SHOP") / "plans" / "SHOP.md").write_text(DOC, encoding="utf-8")
    conftest._install(repo.bin, "claude", f"#!{sys.executable}\nimport sys\n"
                      "sys.stderr.write('claude: the model is unavailable\\n')\nsys.exit(1)\n")
    return (("read", "SHOP"), None, "",
            "The cold read of plans/SHOP.md failed: claude: the model is unavailable\n"
            "Next: forge read SHOP\n")


def _story_not_finished(repo, gh, tmp_path, monkeypatch, request):
    return (("story", "done", "SHOP", "Shoppers keep their basket."), None, "",
            "SHOP isn't finished: its story doc isn't on the default branch yet.\n"
            "Next: git fetch origin, then forge next\n")


# The Codex SDK moves its approval handler once a conversation's client is made, after forge
# work's check of the SDK passed. On PYTHONPATH, every Python loads it; only the SDK's has Codex.
MOVED_LATE = """try:
    import openai_codex
except ImportError:
    pass
else:
    start = openai_codex.Codex.__init__

    def moved(self, *args, **kwargs):
        start(self, *args, **kwargs)
        self._client._request_handler = self._client.__dict__.pop("_approval_handler")

    openai_codex.Codex.__init__ = moved
"""


def _codex_handler_moved(repo, gh, tmp_path, monkeypatch, request):
    _codex_repo(repo, monkeypatch, request.getfixturevalue("sdk_data"))
    (tmp_path / "moved").mkdir()
    (tmp_path / "moved" / "sitecustomize.py").write_text(MOVED_LATE, encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "moved"))
    return (("work", "BOARD/PAGE"), None, "",
            "Forge couldn't put in its handler that declines every Codex request, so it started no "
            "conversation.\nNext: forge doctor --fix\n")


def _on_a_branch(repo) -> None:
    repo.write("forge.toml", f'version = "{_version(repo)}"\n')
    repo.git("checkout", "-q", "-b", "fix/adapters")


def _adapter_linked_outside(repo, gh, tmp_path, monkeypatch, request):
    _on_a_branch(repo)
    os.symlink(tmp_path / "elsewhere.md", repo.path / "AGENTS.md")
    return (("sync",), None, "",
            "AGENTS.md leads outside this repo, so Forge won't write through it; remove that link.\n"
            "Next: forge sync\n")


def _unreadable_settings(repo, gh, tmp_path, monkeypatch, request):
    _on_a_branch(repo)
    repo.write(".claude/settings.json", "not json\n")
    return (("sync",), None, "",
            ".claude/settings.json can't be merged (Expecting value: line 1 column 1 (char 0)); fix "
            "it by hand.\nNext: forge sync\n")


def _broken_block(repo, gh, tmp_path, monkeypatch, request):
    _on_a_branch(repo)
    repo.write("AGENTS.md", "<!-- forge:end -->\nOurs.\n<!-- forge:begin -->\n")
    return (("sync",), None, "",
            "AGENTS.md has a broken Forge block; keep one <!-- forge:begin --> line and, after it, "
            "one <!-- forge:end --> line.\nNext: forge sync\n")


def _hooks(repo) -> Path:
    return Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "hooks"))


def _hook_linked_outside(repo, gh, tmp_path, monkeypatch, request):
    _on_a_branch(repo)
    os.symlink(tmp_path / "our-hook", _hooks(repo) / "pre-commit")
    return (("sync",), None, "",
            f"{_hooks(repo) / 'pre-commit'} links to a file outside this repo's .git folder, so "
            "Forge won't write through it; put the hook itself there instead of the link.\n"
            "Next: forge sync\n")


def _two_own_hooks(repo, gh, tmp_path, monkeypatch, request):
    _on_a_branch(repo)
    hook, kept = _hooks(repo) / "pre-commit", _hooks(repo) / "pre-commit.pre-forge"
    for path in (hook, kept):
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return (("sync",), None, "",
            f"{hook} and {kept} both hold a hook that isn't Forge's; combine them into {kept} by "
            f"hand and delete {hook}.\nNext: forge sync\n")


LINKS = pytest.mark.skipif(os.name == "nt", reason="making a symlink needs extra rights on Windows")
TRIGGERS = [_bad_hook_input, _approval_outside_the_contract, _approval_with_no_session,
            _codex_sdk_install_fails, _codex_handler_moved, _init_with_commits,
            _init_without_origin, _protection_fails, _not_a_repo, _unknown_setting, _roadmap_without_items, _not_an_item, _unreadable_state,
            _lower_case_key, _no_title, _no_story, _no_spec, _reader_fails, _story_not_finished,
            pytest.param(_adapter_linked_outside, marks=LINKS), _unreadable_settings,
            _broken_block, pytest.param(_hook_linked_outside, marks=LINKS), _two_own_hooks]


@pytest.mark.parametrize("case", ["every refusal has a test", *TRIGGERS],
                         ids=lambda case: case if isinstance(case, str) else case.__name__.strip("_"))
def test_3_every_refusal_is_tested(repo, gh, tmp_path, monkeypatch, request, case):
    if isinstance(case, str):
        # Each refusal's words (its problem, or its Next line when the problem is only values)
        # are among the texts some test expects, or the refusal is listed above with its reason.
        refusals, texts = _refusals(), _expected()
        assert set(UNTRIGGERED) <= set(refusals), set(UNTRIGGERED) - set(refusals)
        untested = []
        for name, (problem, step) in refusals.items():
            parts = _parts(problem)
            if max(map(len, parts), default=0) < 8:  # only values: its Next line says what it is
                parts = _parts(step)
            if name not in UNTRIGGERED and not all(any(part in text for text in texts)
                                                   for part in parts):
                untested.append(f"{name}: {problem}")
        assert not untested, "refusals no test triggers:\n" + "\n".join(untested)
        return
    args, cwd, stdin, expected = case(repo, gh, tmp_path, monkeypatch, request)
    done = repo.forge(*args, input=stdin, cwd=cwd)
    assert done.returncode != 0, done.stdout
    if isinstance(expected, re.Pattern):
        assert expected.fullmatch(done.stderr), done.stderr
    else:
        assert done.stderr == expected


# --- criterion 6: third-party contracts ------------------------------------------------------

# A field a newer version of the tool might add; Forge must read past it.
EXTRA = {"a_field_forge_never_heard_of": {"added": "in a later version"}}


@pytest.mark.parametrize("tool", ["autoreview", "gh", "claude", "codex"])
def test_6_third_party_contracts(env, claude_payload, codex_payload, tool):
    repo = env.repo
    if tool == "autoreview":
        # Forge reads only the findings and review_status of Autoreview's report.
        env.reviews({"exit": 1, "report": {**report({**finding("P2", "Simpler: drop the cache"),
                                                     **EXTRA}), **EXTRA}})
        closed = env.close(env.start_fix()[0])
        assert closed.returncode == 0, closed.stdout + closed.stderr
        [create] = env.gh_calls("pr", "create")
        assert "1. P2 Simpler: drop the cache (app.py:1): advisory" in body(create)
        # Its version is pinned: forge doctor reports a helper at any other version.
        assert "Autoreview" not in repo.forge("doctor").stdout
        helper = Path(os.environ["AUTOREVIEW"])
        (helper.parents[1] / ".upstream-sha").write_text("0" * 40, "utf-8")
        assert (f"- The Autoreview helper at {helper} is not the pinned version {PIN} (found: "
                f"{'0' * 40}).\n  Fix: install skills/autoreview from "
                f"https://github.com/openclaw/agent-skills at {PIN} into ") in repo.forge(
                    "doctor").stdout
    elif tool == "gh":
        # Pull requests, check runs and statuses as gh gives them, with fields Forge doesn't use.
        env.gh.respond("pr", "list", stdout=json.dumps(
            [{"number": 7, "state": "OPEN", "body": "", "isDraft": False, **EXTRA}]))
        env.checks([{**run("tests"), **EXTRA}],
                   [{"context": "forge-pr-check", "state": "success", **EXTRA}])
        closed = env.close(env.start_fix()[0])
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert env.gh_calls("pr", "edit") and not env.gh_calls("pr", "create")
        env.gh.respond("pr", "list", "--state", "all", stdout=json.dumps([{
            "headRefName": "fix/tidy-readme", "state": "MERGED",
            "title": "Readme greets new readers", "body": "The readme opens with a greeting.\n",
            "mergedAt": "2026-09-24T10:00:00Z",
            "files": [{"path": "app.py", "additions": 1, "deletions": 0, **EXTRA}],
            "statusCheckRollup": [{"__typename": "CheckRun", "name": "tests", "status": "COMPLETED",
                                   "conclusion": "SUCCESS", "completedAt": "2026-09-24T09:00:00Z",
                                   **EXTRA}], **EXTRA}]))
        page = env.tmp / "board.html"
        assert repo.forge("board", "--out", str(page)).returncode == 0
        assert ("Readme greets new readers : Finished on 24 September 2026. The readme opens with a "
                "greeting.") in page_text(page)
    else:
        # The host's hook payloads, with fields Forge doesn't use at every level.
        setup(repo, keys=("WISH",))  # SHOP is the close fixture's story, already on main
        env.commit(repo.path, "forge.toml", with_models((repo.path / "forge.toml").read_text("utf-8")))
        repo.git("push", "-q", "origin", "main")
        wish = ready(repo, "WISH", DOC)
        build = claude_payload if tool == "claude" else codex_payload

        def hooked(name, payload):
            return repo.forge("hook", name, input=json.dumps({**payload, **EXTRA}))

        context = hooked("context", build("SessionStart"))
        assert context.returncode == 0 and context.stdout.startswith(
            repo.forge("next").stdout.strip()), context.stdout
        for command, code in (("rm -rf build", 2), ("ls", 0)):
            denied = hooked("deny", build("PreToolUse", "Bash", {"command": command, **EXTRA}))
            assert denied.returncode == code, (command, denied.stderr)
        if tool == "claude":
            payload = claude_plan(claude_payload, DOC, cwd=wish)
            payload["tool_response"].update(EXTRA)
        else:
            payload = codex_question(codex_payload, _digest(repo), cwd=wish)
            payload["tool_input"]["questions"][0].update(EXTRA)
            next(iter(payload["tool_response"]["answers"].values())).update(EXTRA)
        payload["tool_input"].update(EXTRA)
        approved = hooked("approval", payload)
        assert approved.returncode == 0, approved.stderr
        assert "Next: forge task start WISH/SAVE" in repo.forge("next").stdout
        if tool == "claude":  # the headless worker gets the brief on stdin; Forge reads its exit code
            assert repo.forge("task", "start", "WISH/SAVE").returncode == 0
            log = install_claude(repo)
            worked = repo.forge("work", "WISH/SAVE")
            assert worked.returncode == 0 and "stub claude: built it" in worked.stdout
            assert calls(log)[-1]["args"][:2] == ["-p", "--model"]


# --- criterion 7: the same result on both hosts ------------------------------------------------

def test_7_same_result_on_both_hosts(repo, claude_payload, codex_payload, monkeypatch):
    setup(repo, keys=("SHOP", "WISH"))
    shop, wish = ready(repo, "SHOP"), ready(repo, "WISH", DOC.replace("save a basket",
                                                                     "keep a wish list"))
    # sh finds forge on PATH, as a host does; on Windows that takes a sh script, not a .cmd.
    shim = repo.path.parent / "sh-bin"
    shim.mkdir()
    _executable(shim / "forge", f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" '
                                f'"{(repo.bin / "forge").as_posix()}" "$@"\n')
    monkeypatch.setenv("PATH", f"{shim}{os.pathsep}{os.environ['PATH']}")
    # The hook commands exactly as forge sync writes them into each host's adapter.
    repo.git("checkout", "-q", "-b", "fix/adapters")
    assert repo.forge("sync").returncode == 0
    commands = {(rel.split("/")[0], event): command
                for rel, event, command in _hook_commands(repo.path)}

    def through(host, event, payload):
        done = subprocess.run(["sh", "-c", commands[(host, event)]], input=json.dumps(payload),
                              cwd=repo.path, capture_output=True, text=True, encoding="utf-8")
        return done.returncode, done.stdout, done.stderr

    context = through(".claude", "SessionStart", claude_payload("SessionStart"))
    assert context == through(".codex", "SessionStart", codex_payload("SessionStart"))
    assert context[0] == 0 and "waiting for approval" in context[1]
    for command, code in (("rm -rf build", 2), ("git commit --no-verify -m x", 2),
                          ("gh pr merge 7", 2), ("ls -la", 0)):
        denied = through(".claude", "PreToolUse", claude_payload("PreToolUse", "Bash",
                                                                 {"command": command}))
        assert denied == through(".codex", "PreToolUse", codex_payload("PreToolUse", "Bash",
                                                                       {"command": command}))
        assert denied[0] == code, (command, denied)

    # An approval through Plan Mode and one through request_user_input record the same way.
    by_plan = through(".claude", "PostToolUse", claude_plan(claude_payload, DOC, cwd=shop))
    by_question = through(".codex", "PostToolUse",
                          codex_question(codex_payload, _digest(repo), cwd=wish))
    assert by_plan == by_question and by_plan[:2] == (
        0, "Recorded the approval of Shoppers can save a basket.\n"), (by_plan, by_question)

    def recorded(key):
        return repo.git("show", "--name-only", "--format=%s", f"story/{key}").replace(key, "KEY")

    assert recorded("SHOP") == recorded("WISH")
    shown = repo.forge("next").stdout
    assert all(f"Next: forge task start {key}/SAVE" in shown for key in ("SHOP", "WISH"))


# --- criterion 8: plain English ----------------------------------------------------------------

# What a person must never meet on the board or at the top of a pull request.
JARGON = {"a hash": r"\b[0-9a-f]{7,}\b", "a UUID": r"\b[0-9a-f]{8}-[0-9a-f]{4}-",
          "a window id": r"\bQ-\d", "a story key": r"FORGE-",
          "a code name": r"\b[a-z]+_[a-z0-9_]+\b", "a file path": r"\w/\w|\.(py|md|json|toml)\b",
          "jargon": r"(?i)\b(P0|P1|CI|PR|commit|branch|worktree)\b"}
IDS = ("SHOP", "CART", "T1", "T2", "tidy-readme")


def _not_plain(text: str) -> list[str]:
    return [name for name, pattern in JARGON.items() if re.search(pattern, text)] + [
        f"the ID {name}" for name in IDS
        if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text)]


def test_8_plain_english(env):
    repo, gh = env.repo, env.gh
    env.commit(repo.path, "forge.toml", with_models(
        (repo.path / "forge.toml").read_text("utf-8") + 'repo = "forge-source"\n'))
    env.commit(repo.path, "plans/roadmap.json", json.dumps({"items": [
        {"key": "SHOP", "title": "Shoppers can save a basket"},
        {"key": "CART", "title": "Shoppers can share a cart"}]}))
    repo.git("push", "-q", "origin", "main")

    # A task and a fix close: each pull request opens with a plain title and summary.
    for item, _ in (env.start_task(), env.start_fix()):
        assert env.close(item).returncode == 0
    creates = env.gh_calls("pr", "create")
    shown = [text for call in creates for text in (call[call.index("--title") + 1],
                                                   body(call).splitlines()[0])]
    assert shown == ["Save a basket", "Shoppers can save their basket with one click",
                     "Readme greets new readers", "The readme opens with a greeting"]
    assert not [(text, _not_plain(text)) for text in shown if _not_plain(text)]

    # A story waiting for approval: the question is exactly "Approve this plan?".
    conftest._install(repo.bin, "claude", READER.format(python=sys.executable))
    assert repo.forge("story", "new", "CART", "Shoppers can share a cart").returncode == 0
    (worktree(repo, "story/CART") / "plans" / "CART.md").write_text(CART_DOC, encoding="utf-8")
    assert repo.forge("read", "CART").returncode == 0
    assert 'question "Approve this plan?", header "Approve plan"' in repo.forge("next").stdout

    # The board, once both pull requests merged.
    gh.respond("pr", "list", "--state", "all", stdout=json.dumps([
        {"headRefName": call[call.index("--head") + 1], "state": "MERGED",
         "title": call[call.index("--title") + 1], "body": body(call),
         "mergedAt": "2026-09-25T10:00:00Z", "files": [], "statusCheckRollup": []}
        for call in creates]))
    page = env.tmp / "board.html"
    assert repo.forge("board", "--out", str(page)).returncode == 0
    text = page_text(page)
    for line in ("Save a basket", "Shoppers can share a cart", "Readme greets new readers : "
                 "Finished on 25 September 2026. The readme opens with a greeting"):
        assert line in text, text
    assert not _not_plain(text), (_not_plain(text), text)
    assert not re.search(JARGON["a hash"], page.read_text("utf-8")), "a hash is in the page"

    # Ctrl-C ends a command quietly: no traceback, just the usual exit code. A gh that waits
    # stands in for a slow step. ponytail: POSIX only; Windows has no SIGINT to send one process.
    if os.name != "nt":
        slow, started = env.tmp / "slow", env.tmp / "gh-started"
        slow.mkdir()
        _executable(slow / "gh", f'#!/bin/sh\ntouch "{started}"\nsleep 30\n')
        doctor = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "doctor"], cwd=repo.path,
                               env={**os.environ, "PATH": f"{slow}{os.pathsep}{os.environ['PATH']}"},
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        while not started.exists() and doctor.poll() is None:
            time.sleep(0.05)
        doctor.send_signal(signal.SIGINT)
        out, err = doctor.communicate(timeout=30)
        assert (doctor.returncode, err) == (130, ""), (out, err)


# --- criterion 9: nothing changes outside a pull request --------------------------------------

def _commands() -> dict[str, bool]:
    """Each command in cli.py's table, and whether it changes state, read from its source."""
    tree = ast.parse((SOURCE / "cli.py").read_text(encoding="utf-8"))
    table = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                 and [getattr(t, "id", "") for t in node.targets] == ["TABLE"])
    return {row.elts[0].value: row.elts[2].value for row in table.elts}


def test_9_nothing_changes_outside_a_pull_request(env, claude_payload, monkeypatch):
    repo, commands = env.repo, _commands()
    groups = {words.split()[0] for words in commands if " " in words}
    ran: set[str] = set()
    forge = repo.forge

    def default_branch():
        return (repo.git("rev-parse", "refs/heads/main"),
                repo.git("ls-remote", "origin", "refs/heads/main"),
                repo.git("status", "--porcelain", "-uall"))

    def checked(*args, **options):
        """Every forge command, run from the default branch's checkout, leaves it as it was."""
        before = default_branch()
        done = forge(*args, **options)
        assert default_branch() == before, f"forge {' '.join(args)} changed the default branch"
        ran.add(" ".join(args[:2]) if args[0] in groups else args[0])
        return done

    repo.forge = checked
    walk(env, claude_payload, monkeypatch)  # a story from story new to story done
    for args in (("init",), ("sync",), ("migrate",),
                 ("fix", "start", "Tidy the readme", "--done", "The readme greets readers"),
                 ("fix", "allow-large", "It touches six files"), ("spec", "save", "carts"),
                 ("spec", "confirm", "carts", "--by", "Ravi"), ("decision", "new", "carts"),
                 ("decision", "accept", "carts", "--by", "Ravi"), ("roadmap", "add", "carts")):
        repo.forge(*args)
    changing = {words for words, changes in commands.items() if changes}
    assert not changing - ran, f"state-changing commands not run: {sorted(changing - ran)}"


# --- criterion 25: state only ------------------------------------------------------------------

# What git and GitHub hold, which must never be copied into .factory/: the pull request's link,
# the checks' names and results, and the reader's and worker's output.
ELSEWHERE = ("github.com", "/pull/", "forge-pr-check", "success", "failure", "No findings")


def test_25_state_only(env, claude_payload, monkeypatch):
    walk(env, claude_payload, monkeypatch)
    repo = env.repo
    story = ".factory/stories/CART/story.json"
    # Each branch's own commits (the first task's branch starts from the story's) write only its
    # item's state file. Recording a finished story is a fix that writes the story's state too.
    own = {"story/CART": ("main", story),
           "task/CART-SAVE": ("story/CART", ".factory/stories/CART/tasks/SAVE.json"),
           "task/CART-SEND": ("main", ".factory/stories/CART/tasks/SEND.json"),
           "fix/cart-done": ("main", ".factory/fixes/cart-done.json")}
    for branch, (start, state) in own.items():
        for line in repo.git("log", "--no-merges", "--format=%H %s",
                             f"{start}..{branch}").splitlines():
            sha, subject = line.split(" ", 1)
            wrote = set(repo.git("diff-tree", "--no-commit-id", "--name-only", "-r", sha, "--",
                                 ".factory").splitlines())
            allowed = {state, story} if subject.startswith("Record the outcome of ") else {state}
            assert wrote <= allowed, (branch, subject, wrote)
    # Nothing in .factory/ repeats a pull request link, a check result or a tool's output.
    for ref in ["main", *own]:
        for rel in repo.git("ls-tree", "-r", "--name-only", ref, "--", ".factory").splitlines():
            text = repo.git("show", f"{ref}:{rel}")
            assert not [word for word in ELSEWHERE if word in text], (ref, rel, text)
