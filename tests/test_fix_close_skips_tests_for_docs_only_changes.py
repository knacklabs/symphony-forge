"""forge close skips forge.toml's test command when every changed file is under docs/ or plans/,
a Markdown file, or under .factory/, and still runs the review and waits for every named check;
any other changed file runs the test command as before."""
from __future__ import annotations

import sys
from pathlib import Path

from test_close import env, run  # noqa: F401

STORY = "FIX-CLOSE-RUNS-THE-FULL-TEST-COMMAND-EVEN-WH"

DOCS_ONLY = {"docs/guide.txt": "How to start\n", "plans/ROADMAP.md": "| Next | Search |\n",
             "README.md": "# Shop\n", "notes/setup.md": "Run it\n"}
SKIPPED = "so close did not run"


def _with_test_command(env) -> Path:
    log = env.tmp / "runs.log"
    script = env.tmp / "suite.py"
    script.write_text(f"open({str(log)!r}, 'a').write('ran\\n')\nprint('1 passed')\n", "utf-8")
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + f"test = {f'{sys.executable} {script}'!r}\n".replace("'", '"'))
    env.repo.git("push", "-q", "origin", "main")
    return log


def test_1_close_skips_the_test_command_for_a_docs_and_plans_only_fix(env):
    log = _with_test_command(env)
    env.checks([run("tests", "failure"), run("forge-pr-check")])
    item, _ = env.start_fix(DOCS_ONLY)
    closed = env.close(item)
    assert not log.exists()
    said = [line for line in closed.stdout.splitlines() if SKIPPED in line]
    assert len(said) == 1, closed.stdout
    assert len(env.review_calls()) == 1
    assert SKIPPED in env.prompt()
    # The named checks still gate it: the red tests check stops close.
    assert closed.returncode != 0
    assert "Checks failed on the pull request: tests." in closed.stderr
    env.checks([run("tests"), run("forge-pr-check")])
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    assert not log.exists()


def test_2_close_runs_the_test_command_when_a_docs_fix_also_changes_code(env):
    log = _with_test_command(env)
    item, _ = env.start_fix({**DOCS_ONLY, "app.py": "print('hello')\n"})
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    assert log.read_text("utf-8") == "ran\n"
    assert SKIPPED not in closed.stdout
    assert "exited with status 0" in env.prompt()
