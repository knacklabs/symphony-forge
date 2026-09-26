"""forge work on Windows retries a record held open by another reader instead of crashing.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

STORY = "WINDOWS-RECORD-RETRY"


def _record_in_process(tmp_path, refuse: str, seed: bool = True):
    """Run codex._record on a record in a fresh process whose os.replace is refused as Windows
    refuses it while another process has the file open. `refuse` is an expression of the count
    of renames so far and the seconds since the first one; when true, the rename is refused."""
    script = ("import os, sys, time; sys.path.insert(0, sys.argv[1])\n"
              "from pathlib import Path\n"
              "from forge import codex, repo\n"
              "real, seen, first = os.replace, [], time.monotonic()\n"
              "def replace(a, b):\n"
              "    seen.append(a)\n"
              f"    if {refuse}: raise PermissionError(5, 'Access is denied')\n"
              "    real(a, b)\n"
              "os.replace = replace\n"
              "try:\n"
              "    codex._record(Path(sys.argv[2]), b=2)\n"
              "except repo.Refused as refusal:\n"
              "    print(refusal)\n"
              "print(len(seen))\n")
    record = tmp_path / "PAGE.json"
    if seed:
        record.write_text('{"a": 1}\n')
    src = Path(__file__).resolve().parent.parent / "src"
    done = subprocess.run([sys.executable, "-c", script, str(src), str(record)],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return record, done.stdout


def test_7_record_retries_while_another_reader_holds_it(tmp_path):
    # Windows refuses the rename ("Access is denied") while another process has the file open;
    # here the first three renames are refused.
    record, out = _record_in_process(tmp_path, "len(seen) <= 3", seed=False)
    assert out.strip() == "4"
    assert json.loads(record.read_text()) == {"b": 2}


def test_8_record_refuses_when_another_reader_never_lets_go(tmp_path):
    # A reader that never releases the file ends in a plain refusal, not a PermissionError.
    record, out = _record_in_process(tmp_path, "True")
    assert out.startswith(f"Forge couldn't update {record} because another program kept it open.")
    assert json.loads(record.read_text()) == {"a": 1} and not record.with_suffix(".tmp").exists()


def test_9_record_waits_for_a_reader_to_release_an_existing_record(tmp_path):
    # The replace stays refused until a reader lets go half a second later: a loop that never
    # waited would use up its attempts first.
    record, out = _record_in_process(tmp_path, "time.monotonic() - first < 0.5")
    assert json.loads(record.read_text()) == {"a": 1, "b": 2}
