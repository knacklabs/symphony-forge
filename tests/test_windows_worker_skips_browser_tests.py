"""On Windows a builder's own test run skips separate browser-test steps; every other run keeps them.

Test-audit: the contract is which steps run. Each fake program below (the third-party edge: npm,
npx, corepack, Playwright, Cypress and the client's own tools) writes one line when it really runs,
so the log shows every step that ran. Forge's classifier is never faked. FORGE_OS=nt picks the
Windows path on any machine; on Windows itself it is the default.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from conftest import _install, patient
from test_close import env, run  # noqa: F401
from test_close_always_tests import adopt_earlier

STORY = "FIX-ON-A-WINDOWS-LAPTOP-A-BUILDER-S-OWN-TEST"
# The Windows workflow runs only platform tests, and this is a Windows-only rule.
pytestmark = pytest.mark.platform

# npm and corepack run the repo's package scripts, npx and `exec` run the rest of the line, and every
# other program logs its name and first two words (Forge adds options to some runners after those).
# The shell runs script bodies, as the real tools do.
PROGRAM = f"""#!{sys.executable}
import json, os, pathlib, subprocess, sys

name, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]


def shell(command):
    sys.exit(subprocess.run(command, shell=True).returncode)


if name == "corepack":  # corepack pnpm ...: pnpm takes the same words as npm here
    name, args = "npm", args[1:]
if name == "npx" or args[:1] == ["exec"]:
    shell(subprocess.list2cmdline(args if name == "npx" else args[1:]))
if name == "npm" and args[:1] != ["ci"]:
    scripts = json.loads(pathlib.Path("package.json").read_text("utf-8"))["scripts"]
    shell(scripts[args[1] if args[0] == "run" else args[0]])
