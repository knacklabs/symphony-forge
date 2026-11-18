"""Close pushes its review record only after the code's own CI run ends (issue 1656)."""
import json
import sys

from test_close import CLEAN, env  # noqa: F401

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


def test_1_record_push_waits_for_the_code_ci_run(env, tmp_path, monkeypatch):
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", "\n".join(
        line for line in config.splitlines() if line.partition("=")[0].strip() != "test_place")
        + '\ntest_place = "ci"\n')
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Tests run in CI")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.repo.git("push", "-q", "-u", "origin", "fix/tidy-readme", cwd=where)
    parent = env.repo.git("rev-parse", "HEAD", cwd=where)
    log = tmp_path / "remote-pushes.jsonl"
    hook = env.repo.path.parent / env.repo.git("remote", "get-url", "origin")
    hook = (hook if hook.is_absolute() else env.repo.path / hook) / "hooks/pre-receive"
    hook.write_text(HOOK.format(python=sys.executable, parent=parent, log=str(log),
                                calls=str(env.repo.bin / "gh-calls.jsonl")), "utf-8")
    hook.chmod(0o755)
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    env.reviews(CLEAN)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    pushes = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    [record] = [push for push in pushes if push[1] == parent]
    assert record[3] > 0, "close pushed its review record before it looked at the code's CI run"
