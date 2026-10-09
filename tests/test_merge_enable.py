"""The owner switches a repo to agent merges with one command; the agent never does."""
from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_merge_command import _merge_at_github, _ready

STORY = "FORGE-MERGESWITCH-1"
FIX = "let-the-agent-merge"
BRANCH = f"fix/{FIX}"
URL = "https://github.com/acme/shop/pull/7"
READY = [f"Ready: {FIX} has a clean review and green checks. A human merges its pull request.",
         "Next: merge its pull request to switch on agent merges."]
OWNER_MERGES = (f"{FIX} changes the merge setting in forge.toml, so only the repo owner merges its "
                "pull request.\nNext: the repo owner merges its pull request, then forge next\n")
TAKEN = ("The fix let-the-agent-merge holds other work, so Forge left it alone.\n"
         "Next: finish or remove that fix, then forge merge enable\n")
OWNER_ONLY = ("Only the repo owner switches on agent merges, on main, from their own terminal.\n"
              "Next: the repo owner runs forge merge enable on main in their own terminal\n")
# Interruptions at the git and GitHub edges: a failing commit, push or pull request, red checks.
FAIL_ANY_COMMIT = "#!/bin/sh\nexit 1\n"
FAIL_SETTING_COMMIT = "#!/bin/sh\ngit diff --cached --name-only | grep -qx forge.toml && exit 1\nexit 0\n"


@pytest.fixture
def owner(env, monkeypatch):
    monkeypatch.delenv("CODEX_THREAD_ID")  # the owner's own terminal: no agent's variables
    return env


def raw(env, ref: str) -> bytes:
    """forge.toml's exact bytes at a ref, line endings included."""
    return subprocess.run(["git", "show", f"{ref}:forge.toml"], cwd=env.repo.path, check=True,
                          capture_output=True).stdout


def set_main(env, text: str) -> None:
    (env.repo.path / "forge.toml").write_bytes(text.encode("utf-8"))
    env.repo.git("commit", "-q", "-am", "Settings")
    env.repo.git("push", "-q", "origin", "main")


def hook(env, name: str, script: str | None) -> None:
    path = env.repo.path / ".git" / "hooks" / name
    if script is None:
        path.unlink()
        return
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def enable(env):
    return env.repo.forge("merge", "enable")


def prototype(env) -> None:
    set_main(env, 'stage = "prototype"\n' + (env.repo.path / "forge.toml").read_text("utf-8"))


def worktree(env) -> Path:
    return Path(env.tmp / f"{env.repo.path.name}-fix-{FIX}")


def unchanged(env, before: set[str]) -> None:
    """A refusal created nothing: no new branch or worktree, and no pull request."""
    assert set(env.repo.git("branch", "--all", "--format=%(refname)").splitlines()) == before
    assert not worktree(env).exists() or BRANCH in "".join(before)
    assert not env.gh_calls("pr", "create")


def branches(env) -> set[str]:
    return set(env.repo.git("branch", "--all", "--format=%(refname)").splitlines())


def _normal_run(env, setting):
    text = (env.repo.path / "forge.toml").read_text("utf-8")
    if setting == "human":
        set_main(env, 'merge = "human"\n' + text)
    elif setting == "crlf table":  # CRLF, ending in a table: the key goes above it, still CRLF
        set_main(env, (text.replace('models.build = { model = "opus", effort = "high" }\n', "")
                       + '[models.build]\nmodel = "opus"\neffort = "high"\n').replace("\n", "\r\n"))
    before = raw(env, "origin/main")

    switched = enable(env)

    assert switched.returncode == 0, switched.stdout + switched.stderr
    assert switched.stdout.splitlines()[-2:] == READY
    assert len(env.gh_calls("pr", "create")) == 1
    after = raw(env, f"origin/{BRANCH}")
    if setting == "human":
        assert after == before.replace(b'merge = "human"', b'merge = "agent"')
    else:
        # The file's own line ending: Windows writes the fixture's forge.toml with CRLF.
        ending = b"\r\n" if b"\r\n" in before else b"\n"
        assert after == b'merge = "agent"' + ending + before
    assert tomllib.loads(after.decode()) == {**tomllib.loads(before.decode()), "merge": "agent"}
    assert raw(env, "origin/main") == before


