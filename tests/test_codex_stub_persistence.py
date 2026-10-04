"""The resuming Codex stand-in survives Windows readers of its conversation store."""
from __future__ import annotations

import json
import subprocess
import sys

from test_codex_resume import RESUMING

STORY = "FIX-CODEX-STUB-PERSISTENCE"


def test_1_turn_start_survives_a_reader_blocking_the_store_replace(tmp_path):
    # Windows refuses replacement while the recovery test reads the destination. Inject that
    # OS failure in the child on every platform; successful attempts still do the real rename.
    contention = '''
import os
replace = os.replace
blocked = 3
def replace_after_reader_closes(source, destination):
    global blocked
    if blocked:
        blocked -= 1
        raise PermissionError("the conversation store is open for reading")
    return replace(source, destination)
os.replace = replace_after_reader_closes
'''
    server = tmp_path / "codex-app-server.py"
    server.write_text(contention + RESUMING, encoding="utf-8")
    store = tmp_path / "threads.json"
    store.write_text(json.dumps({"thr-stub-1": {"cwd": str(tmp_path), "turns": {}}}),
                     encoding="utf-8")
    request = {"id": 1, "method": "turn/start", "params": {"threadId": "thr-stub-1"}}
    run = subprocess.run([sys.executable, str(server)], input=json.dumps(request) + "\n",
                         capture_output=True, text=True, timeout=10)

    assert run.returncode == 0, run.stderr
    messages = [json.loads(line) for line in run.stdout.splitlines()]
    assert messages[0] == {"id": 1, "result": {"turn": {
        "id": "turn-stub-1", "items": [], "status": "inProgress"}}}
    assert messages[-1]["method"] == "turn/completed"
    assert json.loads(store.read_text(encoding="utf-8"))["thr-stub-1"]["turns"] == {
        "turn-stub-1": "completed"}
