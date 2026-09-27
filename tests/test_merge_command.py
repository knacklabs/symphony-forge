"""A ready pull request merges through Forge, and Codex reads leave no active chat."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import GH_STUB, _install
from test_close import GREEN, env, run
from test_codex_reader import GRILL
from test_codex_worker import ROOT, _toml
from test_codex_worker import sdk_data  # noqa: F401
from test_story import DOC, new_story, setup

STORY = "FORGE-MERGE-1"


def _ready(env):
    env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
               + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.open_pr("")
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    return item, where


def _merge_at_github(env, local_commit=None):
    """The gh edge performs a squash in the fixture's bare remote, as GitHub would."""
    stub = GH_STUB.format(python=sys.executable)
    head = env.repo.git("rev-parse", "fix/tidy-readme")
    code = '''import json, pathlib, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
if sys.argv[1:3] == ["pr", "view"] and (here / "github-merged").exists():
    with (here / "gh-calls.jsonl").open("a", encoding="utf-8") as calls:
        calls.write(json.dumps(sys.argv[1:]) + "\\n")
    if "--jq" in sys.argv:
        print("MERGED")
    else:
        print(json.dumps({"number": 7, "state": "MERGED", "baseRefName": "main",
                          "headRefOid": MERGED_OID, "headRefName": "fix/tidy-readme",
                          "title": "Tidy readme", "isDraft": False}))
    sys.exit(0)
if sys.argv[1:3] == ["pr", "merge"]:
    args = sys.argv[1:]
    with (here / "gh-calls.jsonl").open("a", encoding="utf-8") as calls:
        calls.write(json.dumps(args) + "\\n")
    if "--squash" not in args or "--delete-branch" in args:
        sys.exit(1)
    if LOCAL_COMMIT:
        subprocess.run(["git", "-C", LOCAL_COMMIT, "commit", "-q", "--allow-empty",
                        "-m", "Keep this local work"], check=True)
    remote = pathlib.Path(REMOTE)
    checkout = here / "github-merge"
    subprocess.run(["git", "clone", "-q", str(remote), str(checkout)], check=True)
    subprocess.run(["git", "fetch", "-q", "origin", "fix/tidy-readme"], cwd=checkout, check=True)
    actual = subprocess.run(["git", "rev-parse", "FETCH_HEAD"], cwd=checkout, check=True,
                            capture_output=True, text=True).stdout.strip()
    if actual != args[args.index("--match-head-commit") + 1]:
        sys.exit(1)
    subprocess.run(["git", "merge", "--squash", "FETCH_HEAD"], cwd=checkout, check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", args[args.index("--subject") + 1]],
                   cwd=checkout, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=checkout, check=True)
    (here / "github-merged").write_text("merged", encoding="utf-8")
    sys.exit(0)
'''.replace("REMOTE", repr(str(env.tmp / "remote.git"))).replace("MERGED_OID", repr(head)).replace(
    "LOCAL_COMMIT", repr(str(local_commit)) if local_commit else "None")
    _install(env.repo.bin, "gh", "#!" + sys.executable + "\n" + code + stub.split("\n", 1)[1])


def _archiving_codex(repo, sdk_data, tmp_path, monkeypatch):
    stub = (ROOT / "tests" / "stubs" / "codex-app-server").read_text(encoding="utf-8")
    stub = stub.replace('THREAD, TURN = "thr-stub-1", "turn-stub-1"',
                        'THREAD, TURN = os.environ.get("STUB_THREAD", "thr-stub-1"), "turn-stub-1"')
    stub = stub.replace('        elif method == "thread/name/set":',
                        '        elif method == "thread/archive":\n'
                        '            if os.environ.get("STUB_NOTES"):\n'
                        '                log(notes_exist=pathlib.Path(os.environ["STUB_NOTES"]).is_file())\n'
                        '            if (os.environ.get("STUB_ARCHIVE_FAIL") or\n'
                        '                    os.environ.get("STUB_ARCHIVE_FAIL_THREAD") == message["params"]["threadId"]):\n'
                        '                send(id=message["id"], error={"code": -32603, "message": "archive failed"})\n'
                        '            else:\n'
                        '                reply(message, {})\n'
                        '        elif method == "thread/name/set":')
    _install(repo.bin, "codex-app-server", stub)
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    home = tmp_path / "codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    return repo.bin / "codex-app-server.jsonl"


