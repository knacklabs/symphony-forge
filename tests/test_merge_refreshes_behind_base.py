"""Merge and land recover when the default branch advances after close."""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import GH_STUB, _install, patient
from test_close import GREEN, env  # noqa: F401
from test_setup import _fresh_client
from test_running_commands_follow_changed_forge_pin import _earlier_release

STORY = "merge-behind-base"


def _client(env, tmp_path, previous):
    if previous:
        patient(lambda: shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                                        env.repo.path, dirs_exist_ok=True))
        env.repo.git("add", "-A")
        env.repo.git("commit", "-qm", "Adopt earlier Forge")
        env.repo.git("push", "-q", "origin", "main")
    else:
        client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        env.repo.path = client
    _, prepared = env.start("prepare-client", "fix/prepare-client",
                            ".factory/fixes/prepare-client.json",
                            {"kind": "fix", "why": "Prepare the client",
                             "done_when": "The client runs its test command"}, {})
    config = (prepared / "forge.toml").read_text("utf-8")
    version = env.repo.forge("--version").stdout.split()[-1]
    config = config.replace('version = "v1.2.2"', f'version = "{version}"')
    config = config.replace('merge = "human"', 'merge = "agent"')
    config = re.sub(r'^test = .*$', 'test = "python verify.py"', config, flags=re.M)
    config = re.sub(r'^fast_test = .*\n', '', config, flags=re.M)
    env.commit(prepared, "forge.toml", config)
    synced = env.repo.forge("sync", cwd=prepared)
    assert synced.returncode == 0, synced.stderr
    log = tmp_path / "client-test-heads.jsonl"
    env.commit(prepared, "verify.py", (
        "import json, pathlib, subprocess\n"
        "assert pathlib.Path('app.py').read_text().startswith('print(')\n"
        "head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
        f"with pathlib.Path({json.dumps(log.as_posix())}).open('a', encoding='utf-8') as out:\n"
        "    out.write(json.dumps(head) + '\\n')\n"))
    env.commit(prepared, "README.md", "Original greeting\n\nKeep this paragraph.\n\nOld closing\n")
    env.repo.git("merge", "-q", "--ff-only", "fix/prepare-client")
    # The fixture's GitHub lands setup; installed client hooks rightly refuse a main push.
    remote = Path(env.repo.git("remote", "get-url", "origin"))
    env.repo.git("fetch", "-q", str(env.repo.path), "main:main", cwd=remote)
    env.checks(GREEN)
    return log


def _github_moves_default(env, conflict, merge_state, upgraded=None, failing_test=False):
    """GitHub advances main at the first merge attempt, then enforces head matching."""
    remote = env.repo.git("remote", "get-url", "origin")
    code = '''import json, pathlib, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
remote = REMOTE
conflict = CONFLICT
merge_state = MERGE_STATE
upgraded = UPGRADED
failing_test = FAILING_TEST
marker = here / "default-moved"
merged = here / "github-merged"
def git(*words, cwd=None):
    return subprocess.check_output(["git", *words], cwd=cwd, text=True).strip()
if args[:2] in (["pr", "merge"], ["pr", "view"]):
    with (here / "gh-calls.jsonl").open("a", encoding="utf-8") as calls:
        calls.write(json.dumps(args) + "\\n")
    head = git("ls-remote", remote, "refs/heads/fix/tidy-readme").split()[0]
    if args[:2] == ["pr", "view"]:
        state = "MERGED" if merged.exists() else "OPEN"
        if "--jq" in args:
            print(state)
        else:
            print(json.dumps({"number": 7, "state": state, "baseRefName": "main",
                              "headRefOid": head, "headRefName": "fix/tidy-readme",
                              "title": "Tidy readme", "isDraft": False, "body": "",
                              "mergeStateStatus": merge_state}))
        sys.exit(0)
    if not marker.exists():
        checkout = here / "other-merge"
        git("clone", "-q", remote, str(checkout))
        text = (checkout / "README.md").read_text(encoding="utf-8")
        text = text.replace("Original greeting", "Other greeting") if conflict else text.replace("Old closing", "Other closing")
        (checkout / "README.md").write_text(text, encoding="utf-8")
        git("add", "README.md", cwd=checkout)
        if upgraded is not None:
            (checkout / "forge.toml").write_text(upgraded, encoding="utf-8")
            git("add", "forge.toml", cwd=checkout)
        if failing_test:
            (checkout / "verify.py").write_text("raise AssertionError('The upgraded client test fails')\\n", encoding="utf-8")
            git("add", "verify.py", cwd=checkout)
        git("commit", "-qm", "Another pull request merged", cwd=checkout)
        git("push", "-q", "origin", "main", cwd=checkout)
        marker.write_text(git("rev-parse", "HEAD", cwd=checkout), encoding="utf-8")
        sys.stderr.write("Pull request branch is not up to date with the base branch.\\n"
                         "gh pr checkout 7 && git fetch origin main && git merge origin/main\\n")
        sys.exit(1)
    assert args[args.index("--match-head-commit") + 1] == head
    checkout = here / "github-merge"
    git("clone", "-q", remote, str(checkout))
    git("fetch", "-q", "origin", "fix/tidy-readme", cwd=checkout)
    subprocess.run(["git", "merge-base", "--is-ancestor", marker.read_text(), "FETCH_HEAD"],
                   cwd=checkout, check=True)
    git("merge", "--squash", "FETCH_HEAD", cwd=checkout)
    git("commit", "-qm", args[args.index("--subject") + 1], cwd=checkout)
    git("push", "-q", "origin", "main", cwd=checkout)
    merged.write_text("merged", encoding="utf-8")
    sys.exit(0)
'''.replace("REMOTE", json.dumps(remote)).replace("CONFLICT", repr(conflict)).replace(
    "MERGE_STATE", json.dumps(merge_state)).replace("UPGRADED", repr(upgraded)).replace(
    "FAILING_TEST", repr(failing_test))
    fallback = GH_STUB.format(python=sys.executable).split("\n", 1)[1]
    _install(env.repo.bin, "gh", "#!" + sys.executable + "\n" + code + fallback)


