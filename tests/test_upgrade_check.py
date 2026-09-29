"""An upgrade pull request passes Forge's check: the generated workflow installs the release the
pull request pins, and a review this version records still passes the v1.1.0 release's check."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys

import conftest
import pytest
from test_close import env  # noqa: F401 (the shared fixture)

STORY = "FORGE-UPGRADE-1"

SOURCE = "git+https://github.com/knacklabs/symphony-forge@"
UPGRADE = "v9.9.9"

# Stands in for uv at its edge: records what it would install, and installs nothing.
UV_STUB = """#!{python}
import json, pathlib, sys
with open(pathlib.Path(__file__).resolve().parent / "uv-calls.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
"""


def _version(env) -> str:
    return env.repo.forge("--version").stdout.split()[-1]


def _pr_check_steps(env) -> list[str]:
    """The forge-pr-check job's shell steps, as forge sync writes them on the default branch."""
    synced = env.tmp / "synced"
    env.repo.git("worktree", "add", "-q", "-b", "fix/sync", str(synced))
    done = env.repo.forge("sync", cwd=synced)
    assert done.returncode == 0, done.stderr
    job = (synced / ".github/workflows/forge.yml").read_text("utf-8").split("\n  forge-pr-check:\n")[1]
    steps = []
    for step in re.split(r"^      - ", job, flags=re.M)[1:]:
        found = re.search(r"^ *run: (\|\n)?(.*)", step, re.M | re.S)
        if found:
            body = found[2]
            steps.append("\n".join(line.removeprefix("          ") for line in body.splitlines())
                         if found[1] else body.strip())
    return steps


def _run_pr_check_job(env, where) -> subprocess.CompletedProcess[str]:
    """The job's steps until the check itself, run like the runner does on the base checkout: each
    in bash -e, each seeing what earlier steps added to $GITHUB_ENV, stopping at the first failure."""
    steps = _pr_check_steps(env)
    env.repo.git("push", "-q", "origin", "HEAD:refs/pull/1/head", cwd=where)
    github_env = env.tmp / "github-env"
    github_env.write_text("", "utf-8")
    variables = {**os.environ, "PR": "1", "GITHUB_ENV": str(github_env),
                 "BASE_SHA": env.repo.git("rev-parse", "main"),
                 "HEAD_SHA": env.repo.git("rev-parse", "HEAD", cwd=where)}
    install = next(n for n, step in enumerate(steps) if step.startswith("uv tool install"))
    for step in steps[:install + 1]:
        variables.update(line.split("=", 1) for line in github_env.read_text("utf-8").splitlines())
        done = subprocess.run(["bash", "-e", "-c", step], cwd=env.repo.path, env=variables,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        if done.returncode:
            break
    return done


def _uv_calls(env) -> list[list[str]]:
    log = env.repo.bin / "uv-calls.jsonl"
    return [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []


def _upgrade_installs_the_release_it_pins(env):
    toml = env.repo.path.joinpath("forge.toml").read_text("utf-8")
    _, where = env.start_fix({"forge.toml": toml.replace(_version(env), UPGRADE)})

    done = _run_pr_check_job(env, where)

    assert done.returncode == 0, done.stderr
    assert _uv_calls(env) == [["tool", "install", SOURCE + UPGRADE]]


def _version_that_is_not_a_release_refused_plainly(env):
    toml = env.repo.path.joinpath("forge.toml").read_text("utf-8")
    _, where = env.start_fix({"forge.toml": toml.replace(_version(env), "main; curl evil")})

    done = _run_pr_check_job(env, where)

    assert done.returncode == 1
    assert done.stderr.splitlines()[-1] == (
        "This pull request sets Forge's version in forge.toml to \"main; curl evil\", which isn't "
        "a Forge release such as v1.2.0. Set it to a Forge release, then push again.")
    assert _uv_calls(env) == []


def _ordinary_pull_request_installs_the_default_branch_release(env):
    _, where = env.start_fix()

    done = _run_pr_check_job(env, where)

    assert done.returncode == 0, done.stderr
    assert _uv_calls(env) == [["tool", "install", SOURCE + _version(env)]]


def _v1_1_0_fingerprint(where, base: str, state: dict) -> str:
    """v1.1.0's forge-pr-check fingerprint for a fix, copied from that release's review.py: the
    whole product tree at the head, the fix's why and done-when, and its functional check."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=where, check=True, capture_output=True,
                              text=True, encoding="utf-8").stdout.strip()
    bookkeeping = (".factory/", "plans/")
    listing = git("ls-tree", "-r", "-z", "--full-tree", "HEAD").split("\0")
    product = [entry for entry in listing if not entry.partition("\t")[2].startswith(bookkeeping)]
    digest = hashlib.sha256("\0".join(product).encode("utf-8"))
    check = ""
    for sha in git("rev-list", "--no-merges", f"{base}..HEAD").split():
        files = git("diff-tree", "--no-commit-id", "--name-only", "-r", sha).split()
        if files and all(f.startswith(bookkeeping) for f in files):
            continue
        found = re.search(r"^Functional check:.*", git("show", "-s", "--format=%B", sha),
                          re.M | re.S)
        check = found[0].strip() if found else ""
        break
    for part in (str(state.get("why", "")), str(state.get("done_when", "")), check):
        digest.update(b"\0" + part.encode("utf-8"))
    return digest.hexdigest()


def _review_record(env, where) -> dict:
    return json.loads(env.repo.git("show", "HEAD:.factory/fixes/tidy-readme.json", cwd=where))


def _upgrade_review_passes_the_v1_1_0_check(env):
    # A client on v1.1.0 still runs v1.1.0's workflow for its upgrade pull request, so the review
    # this version records must carry the fingerprint that release's check compares.
    item, where = env.start_fix()
    env.commit(where, "app.py", "print('hi')\n", "Say hi\n\nFunctional check: ran app.py.")
    assert env.close(item).returncode == 0
    state = _review_record(env, where)
    assert state["review"]["tree"] == _v1_1_0_fingerprint(where, env.repo.git("rev-parse", "main"),
                                                          state)

    # The default branch moves on; close merges it in, keeps the clean review without rerunning
    # it, and brings the fingerprint up to date with the new head.
    env.commit(env.repo.path, "README.md", "# Shop\n", "Readme on main")
    env.repo.git("push", "-q", "origin", "main")
    assert env.close(item).returncode == 0
    state = _review_record(env, where)
    assert state["review"]["tree"] == _v1_1_0_fingerprint(where, env.repo.git("rev-parse", "main"),
                                                          state)
    assert len(env.review_calls()) == 1


BASH = pytest.mark.skipif(os.name == "nt", reason="the workflow's steps run in bash on ubuntu-latest")


@pytest.mark.parametrize("case", [pytest.param(_upgrade_installs_the_release_it_pins, marks=BASH),
                                  pytest.param(_version_that_is_not_a_release_refused_plainly,
                                               marks=BASH),
                                  pytest.param(_ordinary_pull_request_installs_the_default_branch_release,
                                               marks=BASH),
                                  _upgrade_review_passes_the_v1_1_0_check],
                         ids=lambda case: case.__name__.strip("_"))
def test_1_upgrade_pull_request_passes_forge_check(env, case):
    conftest._install(env.repo.bin, "uv", UV_STUB.format(python=sys.executable))
    case(env)
