"""Vitest details survive long output and reach the worker."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_worker import install_claude, calls

STORY = "FIX-VITEST-FAILURE-DETAILS"


# Audit: the command report and CI transport must retain every case and first error.
# Existing pytest coverage cannot parse Vitest's external text protocol. Replay only
# that third-party protocol; Forge runs normally and needs no test-only seam.
@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_vitest_report_and_worker_keep_every_failure(env, adopted):
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    config = (repo.path / "forge.toml").read_text("utf-8")
    kept = [line for line in config.splitlines()
            if line.partition("=")[0].strip() not in
            ("version", "test", "fast_test", "test_place", "workers")]
    command = f'"{Path(sys.executable).as_posix()}" vitest-output.py'
    env.commit(repo.path, "forge.toml", f'version = "{version}"\nworkers = "claude"\n'
               f'test = {json.dumps(command)}\nfast_test = {json.dumps(command)}\n'
               + "\n".join(kept) + "\n")
    repo.git("push", "-q", "origin", "main")
    names = [f"[api] tests/example.test.ts > saves case {n}" for n in range(45)]
    output = "".join(f" FAIL  {name}\nError: failure {n}\nError: secondary\n"
                     for n, name in enumerate(names))
    output += " × summary-only case\n   → summary failure\n"
    output += "\n".join(f"diagnostic detail {n}" for n in range(100))
    item, where = env.start_fix({"vitest-output.py":
                                f"print({output!r})\nraise SystemExit(1)\n"},
                               review={"status": "clean", "findings": []})
    tested = repo.forge("test", cwd=where)
    assert tested.returncode == 1, tested.stdout + tested.stderr
    expected = [f"- {name} - Error: failure {n}" for n, name in enumerate(names)]
    expected += ["- summary-only case - summary failure"]
    footer = tested.stdout.rsplit("Failed tests:\n", 1)[-1]
    assert sorted(footer.splitlines()[:-1]) == sorted(expected), tested.stdout
    assert "Test names are not available" not in tested.stdout
    ci_log = "\n".join("tests step 2026-11-09T00:00:00Z " + line
                       for line in tested.stdout.splitlines()) + "\n" + "cleanup\n" * 50
    env.gh.respond("pr", "checks", exit=1, stdout=json.dumps([
        {"name": "tests", "bucket": "fail", "link": "https://github.com/o/r/actions/runs/1/job/22"}]))
    env.gh.respond("run", "view", stdout=ci_log)
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = calls(log)[-1]["brief"]
    for line in expected:
        assert line in brief, brief