with open(os.environ["RAN_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join([name, *args[:2]]) + "\\n")
"""
PROGRAMS = ("npm", "npx", "corepack", "playwright", "cypress", "vitest", "unit-tests", "lint-tests",
            "npm-run-all", "full-suite")
SCRIPTS = {
    "test": "playwright test default",
    "test:browser": "playwright test script",
    "test:e2e": "cypress run script",
    "lint:playwright": "lint-tests playwright",
    "all": "npm-run-all test:unit test:playwright",
    "ci": "unit-tests two && playwright test combined",
}
# (step in the test setting, lines it logs when it runs, does a Windows builder run skip it?)
STEPS = [
    ("unit-tests one", ["unit-tests one"], False),
    ("playwright test direct", ["playwright test direct"], True),
    ("cypress run direct", ["cypress run direct"], True),
    ("npx playwright test npx", ["playwright test npx"], True),
    ("corepack pnpm exec playwright test corepack", ["playwright test corepack"], True),
    ("corepack pnpm run test:browser", ["playwright test script"], True),
    ("npm run test:e2e", ["cypress run script"], True),
    ("npm run lint:playwright", ["lint-tests playwright"], False),
    ("npm run all", ["npm-run-all test:unit test:playwright"], False),
    ("npm run ci", ["unit-tests two", "playwright test combined"], False),
]
ALL = " && ".join(step for step, _, _ in STEPS)
EVERYTHING = [line for _, lines, _ in STEPS for line in lines]
KEPT = [line for _, lines, skipped in STEPS if not skipped for line in lines]


def said(*steps: str) -> str:
    return (f"On Windows this run skips the browser tests ({', '.join(steps)}). "
            "The pull request check, the final check and the full test run still run them.")


SKIPPED = said(*(step for step, _, skipped in STEPS if skipped))
NODE_SETTING = "[ ! -f package.json ] || (npm ci && npm test)"  # what init writes for a Node repo
PYTEST = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
CASES = {
    "new-repo": dict(test=ALL, ran=KEPT, said=SKIPPED),
    # fast_test is the command a builder's run uses; test would run full-suite.
    "adopted-repo": dict(adopted=True, test="full-suite", fast_test=ALL, ran=KEPT, said=SKIPPED),
    "default-node-setting": dict(test=NODE_SETTING, ran=["npm ci"], said=said("npm test")),
    "only-browser-steps": dict(test="playwright test one && cypress run two", ran=[],
                               said=said("playwright test one", "cypress run two")),
    # pytest runs through Forge's picker or its wrapper; its own marker comes from tests/test_unit.py.
    "pytest-wrapper": dict(test=PYTEST + " && playwright test e2e", ran=["pytest unit"],
                           said=said("playwright test e2e")),
    "pytest-picker": dict(test=PYTEST + " && playwright test e2e", ran=["pytest unit"],
                          fast_test="forge test --pytest {base} && playwright test e2e",
                          said=said("playwright test e2e")),
    "pytest-and-vitest": dict(test=PYTEST + " && vitest run unit && playwright test e2e",
                              ran=["pytest unit", "vitest run unit"], said=said("playwright test e2e")),
}


def set_up(env, monkeypatch, *, test, fast_test="", adopted=False, **_):
    if adopted:
        adopt_earlier(env)
    for name in PROGRAMS:
        _install(env.repo.bin, name, PROGRAM)
    monkeypatch.setenv("RAN_LOG", str(env.tmp / "ran.log"))
    path = env.repo.path / "forge.toml"
    settings = re.sub(r"^(?:test|fast_test|test_place) = .*\n", "", path.read_text("utf-8"), flags=re.M)
    lines = ['test_place = "local"', 'always_test = ["tests/test_unit.py"]', f"test = {json.dumps(test)}"]
    lines += [f"fast_test = {json.dumps(fast_test)}"] if fast_test else []
    env.repo.write("forge.toml", "\n".join(lines) + "\n" + settings)
    env.repo.write("package.json", json.dumps({"scripts": SCRIPTS}))
    env.repo.write("tests/test_unit.py", "import os\n\n\ndef test_unit():\n"
                   "    with open(os.environ['RAN_LOG'], 'a') as log:\n        log.write('pytest unit\\n')\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Set up tests")
    if adopted:  # stands in for the merged pull request that the synced hooks require
        env.repo.git("switch", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/adopt")
    env.repo.git("-c", f"core.hooksPath={env.tmp / 'no-hooks'}", "push", "-q", "origin", "main")
    return env.tmp / "ran.log"


def steps_run(log) -> list[str]:
    """The lines the programs wrote, in order; the log starts empty again."""
    lines = log.read_text("utf-8").splitlines() if log.exists() else []
    patient(lambda: log.unlink(missing_ok=True))
    return lines


@pytest.mark.parametrize("case", CASES)
def test_3_windows_builder_run_skips_browser_steps_and_nothing_else(env, monkeypatch, case):
    log = set_up(env, monkeypatch, **CASES[case])
    monkeypatch.setenv("FORGE_OS", "nt")

    done = env.repo.forge("test")

    assert done.returncode == 0, done.stdout + done.stderr
    assert steps_run(log) == CASES[case]["ran"], done.stdout
    assert done.stdout.count("On Windows this run skips") == 1 and CASES[case]["said"] in done.stdout


def test_4_every_other_run_keeps_the_browser_steps(env, monkeypatch):
    log = set_up(env, monkeypatch, test=ALL)
    env.gh.respond("api", "--method", "POST", stdout="{}")
    cases = [("Mac and Linux builder run", "posix", ["test"]),
             ("pull request check", "nt", ["test", "--change"]),
             ("full test run", "nt", ["test", "--full"])]
    for name, system, command in cases:
        monkeypatch.setenv("FORGE_OS", system)

        done = env.repo.forge(*command)

        assert done.returncode == 0, f"{name}: {done.stdout}{done.stderr}"
        assert steps_run(log) == EVERYTHING, name
        assert "On Windows this run skips" not in done.stdout, name
    monkeypatch.setenv("FORGE_OS", "nt")
    item, _ = env.start_fix()
    env.checks([run("tests"), run("forge-pr-check")])

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert steps_run(log) == EVERYTHING, "close"
