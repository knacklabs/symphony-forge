"""A person can skip close's model review only on an item with no earlier block.

Test-audit answers:
1. These command tests protect skip validation, the saved human choice, and the checks/readiness
   that remain around a skipped model review.
2. Regressions include accepting a malformed choice, calling the model after a valid skip, losing
   the choice on retry, or treating it as a standing waiver after later work.
3. Existing close tests cover normal and blocked reviews, but not skip behavior. This file owns the
   new command contract and combines related paths rather than repeating scenarios at each layer.
4. The tests use Forge's real CLI and existing external-service stubs; no production test seam is
   needed.
"""
from __future__ import annotations

import json
import sys

import pytest

from conftest import Repo, _install
from test_close import CLEAN, GREEN, body, blocked, env, finding, run
from test_close_keeps_reviews_for_unchanged_branch_diffs import client as setup_adopted_client
from test_land import _agent, _fix, land  # noqa: F401
from test_score_notes import _client_repo as setup_new_client

STORY = "FORGE-REVIEWCHOICE-1"


def _skip(env, item, by="A Person", reason="Docs only"):
    return env.close(item, "--no-review", "--by", by, "--reason", reason)


def _default_moves_during_checks(env, tmp_path, where, change_item: bool, monkeypatch):
    """Move main and optionally add worker work during close's check polling."""
    remote = env.repo.git("remote", "get-url", "origin")
    script = tmp_path / "move-default.py"
    script.write_text(
        "import pathlib, subprocess\n"
        f"remote = {json.dumps(remote)}\n"
        f"worktree = pathlib.Path({json.dumps(where.as_posix())})\n"
        f"writer = pathlib.Path({json.dumps((tmp_path / 'default-writer').as_posix())})\n"
        "subprocess.run(['git', 'clone', '-q', remote, str(writer)], check=True)\n"
        "(writer / 'NEWS.md').write_text('Default moved while checks ran\\n', encoding='utf-8')\n"
        "subprocess.run(['git', 'add', 'NEWS.md'], cwd=writer, check=True)\n"
        "subprocess.run(['git', 'commit', '-qm', 'Move the default branch'], cwd=writer, check=True)\n"
        "subprocess.run(['git', 'push', '-q', 'origin', 'main'], cwd=writer, check=True)\n"
        + ("(worktree / 'later.py').write_text('print(2)\\n', encoding='utf-8')\n"
           "subprocess.run(['git', 'add', 'later.py'], cwd=worktree, check=True)\n"
           "subprocess.run(['git', 'commit', '-qm', 'Add worker work'], cwd=worktree, check=True)\n"
           if change_item else ""),
        encoding="utf-8",
    )
    gh = (env.repo.bin / "gh").read_text("utf-8")
    marker = (env.repo.bin / "default-move-during-close").as_posix()
    responses = (env.repo.bin / "gh-responses.json").as_posix()
    green = "".join(json.dumps(row) + "\n" for row in GREEN)
    needle = 'responses = here / "gh-responses.json"\n'
    inject = (
        f"marker = pathlib.Path({json.dumps(marker)})\n"
        "if args[:2] == ['api', '--paginate'] and '.check_runs[]' in args and not marker.exists():\n"
        f"    subprocess.run([sys.executable, {json.dumps(script.as_posix())}], check=True)\n"
        "    marker.write_text('moved', encoding='utf-8')\n"
        "elif args[:2] == ['api', '--paginate'] and '.check_runs[]' in args and marker.read_text(encoding='utf-8') == 'moved':\n"
        f"    response_file = pathlib.Path({json.dumps(responses)})\n"
        "    rules = json.loads(response_file.read_text(encoding='utf-8'))\n"
        "    for rule in rules:\n"
        "        if rule['args'] == ['api', '--paginate', '--jq', '.check_runs[]']:\n"
        f"            rule['stdout'] = {json.dumps(green)}\n"
        "    response_file.write_text(json.dumps(rules), encoding='utf-8')\n"
        "    marker.write_text('green', encoding='utf-8')\n"
    )
    assert needle in gh
    _install(env.repo.bin, "gh", gh.replace(needle, inject + needle, 1))
    # A progressing check keeps close in its normal wait path. The next read is green.
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "10")
    env.checks([run("tests", None, "in_progress"), run("forge-pr-check")])


