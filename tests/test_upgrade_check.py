"""An upgrade pull request passes Forge's check: the release it pins runs that check, and a review
this version records still passes the previous release's check."""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import conftest
import pytest
from test_close import env  # noqa: F401 (the shared fixture)

STORY = "FORGE-UPGRADE-1"

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = "v1.1.0"
SOURCE = "git+https://github.com/knacklabs/symphony-forge@"

# Stands in for uv at its edge: records its arguments, and "installs" any release as this
# checkout's forge, which is the release a pull request upgrading to this version pins.
UV_STUB = """#!{python}
import json, pathlib, subprocess, sys
args = sys.argv[1:]
here = pathlib.Path(__file__).resolve().parent
with open(here / "uv-calls.jsonl", "a", encoding="utf-8") as calls:
    calls.write(json.dumps(args) + "\\n")
if args[:3] != ["tool", "run", "--from"] or args[4] != "forge":
    sys.exit("stub uv: unexpected call: uv " + " ".join(args))
sys.exit(subprocess.call([sys.executable, str(here / "forge"), *args[5:]]))
"""


def _launcher(env, name: str, package: Path) -> Path:
    """A command that runs the Forge package in package's folder."""
    path = env.tmp / "bin-releases" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(conftest.FORGE_SHIM.format(python=sys.executable, src=str(package.parent)),
                    encoding="utf-8")
    return path


def _older_build(env, version: str) -> Path:
    """This checkout's Forge calling itself an older release, as the default branch installs it."""
    package = env.tmp / "older" / "forge"
    shutil.copytree(ROOT / "src" / "forge", package)
    init = package / "__init__.py"
    text = init.read_text("utf-8")
    init.write_text(text.replace(f'__version__ = "{_version(env)[1:]}"',
                                 f'__version__ = "{version[1:]}"'), encoding="utf-8")
    return _launcher(env, "older", package)


