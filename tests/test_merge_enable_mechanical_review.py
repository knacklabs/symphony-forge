"""Only the owner's generated merge switch gets a mechanical close review."""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib

import pytest

import conftest
from test_close import GREEN, blocked, body, env, finding, run  # noqa: F401
from test_merge_enable import (FIX, OWNER_MERGES, enable, owner, raw,
                               worktree)  # noqa: F401
from test_setup import _fresh_client

STORY = "enable-no-review"
REFUSED = ("The merge switch must change only forge.toml's top-level merge setting to agent; "
           "it contains another change.\n"
           "Next: the repo owner removes the extra change, then forge close let-the-agent-merge\n")


@pytest.fixture(params=["new", "adopted-v1.2.2"])
def client(owner, request):
    repo = owner.repo
    if request.param == "new":
        path, initialized = _fresh_client(repo, owner.gh, owner.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = path
    else:
        conftest.patient(lambda: shutil.copytree(
            conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True))
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Earlier adoption")
        repo.git("push", "-q", "origin", "main")
    text = (repo.path / "forge.toml").read_text("utf-8")
    # Real tests write a receipt; neither the review fake nor GitHub can produce it.
    args = [sys.executable, "-c",
            f"from pathlib import Path; Path({json.dumps(str(owner.tmp / 'tested.txt'))}).write_text('passed')"]
    command = subprocess.list2cmdline(args) if os.name == "nt" else shlex.join(args)
    text = re.sub(r'^test = .*$', lambda _: "test = " + json.dumps(command), text, flags=re.M)
    version = repo.forge("--version").stdout.split()[-1]
    text = re.sub(r'^version = .*$', lambda _: "version = " + json.dumps(version), text, flags=re.M)
    repo.write("forge.toml", text)
    repo.write("plans/spotted.json", json.dumps({"items": [{
        "key": "bug\tforge.toml\tThe merge setting needs attention",
        "kind": "bug", "path": "forge.toml", "line": 1,
        "text": "The merge setting needs attention", "from": "worker",
        "item": "another-fix", "status": "open", "closed_by": None,
    }]}))
    repo.git("add", "-A")
    # Fixture setup represents the owner's settings PR already landed on main.
    hooks = f"core.hooksPath={owner.tmp / 'no-hooks'}"
    repo.git("-c", hooks, "commit", "-qm", "Upgrade adopted settings" if request.param != "new" else "Client settings")
    repo.git("-c", hooks, "push", "-q", "origin", "main")
    owner.checks(GREEN)
    owner.reviews(blocked(finding("P1", "Missing proof list", "forge.toml")))
    return owner


def test_merge_enable_checks_the_final_published_change_runs_tests_and_waits_for_ci_without_model_review(client):
    before = raw(client, "origin/main")
    spotted = client.repo.git("show", "origin/main:plans/spotted.json")

    def check_published_change():
        ref = f"origin/fix/{FIX}"
        assert set(client.repo.git("diff", "--name-only", "origin/main", ref).splitlines()) == {
            "forge.toml", f".factory/fixes/{FIX}.json"}
        assert client.repo.git("show", f"{ref}:plans/spotted.json") == spotted
        assert (worktree(client) / "plans/spotted.json").read_text("utf-8").strip() == spotted
        assert tomllib.loads(raw(client, ref).decode("utf-8")) == {
            **tomllib.loads(before.decode("utf-8")), "merge": "agent"}

    client.checks([run("tests", "failure"), run("forge-pr-check")])
    stopped = enable(client)
    assert stopped.returncode != 0, stopped.stdout + stopped.stderr
    assert not client.review_calls()
    assert (client.tmp / "tested.txt").read_text("utf-8") == "passed"
    published = [call for call in client.gh_calls("pr") if "--body-file" in call]
    assert "Review: clean, 0 dismissed, 0 advice." in body(published[-1])
    check_published_change()
    client.checks(GREEN)
    client.open_pr("")
    ready = client.close(FIX)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    check_published_change()
    assert "A human merges its pull request" in ready.stdout
    assert not client.review_calls()
    assert not client.gh_calls("pr", "merge")
    assert raw(client, "origin/main") == before
    refused = client.repo.forge("merge", FIX)
    assert refused.stderr == OWNER_MERGES


@pytest.mark.parametrize("extra", ["file", "setting", "merge value", "mode"])
def test_merge_enable_close_refuses_extra_changes_without_a_review(client, extra):
    # Interrupt before review at the real GitHub edge, leaving the generated commit.
    client.gh.respond("pr", "create", stderr="GitHub unavailable", exit=1)
    assert enable(client).returncode != 0
    where = worktree(client)
    if extra == "file":
        client.commit(where, "extra.txt", "Other work\n")
    elif extra == "mode":
        client.repo.git("update-index", "--chmod=+x", "--", "forge.toml", cwd=where)
        client.repo.git("commit", "-qm", "Other file mode", cwd=where)
    else:
        text = (where / "forge.toml").read_text("utf-8")
        text = (re.sub(r'^interfaces = .*$', 'interfaces = ["other/**"]', text, flags=re.M) if extra == "setting"
                else text.replace('merge = "agent"', 'merge = "human"'))
        client.commit(where, "forge.toml", text)
    client.gh.respond("pr", "create", stdout="https://github.com/acme/shop/pull/7\n")
    refused = client.close(FIX)
    assert refused.returncode != 0
    assert refused.stderr == REFUSED
    assert not client.review_calls()
    assert not client.gh_calls("pr", "merge")


def test_other_fix_with_the_same_purpose_still_runs_model_review(owner):
    item, _ = owner.start_fix({"app.py": "print('hello')\n"},
                              why="Let the agent merge this repo's ready pull requests.",
                              done_when='The default branch\'s forge.toml sets merge = "agent".')
    owner.reviews(blocked(finding("P1", "Keep the normal review")))
    closed = owner.close(item)
    assert closed.returncode != 0
    assert "Keep the normal review" in closed.stderr
    assert len(owner.review_calls()) == 1
