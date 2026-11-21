"""An owner-choice push rechecks a remote head discovered after rejection."""
import json
import sys

import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_close_pushes_record_after_code_ci import HOOK

STORY = "FIX-RECORDS-CANCEL-CI"


@pytest.mark.parametrize("fake_clock", [150], indirect=True)
@pytest.mark.parametrize("defaulted", [False, True])
def test_4_rejected_record_push_waits_for_the_new_remote_run(env, tmp_path, monkeypatch, fake_clock,
                                                          defaulted):
    # Audit: another machine can publish between the check read and the real push.
    # The pre-receive hook observes the retry; only GitHub triggers the other Git writer.
    # Ordinary close waits cannot observe this new remote-head lifecycle.
    # Reversing a default choice must use the same checked push as an ordinary choice.
    item, where = env.start_fix(stop={"file": "app.py", **({"by": "default"} if defaulted else {})})
    env.open_pr("")  # The queued remote run belongs to this pull request.
    env.repo.git("push", "-q", "-u", "origin", "fix/tidy-readme", cwd=where)
    parent = env.repo.git("rev-parse", "HEAD", cwd=where)
    writer = tmp_path / "other-machine"
    env.repo.git("worktree", "add", "-q", "--detach", writer.as_posix(), "HEAD", cwd=where)
    env.commit(writer, "plans/spotted/other-machine.json", "{}\n", "Save another machine's record")
    incoming = env.repo.git("rev-parse", "HEAD", cwd=writer)
    log = tmp_path / "pushes.jsonl"
    origin = env.repo.path.parent / env.repo.git("remote", "get-url", "origin")
    origin = origin if origin.is_absolute() else env.repo.path / origin
    hook = origin / "hooks" / "pre-receive"
    (env.repo.bin / "gh-calls.jsonl").touch(exist_ok=True)
    hook.write_text(HOOK.format(python=sys.executable, parent=incoming, log=log.as_posix(),
                               calls=(env.repo.bin / "gh-calls.jsonl").as_posix()), "utf-8")
    # The branch lookup can now see this same-code run before the push rejects.
    # Observe that run's completion rather than demand repeated per-head job reads.
    hook.write_text(hook.read_text("utf-8").replace(
        '"commits/" + ' + repr(incoming) + ' + "/check-runs" in call',
        '"branch=fix/tidy-readme" in call'), "utf-8")
    hook.chmod(0o755)
    env.checks(GREEN)
    endpoint = f"repos/{{owner}}/{{repo}}/commits/{incoming}/check-runs?per_page=100"
    env.gh.respond("api", "--paginate", "--jq", ".check_runs[]", endpoint, stdout="")
    rules = json.loads(env.gh.responses.read_text("utf-8"))
    lines = lambda rows: "".join(json.dumps(row) + "\n" for row in rows)  # noqa: E731
    rules[-1]["then"] = [lines([run("forge-pr-check")])] * 3 + [lines(GREEN)]
    env.gh.responses.write_text(json.dumps(rules), "utf-8")
    env.gh.respond("api", "--jq", ".workflow_runs[]", stdout="")
    rules = json.loads(env.gh.responses.read_text("utf-8"))
    workflow = {"id": 77, "head_sha": incoming, "event": "pull_request", "status": "queued"}
    # The branch history includes the other machine's newly published head.
    rules[-1]["then"] = [lines([workflow])] * 4 + [lines([
        {**workflow, "status": "completed", "conclusion": "success"}])]
    env.gh.responses.write_text(json.dumps(rules), "utf-8")
    trigger = tmp_path / "remote-advanced"
    gh = env.repo.bin / "gh"
    old_endpoint = f"repos/{{owner}}/{{repo}}/commits/{parent}/check-runs?per_page=100"
    gh.write_text(gh.read_text("utf-8").replace('args = sys.argv[1:]',
        'args = sys.argv[1:]\n'
        f'trigger = pathlib.Path({trigger.as_posix()!r})\n'
        f'if {old_endpoint!r} in args and not trigger.exists():\n'
        '    trigger.touch()\n'
        f'    subprocess.run(["git", "push", "-q", "origin", "HEAD:fix/tidy-readme"], '
        f'cwd={writer.as_posix()!r}, check=True)\n'), "utf-8")
    monkeypatch.delenv("FORGE_CHECKS_WAIT", raising=False)

    closed = env.close(item, "--resolve", "more", "--reason", "Repair the findings")

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Recorded the human's choice" in closed.stdout
    assert trigger.exists(), "The choice was pushed without waiting for the published code"
    pushes = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    [retry] = [push for push in pushes if push[1] == incoming]
    assert retry[3] >= 5, "The reconciled record push cancelled the new queued run"
