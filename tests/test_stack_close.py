"""A stacked story part is reviewed on its own work and follows its base to main."""

import json
import shutil
import subprocess
import sys

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from conftest import _install
from test_last_task_records_story_outcome import github_merge
from test_stack_start import configured, start


def _set_part_limit(repo):
    repo.git("switch", "-q", "story/STACK")
    path = ".factory/stories/STACK/story.json"
    state = json.loads((repo.path / path).read_text("utf-8"))
    state["approval"]["part_line_limit"] = 400
    repo.write(path, json.dumps(state))
    repo.git("add", path)
    repo.git("commit", "-q", "-m", "Approve the part size limit")
    repo.git("push", "-q", "origin", "story/STACK")
    repo.git("switch", "-q", "main")


def _stacked_pair(env, previous, child_review=None):
    repo = configured(env, previous)
    base_work, _ = start(repo, "A")
    base_head = env.commit(base_work, "app.py", "A_VALUE = 1\n", "Build the base part")
    parent_close = env.close("STACK/A")
    assert parent_close.returncode == 0, parent_close.stdout + parent_close.stderr
    child_work, _ = start(repo, "B")
    env.commit(child_work, "use.py", "B_VALUE = 1\n", "Build the stacked part")
    env.gh.respond("pr", "create", stdout="https://github.com/acme/shop/pull/8\n")
    if child_review is not None:
        env.reviews(child_review)
    child_close = env.close("STACK/B")
    assert child_close.returncode == 0, child_close.stdout + child_close.stderr
    return repo, base_head


def _merge_base_by_hand(repo):
    writer = repo.path.parent / "github-manual-merge"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(writer))
    repo.git("fetch", "-q", "origin", "task/STACK-A", cwd=writer)
    repo.git("merge", "-q", "--no-ff", "--no-edit", "FETCH_HEAD", cwd=writer)
    repo.git("push", "-q", "origin", "main", cwd=writer)
    repo.git("fetch", "-q", "origin")


