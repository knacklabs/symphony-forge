"""Real close and merge commands recover at the gh edge, or stop after a bounded outage.

Existing check-wait tests do not cover the PR lookup before that wait. The gh
fake supplies bad transport answers only; Forge decides retries and completion.
"""
import json
import shutil

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_merge_command import _merge_at_github

STORY = "gh-retry"


@pytest.fixture(params=[False, True], ids=["new-client", "adopted-v1.2.2"])
def client(env, request):
    env.repo.git("switch", "-q", "-c", "fix/setup")
    if request.param:
        settings = (env.repo.path / "forge.toml").read_text("utf-8")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", env.repo.path,
                        dirs_exist_ok=True)
        env.repo.write("forge.toml", settings)
    env.repo.write(".factory/fixes/setup.json", json.dumps({
        "kind": "fix", "branch": "fix/setup", "status": "working",
        "why": "Adopt Forge", "done_when": "The client uses current Forge"}))
    synced = env.repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "--allow-empty", "-m", "Use current Forge")
    env.repo.git("switch", "-q", "main")
    env.repo.git("merge", "-q", "--ff-only", "fix/setup")
    # Publish the fixture's adopted default branch as the human merge would.
    env.repo.git("-c", f"core.hooksPath={env.tmp / 'fixture-hooks'}", "push", "-q", "origin", "main")
    return env


def bad_answers(env, count, stdout="", stderr="", code=1, prefix=("pr", "list", "--head")):
    gh = env.repo.bin / "gh"
    source = gh.read_text("utf-8")
    source = source.replace('responses = here / "gh-responses.json"', f'''
prefix = {list(prefix)!r}
if args[:len(prefix)] == prefix:
    import time
    with (here / "gh-read-times.jsonl").open("a", encoding="utf-8") as times:
        times.write(json.dumps(time.monotonic()) + "\\n")
    calls = [json.loads(line) for line in (here / "gh-calls.jsonl").read_text("utf-8").splitlines()]
    if sum(call[:len(prefix)] == prefix for call in calls) <= {count}:
        sys.stdout.write({stdout!r})
        sys.stderr.write({stderr!r})
        sys.exit({code})
responses = here / "gh-responses.json"
''')
    gh.write_text(source, "utf-8")


@pytest.mark.parametrize("answer", [
    {"stderr": "invalid character '<' looking for beginning of value"},
    {"stderr": "HTTP 502: Bad Gateway"},
    {"stdout": "<html>Bad Gateway</html>", "code": 0},
    {"stdout": "<html>Bad Gateway</html>", "code": 1},
])
def test_1_close_carries_on_after_one_bad_github_answer(client, answer):
    item, _ = client.start_fix()
    bad_answers(client, 1, **answer)
    done = client.close(item)
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(client.gh_calls("pr", "list", "--head")) >= 2
    assert client.gh_calls("pr", "ready") == [["pr", "ready", "7"]]
    assert f"Ready: {item} has a clean review and green checks." in done.stdout


@pytest.mark.parametrize("answer", [
    {"stderr": "invalid character '<' looking for beginning of value"},
    {"stderr": "HTTP 503: Service Unavailable"},
    {"stdout": "<html>Bad Gateway</html>", "code": 0},
    {"stdout": "<html>Bad Gateway</html>", "code": 1},
])
def test_2_a_lasting_github_outage_stops_plainly_and_can_be_rerun(client, answer):
    item, _ = client.start_fix()
    bad_answers(client, 4, **answer)
    done = client.close(item)
    assert done.returncode == 1, done.stdout + done.stderr
    assert done.stderr == "GitHub did not answer. Rerun the command.\n"
    assert len(client.gh_calls("pr", "list", "--head")) == 4
    times = [json.loads(line) for line in
             (client.repo.bin / "gh-read-times.jsonl").read_text("utf-8").splitlines()]
    assert all(after - before >= pause for before, after, pause in
               zip(times, times[1:], (1, 2, 4)))
    assert not client.gh_calls("pr", "create")
    assert "Traceback" not in done.stderr
    again = client.close(item)
    assert again.returncode == 0, again.stdout + again.stderr


