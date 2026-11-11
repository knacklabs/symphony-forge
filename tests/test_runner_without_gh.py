"""A self-hosted runner without gh still sets the review status and reads earlier runs."""
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from test_close import blocked, env, finding  # noqa: F401
from test_groups_pytest import _adopted_client, _new_client, _settings
from test_testplace_workflow import _jobs
from test_two_round_limit import client

STORY = "FIX-RUNNER-WITHOUT-GH"

# A runner without gh is a Linux runner running bash, and the PATH is built from links, so
# Windows skips these. The platform mark keeps the policy test happy about the os.name branch.
pytestmark = [pytest.mark.platform,
              pytest.mark.skipif(os.name == "nt", reason="The trusted workflow runs in bash on Linux")]


@pytest.fixture
def github():
    """A stand-in for the GitHub API that records each call."""
    calls, answers = [], {}

    class Handler(BaseHTTPRequestHandler):
        def respond(self, body=b""):
            calls.append((self.command, self.path, self.headers.get("Authorization"), body))
            reply = json.dumps(answers.get(self.path.split("?")[0], {})).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(reply)))
            self.end_headers()
            self.wfile.write(reply)

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond(self.rfile.read(int(self.headers["Content-Length"])))

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", calls, answers
    server.shutdown()


def no_gh_path(tmp_path, *tools):
    """A PATH with only the named tools linked in, so gh is not found."""
    bin_dir = tmp_path / "no-gh-bin"
    bin_dir.mkdir()
    for tool in tools:
        (bin_dir / tool).symlink_to(shutil.which(tool))
    return str(bin_dir)


def logged_python(path, log):
    """The runner's `python`, recording each command line so the test can read it."""
    wrapper = path / "python"
    wrapper.write_text(f"#!{sys.executable}\nimport json, os, sys\n"
                       f"open({str(log)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
                       f"os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])\n")
    wrapper.chmod(0o755)


def read_job(job):
    """A generated job as plain data: its permissions and its steps. A mapping such as env or with
    becomes a dict, a run block its text. The suite has no YAML library and the job is block YAML."""
    def mapping(block):
        return dict(re.findall(r"^([\w-]+): (.*)$", textwrap.dedent(block), re.M))
    steps = []
    for chunk in re.split(r"^      - ", job.split("    steps:\n", 1)[1], flags=re.M)[1:]:
        step = {}
        for key, inline, block in re.findall(r"^        ([\w-]+):[ ]*(.*)\n((?:          .*\n|\n)*)",
                                             "        " + chunk, re.M):
            step[key] = textwrap.dedent(block) if inline == "|" else inline or mapping(block)
        steps.append(step)
    return mapping(re.search(r"^    permissions:\n((?:      .*\n)+)", job, re.M)[1]), steps


@pytest.mark.parametrize("adopted,review", [(False, "clean"), (False, "stale"), (True, "clean")],
                         ids=["new-clean", "new-stale", "earlier-adopted-clean"])
