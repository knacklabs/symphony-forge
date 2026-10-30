"""CI timings name only tests that pytest still collects."""
import json
import os
from pathlib import Path
import subprocess
import sys

STORY = "FIX-FRESH-TEST-TIMINGS"
ROOT = Path(__file__).resolve().parents[1]


def test_1_recorded_timings_name_existing_tests(tmp_path):
    # Group budgets already check that pytest-split reads these weights. This
    # check catches deleted or renamed tests left in the timing file.
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q",
         "--basetemp", str(tmp_path / "collection"),
         "-o", "cache_dir=" + str(tmp_path / "cache")],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
        env={key: value for key, value in os.environ.items() if key != "PYTEST_ADDOPTS"})
    assert collected.returncode == 0, collected.stdout + collected.stderr
    nodeids = {line for line in collected.stdout.splitlines()
               if line.startswith("tests/") and "::" in line}
    assert nodeids, collected.stdout
    timings = json.loads((ROOT / ".test_durations").read_text(encoding="utf-8"))
    obsolete = sorted(timings.keys() - nodeids)
    assert not obsolete, f"Refresh .test_durations: {len(obsolete)} obsolete tests: {obsolete[:10]}"