def test_4_merge_refuses_a_changed_head_and_checks_the_recorded_head(env):
    item, where = _ready(env)
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    ready = env.repo.path / ".git" / "forge" / "ready" / f"{item}.json"
    saved = ready.read_text("utf-8")
    ready.unlink()
    missing = env.repo.forge("merge", item)
    assert missing.stderr == (f"Forge has no clean ready record for {item}.\n"
                              f"Next: forge close {item}\n")
    ready.write_text(saved.replace('"clean"', '"blocked"'), encoding="utf-8")
    unclean = env.repo.forge("merge", item)
    assert unclean.stderr == (f"Forge has no clean ready record for {item}.\n"
                              f"Next: forge close {item}\n")
    assert not env.gh_calls("pr", "merge")
    ready.write_text(saved, encoding="utf-8")
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": "wrong",
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    changed = env.repo.forge("merge", item)
    assert changed.returncode != 0
    assert changed.stderr == (f"The pull request's head changed since Forge recorded {item} ready.\n"
                              f"Next: forge close {item}\n")
    assert not env.gh_calls("pr", "merge")

    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "CLOSED", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    closed_pr = env.repo.forge("merge", item)
    assert closed_pr.stderr == (f"Forge needs an open pull request for {item} targeting main "
                                f"from fix/tidy-readme.\nNext: open or correct its pull request, "
                                f"then forge close {item}\n")
    assert not env.gh_calls("pr", "merge")

    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "other", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    wrong_target = env.repo.forge("merge", item)
    assert wrong_target.stderr == (f"Forge needs an open pull request for {item} targeting main "
                                   f"from fix/tidy-readme.\nNext: open or correct its pull request, "
                                   f"then forge close {item}\n")
    assert not env.gh_calls("pr", "merge")

    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    env.checks([run("tests", "failure"), run("forge-pr-check")])
    before_checks = len(env.gh_calls("api"))
    red = env.repo.forge("merge", item)
    assert red.stderr == (f"Checks failed on the pull request: tests.\n"
                          f"Next: forge work {item}\n")
    lookups = env.gh_calls("api")[before_checks:]
    endpoint = f"repos/{{owner}}/{{repo}}/commits/{head}"
    assert ["api", "--paginate", "--jq", ".check_runs[]",
            f"{endpoint}/check-runs?per_page=100"] in lookups
    assert ["api", "--paginate", "--jq", ".statuses[]",
            f"{endpoint}/status?per_page=100"] in lookups
    assert not env.gh_calls("pr", "merge")
    env.checks(GREEN)
    env.gh.respond("pr", "merge", stderr="merge queue refused the request\n", exit=1)
    refused = env.repo.forge("merge", item)
    assert refused.stderr == (f"GitHub did not merge the pull request for {item}: merge queue "
                              f"refused the request.\nNext: check the pull request, then forge merge {item}\n")
    env.gh.respond("pr", "merge")
    pending = env.repo.forge("merge", item)
    assert pending.stderr == (f"GitHub has not finished merging the pull request for {item}.\n"
                              f"Next: check the pull request, then forge merge {item}\n")
    _merge_at_github(env)
    merged = env.repo.forge("merge", item, cwd=where)
    assert merged.returncode == 0, merged.stderr
    assert any("--match-head-commit" in call and head in call for call in env.gh_calls("pr", "merge"))
    assert (env.repo.path / "app.py").is_file() is False
    assert env.repo.git("show", "origin/main:app.py") == "print('hello')"
    assert env.repo.git("log", "-1", "--format=%s", "origin/main") == "Tidy readme"
    assert env.repo.git("ls-remote", "--heads", "origin", "fix/tidy-readme") == ""
    assert not where.exists()
    assert "fix/tidy-readme" not in env.repo.git("branch", "--list", "fix/tidy-readme")


