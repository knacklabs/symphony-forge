"""Close takes in main only for a local or GitHub-reported clash."""
import json
import sys

import pytest

from conftest import GH_STUB, _install
from test_close import CLEAN, blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "FORGE-MAINONCE-1"


def _green_pull_request(env):
    # GitHub reports the actual pushed head; it does not decide whether Forge merges main.
    remote = env.repo.git("remote", "get-url", "origin")
    code = '''import json, pathlib, subprocess, sys
args = sys.argv[1:]
if args[:2] == ["pr", "view"]:
    here = pathlib.Path(__file__).resolve().parent
    with (here / "gh-calls.jsonl").open("a", encoding="utf-8") as calls:
        calls.write(json.dumps(args) + "\\n")
    head = subprocess.check_output(["git", "ls-remote", REMOTE,
                                   "refs/heads/fix/tidy-readme"], text=True).split()[0]
    print(json.dumps({"mergeable": "MERGEABLE", "headRefOid": head}))
    sys.exit(0)
'''.replace("REMOTE", json.dumps(remote))
    fallback = GH_STUB.format(python=sys.executable).split("\n", 1)[1]
    _install(env.repo.bin, "gh", "#!" + sys.executable + "\n" + code + fallback)


def _open_pr(env, content, *, mergeable="MERGEABLE", merge_state="CLEAN"):
    env.gh.respond("pr", "list", "--head", stdout=json.dumps([{
        "number": 7, "state": "OPEN", "body": content, "isDraft": True,
        "mergeable": mergeable, "mergeStateStatus": merge_state,
    }]))


@pytest.mark.parametrize("previous", [False, True], ids=["new-repo", "earlier-adoption"])
def test_1_close_rounds_leave_unrelated_main_changes_out_of_the_pull_request(env, previous):
    client(env, previous)
    _green_pull_request(env)
    item, where = env.start_fix({"app.py": "print('draft greeting')\n"})
    env.commit(env.repo.path, "NEWS.md", "Another change landed\n")
    env.repo.git("push", "-q", "origin", "main")
    env.reviews(blocked(finding("P1", "Greeting needs the final text")), CLEAN)

    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert "The review left serious findings open:" in first.stderr
    _open_pr(env, body(env.gh_calls("pr", "create")[-1]))
    env.commit(where, "app.py", "print('hello')\n", "Finish the greeting")
    env.commit(env.repo.path, "NEWS.md", "Another unrelated change landed\n")
    env.repo.git("push", "-q", "origin", "main")
    second = env.close(item)

    assert second.returncode == 0, second.stdout + second.stderr
    assert "Ready:" in second.stdout
    # The old contract always merged a moving main. The new one keeps this branch's own history.
    assert env.repo.git("log", "--merges", "--oneline", "origin/main..fix/tidy-readme") == ""
    pushed = env.repo.git("ls-remote", "origin", "refs/heads/fix/tidy-readme").split()[0]
    assert pushed == env.repo.git("rev-parse", "HEAD", cwd=where)
    assert not (where / "NEWS.md").exists()
    calls = env.review_calls()
    assert len(calls) == 2
    for call in calls:
        base = call["args"][call["args"].index("--base") + 1]
        reviewed = env.repo.git("diff", "--name-only", f"{base}...{call['head']}", cwd=where)
        assert {path for path in reviewed.splitlines()
                if not path.startswith((".factory/", "plans/"))} == {"app.py"}


@pytest.mark.parametrize("previous", [False, True], ids=["new-repo", "earlier-adoption"])
@pytest.mark.parametrize("clash", ["trial", "CONFLICTING", "BEHIND"])
def test_2_close_merges_main_once_when_a_local_or_github_clash_requires_it(env, previous, clash):
    client(env, previous)
    _green_pull_request(env)
    if clash == "trial":
        original = (env.repo.path / "AGENTS.md").read_text("utf-8")
        assert "Working here with Forge" in original
        env.commit(env.repo.path, "AGENTS.md", original.replace("Working here with Forge", "Old guide", 1))
        env.repo.git("push", "-q", "origin", "main")
        item, where = env.start_fix({"AGENTS.md": original.replace("Working here with Forge", "Branch guide", 1)})
        # Same-line generated-guide conflicts are real trial conflicts, resolved by close's sync.
        advanced = env.commit(env.repo.path, "AGENTS.md", original.replace("Working here with Forge", "Default guide", 1))
    elif clash == "CONFLICTING":
        env.commit(env.repo.path, "plans/roadmap.json", json.dumps({"items": []}, indent=2) + "\n")
        env.repo.git("push", "-q", "origin", "main")
        item, where = env.start_fix({"plans/roadmap.json": json.dumps({"items": [
            {"key": "WORKER-1", "title": "Worker plan", "status": "pending", "order": 1}
        ]}, indent=2) + "\n"})
        advanced = env.commit(env.repo.path, "plans/roadmap.json", json.dumps({"items": [
            {"key": "MAIN-1", "title": "Main plan", "status": "pending", "order": 1}
        ]}, indent=2) + "\n")
        _open_pr(env, "", mergeable="CONFLICTING", merge_state="DIRTY")
    else:
        item, where = env.start_fix()
        advanced = env.commit(env.repo.path, "NEWS.md", "Main has moved\n")
        _open_pr(env, "", merge_state="BEHIND")
    env.repo.git("push", "-q", "origin", "main")

    if clash == "CONFLICTING":
        synced = env.repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stderr
        assert env.repo.git("status", "--porcelain", cwd=where) == ""
        env.repo.git("fetch", "-q", "origin", "main", cwd=where)
        # The local roadmap merge driver resolves this clash; GitHub has no driver.
        env.repo.git("merge-tree", "--write-tree", "--no-messages", "HEAD", "origin/main", cwd=where)

    first = env.close(item)

    assert first.returncode == 0, first.stdout + first.stderr
    assert "Ready:" in first.stdout
    env.repo.git("merge-base", "--is-ancestor", advanced, "HEAD", cwd=where)
    merges = env.repo.git("rev-list", "--merges", "origin/main..HEAD", cwd=where).splitlines()
    assert len(merges) == 1
    assert len(env.repo.git("rev-list", "--parents", "-1", merges[0], cwd=where).split()) == 3
    if clash == "trial":
        assert "Working here with Forge" in (where / "AGENTS.md").read_text("utf-8")
        assert len(env.gh_calls("pr", "create")) == 1
    elif clash == "CONFLICTING":
        assert {row["key"] for row in json.loads(
            (where / "plans/roadmap.json").read_text("utf-8"))["items"]} == {"WORKER-1", "MAIN-1"}
    else:
        assert (where / "NEWS.md").read_text("utf-8") == "Main has moved\n"
    content = body((env.gh_calls("pr", "edit") or env.gh_calls("pr", "create"))[-1])
    _open_pr(env, content)
    # GitHub now reports MERGEABLE and main moves on unrelated lines. The old
    # unconditional merge would add a second merge; this round must leave it out.
    writer = env.tmp / "later-main"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(writer))
    env.commit(writer, "AFTER.md", "Unrelated work after the clash\n")
    env.repo.git("push", "-q", "origin", "main", cwd=writer)

    second = env.close(item)

    assert second.returncode == 0, second.stdout + second.stderr
    assert "Ready:" in second.stdout
    assert env.repo.git("rev-list", "--merges", "origin/main..HEAD", cwd=where).splitlines() == merges
    pushed = env.repo.git("ls-remote", "origin", "refs/heads/fix/tidy-readme").split()[0]
    assert pushed == env.repo.git("rev-parse", "HEAD", cwd=where)