def _rerun(env, stage):
    if stage == "before the edit":
        hook(env, "pre-commit", FAIL_ANY_COMMIT)
    elif stage == "before the commit":
        hook(env, "pre-commit", FAIL_SETTING_COMMIT)
    elif stage == "after the commit":
        hook(env, "pre-push", FAIL_ANY_COMMIT)
    elif stage == "after the push":
        env.gh.respond("pr", "create", stderr="GitHub is down", exit=1)
    else:
        env.checks([run("tests", None, "in_progress"), run("forge-pr-check")])

    stopped = enable(env)

    assert stopped.returncode != 0
    edited = b'merge = "agent"' in (worktree(env) / "forge.toml").read_bytes()
    assert edited == (stage != "before the edit")
    pushed = env.repo.git("ls-remote", "origin", BRANCH)
    assert bool(pushed) == (stage in ("after the push", "after the pull request"))
    if stage in ("before the edit", "before the commit", "after the commit"):
        hook(env, "pre-push" if stage == "after the commit" else "pre-commit", None)
    elif stage == "after the push":
        env.gh.respond("pr", "create", stdout=URL + "\n")
    else:
        env.open_pr("")  # GitHub now lists the pull request the first run opened
        env.checks(GREEN)

    resumed = enable(env)

    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert resumed.stdout.splitlines()[-2:] == READY
    assert b'merge = "agent"' in raw(env, f"origin/{BRANCH}")
    creates = env.gh_calls("pr", "create")
    assert len(creates) == (2 if stage == "after the push" else 1)


def _prototype_run(env, _):
    prototype(env)
    main = env.repo.git("rev-parse", "origin/main")
    rollup = [{"name": name, "status": "COMPLETED", "conclusion": "SUCCESS",
               "completedAt": "2026-09-29T10:00:00Z"}
              for name in ("tests", "forge-pr-check")]

    def next_lines():
        shown = env.repo.forge("next")
        assert shown.returncode == 0, shown.stderr
        lines = [line for line in shown.stdout.splitlines() if FIX in line or "switch" in line]
        assert not [line for line in lines if "automatic" in line]
        return shown.stdout

    # Started: interrupted before the setting's commit.
    hook(env, "pre-commit", FAIL_SETTING_COMMIT)
    assert enable(env).returncode != 0
    hook(env, "pre-commit", None)
    assert (f"The fix {FIX} is started.\n"
            "Next: the repo owner runs forge merge enable in their own terminal") in next_lines()

    # The pull request is open and its checks have since passed.
    env.checks([run("tests", None, "in_progress"), run("forge-pr-check")])
    assert enable(env).returncode != 0
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps(
        [{"headRefName": BRANCH, "url": URL, "isDraft": False}]))
    # The old pr-list rollup lacks completeness and head evidence. Readiness now reads
    # the cached GraphQL result; keep the same owner-only merge assertions below.
    env.gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {
        "pullRequests": {"nodes": [{"headRefName": BRANCH, "url": URL, "isDraft": False,
            "headRefOid": env.repo.git("rev-parse", BRANCH),
            "commits": {"nodes": [{"commit": {"statusCheckRollup": {"contexts": {
                "nodes": rollup, "pageInfo": {"hasNextPage": False}}}}}]}}]}}}}))
    shown = next_lines()
    # Green checks alone formerly advertised a merge; the coordinator now requires
    # close's receipt. The owner-only merge advice appears after enable finishes below.
    assert f"The fix {FIX} is waiting for its checks.\nNext: forge close {FIX}" in shown
    assert "ready to merge" not in shown

    # Ready: the whole output names only the owner's merge.
    env.open_pr("")
    env.checks(GREEN)
    ready = enable(env)
    assert ready.returncode == 0, ready.stderr
    assert ready.stdout == "\n".join(["Updated the pull request's review block.", *READY]) + "\n"
    shown = next_lines()
    assert f"The fix {FIX} is ready to merge: {URL}\nNext: merge {URL}, then forge next" in shown
    assert f"Next: forge merge {FIX}" not in shown

    # forge merge refuses it, though a prototype otherwise merges by agent.
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main",
        "headRefOid": env.repo.git("rev-parse", BRANCH), "headRefName": BRANCH,
        "title": "Let the agent merge", "isDraft": False}))
    refused = env.repo.forge("merge", FIX)
    assert refused.returncode != 0
    assert refused.stderr == OWNER_MERGES
    assert not env.gh_calls("pr", "merge")
    assert env.repo.git("rev-parse", "origin/main") == main

    # The owner merges it; then forge next and forge merge tidy up as for any merged item.
    head = env.repo.git("rev-parse", BRANCH)
    env.repo.git("merge", "-q", "--ff-only", f"origin/{BRANCH}")
    env.repo.git("push", "-q", "origin", "main")
    env.gh.respond("pr", "list", "--state", "merged", stdout=json.dumps([{"headRefName": BRANCH}]))
    assert (f"The fix {FIX} is merged; Forge needs to finish tidying up.\n"
            f"Next: forge merge {FIX}") in next_lines()
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "MERGED", "baseRefName": "main", "headRefOid": head,
        "headRefName": BRANCH, "title": "Let the agent merge", "isDraft": False}))
    tidied = env.repo.forge("merge", FIX)
    assert tidied.returncode == 0, tidied.stderr
    assert tidied.stdout == f"Merged {FIX} and removed its worktree and local branch.\n"
    assert not worktree(env).exists() and BRANCH not in env.repo.git("branch", "--all")
    assert not env.gh_calls("pr", "merge")