@pytest.mark.parametrize("error", ["HTTP 404: Not Found", "HTTP 403: Forbidden", "HTTP 401: Unauthorized"])
def test_3_intentional_github_refusals_are_not_retried(client, error):
    item, _ = client.start_fix()
    bad_answers(client, 4, stderr=error)
    done = client.close(item)
    assert done.returncode == 1, done.stdout + done.stderr
    assert error in done.stderr
    assert len(client.gh_calls("pr", "list", "--head")) == 1
    assert not client.gh_calls("pr", "create")


def test_4_read_retries_do_not_replay_a_pull_request_write(client):
    item, _ = client.start_fix()
    bad_answers(client, 4, stderr="HTTP 502: Bad Gateway", prefix=("pr", "create"))
    done = client.close(item)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "HTTP 502: Bad Gateway" in done.stderr
    assert len(client.gh_calls("pr", "create")) == 1


def test_5_check_reads_retry_without_losing_json_streams(client):
    item, _ = client.start_fix()
    prefix = ("api", "--paginate", "--jq", ".check_runs[]")
    bad_answers(client, 1, stdout="<html>Bad Gateway</html>", code=0, prefix=prefix)
    done = client.close(item)
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(client.gh_calls(*prefix)) == 2
    assert client.gh_calls("pr", "ready") == [["pr", "ready", "7"]]


def test_6_release_reads_retry_before_deciding_whether_to_upgrade(client):
    version = client.repo.forge("--version").stdout.split()[-1]
    client.gh.respond("release", "view", stdout=json.dumps({"tagName": version}))
    bad_answers(client, 1, stderr="HTTP 502: Bad Gateway", prefix=("release", "view"))
    done = client.repo.forge("upgrade")
    assert done.returncode == 1, done.stdout + done.stderr
    assert "already pins" in done.stderr
    assert len(client.gh_calls("release", "view")) == 2


@pytest.mark.parametrize("confirmation", [False, True], ids=["initial-lookup", "after-write"])
@pytest.mark.parametrize("answer", [
    {"stdout": "<html>Bad Gateway</html>", "code": 0},
    {"stderr": "HTTP 503: Service Unavailable", "code": 1},
])
def test_7_merge_preserves_the_outage_refusal_and_resumes_without_replaying_a_write(
        client, confirmation, answer):
    client.repo.git("switch", "-q", "fix/setup")
    client.commit(client.repo.path, "forge.toml",
                  (client.repo.path / "forge.toml").read_text("utf-8") + 'merge = "agent"\n')
    client.repo.git("switch", "-q", "main")
    client.repo.git("merge", "-q", "--ff-only", "fix/setup")
    client.repo.git("-c", f"core.hooksPath={client.tmp / 'fixture-hooks'}",
                    "push", "-q", "origin", "main")
    item, where = client.start_fix()
    closed = client.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    head = client.repo.git("rev-parse", "HEAD", cwd=where)
    client.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    _merge_at_github(client)
    prefix = ["pr", "view", "7" if confirmation else "fix/tidy-readme"]
    gh = client.repo.bin / "gh"
    # Intercept the service's reads before its post-merge answer, keeping its real squash write.
    source = gh.read_text("utf-8").replace('if sys.argv[1:3] == ["pr", "view"]', f'''
args = sys.argv[1:]
prefix = {prefix!r}
if args[:len(prefix)] == prefix:
    calls = [json.loads(line) for line in (here / "gh-calls.jsonl").read_text("utf-8").splitlines()]
    if sum(call[:len(prefix)] == prefix for call in calls) < 4:
        with (here / "gh-calls.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps(args) + "\\n")
        sys.stdout.write({answer.get("stdout", "")!r})
        sys.stderr.write({answer.get("stderr", "")!r})
        sys.exit({answer["code"]})
if sys.argv[1:3] == ["pr", "view"]''', 1)
    gh.write_text(source, "utf-8")

    stopped = client.repo.forge("merge", item)
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert stopped.stderr == "GitHub did not answer. Rerun the command.\n"
    assert len(client.gh_calls(*prefix)) == 4
    assert len(client.gh_calls("pr", "merge")) == int(confirmation)
    assert where.exists()

    resumed = client.repo.forge("merge", item)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert len(client.gh_calls("pr", "merge")) == 1
    assert client.repo.git("show", "origin/main:app.py") == "print('hello')"
    assert not where.exists()
