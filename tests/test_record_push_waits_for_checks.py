"""Blocked close records wait for published code checks (issue 1723)."""
import json
import os
import sys
import pytest

from test_close import CLEAN, GREEN, blocked, finding, env, run  # noqa: F401
from test_checks_finish_after_long_runner_queues import _watch_progress
from test_close_pushes_record_after_code_ci import HOOK

STORY = "FIX-RECORDS-CANCEL-CI"

@pytest.mark.platform
@pytest.mark.parametrize("fake_clock,polls,override,conclusion", [
    (150, 3, None, "success"), (150, 3, None, "failure"), (150, 3, "0", "success"),
    (150, 3, None, "code"),
    (150, 3, None, "queued"), (150, 3, None, "net-empty"),
    (150, 3, None, "earlier-running"), (150, 3, None, "earlier-queued"),
    pytest.param(150, 3, None, "interrupt", marks=pytest.mark.skipif(
        os.name == "nt", reason="POSIX signal delivery to the close process"))],
                         indirect=["fake_clock"])
def test_1_record_push_waits_until_the_running_code_ci_run_ends(env, tmp_path, monkeypatch, fake_clock,
                                                               polls, override, conclusion):
    # Audit: the two phases share one output cadence; an explicit wait limit must
    # flush saved records before exit. The existing remote hook
    # owns that lifecycle, which ordinary post-push wait tests cannot observe.
    progress = _watch_progress(tmp_path)
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", "\n".join(
        line for line in config.splitlines() if line.partition("=")[0].strip() != "test_place")
        + '\ntest_place = "ci"\n')
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Tests run in CI")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.open_pr("")
    env.repo.git("push", "-q", "-u", "origin", "fix/tidy-readme", cwd=where)
    earlier = conclusion.startswith("earlier-")
    code_head = env.repo.git("rev-parse", "HEAD", cwd=where)
    if conclusion == "net-empty" or earlier:
        env.reviews(CLEAN)
        env.checks(GREEN)
        first = env.close(item)
        assert first.returncode == 0, first.stdout + first.stderr
        env.commit(where, "plans/spotted/temporary.md", "Temporary record\n", "Save a record")
        env.repo.git("rm", "plans/spotted/temporary.md", cwd=where)
        env.repo.git("commit", "-q", "-m", "Remove the temporary record", cwd=where)
        env.repo.git("fetch", "origin", cwd=where)
    parent = env.repo.git("rev-parse", "origin/fix/tidy-readme", cwd=where)
    log = tmp_path / "remote-pushes.jsonl"
    hook = env.repo.path.parent / env.repo.git("remote", "get-url", "origin")
    hook = (hook if hook.is_absolute() else env.repo.path / hook) / "hooks/pre-receive"
    hook.write_text(HOOK.format(python=sys.executable, parent=parent, log=log.as_posix(),
                                calls=(env.repo.bin / "gh-calls.jsonl").as_posix()), "utf-8")
    if earlier:
        # Audit: the remote must see an earlier same-code rerun finish before
        # receiving records. Immediate-head tests miss it once a record run is green.
        # The real push hook and GitHub edge need no production seam.
        before = len(env.gh_calls("api", query="branch=fix/tidy-readme"))
        hook.write_text(hook.read_text("utf-8").replace(
            '"commits/" + ' + repr(parent) + ' + "/check-runs" in call',
            '"branch=fix/tidy-readme" in call').replace(
            "looked = sum", f"looked = -{before} + sum"), "utf-8")
    hook.chmod(0o755)
    monkeypatch.delenv("FORGE_CHECKS_WAIT", raising=False)
    if override is not None:
        monkeypatch.setenv("FORGE_CHECKS_WAIT", override)
    # The remote observes actual pushes. Existing coverage covers clean reviews,
    # but misses blocked reviews bypassing the wait. No test-only seam is needed.
    env.reviews(CLEAN if conclusion == "net-empty" else
                blocked(finding("P1", "The main action fails")))
    # The record push must not cancel the code's queued or running tests.
    # This lifecycle boundary needs the remote push hook, which ordinary wait tests lack.
    lines = lambda rows: "".join(json.dumps(row) + "\n" for row in rows)  # noqa: E731
    running = lines([run("docs-check"), run("tests (1/2)", None, "in_progress")])
    if conclusion in ("queued", "net-empty"):
        running = lines([run("forge-pr-check")])
    finished = lines([run("docs-check"), run("tests", "failure" if conclusion == "failure" else "success")])
    env.checks(GREEN)
    env.gh.respond("api", "--paginate", "--jq", ".check_runs[]", stdout="")
    rules = json.loads(env.gh.responses.read_text("utf-8"))
    rules[-1]["then"] = [running] * 2 + [lines(GREEN)] if override is None else [lines(GREEN)]
    env.gh.responses.write_text(json.dumps(rules), "utf-8")
    if conclusion in ("queued", "net-empty"):
        env.gh.respond("api", "--jq", ".workflow_runs[]", stdout="")
        rules = json.loads(env.gh.responses.read_text("utf-8"))
        workflow = {"id": 77, "head_sha": parent, "event": "pull_request", "status": "queued"}
        rules[-1]["then"] = [lines([workflow])] * polls + [lines([
            {**workflow, "status": "completed", "conclusion": "success"}])]
        env.gh.responses.write_text(json.dumps(rules), "utf-8")
    endpoint = f"repos/{{owner}}/{{repo}}/commits/{parent}/check-runs?per_page=100"
    env.gh.respond("api", "--paginate", "--jq", ".check_runs[]", endpoint, stdout="")
    rules = json.loads(env.gh.responses.read_text("utf-8"))
    rules[-1]["then"] = [running] * polls + [finished]
    env.gh.responses.write_text(json.dumps(rules), "utf-8")
    if earlier:
        # GitHub keeps the original run ID when someone starts another attempt.
        running = {"id": 77, "head_sha": code_head, "event": "pull_request", "run_attempt": 2,
                   "status": "queued" if conclusion == "earlier-queued" else "in_progress"}
        record = {"id": 88, "head_sha": parent, "event": "pull_request", "status": "completed",
                  "conclusion": "success"}
        env.gh.respond("api", "--jq", ".workflow_runs[]", stdout="")
        rules = json.loads(env.gh.responses.read_text("utf-8"))
        rules[-1]["then"] = [lines([record, running])] * polls + [lines([
            record, {**running, "status": "completed", "conclusion": "success"}])]
        env.gh.responses.write_text(json.dumps(rules), "utf-8")
    if conclusion == "code":
        # A code push can carry records immediately: the older run tests different code.
        env.commit(where, "app.py", "print('changed action')\n", "Change the action")
    if conclusion == "interrupt":
        gh = env.repo.bin / "gh"
        gh.write_text(gh.read_text("utf-8").replace(
            'args = sys.argv[1:]',
            'args = sys.argv[1:]\n'
            f'if {endpoint!r} in args:\n'
            '    import os, signal\n'
            f'    pathlib.Path({(tmp_path / "interrupted").as_posix()!r}).touch()\n'
            '    os.kill(os.getppid(), signal.SIGINT)\n'), "utf-8")

    closed = env.close(item)

    pushes = [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []
    if conclusion == "code":
        assert closed.returncode == 1, closed.stdout + closed.stderr
        [pushed] = [push for push in pushes if push[1] == parent]
        assert pushed[3] == 0, pushes
        files = env.repo.git("diff", "--name-only", parent, pushed[2], cwd=where).splitlines()
        assert "app.py" in files and any(path.startswith(".factory/") for path in files)
        return
    if conclusion == "interrupt":
        assert (tmp_path / "interrupted").exists()
        assert closed.returncode != 0, closed.stdout + closed.stderr
        assert [push for push in pushes if push[1] == parent], pushes
        return
    if override is not None:
        assert closed.returncode == 1, closed.stdout + closed.stderr
        assert "no check progress for 0 minutes" in closed.stderr
        assert [push for push in pushes if push[1] == parent], pushes
        return
    assert closed.returncode == (0 if conclusion == "net-empty" or earlier else 1), closed.stdout + closed.stderr
    if conclusion == "failure":
        assert "The main action fails" in closed.stdout, closed.stdout + closed.stderr
        bodies = env.repo.bin / "gh-bodies.jsonl"
        assert "The main action fails" in bodies.read_text("utf-8")
    assert "Waiting: the code's checks are still queued or running." in closed.stdout
    [record] = [push for push in pushes if push[1] == parent]
    assert record[3] >= polls + 1, "close pushed its review record while the code's CI run was still going"
    notices = [json.loads(line) for line in progress.read_text("utf-8").splitlines()]
    assert all(after[0] - before[0] >= 300 for before, after in zip(notices, notices[1:])), notices


@pytest.mark.platform
@pytest.mark.parametrize("pull_request", [False, True], ids=["no-pr", "no-check"])
def test_8_published_code_without_started_ci_closes_without_a_pre_push_wait(env, pull_request):
    # Audit: close must publish and open its first PR when no earlier CI can report.
    # Waiting on a missing required check previously stopped that real command.
    # Existing cases own active workflows, including queued runs without job checks;
    # they cannot exercise a branch that has no workflow yet. Extend this owner.
    # Only GitHub's edge is fake; real git pushes and the normal close need no seam.
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", config + '\ntest_place = "ci"\n', "Use CI tests")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    branch = f"fix/{item}"
    env.repo.git("push", "-q", "-u", "origin", branch, cwd=where)
    published = env.repo.git("rev-parse", "HEAD", cwd=where)
    if pull_request:
        env.open_pr("")
    # No check or queued workflow exists on the published code. The later record
    # push starts the PR's checks, which the fixture reports green on its new head.
    env.gh.respond("api", "--paginate", "--jq", ".check_runs[]",
                   f"repos/{{owner}}/{{repo}}/commits/{published}/check-runs?per_page=100", stdout="")

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    assert "Waiting: the code's checks are still queued or running." not in closed.stdout
    if not pull_request:
        assert "Opened the pull request:" in closed.stdout
        assert len(env.gh_calls("pr", "create")) == 1
    else:
        assert not env.gh_calls("pr", "create")
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    remote = env.repo.git("ls-remote", "origin", f"refs/heads/{branch}", cwd=where).split()[0]
    assert remote == head and remote != published, "The saved review never reached the branch"
