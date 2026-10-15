"""Close takes in main only for a local or GitHub-reported clash."""
import json
import re
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


def _draft_pull_request(env, content, require_current, *, is_draft=True, advance_on_checks=None):
    remote = env.repo.git("remote", "get-url", "origin")
    state = env.repo.bin / "draft-pr.json"
    state.write_text(json.dumps({"body": content, "isDraft": is_draft}), encoding="utf-8")
    code = '''import json, pathlib, subprocess, sys
args = sys.argv[1:]
here = pathlib.Path(__file__).resolve().parent
if (ADVANCE_ON_CHECKS is not None and args[:1] == ["api"]
        and any("/check-runs" in arg for arg in args)
        and not (here / "main-advanced-during-checks").exists()):
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=ADVANCE_ON_CHECKS, check=True)
    (here / "main-advanced-during-checks").write_text("advanced", encoding="utf-8")
if args[:2] in (["pr", "list"], ["pr", "view"], ["pr", "ready"], ["pr", "edit"]):
    with (here / "gh-calls.jsonl").open("a", encoding="utf-8") as calls:
        calls.write(json.dumps(args) + "\\n")
    file = here / "draft-pr.json"
    state = json.loads(file.read_text("utf-8"))
    if args[:2] == ["pr", "ready"]:
        state["isDraft"] = "--undo" in args
    if "--body-file" in args:
        state["body"] = pathlib.Path(args[args.index("--body-file") + 1]).read_text("utf-8")
    file.write_text(json.dumps(state), encoding="utf-8")
    head = subprocess.check_output(["git", "ls-remote", REMOTE,
                                   "refs/heads/fix/tidy-readme"], text=True).split()[0]
    base = subprocess.check_output(["git", "ls-remote", REMOTE,
                                   "refs/heads/main"], text=True).split()[0]
    behind = subprocess.run(["git", "merge-base", "--is-ancestor", base, head],
                            cwd=REMOTE).returncode != 0
    status = "DRAFT" if state["isDraft"] else "BEHIND" if behind and REQUIRE_CURRENT else "CLEAN"
    pr = {"number": 7, "state": "OPEN", "body": state["body"],
          "isDraft": state["isDraft"], "mergeable": "MERGEABLE",
          "mergeStateStatus": status, "headRefOid": head}
    with (here / "draft-pr-looks.jsonl").open("a", encoding="utf-8") as looks:
        looks.write(json.dumps({"args": args, "head": head, "status": status,
                               **({"body": state["body"]} if args[:2] == ["pr", "edit"] else {})}) + "\\n")
    if args[:2] == ["pr", "list"]:
        print(json.dumps([pr]))
    elif args[:2] == ["pr", "view"]:
        print(json.dumps(pr))
    sys.exit(0)
'''.replace("REMOTE", json.dumps(remote)).replace("REQUIRE_CURRENT", repr(require_current)).replace(
    "ADVANCE_ON_CHECKS", json.dumps(advance_on_checks.as_posix()) if advance_on_checks else "None")
    fallback = GH_STUB.format(python=sys.executable).split("\n", 1)[1]
    _install(env.repo.bin, "gh", "#!" + sys.executable + "\n" + code + fallback)