def _close_ready_line(result):
    return next(line for line in result.stdout.splitlines() if line.startswith("Ready:"))


def _basic_skip(env, kind, long_value=False):
    if kind == "fix":
        item, _ = env.start_fix()
    else:
        item, _ = env.start_task()
    env.checks(GREEN)
    by = "P" * 240 if long_value else "  A\tPerson  "
    reason = "r" * 240 if long_value else " Docs\n only "
    expected_by = "P" * 200 if long_value else "A Person"
    expected_reason = "r" * 200 if long_value else "Docs only"
    closed = _skip(env, item, by, reason)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert f"Review: skipped by {expected_by}." in closed.stdout
    assert f"Ready: {item} has no model review (skipped by {expected_by}) and green checks." in closed.stdout
    assert env.review_calls() == []
    [create] = env.gh_calls("pr", "create")
    published = body(create)
    assert f"Review: skipped by {expected_by}: {expected_reason}." in published
    assert "Review: clean" not in published


def _invalid_skip(env, invalid):
    item, where = env.start_fix()
    # A default move makes early refusal observable: a valid close would merge it.
    env.commit(env.repo.path, "NEWS.md", "New default-branch work\n")
    env.repo.git("push", "-q", "origin", "main")
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    args = ["--no-review", "--by", "A Person", "--reason", "Docs only"]
    if invalid == "missing-by":
        args.remove("--by")
        args.remove("A Person")
    elif invalid == "blank-by":
        args[args.index("A Person")] = " \t "
    elif invalid == "missing-reason":
        args.remove("--reason")
        args.remove("Docs only")
    elif invalid == "blank-reason":
        args[args.index("Docs only")] = " \n "
    elif invalid == "dismiss":
        args.extend(["--dismiss", "1"])
    elif invalid == "resolve":
        args.extend(["--resolve", "accept"])
    else:
        args.extend(["--because", "app.py:1 fixed"])
    refused = env.close(item, *args)
    assert refused.returncode == 1
    assert "A review skip needs a person's name and reason" in refused.stderr
    assert f'forge close {item} --no-review --by "<name>" --reason "<why>"' in refused.stderr
    assert env.repo.git("rev-parse", "HEAD", cwd=where) == head
    assert not (where / "NEWS.md").exists()
    assert env.gh.calls() == []
    assert env.review_calls() == []


def _worker_cannot_skip(env, monkeypatch):
    item, where = env.start_fix()
    env.commit(env.repo.path, "NEWS.md", "New default-branch work\n")
    env.repo.git("push", "-q", "origin", "main")
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    monkeypatch.setenv("FORGE_WORKER", "1")
    refused = _skip(env, item)
    assert refused.returncode == 1
    assert "Only a person can skip the model review; a worker does not." in refused.stderr
    assert f'forge close {item} --no-review --by "<name>" --reason "<why>"' in refused.stderr
    assert env.repo.git("rev-parse", "HEAD", cwd=where) == head
    assert not (where / "NEWS.md").exists()
    assert env.gh.calls() == []
    assert env.review_calls() == []