def _previous_release(env) -> Path:
    """The previous release's Forge, from its tag (fetched when a shallow CI checkout lacks it)."""
    if subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{PREVIOUS}"],
                      cwd=ROOT, capture_output=True).returncode:
        subprocess.run(["git", "fetch", "-q", "--depth=1", "origin",
                        f"refs/tags/{PREVIOUS}:refs/tags/{PREVIOUS}"], cwd=ROOT, check=True)
    archive = subprocess.run(["git", "archive", "--format=tar", PREVIOUS, "src/forge"], cwd=ROOT,
                             check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(env.tmp / "previous", filter="data")
    return _launcher(env, "previous", env.tmp / "previous" / "src" / "forge")


def _version(env) -> str:
    return env.repo.forge("--version").stdout.split()[-1]


def _pin_on_main(env, version: str) -> None:
    toml = env.repo.path.joinpath("forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", toml.replace(f'version = "{_version(env)}"',
                                              f'version = "{version}"'))
    env.repo.git("commit", "-qam", f"Pin {version}")
    env.repo.git("push", "-q", "origin", "main")


def _check_args(env, where: Path) -> list[str]:
    return ["--base", env.repo.git("rev-parse", "HEAD"),
            "--head", env.repo.git("rev-parse", "HEAD", cwd=where), "--branch", "fix/tidy-readme"]


def _check(env, where: Path, forge: Path | None = None) -> subprocess.CompletedProcess[str]:
    """forge-pr-check as the workflow runs it: from the base checkout, on main."""
    return subprocess.run([sys.executable, str(forge or env.repo.bin / "forge"), "hook", "pr-check",
                           *_check_args(env, where)],
                          cwd=env.repo.path, capture_output=True, text=True, encoding="utf-8",
                          timeout=120)


def _uv_calls(env) -> list[list[str]]:
    log = env.repo.bin / "uv-calls.jsonl"
    return [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []


PASSED = "forge-pr-check passed for fix/tidy-readme.\n"


def _upgrade_checked_by_the_release_it_pins(env):
    new = _version(env)
    _pin_on_main(env, "v1.0.9")
    upgraded = env.repo.path.joinpath("forge.toml").read_text("utf-8").replace(
        'version = "v1.0.9"', f'version = "{new}"')
    item, where = env.start_fix({"forge.toml": upgraded, "app.py": "print('hello')\n"})
    closed = env.repo.forge("close", item, cwd=where)  # the upgrade's folder pins the new Forge
    assert closed.returncode == 0, closed.stderr

    done = _check(env, where, _older_build(env, "v1.0.9"))

    assert done.returncode == 0, done.stderr
    assert done.stdout == PASSED
    [call] = _uv_calls(env)
    assert call[:5] == ["tool", "run", "--from", SOURCE + new, "forge"]
    assert call[5:] == ["hook", "pr-check", *_check_args(env, where)]


def _version_that_is_not_a_release_refused_plainly(env):
    toml = env.repo.path.joinpath("forge.toml").read_text("utf-8")
    _, where = env.start_fix({"forge.toml": toml.replace(f'version = "{_version(env)}"',
                                                         'version = "main; curl evil"')})

    done = _check(env, where)

    assert done.returncode == 1
    assert done.stderr.splitlines()[-2:] == [
        'The pull request on fix/tidy-readme pins Forge "main; curl evil", which isn\'t a Forge '
        "release such as v1.2.0.",
        "Next: set forge.toml's version to a Forge release, then push fix/tidy-readme again"]
    assert _uv_calls(env) == []


def _ordinary_pull_request_checked_by_the_default_branch_forge(env):
    _pin_on_main(env, "v1.0.9")
    item, where = env.start_fix()
    older = _older_build(env, "v1.0.9")
    closed = subprocess.run([sys.executable, str(older), "close", item], cwd=where,
                            capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert closed.returncode == 0, closed.stderr

    done = _check(env, where, older)

    assert done.returncode == 0, done.stderr
    assert done.stdout == PASSED
    assert _uv_calls(env) == []


def _pull_request_older_than_a_base_upgrade_checked_by_the_base(env):
    # The pull request never touched forge.toml; the default branch upgraded after it started, so
    # its older pin is no upgrade and the default branch's own Forge still checks it.
    _pin_on_main(env, "v1.0.9")
    item, where = env.start_fix()
    older = _older_build(env, "v1.0.9")
    closed = subprocess.run([sys.executable, str(older), "close", item], cwd=where,
                            capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert closed.returncode == 0, closed.stderr
    toml = env.repo.path.joinpath("forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", toml.replace('version = "v1.0.9"', f'version = "{_version(env)}"'))
    env.repo.git("commit", "-qam", "Upgrade Forge")
    env.repo.git("push", "-q", "origin", "main")

    done = _check(env, where)

    assert done.returncode == 0, done.stderr
    assert done.stdout == PASSED
    assert _uv_calls(env) == []


def _changed_pin_without_its_v_refused_plainly(env):
    toml = env.repo.path.joinpath("forge.toml").read_text("utf-8")
    bare = _version(env)[1:]
    _, where = env.start_fix({"forge.toml": toml.replace(f'version = "{_version(env)}"',
                                                         f'version = "{bare}"')})

    done = _check(env, where)

    assert done.returncode == 1
    assert done.stderr.splitlines()[-2:] == [
        f'The pull request on fix/tidy-readme pins Forge "{bare}", which isn\'t a Forge '
        "release such as v1.2.0.",
        "Next: set forge.toml's version to a Forge release, then push fix/tidy-readme again"]
    assert _uv_calls(env) == []


def _one_review_passes_the_previous_release_check_and_this_one(env):
    previous = _previous_release(env)
    item, where = env.start_fix()
    assert env.close(item).returncode == 0
    for forge in (previous, None):
        done = _check(env, where, forge)
        assert done.returncode == 0, done.stderr

    # The default branch moves on; close merges it in and keeps the clean review without rerunning
    # it, and both checks still pass against the new base.
    env.commit(env.repo.path, "README.md", "# Shop\n", "Readme on main")
    env.repo.git("push", "-q", "origin", "main")
    assert env.close(item).returncode == 0
    for forge in (previous, None):
        done = _check(env, where, forge)
        assert done.returncode == 0, done.stderr
        assert done.stdout == PASSED
    assert len(env.review_calls()) == 1


@pytest.mark.parametrize("case", [_upgrade_checked_by_the_release_it_pins,
                                  _version_that_is_not_a_release_refused_plainly,
                                  _ordinary_pull_request_checked_by_the_default_branch_forge,
                                  _pull_request_older_than_a_base_upgrade_checked_by_the_base,
                                  _changed_pin_without_its_v_refused_plainly,
                                  _one_review_passes_the_previous_release_check_and_this_one],
                         ids=lambda case: case.__name__.strip("_"))
def test_1_upgrade_pull_request_passes_forge_check(env, case):
    conftest._install(env.repo.bin, "uv", UV_STUB.format(python=sys.executable))
    case(env)