def _draft_clash(env, require_current):
    tested = env.tmp / "draft-test-heads.jsonl"
    script = env.tmp / "verify-draft.py"
    script.write_text("import json, pathlib, subprocess, sys\n"
                      "greeting = subprocess.check_output([sys.executable, 'app.py'], text=True).strip()\n"
                      "assert greeting in {'draft greeting', 'hello'}\n"
                      "head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
                      f"with pathlib.Path({json.dumps(tested.as_posix())}).open('a', encoding='utf-8') as out:\n"
                      "    out.write(json.dumps(head) + '\\n')\n", encoding="utf-8")
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    command = f'"{sys.executable}" "{script.as_posix()}"'
    config = re.sub(r'^fast_test = .*\n', '', config, flags=re.M)
    env.commit(env.repo.path, "forge.toml", "fast_test = " + json.dumps(command) + "\n" + config)
    env.commit(env.repo.path, "NEWS.md", "Old news\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({"app.py": "print('draft greeting')\n"})
    env.reviews(blocked(finding("P1", "Greeting needs final text")), CLEAN)
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert "The review left serious findings open:" in first.stderr
    created = env.gh_calls("pr", "create")[-1]
    assert "--draft" in created
    _draft_pull_request(env, body(created), require_current)
    env.commit(where, "app.py", "print('hello')\n", "Finish the greeting")
    advanced = env.commit(env.repo.path, "NEWS.md", "New news from another change\n")
    env.repo.git("push", "-q", "origin", "main")
    return item, where, advanced, tested


def _clash_during_checks(env, require_current):
    env.commit(env.repo.path, "NEWS.md", "Old news\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({"app.py": "print('draft greeting')\n"})
    first = env.close(item)
    assert first.returncode == 0, first.stdout + first.stderr
    assert "Ready:" in first.stdout
    created = env.gh_calls("pr", "create")[-1]
    writer = env.tmp / "main-during-checks"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(writer))
    advanced = env.commit(writer, "NEWS.md", "Main advanced while checks ran\n")
    _draft_pull_request(env, body(created), require_current,
                        is_draft=False, advance_on_checks=writer)
    env.commit(where, "app.py", "print('hello')\n", "Finish the greeting")
    return item, where, advanced


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
@pytest.mark.parametrize("problem,next_action", [
    ("GraphQL: API rate limit exceeded", "wait for GitHub's rate limit to reset"),
    ("GraphQL: Resource not accessible by integration", "fix the GitHub problem"),
], ids=["rate-limit", "other-refusal"])
def test_3_close_stops_after_github_refuses_one_pull_request_body_update(env, previous, problem, next_action):
    client(env, previous)
    _green_pull_request(env)
    item, where = env.start_fix({"app.py": "print('draft greeting')\n"})
    initial = env.close(item)
    assert initial.returncode == 0, initial.stdout + initial.stderr
    assert "Ready:" in initial.stdout
    _open_pr(env, body(env.gh_calls("pr", "create")[-1]))
    env.commit(where, "app.py", "print('hello')\n", "Finish the greeting")
    before = len(env.gh_calls("pr", "edit"))
    env.gh.respond("pr", "edit", "7", "--body-file", stderr=problem + "\n", exit=1)

    stopped = env.close(item)

    assert stopped.returncode != 0, stopped.stdout + stopped.stderr
    assert "Ready:" not in stopped.stdout
    assert len(env.gh_calls("pr", "edit")) - before == 1
    assert stopped.stderr == (
        "GitHub refused to update this pull request, so this command stopped.\n"
        f"{problem}\nNext: {next_action}, then retry this command\n"
    )


@pytest.mark.parametrize("previous", [False, True], ids=["new-repo", "earlier-adoption"])
@pytest.mark.parametrize("clash", ["trial", "CONFLICTING", "BEHIND", "DRAFT", "DRAFT-clean",
                                   "LATE-BEHIND", "LATE-clean"])
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
        common = {"key": "BASE-1", "title": "Base plan", "status": "pending", "order": 1}
        env.commit(env.repo.path, "plans/roadmap.json", json.dumps({"items": [common]}, indent=2) + "\n")
        env.repo.git("push", "-q", "origin", "main")
        item, where = env.start_fix({"plans/roadmap.json": json.dumps({"items": [common,
            {"key": "WORKER-1", "title": "Worker plan", "status": "pending", "order": 1}
        ]}, indent=2) + "\n"})
        advanced = env.commit(env.repo.path, "plans/roadmap.json", json.dumps({"items": [common,
            {"key": "MAIN-1", "title": "Main plan", "status": "pending", "order": 1}
        ]}, indent=2) + "\n")
        _open_pr(env, "", mergeable="CONFLICTING", merge_state="DIRTY")
    elif clash.startswith("DRAFT"):
        item, where, advanced, tested = _draft_clash(env, clash == "DRAFT")
    elif clash.startswith("LATE"):
        item, where, advanced = _clash_during_checks(env, clash == "LATE-BEHIND")
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
    if clash not in ("DRAFT-clean", "LATE-clean"):
        env.repo.git("merge-base", "--is-ancestor", advanced, "HEAD", cwd=where)
    merges = env.repo.git("rev-list", "--merges", "origin/main..HEAD", cwd=where).splitlines()
    assert len(merges) == (0 if clash in ("DRAFT-clean", "LATE-clean") else 1)
    if merges:
        assert len(env.repo.git("rev-list", "--parents", "-1", merges[0], cwd=where).split()) == 3
    if clash == "trial":
        assert "Working here with Forge" in (where / "AGENTS.md").read_text("utf-8")
        assert len(env.gh_calls("pr", "create")) == 1
    elif clash == "CONFLICTING":
        assert {row["key"] for row in json.loads(
            (where / "plans/roadmap.json").read_text("utf-8"))["items"]} == {"BASE-1", "WORKER-1", "MAIN-1"}
    elif clash.startswith("DRAFT"):
        assert (where / "NEWS.md").read_text("utf-8") == (
            "New news from another change\n" if clash == "DRAFT" else "Old news\n")
        looks = [json.loads(line) for line in
                 (env.repo.bin / "draft-pr-looks.jsonl").read_text("utf-8").splitlines()]
        assert any(look["status"] == "DRAFT" for look in looks)
        ready = next(n for n, look in enumerate(looks) if look["args"][:2] == ["pr", "ready"])
        assert looks[ready]["status"] == ("BEHIND" if clash == "DRAFT" else "CLEAN")
        assert any(look["status"] == "CLEAN" for look in looks[ready + 1:])
        for call in env.review_calls():
            base = call["args"][call["args"].index("--base") + 1]
            reviewed = env.repo.git("diff", "--name-only", f"{base}...{call['head']}", cwd=where)
            assert {path for path in reviewed.splitlines()
                    if not path.startswith((".factory/", "plans/"))} == {"app.py"}
        test_heads = [json.loads(line) for line in tested.read_text("utf-8").splitlines()]
        assert env.repo.git("show", f"{test_heads[-1]}:app.py", cwd=where) == "print('hello')"
        pushed_head = env.repo.git("ls-remote", "origin", "refs/heads/fix/tidy-readme").split()[0]
        assert any(f"/commits/{pushed_head}/check-runs" in call[-1] for call in env.gh_calls("api"))
    elif clash.startswith("LATE"):
        assert (env.repo.bin / "main-advanced-during-checks").exists()
        assert (where / "NEWS.md").read_text("utf-8") == (
            "Main advanced while checks ran\n" if clash == "LATE-BEHIND" else "Old news\n")
        looks = [json.loads(line) for line in
                 (env.repo.bin / "draft-pr-looks.jsonl").read_text("utf-8").splitlines()]
        assert looks[0]["args"][:2] == ["pr", "list"] and looks[0]["status"] == "CLEAN"
        written = [look["body"] for look in looks if look["args"][:2] == ["pr", "edit"]]
        assert len(written) <= (3 if clash == "LATE-clean" else 6), written
        assert len(set(written)) == len(written), written
        assert not any(look["args"][:2] == ["pr", "ready"] for look in looks)
        if clash == "LATE-BEHIND":
            behind = next(n for n, look in enumerate(looks) if look["status"] == "BEHIND")
            assert any(look["status"] == "CLEAN" for look in looks[behind + 1:])
        else:
            assert all(look["status"] == "CLEAN" for look in looks)
        pushed_head = env.repo.git("ls-remote", "origin", "refs/heads/fix/tidy-readme").split()[0]
        assert any(f"/commits/{pushed_head}/check-runs" in call[-1] for call in env.gh_calls("api"))
        published = json.loads(re.search(r"<!-- forge:time-record (\{.*?\}) -->", written[-1], re.S)[1])
        assert published["ready"] == {"commit": pushed_head, "review": "clean"}
        assert any(event.get("event") == "CI result" and event.get("commit") == pushed_head
                   and event.get("outcome") == "passed" for event in published["events"])
        for call in env.review_calls():
            base = call["args"][call["args"].index("--base") + 1]
            reviewed = env.repo.git("diff", "--name-only", f"{base}...{call['head']}", cwd=where)
            assert {path for path in reviewed.splitlines()
                    if not path.startswith((".factory/", "plans/"))} == {"app.py"}
    else:
        assert (where / "NEWS.md").read_text("utf-8") == "Main has moved\n"
    content = body((env.gh_calls("pr", "edit") or env.gh_calls("pr", "create"))[-1])
    if not clash.startswith(("DRAFT", "LATE")):
        _open_pr(env, content)
    # GitHub now reports MERGEABLE and main moves on unrelated lines. The old
    # unconditional merge would add a second merge; this round must leave it out.
    if clash not in ("DRAFT", "LATE-BEHIND"):  # the up-to-date rule still applies after refresh
        writer = env.tmp / "later-main"
        env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(writer))
        env.commit(writer, "AFTER.md", "Unrelated work after the clash\n")
        env.repo.git("push", "-q", "origin", "main", cwd=writer)

    if clash.startswith("LATE"):
        before_looks = len((env.repo.bin / "draft-pr-looks.jsonl").read_text("utf-8").splitlines())
    second = env.close(item)

    assert second.returncode == 0, second.stdout + second.stderr
    assert "Ready:" in second.stdout
    if clash.startswith("LATE"):
        subsequent = [json.loads(line) for line in
                      (env.repo.bin / "draft-pr-looks.jsonl").read_text("utf-8").splitlines()[before_looks:]]
        edits = [look["body"] for look in subsequent if look["args"][:2] == ["pr", "edit"]]
        # A reused clean review and Ready each need at most one update; rereading GitHub
        # must not discard an updated body and send the same Ready text again.
        assert len(edits) <= 2, edits
        assert len(set(edits)) == len(edits), edits
    assert env.repo.git("rev-list", "--merges", "origin/main..HEAD", cwd=where).splitlines() == merges
    pushed = env.repo.git("ls-remote", "origin", "refs/heads/fix/tidy-readme").split()[0]
    assert pushed == env.repo.git("rev-parse", "HEAD", cwd=where)