@pytest.mark.parametrize("previous", [False, True], ids=["new-repo", "earlier-adoption"])
@pytest.mark.parametrize("command", ["merge", "land"])
@pytest.mark.parametrize("merge_state,conflict", [("BEHIND", False), ("DIRTY", False),
                                                 ("DIRTY", True)],
                         ids=["behind-clean", "hint-clean", "conflict"])
def test_1_merge_and_land_refresh_behind_base_or_preserve_conflict(
        env, tmp_path, previous, command, conflict, merge_state):
    test_log = _client(env, tmp_path, previous)
    item, where = env.start_fix({"app.py": "print('hello')\n",
                                 "README.md": "Branch greeting\n\nKeep this paragraph.\n\nOld closing\n"})
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    first_head = env.repo.git("rev-parse", "HEAD", cwd=where)
    before_reviews = len(env.review_calls())
    _github_moves_default(env, conflict, merge_state)

    result = env.repo.forge(command, item)

    attempts = env.gh_calls("pr", "merge")
    if conflict:
        assert result.returncode == 1, result.stdout + result.stderr
        assert result.stderr.splitlines()[-2] == (
            "Merging main into fix/tidy-readme conflicts in README.md.")
        assert re.fullmatch(
            r"Next: git -C .+ merge origin/main, follow Keeping work moving in "
            r"\.codex/skills/forge/SKILL\.md or \.claude/skills/forge/SKILL\.md and commit, "
            r"then forge close tidy-readme", result.stderr.splitlines()[-1])
        assert len(attempts) == 1
        assert len(env.review_calls()) == before_reviews
        assert env.repo.git("rev-parse", "HEAD", cwd=where) == first_head
        assert env.repo.git("status", "--porcelain", cwd=where) == ""
        assert (where / "README.md").read_text("utf-8") == (
            "Branch greeting\n\nKeep this paragraph.\n\nOld closing\n")
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(attempts) == 2
        heads = [call[call.index("--match-head-commit") + 1] for call in attempts]
        assert heads[0] == first_head and heads[1] != first_head
        advanced = (env.repo.bin / "default-moved").read_text("utf-8")
        env.repo.git("merge-base", "--is-ancestor", advanced, heads[1])
        assert len(env.review_calls()) == before_reviews + 1
        env.repo.git("merge-base", "--is-ancestor", advanced, env.review_calls()[-1]["head"])
        tested = [json.loads(line) for line in test_log.read_text("utf-8").splitlines()]
        assert len(tested) == 2
        env.repo.git("merge-base", "--is-ancestor", advanced, tested[-1])
        assert any(f"/commits/{heads[1]}/" in call[-1] for call in env.gh_calls("api"))
        assert env.repo.git("show", "origin/main:app.py") == "print('hello')"
        assert env.repo.git("show", "origin/main:README.md") == (
            "Branch greeting\n\nKeep this paragraph.\n\nOther closing")
        assert not where.exists()
        assert any("main" in line and "close" in line.lower() and "again" in line.lower()
                   for line in result.stdout.splitlines()), result.stdout