def test_1_review_status_is_set_without_gh(env, github, tmp_path, adopted, review):
    server, calls, answers = github
    client(env, adopted)
    item, where = env.start_fix()
    assert env.close(item).returncode == 0
    if review == "stale":
        env.commit(where, "app.py", "print('changed after review')\n")
    repo = env.repo
    job_url = "https://github.com/acme/shop/actions/runs/123/job/456"
    answers["/repos/acme/shop/actions/runs/123/jobs"] = {
        "jobs": [{"name": "Other", "html_url": "x"}, {"name": "Review pull request", "html_url": job_url}]}
    job = repo.git("show", "main:.github/workflows/forge.yml").split("\n  forge-pr-check:\n", 1)[1]
    steps = re.split(r"^      - ", job, flags=re.M)
    command = re.search(r"^        run: (.+)$", next(s for s in steps if "run: forge hook pr-check" in s), re.M)[1]
    reporter = next(s for s in steps if "Report review status" in s).split("        run: |\n", 1)[1]
    reporter = "\n".join(line.removeprefix("          ") for line in reporter.splitlines())
    path = no_gh_path(tmp_path, "git", "forge", "cat")
    log = tmp_path / "python-arguments.jsonl"
    logged_python(tmp_path / "no-gh-bin", log)
    head = repo.git("rev-parse", "HEAD", cwd=where)
    variables = {**os.environ, "PATH": path, "GITHUB_API_URL": server, "GH_TOKEN": "test-token",
                 "GITHUB_REPOSITORY": "acme/shop", "GITHUB_RUN_ID": "123", "HEAD_SHA": head,
                 "BASE_SHA": repo.git("rev-parse", "main"), "HEAD_REF": "fix/tidy-readme",
                 "RUNNER_TEMP": str(tmp_path), "GITHUB_OUTPUT": str(tmp_path / "outputs")}
    bash = shutil.which("bash")
    checked = subprocess.run([bash, "-e", "-c", command], cwd=repo.path, env=variables,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    variables["REVIEW_OUTCOME"] = "success" if checked.returncode == 0 else "failure"
    variables["REVIEW_PENDING"] = ""
    reported = subprocess.run([bash, "-e", "-c", reporter], cwd=repo.path, env=variables,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
    state = "success" if review == "clean" else "failure"
    assert (checked.returncode, reported.returncode) == (0 if review == "clean" else 1,) * 2, (
        checked.stderr, reported.stderr)
    method, endpoint, auth, body = calls[-1]
    assert (method, endpoint, auth) == ("POST", f"/repos/acme/shop/statuses/{head}", "Bearer test-token")
    assert json.loads(body) == {"context": "forge-pr-check", "state": state, "target_url": job_url}
    # The token reaches GitHub in a header. The shell never expands it into a command line, and
    # no program that ran got it as an argument.
    arguments = log.read_text("utf-8")
    assert "GH_TOKEN" not in reporter and ".forge/review-tests.py" in arguments
    assert "test-token" not in arguments


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
def test_2_earlier_green_run_is_read_without_gh(env, github, tmp_path, previous):
    server, calls, answers = github
    client(env, previous)
    env.commit(env.repo.path, "greeting.py", "GREETING = 'Hello'\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    defect = finding("P1", "Greeting needs more detail", "greeting.py")
    defect["body"] = "Gain 4, Work 1, Harm 2\nCase: normal use - Readers miss the detail."
    env.reviews(blocked(defect))
    assert env.close(item).returncode == 1
    parent = env.repo.git("rev-parse", "HEAD", cwd=where)
    assert env.close(item, "--resolve", "accept", "--reason", "Keep this greeting for now").returncode == 0
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    base = env.repo.git("rev-parse", "origin/main", cwd=where)
    answers["/repos/acme/shop/actions/workflows/forge.yml/runs"] = {"workflow_runs": [{
        "id": 1, "head_sha": parent, "status": "completed", "conclusion": "success",
        "event": "pull_request", "pull_requests": [{"head": {"sha": parent}, "base": {"sha": base}}]}]}
    output = tmp_path / "ci-output"
    ci_env = dict(os.environ, PATH=no_gh_path(tmp_path, "git"), HEAD_SHA=head, BASE_SHA=base,
                  GITHUB_OUTPUT=str(output), GITHUB_API_URL=server, GH_TOKEN="test-token",
                  GITHUB_REPOSITORY="acme/shop", GITHUB_EVENT_NAME="pull_request",
                  GITHUB_WORKFLOW_REF="acme/shop/.github/workflows/forge.yml@refs/heads/main")
    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=where, env=ci_env,
                             capture_output=True, text=True, timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "reuse=true" in output.read_text("utf-8")
    assert calls[0][2] == "Bearer test-token"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_3_full_test_result_is_posted_without_gh(repo, gh, github, tmp_path, monkeypatch, adopted):
    server, calls, _ = github
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    work = (_adopted_client(repo, tmp_path, "nightly-client") if adopted else
            _new_client(repo, gh, tmp_path, "nightly-client"))
    if not adopted:
        repo.git("checkout", "-qb", "fix/nightly-result", cwd=work)
    _settings(work, test="python -m pytest tests -q")
    synced = repo.forge("sync", cwd=work)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    workflow = (work / ".github/workflows/forge.yml").read_text("utf-8")
    permissions, steps = read_job(_jobs(workflow)["full-suite-result"])
    uses = [step.get("uses", "") for step in steps]
    [setup] = [at for at, name in enumerate(uses) if name.startswith("actions/setup-python@")]
    [report] = [at for at, step in enumerate(steps) if step.get("name") == "Report full test result"]
    # Python is set up before the report step runs, the job has no checkout, and it can only set statuses.
    assert setup < report and not [name for name in uses if name.startswith("actions/checkout")]
    assert permissions == {"statuses": "write"}
    script, step_env = steps[report]["run"], steps[report]["env"]
    # The runner sets the GITHUB_* variables itself. Every other variable the script reads must come
    # from the step's env.
    runner = {"GITHUB_API_URL": server, "GITHUB_REPOSITORY": "acme/shop", "GITHUB_RUN_ID": "7",
              "GITHUB_SERVER_URL": "https://github.example"}
    reads = set(re.findall(r"(?:\$\{?|env(?:\[|\.get\()')([A-Z][A-Z0-9_]+)", script))
    assert reads <= set(step_env) | set(runner), reads - set(step_env) - set(runner)
    # `python` is the only interpreter on the PATH, as the set-up interpreter would be.
    log = tmp_path / "python-arguments.jsonl"
    path = no_gh_path(tmp_path, "git")
    logged_python(tmp_path / "no-gh-bin", log)
    for outcome in ("success", "failure"):
        values = {"${{ github.token }}": "test-token", "${{ github.sha }}": "abc123",
                  "${{ needs.full-suite.result }}": outcome}
        before = len(calls)
        ran = subprocess.run([shutil.which("bash"), "-e", "-c", script], cwd=work, capture_output=True,
                             text=True, encoding="utf-8", timeout=60,
                             env={"PATH": path, **runner, **{key: values[text] for key, text in step_env.items()}})
        assert ran.returncode == (0 if outcome == "success" else 1), ran.stdout + ran.stderr
        method, endpoint, auth, body = calls[before]
        assert (method, endpoint, auth) == ("POST", "/repos/acme/shop/statuses/abc123", "Bearer test-token")
        assert json.loads(body) == {"context": "forge-full-suite", "state": outcome,
                                    "target_url": "https://github.example/acme/shop/actions/runs/7"}
    arguments = log.read_text("utf-8")
    assert len(arguments.splitlines()) == 2 and "test-token" not in arguments