def _check_dirty_merge(
        env, sdk_data, tmp_path, monkeypatch):
    item, where = _ready(env)
    stub = _archiving_codex(env.repo, sdk_data, tmp_path, monkeypatch)
    record = env.repo.path / ".git" / "forge" / "threads" / "fix" / f"{item}.log"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(''.join(json.dumps({"conversation": thread, "turn": "turn-1"}) + "\n"
                              for thread in ("thr-one", "thr-two")), encoding="utf-8")
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    env.gh.respond("pr", "merge")
    queued = env.repo.forge("merge", item)
    assert "GitHub has not finished merging" in queued.stderr
    assert where.exists()
    _merge_at_github(env)
    subprocess.run([str(env.repo.bin / "gh"), "pr", "merge", "7", "--squash", "--subject", "Tidy readme",
                    "--match-head-commit", head], cwd=env.repo.path, check=True)
    env.gh.respond("pr", "list", "--state", "merged", stdout=json.dumps(
        [{"headRefName": "fix/tidy-readme"}]))
    assert f"Next: forge merge {item}" in env.repo.forge("next").stdout
    merge_calls = len(env.gh_calls("pr", "merge"))
    (where / "unsaved.txt").write_text("keep me\n", encoding="utf-8")
    remote = env.tmp / "remote.git"
    subprocess.run(["git", "-C", str(remote), "config", "receive.denyDeletes", "true"], check=True)
    blocked = env.repo.forge("merge", item)
    assert blocked.returncode != 0
    assert blocked.stderr == (f"Forge could not delete the remote branch for {item}.\n"
                              f"Next: check the branch on GitHub, then forge merge {item}\n")
    assert env.repo.git("ls-remote", "--heads", "origin", "fix/tidy-readme")
    assert (env.repo.path / ".git" / "forge" / "ready" / f"{item}.json").is_file()
    assert f"Next: forge merge {item}" in env.repo.forge("next").stdout
    subprocess.run(["git", "-C", str(remote), "config", "receive.denyDeletes", "false"], check=True)
    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stderr
    assert len(env.gh_calls("pr", "merge")) == merge_calls
    assert where.is_dir() and (where / "unsaved.txt").read_text("utf-8") == "keep me\n"
    assert "uncommitted" in merged.stdout.lower()
    assert all("--delete-branch" not in call for call in env.gh_calls("pr", "merge"))
    assert env.repo.git("ls-remote", "--heads", "origin", "fix/tidy-readme") == ""
    calls = [json.loads(line) for line in stub.read_text("utf-8").splitlines()]
    assert {call["params"]["threadId"] for call in calls
            if call.get("method") == "thread/archive"} == {"thr-one", "thr-two"}
    next_step = env.repo.forge("next")
    assert next_step.returncode == 0, next_step.stderr
    assert item not in next_step.stdout
    (env.repo.path / ".git" / "forge" / "ready" / f"{item}.json").unlink()
    legacy = env.repo.forge("next")
    assert f"Next: git worktree remove {where}" in legacy.stdout


def _check_later_local_commit(env):
    item, where = _ready(env)
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    _merge_at_github(env, local_commit=where)
    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stderr
    assert where.is_dir()
    assert env.repo.git("status", "--porcelain", cwd=where) == ""
    assert env.repo.git("log", "-1", "--format=%s", "fix/tidy-readme") == "Keep this local work"
    assert "local commits" in merged.stdout.lower()
    assert env.repo.git("show", "origin/main:app.py") == "print('hello')"