def _existing_clean_review(env):
    item, _ = env.start_fix()
    env.reviews(CLEAN)
    assert env.close(item).returncode == 0
    env.open_pr(body(env.gh_calls("pr", "create")[-1]))
    closed = _skip(env, item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Review: clean." in closed.stdout
    assert "Review: skipped by" not in closed.stdout
    assert len(env.review_calls()) == 1
    assert "Review: skipped by" not in body(env.gh_calls("pr", "edit")[-1])


def _assert_full_review(env, where):
    args = env.review_calls()[-1]["args"]
    assert args[args.index("--base") + 1] == env.repo.git("rev-parse", "origin/main", cwd=where)
    assert "The previous review checked commit" not in env.prompt()
    assert "Do not start a fresh review of the whole branch or proof list." not in env.prompt()


def _later_change_gets_full_review(env):
    item, where = env.start_fix()
    assert _skip(env, item).returncode == 0
    env.open_pr(body(env.gh_calls("pr", "create")[-1]))
    env.commit(where, "later.py", "print('later work')\n")
    stale = env.repo.forge("next")
    assert stale.returncode == 0, stale.stderr
    assert "Readme greets new readers is ready to merge." not in stale.stdout
    env.reviews(CLEAN)
    reviewed = env.close(item)
    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    assert len(env.review_calls()) == 1
    _assert_full_review(env, where)
    assert "Review: skipped by" not in body(env.gh_calls("pr", "edit")[-1])


def _retry_with_default_move(env, tmp_path, monkeypatch, change_item):
    item, where = env.start_fix()
    _default_moves_during_checks(env, tmp_path, where, change_item, monkeypatch)
    closed = _skip(env, item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert (env.repo.bin / "default-move-during-close").is_file()
    if change_item:
        assert len(env.review_calls()) == 1
        _assert_full_review(env, where)
        assert "Review: skipped by" not in body(env.gh_calls("pr", "edit")[-1])
    else:
        assert env.review_calls() == []
        assert "Review: skipped by A Person: Docs only." in body(env.gh_calls("pr", "edit")[-1])


def _missing_tool_skip(env, monkeypatch):
    config = env.repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8") + 'tools = "codex"\n', encoding="utf-8")
    env.repo.git("add", "forge.toml")
    env.repo.git("commit", "-q", "-m", "Select the review tool")
    env.repo.git("push", "-q", "origin", "main")
    for name in ("codex", "codex.cmd"):
        (env.repo.bin / name).unlink(missing_ok=True)
    monkeypatch.delenv("CODEX_BIN", raising=False)
    item, where = env.start_fix()
    closed = _skip(env, item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Review: skipped by A Person." in closed.stdout
    assert env.review_calls() == []
    env.open_pr(body(env.gh_calls("pr", "create")[-1]))
    env.commit(where, "later.py", "print('needs a review')\n")
    refused = env.close(item)
    assert refused.returncode == 1
    assert "Codex, which isn't installed" in refused.stderr
    assert "forge doctor --fix" in refused.stderr
    assert env.review_calls() == []


def _blocked_history(env, tmp_path, resolution, adopted=False):
    if adopted:
        setup_adopted_client(env, True)
    item, where = env.start_fix()
    branch = "fix/tidy-readme"
    stale = None
    if resolution == "stale-clone":
        env.repo.git("push", "-q", "origin", branch, cwd=where)
        clone_path = tmp_path / "stale-clone"
        remote = env.repo.git("remote", "get-url", "origin")
        env.repo.git("clone", "-q", remote, str(clone_path))
        stale = Repo(clone_path, env.repo.bin)
        stale.git("checkout", "-q", "-b", branch, f"origin/{branch}")
    env.reviews(blocked(finding("P1", "Not done: The readme opens with a greeting")))
    first = env.close(item)
    assert first.returncode == 1
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    direct = _skip(env, item)
    assert direct.returncode == 1
    assert f"A review already blocked {item}, so the model review cannot be skipped." in direct.stderr
    assert env.repo.git("rev-parse", "HEAD", cwd=where) == head
    assert len(env.review_calls()) == 1
    if resolution in ("worker-clean", "stale-clone"):
        # A fix has one review round. The owner records another round before the worker repairs it.
        more = env.close(item, "--resolve", "more", "--reason", "Repair the greeting")
        assert more.returncode == 0, more.stdout + more.stderr
        env.commit(where, "app.py", "print('the greeting is now present')\n")
        env.reviews(CLEAN)
        clean = env.close(item)
        assert clean.returncode == 0, clean.stdout + clean.stderr
        env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
    elif resolution == "dismiss":
        more = env.close(item, "--resolve", "more", "--reason", "Repair the greeting")
        assert more.returncode == 0, more.stdout + more.stderr
        resolved = env.close(item, "--dismiss", "1", "--because", "app.py:1 The greeting is present")
        assert resolved.returncode == 0, resolved.stdout + resolved.stderr
        env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
    else:
        resolved = env.close(item, "--resolve", "accept", "--reason", "The owner accepts this change")
        assert resolved.returncode == 0, resolved.stdout + resolved.stderr
        env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
    if stale is not None:
        # This clone had no review event when created; reconciliation must still find the block.
        stale.git("fetch", "-q", "origin")
        result = stale.forge("close", item, "--no-review", "--by", "A Person",
                             "--reason", "Docs only", cwd=stale.path)
    else:
        result = _skip(env, item)
    assert result.returncode == 1
    assert f"A review already blocked {item}, so the model review cannot be skipped." in result.stderr
    assert f"forge work {item}, then forge close {item} the normal way" in result.stderr
    assert len(env.review_calls()) == (2 if resolution in ("worker-clean", "stale-clone") else 1)


def _skip_does_not_bypass_checks(env, tmp_path, failure, monkeypatch):
    if failure == "design":
        setup_new_client(env, tmp_path, False)
        monkeypatch.setenv("IMPECCABLE_HOME", str(tmp_path / "impeccable-home"))
        monkeypatch.delenv("IMPECCABLE_BIN", raising=False)
        item, _ = env.start_fix(changes={
            "apps/web/src/screen.tsx": '<main><h1>Work</h1><div className="p-[13px]">Panel</div></main>\n'
        })
        env.checks(GREEN)
        refused = _skip(env, item)
        assert refused.returncode == 1
        assert "spacing-scale" in refused.stdout + refused.stderr
        assert "Ready:" not in refused.stdout
        assert env.review_calls() == []
        return
    item, _ = env.start_fix()
    if failure == "local-test":
        config = env.repo.path / "forge.toml"
        text = config.read_text("utf-8").replace('checks = ["tests", "forge-pr-check"]',
                                                   'test_place = "local"\nchecks = ["forge-pr-check"]')
        fail = tmp_path / "fail-test.py"
        fail.write_text("raise SystemExit(1)\n", encoding="utf-8")
        command = f'"{sys.executable}" "{fail.as_posix()}"'
        config.write_text(text + f'test = {json.dumps(command)}\n', encoding="utf-8")
        env.repo.git("add", "forge.toml")
        env.repo.git("commit", "-q", "-m", "Run the local test")
        env.repo.git("push", "-q", "origin", "main")
        env.checks([run("forge-pr-check")])
    elif failure == "ci":
        env.checks([run("tests", "failure"), run("forge-pr-check")])
    refused = _skip(env, item)
    assert refused.returncode == 1
    assert "Ready:" not in refused.stdout
    assert "Review: skipped by A Person." in refused.stdout
    if failure == "ci":
        assert "Checks failed on the pull request: tests." in refused.stderr
    else:
        assert "failed on this machine" in refused.stderr
    assert env.review_calls() == []


def _ready_and_board(env):
    _agent(env)
    item, _ = env.start_fix()
    env.checks(GREEN)
    skipped = _skip(env, item)
    assert skipped.returncode == 0, skipped.stdout + skipped.stderr
    skip_ready = _close_ready_line(skipped)
    assert "has no model review (skipped by A Person)" in skip_ready

    clean_item, _ = env.start(
        "clean-readme", "fix/clean-readme", ".factory/fixes/clean-readme.json",
        {"kind": "fix", "why": "Check clean readiness", "done_when": "The clean check is ready"},
        {"README.md": "Ready\n"},
    )
    env.reviews(CLEAN)
    clean = env.close(clean_item)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    clean_ready = _close_ready_line(clean)
    assert "has a clean review" in clean_ready
    next_step = env.repo.forge("next")
    board = env.repo.forge("board", "--json")
    assert next_step.returncode == 0, next_step.stderr
    assert "Readme greets new readers is ready to merge" in next_step.stdout
    assert f"Next: forge merge {item}" in next_step.stdout
    assert "Check clean readiness is ready to merge" in next_step.stdout
    assert board.returncode == 0, board.stderr
    data = json.loads(board.stdout)
    view = json.dumps(data)
    assert "Review skipped by A Person" in view
    rows = {row["id"]: row for row in data["items"]}
    skip_row, clean_row = rows[item], rows[clean_item]
    assert skip_row["status"] == clean_row["status"]
    assert skip_row["stage"] == clean_row["stage"]
    assert len(env.review_calls()) == 1


def _merge_skip(env, command, monkeypatch, adopted=False):
    if adopted:
        setup_adopted_client(env, True)
    _agent(env)
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8") + 'tools = "codex"\n')
    env.repo.git("push", "-q", "origin", "main")
    if command == "land":
        for name in ("codex", "codex.cmd"):
            (env.repo.bin / name).unlink(missing_ok=True)
        monkeypatch.delenv("CODEX_BIN", raising=False)
    _fix(env, "working", worked=True)
    opened = _skip(env, "tidy-readme")
    assert opened.returncode == 0, opened.stdout + opened.stderr
    assert env.review_calls() == []
    merged = env.repo.forge(command, "tidy-readme")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert "merged" in merged.stdout.lower()
    assert len(env.gh_calls("pr", "merge")) == 1
    assert env.review_calls() == []


def _adopted_skip(env):
    setup_adopted_client(env, True)
    item, _ = env.start_fix()
    env.checks(GREEN)
    closed = _skip(env, item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Review: skipped by A Person." in closed.stdout
    assert "Review: skipped by A Person: Docs only." in body(env.gh_calls("pr", "create")[-1])
    assert env.review_calls() == []


@pytest.mark.parametrize("case", [
    "fix", "task", "long-values", "invalid-missing-by", "invalid-blank-by",
    "invalid-missing-reason", "invalid-blank-reason", "invalid-dismiss", "invalid-resolve",
    "invalid-because", "worker", "existing-clean", "later-change", "retry-same",
    "retry-changed", "missing-tool",
], ids=lambda case: case)
def test_1_person_can_skip_model_review(env, tmp_path, monkeypatch, case):
    if case in ("fix", "task"):
        _basic_skip(env, case)
    elif case == "long-values":
        _basic_skip(env, "fix", long_value=True)
    elif case.startswith("invalid-"):
        _invalid_skip(env, case.removeprefix("invalid-"))
    elif case == "worker":
        _worker_cannot_skip(env, monkeypatch)
    elif case == "existing-clean":
        _existing_clean_review(env)
    elif case == "later-change":
        _later_change_gets_full_review(env)
    elif case == "retry-same":
        _retry_with_default_move(env, tmp_path, monkeypatch, False)
    elif case == "retry-changed":
        _retry_with_default_move(env, tmp_path, monkeypatch, True)
    else:
        _missing_tool_skip(env, monkeypatch)


@pytest.mark.parametrize("case", [
    "blocked-worker-clean", "blocked-dismiss", "blocked-accept", "stale-clone",
    "blocked-adopted", "red-local-test", "red-ci", "red-design", "ready-board",
    "merge", "land-no-tool", "merge-adopted", "adopted-skip",
], ids=lambda case: case)
def test_2_skip_refuses_after_prior_block(env, tmp_path, monkeypatch, request, case):
    if case.startswith("blocked-") and case != "blocked-adopted":
        _blocked_history(env, tmp_path, case.removeprefix("blocked-"))
    elif case == "stale-clone":
        _blocked_history(env, tmp_path, "stale-clone")
    elif case == "blocked-adopted":
        _blocked_history(env, tmp_path, "dismiss", adopted=True)
    elif case.startswith("red-"):
        _skip_does_not_bypass_checks(env, tmp_path, case.removeprefix("red-"), monkeypatch)
    elif case == "ready-board":
        _ready_and_board(env)
    elif case == "merge":
        _merge_skip(request.getfixturevalue("land"), "merge", monkeypatch)
    elif case == "land-no-tool":
        _merge_skip(request.getfixturevalue("land"), "land", monkeypatch)
    elif case == "merge-adopted":
        _merge_skip(request.getfixturevalue("land"), "merge", monkeypatch, adopted=True)
    else:
        _adopted_skip(env)