def _other_fix_changes_merge(env, _):
    prototype(env)
    text = (env.repo.path / "forge.toml").read_text("utf-8")
    item, where = env.start_fix({"forge.toml": text + 'merge = "agent"\n'})
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main",
        "headRefOid": env.repo.git("rev-parse", "HEAD", cwd=where),
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    refused = env.repo.forge("merge", item)
    assert refused.stderr == OWNER_MERGES.replace(FIX, item, 1)
    assert not env.gh_calls("pr", "merge")


def _refusal(env, case):
    if case == "elsewhere":
        env.repo.git("switch", "-q", "-c", "notes")
        expected = OWNER_ONLY
    elif case == "already on":
        set_main(env, 'merge = "agent"\n' + (env.repo.path / "forge.toml").read_text("utf-8"))
        expected = "The default branch's forge.toml already lets the agent merge.\nNext: forge next\n"
    elif case == "same name":  # an unrelated fix whose name happens to match
        started = env.repo.forge("fix", "start", "Let the agent merge", "--done", "Docs say how")
        assert started.returncode == 0, started.stderr
        expected = TAKEN
    else:  # the switch's own fix, with another change added to it
        hook(env, "pre-commit", FAIL_SETTING_COMMIT)
        assert enable(env).returncode != 0
        hook(env, "pre-commit", None)
        (worktree(env) / "README.md").write_text("# More\n", encoding="utf-8")
        expected = TAKEN
    before, head = branches(env), env.repo.git("rev-parse", "HEAD")
    fix_head = env.repo.git("rev-parse", BRANCH) if BRANCH in "".join(before) else None
    fix_status = (env.repo.git("status", "--porcelain", cwd=worktree(env)) if fix_head else None)

    refused = enable(env)

    assert refused.returncode != 0
    assert refused.stderr == expected
    unchanged(env, before)
    assert env.repo.git("rev-parse", "HEAD") == head
    if fix_head:
        assert env.repo.git("rev-parse", BRANCH) == fix_head
        assert env.repo.git("status", "--porcelain", cwd=worktree(env)) == fix_status


def _agent_refused(env, agent):
    before = branches(env)

    refused = enable(env)

    assert refused.returncode != 0
    assert refused.stderr == OWNER_ONLY
    unchanged(env, before)

    # With agent merges off, forge merge names the owner's command.
    denied = env.repo.forge("merge", "tidy-readme")
    assert denied.returncode != 0
    assert denied.stderr == ('forge merge is disabled by merge = "human" in the default branch\'s '
                             "forge.toml.\nNext: the repo owner runs forge merge enable in their own terminal\n")


def _synced_skill(env, _):
    env.repo.git("checkout", "-q", "-b", "fix/sync-skill")
    synced = env.repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    for host in (".claude", ".codex"):
        skill = " ".join((env.repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "The `merge` setting is the owner's" in skill
        assert 'never change it to `"agent"` or run `forge merge enable`' in skill
        assert "tell them to run `forge merge enable` in their own terminal" in skill
        assert "edit `forge.toml` (never its `merge` setting)" in skill
        assert '| "Let the agent merge" | The owner runs `forge merge enable`' in skill


def _merge_item(env, _):
    item, _ = _ready(env)
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefName": "fix/tidy-readme",
        "headRefOid": env.repo.git("rev-parse", "fix/tidy-readme"), "title": "Tidy readme",
        "isDraft": False}))
    _merge_at_github(env)
    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stderr
    assert merged.stdout == f"Merged {item} and removed its worktree and local branch.\n"
    assert env.gh_calls("pr", "merge")


CASES_1 = [(_normal_run, "absent"), (_normal_run, "human"), (_normal_run, "crlf table"),
           *((_rerun, stage) for stage in ("before the edit", "before the commit", "after the commit",
                                           "after the push", "after the pull request")),
           (_prototype_run, "prototype"), (_other_fix_changes_merge, "other fix"),
           *((_refusal, case) for case in ("elsewhere", "already on", "same name", "other edits"))]
CASES_2 = [(_agent_refused, "CODEX_THREAD_ID"), (_agent_refused, "CLAUDECODE"),
           (_synced_skill, "skill"), (_merge_item, "merge item")]


@pytest.mark.parametrize("check,case", CASES_1, ids=[f"{c.__name__.strip('_')}-{v}" for c, v in CASES_1])
def test_1_owner_switches_on_agent_merges_with_one_command(owner, check, case):
    check(owner, case)


@pytest.mark.parametrize("check,case", CASES_2, ids=[f"{c.__name__.strip('_')}-{v}" for c, v in CASES_2])
def test_2_agent_never_switches_and_points_to_the_command(env, monkeypatch, check, case):
    if check is _agent_refused:  # the command run from an agent's shell
        monkeypatch.delenv("CODEX_THREAD_ID")
        monkeypatch.setenv(case, "1")
    check(env, case)