def _check_archive_retry(env, sdk_data, tmp_path, monkeypatch):
    item, where = _ready(env)
    stub = _archiving_codex(env.repo, sdk_data, tmp_path, monkeypatch)
    record = env.repo.path / ".git" / "forge" / "threads" / "fix" / f"{item}.log"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(''.join(json.dumps({"conversation": thread}) + "\n"
                              for thread in ("thr-one", "thr-two")), encoding="utf-8")
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    _merge_at_github(env)
    monkeypatch.setenv("STUB_ARCHIVE_FAIL_THREAD", "thr-two")
    failed = env.repo.forge("merge", item)
    assert failed.returncode != 0
    assert failed.stderr == (f"Forge could not archive every Codex conversation for {item}.\n"
                             f"Next: try forge merge {item} again\n")
    assert where.is_dir()
    assert env.repo.git("ls-remote", "--heads", "origin", "fix/tidy-readme")
    assert f"Next: forge merge {item}" in env.repo.forge("next").stdout
    monkeypatch.delenv("STUB_ARCHIVE_FAIL_THREAD")
    retried = env.repo.forge("merge", item)
    assert retried.returncode == 0, retried.stderr
    assert not where.exists()
    calls = [json.loads(line) for line in stub.read_text("utf-8").splitlines()]
    archived = [call["params"]["threadId"] for call in calls
                if call.get("method") == "thread/archive"]
    assert archived.count("thr-one") == 1
    assert archived.count("thr-two") == 2
    assert item not in env.repo.forge("next").stdout


@pytest.mark.parametrize("scenario", ("dirty", "local_commit", "archive_retry"))
def test_5_merge_cleans_up_only_after_archiving_and_preserves_local_work(
        env, sdk_data, tmp_path, monkeypatch, scenario):
    if scenario == "dirty":
        _check_dirty_merge(env, sdk_data, tmp_path, monkeypatch)
    elif scenario == "local_commit":
        _check_later_local_commit(env)
    else:
        _check_archive_retry(env, sdk_data, tmp_path, monkeypatch)


def test_7_cold_read_archives_after_writing_notes_and_reports_archive_failure(
        repo, gh, tmp_path, monkeypatch, sdk_data):
    setup(repo, keys=("SHOP", "WISH"))
    stub = _archiving_codex(repo, sdk_data, tmp_path, monkeypatch)
    monkeypatch.delenv("CODEX_THREAD_ID")
    monkeypatch.setenv("CLAUDECODE", "1")
    shop = new_story(repo, "SHOP")
    (shop / "plans" / "SHOP.md").write_text(DOC, encoding="utf-8")
    (shop / "forge.toml").write_text(_toml(repo.forge("--version").stdout.split()[-1],
                                           "claude", GRILL), encoding="utf-8")
    notes = shop / "plans" / "SHOP.read.md"
    monkeypatch.setenv("STUB_NOTES", str(notes))
    monkeypatch.setenv("STUB_THREAD", "thr-shop-read")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stderr
    calls = [json.loads(line) for line in stub.read_text("utf-8").splitlines()]
    assert any(call.get("method") == "thread/start" for call in calls)
    assert [call["params"]["threadId"] for call in calls
            if call.get("method") == "thread/archive"] == ["thr-shop-read"]
    assert any(call.get("notes_exist") is True for call in calls)

    wish = new_story(repo, "WISH")
    (wish / "plans" / "WISH.md").write_text(DOC, encoding="utf-8")
    (wish / "forge.toml").write_text((shop / "forge.toml").read_text("utf-8"), encoding="utf-8")
    monkeypatch.setenv("STUB_NOTES", str(wish / "plans" / "WISH.read.md"))
    monkeypatch.setenv("STUB_THREAD", "thr-wish-read")
    monkeypatch.setenv("STUB_ARCHIVE_FAIL", "1")
    failed_archive = repo.forge("read", "WISH")
    assert failed_archive.returncode == 0, failed_archive.stderr
    assert (wish / "plans" / "WISH.read.md").is_file()
    wish_calls = [json.loads(line) for line in stub.read_text("utf-8").splitlines()][len(calls):]
    assert [call["params"]["threadId"] for call in wish_calls
            if call.get("method") == "thread/archive"] == ["thr-wish-read"]
    assert (f"Forge could not archive the cold read's Codex conversation for WISH; "
            "archive it in Codex when it is available.") in failed_archive.stdout
