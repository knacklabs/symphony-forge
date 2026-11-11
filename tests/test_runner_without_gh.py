"""A self-hosted runner without gh still sets the review status and reads earlier runs."""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from test_close import blocked, env, finding  # noqa: F401
from test_two_round_limit import client

STORY = "FIX-RUNNER-WITHOUT-GH"


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


def no_gh_path(tmp_path):
    """A PATH with the tools the steps need and no gh."""
    bin_dir = tmp_path / "no-gh-bin"
    bin_dir.mkdir()
    for tool in ("bash", "cat", "curl", "git", "python3"):
        (bin_dir / tool).symlink_to(shutil.which(tool))
    return str(bin_dir)


@pytest.mark.platform
@pytest.mark.skipif(os.name == "nt", reason="The trusted workflow runs in bash on Linux")
@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
def test_1_review_status_is_set_without_gh(env, github, tmp_path, previous):
    server, calls, answers = github
    client(env, previous)
    job_url = "https://github.com/acme/shop/actions/runs/123/job/456"
    answers["/repos/acme/shop/actions/runs/123/jobs"] = {
        "jobs": [{"name": "Other", "html_url": "x"}, {"name": "Review pull request", "html_url": job_url}]}
    workflow = env.repo.git("show", "main:.github/workflows/forge.yml")
    step = next(s for s in re.split(r"^      - ", workflow, flags=re.M) if "Report review status" in s)
    script = step.split("        run: |\n", 1)[1]
    script = "\n".join(line.removeprefix("          ") for line in script.splitlines())
    variables = {"PATH": no_gh_path(tmp_path), "GITHUB_API_URL": server, "GH_TOKEN": "test-token",
                 "GITHUB_REPOSITORY": "acme/shop", "GITHUB_RUN_ID": "123", "HEAD_SHA": "abc123",
                 "REVIEW_OUTCOME": "success", "REVIEW_PENDING": "", "RUNNER_TEMP": str(tmp_path)}
    done = subprocess.run(["bash", "-e", "-c", script], env=variables, capture_output=True,
                          text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    method, path, auth, body = calls[-1]
    assert (method, path, auth) == ("POST", "/repos/acme/shop/statuses/abc123", "Bearer test-token")
    assert json.loads(body) == {"context": "forge-pr-check", "state": "success", "target_url": job_url}


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
    ci_env = dict(os.environ, PATH=no_gh_path(tmp_path), HEAD_SHA=head, BASE_SHA=base,
                  GITHUB_OUTPUT=str(output), GITHUB_API_URL=server, GH_TOKEN="test-token",
                  GITHUB_REPOSITORY="acme/shop", GITHUB_EVENT_NAME="pull_request",
                  GITHUB_WORKFLOW_REF="acme/shop/.github/workflows/forge.yml@refs/heads/main")
    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=where, env=ci_env,
                             capture_output=True, text=True, timeout=60)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "reuse=true" in output.read_text("utf-8")
    assert calls[0][2] == "Bearer test-token"
