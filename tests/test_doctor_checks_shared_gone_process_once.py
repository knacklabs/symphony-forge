"""Doctor checks finished Codex processes with one process snapshot."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import _install
from test_doctor_fix import _client

STORY = "next-and-doctor-speed"


@pytest.mark.skipif(os.name == "nt", reason="Codex uses native process APIs on Windows")
def test_2_doctor_checks_a_shared_gone_codex_process_once(repo, gh, tmp_path, monkeypatch):
    _client(repo)
    pids = []
    for _ in range(8):
        process = subprocess.Popen(["sleep", "30"])
        pids.append(process.pid)
        try:
            process.terminate()
            process.wait(timeout=5)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    log = tmp_path / "ps-calls.jsonl"
    real_ps = shutil.which("ps")
    assert real_ps
    _install(repo.bin, "ps", f'''#!{sys.executable}
import json, subprocess, sys
with open({json.dumps(log.as_posix())}, "a", encoding="utf-8") as calls:
    calls.write(json.dumps(sys.argv[1:]) + "\\n")
done = subprocess.run([{json.dumps(real_ps)}, *sys.argv[1:]], capture_output=True, text=True)
sys.stdout.write(done.stdout)
sys.stderr.write(done.stderr)
sys.exit(done.returncode)
''')

    threads = repo.path / ".git" / "forge" / "threads" / "fix"
    for number, pid in enumerate(pids):
        record = threads / f"item-{number}.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps({"driver": {
            "pid": pid, "started": "UTC Mon Jan 01 00:00:00 2000", "command": "sleep 30"}}),
            encoding="utf-8")

    done = repo.forge("doctor")

    assert done.returncode in (0, 1)
    assert (done.returncode == 1) == done.stderr.startswith("forge doctor found ")
    calls = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    identity_checks = [args for args in calls if args[-1:] in [[str(pid)] for pid in pids]]
    assert identity_checks == [], identity_checks
    assert len([args for args in calls if args == ["-axo", "pid="]]) == 1, calls
    assert all(f"Process {pid}, which a crashed forge" not in done.stdout for pid in pids)