@pytest.mark.parametrize("previous", [False, True], ids=["new-repo", "earlier-adoption"])
@pytest.mark.parametrize("command,failing_test", [("merge", False), ("land", False),
                                                ("merge", True)],
                         ids=["merge-green-close", "land-green-close", "merge-red-close"])
def test_2_behind_recovery_finishes_close_under_the_upgraded_pin_before_retrying_merge(
        env, tmp_path, monkeypatch, previous, command, failing_test):
    test_log = _client(env, tmp_path, previous)
    current = env.repo.forge("--version").stdout.split()[-1]
    _earlier_release(env)
    monkeypatch.setenv("FORGE_PINNED_RUN", "v1.2.2")
    _, prepared = env.start("repin-client", "fix/repin-client",
                            ".factory/fixes/repin-client.json",
                            {"kind": "fix", "why": "Run the earlier release",
                             "done_when": "The client uses its earlier Forge pin"}, {})
    config = (prepared / "forge.toml").read_text("utf-8")
    config = re.sub(r'version = "[^"]+"', 'version = "v1.2.2"', config)
    env.commit(prepared, "forge.toml", config)
    env.repo.git("merge", "-q", "--ff-only", "fix/repin-client")
    remote = Path(env.repo.git("remote", "get-url", "origin"))
    env.repo.git("fetch", "-q", str(env.repo.path), "main:main", cwd=remote)
    item, where = env.start_fix({"app.py": "print('hello')\n",
                                 "README.md": "Branch greeting\n\nKeep this paragraph.\n\nOld closing\n"})
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    first_head = env.repo.git("rev-parse", "HEAD", cwd=where)
    before_reviews = len(env.review_calls())
    upgraded = config.replace('version = "v1.2.2"', f'version = "{current}"\nfast_test = ""')
    _github_moves_default(env, False, "BEHIND", upgraded, failing_test)

    done = env.repo.forge(command, item, cwd=where)

    attempts = env.gh_calls("pr", "merge")
    resumed = [entry["args"][5:] for line in
               (env.repo.bin / "uv-calls.jsonl").read_text("utf-8").splitlines()
               if (entry := json.loads(line))["args"][5] in {"close", "merge", "land"}]
    # Merge must finish the selected release's close first; land resumes its existing close loop.
    expected = [["land", item]] if command == "land" else (
        [["close", item]] if failing_test else [["close", item], ["merge", item]])
    assert resumed == expected
    if failing_test:
        assert done.returncode == 1, done.stdout + done.stderr
        assert "`python verify.py` failed on this machine, so close stopped before the review" in done.stderr
        # Close keeps the test output for the next worker instead of printing its traceback.
        logs = Path(env.repo.git("rev-parse", "--path-format=absolute", "--git-common-dir")) / "forge"
        assert any("The upgraded client test fails" in log.read_text("utf-8")
                   for log in logs.glob("test-*.log"))
        assert len(attempts) == 1
        assert len(env.review_calls()) == before_reviews
        assert where.is_dir()
        assert not (env.repo.bin / "github-merged").exists()
        return
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(attempts) == 2
    heads = [call[call.index("--match-head-commit") + 1] for call in attempts]
    assert heads[0] == first_head and heads[1] != first_head
    advanced = (env.repo.bin / "default-moved").read_text("utf-8")
    env.repo.git("merge-base", "--is-ancestor", advanced, heads[1])
    assert len(env.review_calls()) == before_reviews + 1
    env.repo.git("merge-base", "--is-ancestor", advanced, env.review_calls()[-1]["head"])
    tested = [json.loads(line) for line in test_log.read_text("utf-8").splitlines()]
    assert len(tested) == 2
    env.repo.git("merge-base", "--is-ancestor", advanced, tested[-1])
    assert any(f"/commits/{heads[1]}/" in call[-1] for call in env.gh_calls("api"))
    assert env.repo.git("show", "origin/main:forge.toml") == upgraded.strip()
    assert env.repo.git("show", "origin/main:README.md") == (
        "Branch greeting\n\nKeep this paragraph.\n\nOther closing")
    assert not where.exists()
