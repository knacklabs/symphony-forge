"""Close pushes its review record only after the code's own CI run ends (issue 1656)."""
import json
import sys
import pytest

from test_close import CLEAN, GREEN, env, run  # noqa: F401
from test_checks_finish_after_long_runner_queues import _watch_progress

STORY = "issue-1656-in-ci-test-repos-close-pushes"

# Runs on the remote when a push arrives: how many times had close looked at the code's CI?
HOOK = """#!{python}
import json, sys
calls = open({calls!r}, encoding="utf-8").read().splitlines()
for line in sys.stdin:
    old, new, ref = line.split()
    looked = sum(1 for call in calls if "commits/" + {parent!r} + "/check-runs" in call)
    open({log!r}, "a", encoding="utf-8").write(json.dumps([ref, old, new, looked]) + "\\n")
"""


@pytest.mark.parametrize("fake_clock,polls,override", [(900, 9, None), (150, 3, None), (150, 3, "0")],
                         indirect=["fake_clock"])
def test_1_record_push_waits_until_the_running_code_ci_run_ends(env, tmp_path, monkeypatch, fake_clock,
                                                               polls, override):
    # Audit: the two phases share one output cadence; an explicit wait limit must
    # stop before the push that cancels unfinished CI. The existing remote hook
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
    env.open_pr("")  # These running checks belong to an existing pull request.
    env.repo.git("push", "-q", "-u", "origin", "fix/tidy-readme", cwd=where)
    parent = env.repo.git("rev-parse", "HEAD", cwd=where)
    log = tmp_path / "remote-pushes.jsonl"
    hook = env.repo.path.parent / env.repo.git("remote", "get-url", "origin")
    hook = (hook if hook.is_absolute() else env.repo.path / hook) / "hooks/pre-receive"
    hook.write_text(HOOK.format(python=sys.executable, parent=parent, log=str(log),
                                calls=str(env.repo.bin / "gh-calls.jsonl")), "utf-8")
    hook.chmod(0o755)
    monkeypatch.delenv("FORGE_CHECKS_WAIT", raising=False)
    if override is not None:
        monkeypatch.setenv("FORGE_CHECKS_WAIT", override)
    env.reviews(CLEAN)
    # The record push must not cancel the code's CI, even past the old 90-minute wait.
    # This lifecycle boundary needs the remote push hook, which ordinary wait tests lack.
    lines = lambda rows: "".join(json.dumps(row) + "\n" for row in rows)  # noqa: E731
    running = lines([run("docs-check"), run("tests (1/2)", None, "in_progress")])
    env.checks(GREEN)
    env.gh.respond("api", "--paginate", "--jq", ".check_runs[]", stdout="")
    rules = json.loads(env.gh.responses.read_text("utf-8"))
    rules[-1]["then"] = [running] * 2 + [lines(GREEN)] if override is None else [lines(GREEN)]
    env.gh.responses.write_text(json.dumps(rules), "utf-8")
    endpoint = f"repos/{{owner}}/{{repo}}/commits/{parent}/check-runs?per_page=100"
    env.gh.respond("api", "--paginate", "--jq", ".check_runs[]", endpoint, stdout="")
    rules = json.loads(env.gh.responses.read_text("utf-8"))
    rules[-1]["then"] = [running] * polls + [lines(GREEN)]
    env.gh.responses.write_text(json.dumps(rules), "utf-8")

    closed = env.close(item)

    pushes = [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []
    if override is not None:
        assert closed.returncode == 1, closed.stdout + closed.stderr
        assert "no check progress for 0 minutes" in closed.stderr
        # An explicit stop now flushes saved records before close exits.
        assert [push for push in pushes if push[1] == parent], pushes
        return
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Waiting: the code's checks are still queued or running." in closed.stdout
    [record] = [push for push in pushes if push[1] == parent]
    assert record[3] >= polls + 1, "close pushed its review record while the code's CI run was still going"
    notices = [json.loads(line) for line in progress.read_text("utf-8").splitlines()]
    assert all(after[0] - before[0] >= 300 for before, after in zip(notices, notices[1:])), notices
