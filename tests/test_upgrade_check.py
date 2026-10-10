"""An upgrade pull request passes Forge's check: the workflow this version generates installs the
release an upgrade pull request pins, then runs its check."""
from __future__ import annotations

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

# This checkout's Forge, installed as the release <version> names: no later release exists yet.
RELEASE = """#!{python}
import sys
sys.path.insert(0, {src!r})
import forge
forge.__version__ = "<version>"
from forge.cli import main
sys.exit(main())
"""

# Stands in for uv at its edge: records the call, and installs the release its tag names.
UV_STUB = """#!{python}
import json, pathlib, sys
here = pathlib.Path(__file__).resolve().parent
with open(here / "uv-calls.jsonl", "a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
(here / "forge").write_text({release!r}.replace("<version>", sys.argv[-1].rsplit("@v", 1)[1]),
                            encoding="utf-8")
(here / "forge").chmod(0o755)
"""


def _release_shim() -> str:
    return RELEASE.format(python=sys.executable, src=str(conftest.ROOT / "src"))


def _install_release(env, tag: str) -> None:
    """The human installs a release, as the pin error tells them to."""
    conftest._install(env.repo.bin, "forge", _release_shim().replace("<version>", tag[1:]))


def _pin(env, where, value: str) -> None:
    toml = (where / "forge.toml").read_text("utf-8")
    pinned = re.sub(r"^version = .*$", f"version = {value}", toml, flags=re.M)
    if pinned != toml:  # This checkout's own version may already be the one pinned.
        env.commit(where, "forge.toml", pinned, f"Pin Forge {value}")


def _upgrade(env, where, value: str) -> None:
    """Pin the installed release and commit what its forge sync writes, as the skill's upgrade
    steps say; close refuses an upgrade whose synced files are out of date."""
    _pin(env, where, value)
    done = env.repo.forge("sync", cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("commit", "-q", "-m", "Sync Forge's files", cwd=where)


def _close(env, item, where) -> None:
    # Run in the fix's folder, which pins the release now installed.
    done = env.repo.forge("close", item, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr


def _pr_check_steps(env) -> list[str]:
    """The forge-pr-check job's required shell steps, written on the default branch."""
    synced = env.tmp / "synced"
    env.repo.git("worktree", "add", "-q", "-b", "fix/sync", str(synced))
    done = env.repo.forge("sync", cwd=synced)
    assert done.returncode == 0, done.stderr
    job = (synced / ".github/workflows/forge.yml").read_text("utf-8").split("\n  forge-pr-check:\n")[1]
    steps = []
    for step in re.split(r"^      - ", job, flags=re.M)[1:]:
        # Advisory reporting now has its own real-script proof in test_client_setup_and_migration;
        # this harness preserves the required gate's output and refusal checks.
        if "continue-on-error: true" in step:
            continue
        found = re.search(r"^ *run: (\|\n)?(.*)", step, re.M | re.S)
        if found:
            body = found[2]
            steps.append("\n".join(line.removeprefix("          ") for line in body.splitlines())
                         if found[1] else body.strip())
    return steps


def _on_v1_2_0(env) -> list[str]:
    """The default branch on v1.2.0, and the forge-pr-check job this version generates for it."""
    _install_release(env, "v1.2.0")
    _pin(env, env.repo.path, '"v1.2.0"')
    env.repo.git("push", "-q", "origin", "main")
    return _pr_check_steps(env)


def _run_pr_check_job(env, where, steps) -> subprocess.CompletedProcess[str]:
    """The whole job, run like the runner does on the base checkout, where no Forge is installed
    until the job installs one: each step in bash -e, each seeing what earlier steps added to
    $GITHUB_ENV, stopping at the first failure."""
    (env.repo.bin / "forge").unlink()
    env.repo.git("push", "-q", "origin", "HEAD:refs/pull/1/head", cwd=where)
    github_env = env.tmp / "github-env"
    github_env.write_text("", "utf-8")
    variables = {**os.environ, "PR": "1", "GITHUB_ENV": str(github_env),
                 "BASE_SHA": env.repo.git("rev-parse", "main"),
                 "HEAD_SHA": env.repo.git("rev-parse", "HEAD", cwd=where),
                 "HEAD_REF": "fix/tidy-readme"}
    for step in steps:
        variables.update(line.split("=", 1) for line in github_env.read_text("utf-8").splitlines())
        done = subprocess.run(["bash", "-e", "-c", step], cwd=env.repo.path, env=variables,
                              capture_output=True, text=True, encoding="utf-8", timeout=60)
        if done.returncode:
            break
    return done


def _uv_calls(env) -> list[list[str]]:
    log = env.repo.bin / "uv-calls.jsonl"
    return [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []


def _upgrade_installs_and_passes_the_release_it_pins(env):
    steps = _on_v1_2_0(env)
    item, where = env.start_fix(allow_large="Forge's synced files")
    _install_release(env, "v1.3.0")
    _upgrade(env, where, "'v1.3.0'  # the upgrade")
    _close(env, item, where)

    done = _run_pr_check_job(env, where, steps)

    assert (done.returncode, done.stdout) == (0, "forge-pr-check passed for fix/tidy-readme.\n"), \
        done.stderr
    assert _uv_calls(env) == [["tool", "install", SOURCE + "v1.3.0"]]
    assert env.repo.forge("--version").stdout.split()[-1] == "v1.3.0"


def _version_that_is_not_a_release_refused_plainly(env):
    steps = _on_v1_2_0(env)
    _, where = env.start_fix()
    # Forge's pre-commit hook refuses this pin, so it comes from a machine without Forge's hooks.
    toml = where / "forge.toml"
    toml.write_text(re.sub(r"^version = .*$", 'version = "main; curl evil"', toml.read_text("utf-8"),
                           flags=re.M), "utf-8")
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "Pin Forge main", cwd=where)

    done = _run_pr_check_job(env, where, steps)

    assert done.returncode == 1
    assert done.stderr.splitlines()[-1] == (
        "This pull request sets Forge's version in forge.toml to \"main; curl evil\", which isn't "
        "a Forge release such as v1.2.0. Set it to a Forge release, then push again.")
    assert _uv_calls(env) == []


def _ordinary_pull_request_installs_and_passes_the_default_branch_release(env):
    steps = _on_v1_2_0(env)
    item, where = env.start_fix()
    _close(env, item, where)

    done = _run_pr_check_job(env, where, steps)

    assert (done.returncode, done.stdout) == (0, "forge-pr-check passed for fix/tidy-readme.\n"), \
        done.stderr
    assert _uv_calls(env) == [["tool", "install", SOURCE + "v1.2.0"]]


BASH = pytest.mark.skipif(os.name == "nt", reason="the workflow's steps run in bash on ubuntu-latest")


@pytest.mark.parametrize("case", [pytest.param(_upgrade_installs_and_passes_the_release_it_pins,
                                               marks=BASH),
                                  pytest.param(_version_that_is_not_a_release_refused_plainly,
                                               marks=BASH),
                                  pytest.param(
                                      _ordinary_pull_request_installs_and_passes_the_default_branch_release,
                                      marks=BASH)],
                         ids=lambda case: case.__name__.strip("_"))
def test_1_upgrade_pull_request_passes_forge_check(env, case):
    conftest._install(env.repo.bin, "uv", UV_STUB.format(python=sys.executable,
                                                         release=_release_shim()))
    case(env)
