"""Docs-only PRs leave a separate test runner free.

Test-audit: the generated workflow is GitHub's public scheduling contract.
Collapsing one group into its result job takes a fast slot before docs detection.
Existing docs-skip tests check suite execution, not runner allocation. No seam is added.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_ci_limits_pull_requests_to_linux import expression
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_testplace_workflow import _jobs

STORY = "FIX-DOCS-ONLY-OFF-FAST-RUNNERS"


@pytest.mark.platform
@pytest.mark.parametrize("runner,test_runner", [
    ("ubuntu-24.04", "windows-latest"),
    ("windows-latest", "ubuntu-24.04"),
    ("regular's pool", "fast's pool"),
])
@pytest.mark.parametrize("required", [False, True], ids=["no-required-tests", "required-tests"])
def test_1_docs_only_pr_keeps_the_test_runner_free(
        repo, gh, tmp_path, monkeypatch, runner, test_runner, required):
    # Audit: also protect mandatory docs tests, Windows shell selection, actual job
    # eligibility and replacement of stale workflows. These extend this rule's owner.
    # Pushes now share the tests gate. Keep runner allocation and gate eligibility
    # together here: a separate test runner can no longer collapse into the gate.
    # Single-runner workflow cases cannot cover this allocation risk.
    # Evaluate the emitted workflow; no production seam or substitute job is needed.
    version = repo.forge("--version").stdout.split()[-1]
    receipt = tmp_path / "required-ran"
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    client = _new_repo(repo, gh, tmp_path, f'version = "{version}"\n'
        f'runner = {json.dumps(runner)}\ntest_runner = {json.dumps(test_runner)}\ngroups = 1\n'
        f'test = {json.dumps(command)}\nchecks = ["tests", "forge-pr-check"]\n')
    initialized = repo.forge("init", "--actions", "yes", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.git("switch", "-qc", "fix/docs-runners", cwd=client)
    record = client / ".factory/fixes/docs-runners.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"kind": "fix", "branch": "fix/docs-runners",
        "why": "Keep test runners free", "done_when": "Docs use the regular runner",
        "status": "started"}), "utf-8")
    (client / "tests").mkdir(exist_ok=True)
    (client / "tests/test_required.py").write_text(
        "from pathlib import Path\ndef test_required():\n"
        f"    Path({json.dumps(receipt.as_posix())}).touch()\n", "utf-8")
    if required:
        (client / ".forge/always-tests.txt").write_text("tests/test_required.py\n", "utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Prepare docs runner check", cwd=client)

    def evaluate(text, event="pull_request", **outputs):
        text = re.sub(r"needs.docs-check.outputs.([\w-]+)",
                      lambda match: repr(outputs.get(match[1], "")), text)
        text = text.replace("needs.docs-check.result", repr(outputs.get("docs-check", "success")))
        text = text.replace("always()", "True")
        text = text.replace("steps.parent-tests.outputs.reuse", repr(outputs.get("reuse", "false")))
        # GitHub escapes an apostrophe by doubling it, unlike Python literals.
        text = re.sub(r"'((?:[^']|'')*)'", lambda match: repr(match[1].replace("''", "'")), text)
        return expression(text if text.startswith("${{") else "${{ " + text + " }}",
                          event_name=event)

    for command in (None, "sync"):
        if command:
            # An existing repo must replace its old workflow, not keep init's output.
            path = client / ".github/workflows/forge.yml"
            path.write_text("name: stale\non: pull_request\njobs:\n  tests:\n"
                            "    runs-on: fast-tests\n    steps:\n      - run: echo stale\n", "utf-8")
            synced = repo.forge(command, cwd=client)
            assert synced.returncode == 0, synced.stdout + synced.stderr
        jobs = _jobs((client / ".github/workflows/forge.yml").read_text("utf-8"))
        assert "docs-check" in jobs, "Docs detection must precede allocation of a fast runner"
        assert f'runs-on: {json.dumps(runner)}' in jobs["docs-check"]
        assert f'runs-on: {json.dumps(runner)}' in jobs["tests-passed"]
        assert "needs: docs-check" in jobs["tests"]
        assert "needs.docs-check.outputs.docs-only != 'true'" in jobs["tests"]
        assert "needs: [docs-check, tests]" in jobs["tests-passed"]
        gate_name = re.search(r"^    name: (.+)$", jobs["tests-passed"], re.M)[1]
        gate_guard = re.search(r"^    if: (.+)$", jobs["tests-passed"], re.M)[1]
        for event in ("pull_request", "push", "pull_request_target"):
            assert evaluate(gate_name, event) == ("tests (other event)"
                                                  if event == "pull_request_target" else "tests")
            assert bool(evaluate(gate_guard, event)) == (event == "pull_request")
    base = repo.git("rev-parse", "HEAD", cwd=client)
    repo.git("update-ref", "refs/remotes/origin/main", base, cwd=client)
    (client / "README.md").write_text("Updated guide\n", "utf-8")
    repo.git("add", "README.md", cwd=client)
    repo.git("commit", "-qm", "Update guide", cwd=client)
    output = tmp_path / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", repo.git("rev-parse", "HEAD", cwd=client))
    excludes = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", jobs["docs-check"], re.M)[1]
    monkeypatch.setenv("DOCS_ONLY_EXCLUDES", excludes)
    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                             capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr
    values = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())

    condition = re.search(r"^    if: (.+)$", jobs["tests"], re.M)[1]
    label = re.search(r"^    runs-on: (.+)$", jobs["tests"], re.M)[1]
    assert '"' not in label.removeprefix("${{").removesuffix("}}"), label
    assert bool(evaluate(condition, **values)) == required
    if required:
        assert evaluate(label, **values) == runner
        assert values["one-group"] == "true"
        # Execute the emitted job step, including its shell wrapper, not a substitute.
        commands = []
        for step in re.split(r"^      - ", jobs["tests"], flags=re.M)[1:]:
            if not step.startswith("run:") or "forge test --change" not in step:
                continue
            guard = re.search(r"^        if: (.+)$", step, re.M)[1]
            if evaluate(guard, **values):
                commands.append(json.loads(step.splitlines()[0].removeprefix("run: ")))
        assert len(commands) == 1
        if runner.startswith("windows-"):
            shell = shutil.which("pwsh")
            if shell is None and os.name != "nt":
                pytest.skip("The emitted Windows command needs real PowerShell; Windows CI executes it")
            assert shell, "Windows CI must supply PowerShell"
            invocation = [shell, "-NoProfile", "-NonInteractive", "-Command", commands[0]]
        else:
            invocation = [shutil.which("bash"), "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", commands[0]]
        tested = subprocess.run(invocation, cwd=client, capture_output=True, text=True, timeout=30,
            env={**os.environ, "FORGE_GROUP": "1", "FORGE_GROUPS": "1"})
        assert tested.returncode == 0, tested.stdout + tested.stderr
        assert receipt.exists()
    else:
        assert values["docs-only"] == "true"
    # Check code and non-PR events too: changing && to || must fail this test.
    for event in ("pull_request", "push", "pull_request_target", "schedule"):
        code_outputs = {"docs-only": "false", "docs-tests": "false"}
        assert bool(evaluate(condition, event, **code_outputs)) == (event == "pull_request")
        assert not evaluate(condition, event, **{"docs-only": "true", "docs-tests": "false"})
    assert evaluate(label, **{"docs-tests": "false"}) == test_runner
    # Execute the emitted required-check rule: failed detection or tests never pass.
    shell = shutil.which("bash")
    assert shell, "The GitHub result job requires bash"
    assert "shell: bash" in jobs["tests-passed"]
    rule = re.search(r"^        run: (test .*?)$", jobs["tests-passed"], re.M)[1]
    for docs_check, docs_only, tests, passes in [
        ("success", "true", "skipped", True), ("success", "false", "success", True),
        ("success", "true", "failure", False), ("success", "false", "skipped", False),
        ("failure", "true", "skipped", False), ("success", "false", "cancelled", False),
    ]:
        result = subprocess.run([shell, "-c", rule], env={**os.environ,
            "DOCS_CHECK": docs_check, "DOCS_ONLY": docs_only, "TEST_GROUP_RESULT": tests})
        assert (result.returncode == 0) == passes
