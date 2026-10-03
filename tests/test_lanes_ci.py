"""Slow container and model tests are opt-in locally and enabled in their CI jobs."""
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

STORY = "FORGE-LANES-1"
ROOT = Path(__file__).resolve().parents[1]


def test_3_slow_tests_run_only_when_ci_opts_in():
    # Docker being installed used to start containers during ordinary local runs.
    # Check pytest's skip reason, so missing Docker cannot accidentally prove the gate.
    env = dict(os.environ)
    env.pop("FORGE_CONTAINERS", None)
    targets = ["tests/test_proto_deploy.py",
               "tests/test_fix_the_prototype_deploy_test_leaves_its_doc.py"]
    local = subprocess.run([sys.executable, "-m", "pytest", *targets, "-q", "-rs"],
                           cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert local.returncode == 0, local.stdout + local.stderr
    assert "2 skipped" in local.stdout, local.stdout
    assert "FORGE_CONTAINERS=1" in local.stdout, local.stdout

    if sys.platform != "win32":
        # Plan the real tests with opt-in enabled without starting Docker in this check.
        enabled = subprocess.run(
            [sys.executable, "-m", "pytest", *targets, "--setup-plan", "-q"],
            cwd=ROOT, env={**env, "FORGE_CONTAINERS": "1"},
            capture_output=True, text=True, timeout=60)
        assert enabled.returncode == 0, enabled.stdout + enabled.stderr
        assert "skipped" not in enabled.stdout, enabled.stdout
        assert "test_10_new_client_deploys_only_after_migration" in enabled.stdout
        assert "test_1_old_labelled_leftover_is_removed_and_a_fresh_one_is_kept" in enabled.stdout

    # These settings are the independent CI routing contract, not Forge source internals.
    workflow = (ROOT / ".github/workflows/forge-next.yml").read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    assert re.search(r"^    env:\n      FORGE_CONTAINERS: \$\{\{ matrix.os == 'ubuntu-latest' && '1' \|\| '0' \}\}$",
                     tests_job, re.M), "Only the Ubuntu suite must opt in to Linux containers"
    smoke = (ROOT / ".github/workflows/codex-smoke.yml").read_text(encoding="utf-8")
    assert re.search(r'^      FORGE_LIVE_CODEX: "1"$', smoke, re.M)
    command = re.search(r"^        run: (.*pytest .*test_.*)$", smoke, re.M)
    assert command, "The smoke job must run the real-model tests"
    assert {"tests/test_codex_smoke.py", "tests/test_fix_codex_test_home.py"} <= set(
        shlex.split(command[1]))