def _retarget_manual_child(env):
    repo = env.repo
    pr = {"number": 8, "state": "OPEN", "body": "", "isDraft": False,
          "baseRefName": "task/STACK-A"}
    env.gh.respond("pr", "list", "--head", "task/STACK-B", "--state", "all",
                   stdout=json.dumps([pr]))
    held = env.close("STACK/B")
    assert held.returncode == 1
    assert held.stderr.splitlines()[-2:] == [
        "STACK/B builds on STACK/A, which was merged on GitHub outside Forge, so its pull request still targets STACK/A's branch.",
        "Next: gh pr edit 8 --base main, then forge close STACK/B",
    ]
    edited = subprocess.run([sys.executable, str(repo.bin / "gh"), "pr", "edit", "8",
                             "--base", "main"], cwd=repo.path, capture_output=True, text=True)
    assert edited.returncode == 0, edited.stderr
    pr["baseRefName"] = "main"
    env.gh.respond("pr", "list", "--head", "task/STACK-B", "--state", "all",
                   stdout=json.dumps([pr]))


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_3_stacked_close_uses_only_its_changes_and_waits_for_its_base(env, previous):
    repo = configured(env, previous)
    _set_part_limit(repo)
    base_work, _ = start(repo, "A")
    env.commit(base_work, "app.py", "A_VALUE = 1\n" * 300, "Build the base part")
    base_close = env.close("STACK/A")
    assert base_close.returncode == 0, base_close.stdout + base_close.stderr

    child_work, _ = start(repo, "B")
    env.commit(child_work, "use.py", "B_VALUE = 1\n" * 200, "Build the stacked part")
    review_count = len(env.review_calls())
    checks_count = len(env.gh_calls("api", "--paginate", "--jq", ".check_runs[]"))
    child_close = env.close("STACK/B")
    assert child_close.returncode == 0, child_close.stdout + child_close.stderr
    assert child_close.stdout.splitlines()[-2:] == [
        "Reviewed STACK/B; it is tested and merges after STACK/A merges.",
        "Next: forge next",
    ]
    create = env.gh_calls("pr", "create")[-1]
    assert create[create.index("--base") + 1] == "task/STACK-A"
    assert len(env.review_calls()) == review_count + 1
    review_args = env.review_calls()[-1]["args"]
    review_base = review_args[review_args.index("--base") + 1]
    review_head = env.review_calls()[-1]["head"]
    changed = set(repo.git("diff", "--name-only", review_base, review_head, cwd=child_work).splitlines())
    assert "use.py" in changed and "app.py" not in changed
    assert len(env.gh_calls("api", "--paginate", "--jq", ".check_runs[]")) == checks_count
    assert not (repo.path / ".git" / "forge" / "ready" / "STACK" / "B.json").exists()

    too_early = repo.forge("merge", "STACK/B")
    assert too_early.returncode == 1
    assert too_early.stderr == (
        "STACK/B builds on STACK/A, which hasn't merged yet.\nNext: forge merge STACK/A\n")
    assert not env.gh_calls("pr", "merge")

    base = repo.git("rev-parse", "origin/main")
    head = repo.git("rev-parse", "origin/task/STACK-B")
    check = repo.forge("hook", "pr-check", "--base", base, "--head", head,
                       "--branch", "task/STACK-B")
    assert check.returncode == 1
    assert check.stderr.splitlines()[-2:] == [
        "STACK/B builds on STACK/A; Forge checks its pull request once it targets main.",
        "Next: forge close STACK/B",
    ]

    before_merge_calls = len(env.gh_calls("pr", "merge"))
    landed = repo.forge("land", "STACK/B")
    assert landed.returncode == 0, landed.stdout + landed.stderr
    assert "Reviewed STACK/B; it is tested and merges after STACK/A merges." in landed.stdout
    assert len(env.gh_calls("pr", "merge")) == before_merge_calls


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_4_forge_merge_retargets_and_replays_the_stacked_part(env, previous):
    earlier_note = "Keep the saved child value readable"
    repo, base_head = _stacked_pair(env, previous, blocked(finding("P2", earlier_note, "use.py")))

    env.gh.respond("pr", "list", "--base", "task/STACK-A", stdout=json.dumps([
        {"number": 8, "headRefName": "task/STACK-B"},
    ]))
    github_merge(env, "task/STACK-A")
    env.gh.respond("pr", "edit", "8", "--base", "main",
                   stderr="GitHub rejected the target\n", exit=1)
    refused = repo.forge("merge", "STACK/A")
    assert refused.returncode == 1
    assert refused.stderr == (
        "Forge could not point STACK/B's pull request at main, so it kept STACK/A's branch.\n"
        "Next: check that pull request, then forge merge STACK/A\n")
    assert repo.git("ls-remote", "--heads", "origin", "task/STACK-A")

    env.gh.respond("pr", "edit", "8", "--base", "main")
    merged_base = repo.forge("merge", "STACK/A")
    assert merged_base.returncode == 0, merged_base.stdout + merged_base.stderr
    retarget = ["pr", "edit", "8", "--base", "main"]
    assert retarget in env.gh_calls()
    assert repo.git("ls-remote", "--heads", "origin", "task/STACK-A") == ""
    assert "Next: forge close STACK/B" in merged_base.stdout

    # The pull request listing reflects GitHub's successful retarget before close replays it.
    env.gh.respond("pr", "list", "--head", "task/STACK-B", "--state", "all",
                   stdout=json.dumps([{"number": 8, "state": "OPEN", "body": "",
                                       "isDraft": False, "baseRefName": "main"}]))
    (repo.bin / "github-merged").unlink()
    shutil.rmtree(repo.bin / "github-merge")
    github_merge(env, "task/STACK-B")
    gh = repo.bin / "gh"
    _install(repo.bin, "gh", gh.read_text("utf-8").replace('"number": 7,', '"number": 8,'))
    review_count = len(env.review_calls())
    checks_count = len(env.gh_calls("api", "--paginate", "--jq", ".check_runs[]"))
    env.reviews(CLEAN)
    replayed = env.close("STACK/B")
    assert replayed.returncode == 0, replayed.stdout + replayed.stderr
    assert len(env.review_calls()) == review_count + 1
    # A replay needs a full review, with earlier findings retained as context.
    assert "## Repair review" not in env.prompt()
    assert earlier_note in env.prompt()
    assert len(env.gh_calls("api", "--paginate", "--jq", ".check_runs[]")) > checks_count
    child_head = repo.git("rev-parse", "origin/task/STACK-B")
    assert subprocess.run(["git", "merge-base", "--is-ancestor", base_head, child_head],
                          cwd=repo.path, capture_output=True).returncode == 1
    repo.git("merge-base", "--is-ancestor", "origin/main", child_head)
    base = repo.git("rev-parse", "origin/main")
    check = repo.forge("hook", "pr-check", "--base", base, "--head", child_head,
                       "--branch", "task/STACK-B")
    assert check.returncode == 0, check.stdout + check.stderr

    merged_child = repo.forge("merge", "STACK/B")
    assert merged_child.returncode == 0, merged_child.stdout + merged_child.stderr
    assert repo.git("show", "origin/main:app.py") == "A_VALUE = 1"
    assert repo.git("show", "origin/main:use.py") == "B_VALUE = 1"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_4_close_guides_a_manually_merged_base_before_replaying_the_child(env, previous, monkeypatch):
    repo, base_head = _stacked_pair(env, previous)
    _merge_base_by_hand(repo)
    _retarget_manual_child(env)
    d = repo.forge("task", "start", "STACK/D")
    assert d.returncode == 1
    assert d.stderr == (
        "STACK/D waits for STACK/B, which builds on STACK/A, so it starts once STACK/A merges.\n"
        "Next: forge next\n")
    github_merge(env, "task/STACK-B")
    review_count = len(env.review_calls())
    checks_count = len(env.gh_calls("api", "--paginate", "--jq", ".check_runs[]"))
    replayed = env.close("STACK/B")
    assert replayed.returncode == 0, replayed.stdout + replayed.stderr
    assert len(env.review_calls()) == review_count + 1
    assert len(env.gh_calls("api", "--paginate", "--jq", ".check_runs[]")) > checks_count
    child_head = repo.git("rev-parse", "origin/task/STACK-B")
    base = repo.git("rev-parse", "origin/main")
    # GitHub checks out a SHA without origin/HEAD, including on non-main defaults.
    repo.git("push", "-q", "origin", f"{base}:refs/heads/master")
    repo.git("fetch", "-q", "origin", "master:refs/remotes/origin/master")
    repo.git("symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    repo.git("update-ref", "-d", "refs/remotes/origin/main")
    event = repo.path / "github-event.json"
    event.write_text(json.dumps({"repository": {"default_branch": "master"}}), encoding="utf-8")
    with monkeypatch.context() as ci:
        ci.setenv("GITHUB_EVENT_PATH", str(event))
        check = repo.forge("hook", "pr-check", "--base", base, "--head", child_head,
                           "--branch", "task/STACK-B")
    assert check.returncode == 0, check.stdout + check.stderr
    repo.git("fetch", "-q", "origin", "main:refs/remotes/origin/main")
    repo.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    event.unlink()
    check = repo.forge("hook", "pr-check", "--base", base, "--head", child_head,
                       "--branch", "task/STACK-B")
    assert check.returncode == 0, check.stdout + check.stderr
    repo.git("merge-base", "--is-ancestor", "origin/main", child_head)
    assert subprocess.run(["git", "merge-base", "--is-ancestor", base_head, child_head],
                          cwd=repo.path, capture_output=True).returncode == 0
    ready = repo.path / ".git" / "forge" / "ready" / "STACK" / "B.json"
    assert ready.is_file()

    merged_child = repo.forge("merge", "STACK/B")
    assert merged_child.returncode == 0, merged_child.stdout + merged_child.stderr
    assert repo.git("show", "origin/main:use.py") == "B_VALUE = 1"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_4_manual_merge_replay_stops_on_a_clash_in_the_stacked_part(env, previous):
    repo, _ = _stacked_pair(env, previous)
    _merge_base_by_hand(repo)
    _retarget_manual_child(env)
    writer = repo.path.parent / "default-writer"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(writer))
    env.commit(writer, "use.py", "DEFAULT_VALUE = 1\n", "Update the part's file on main")
    repo.git("push", "-q", "origin", "main", cwd=writer)
    repo.git("fetch", "-q", "origin")
    github_merge(env, "task/STACK-B")
    original = repo.git("rev-parse", "origin/task/STACK-B")

    conflict = env.close("STACK/B")
    assert conflict.returncode == 1
    assert "Replaying this fix's own commits onto main conflicts in use.py." in conflict.stderr
    assert "git rebase --rebase-merges=rebase-cousins --onto origin/main" in conflict.stderr
    assert repo.git("rev-parse", "origin/task/STACK-B") == original
    assert repo.git("rev-parse", "task/STACK-B") == original
