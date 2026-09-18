"""The bytes the harness hashes are the bytes it writes.

On Windows a descriptor opened without O_BINARY is text-mode: the C runtime
rewrites every LF as CRLF inside os.write(). The review brief's sha256 was
taken from the LF body in memory and checked against the file on disk, so
every `task close` on a Windows host refused with "review brief hash does not
match the saved all.md" until someone converted the file by hand. These pass
trivially on POSIX; the windows-hook-gates job runs them where it matters.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

from test_gates import HARNESS  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
import factory_lib  # noqa: E402
from forge_cli import delegate, worker_admission  # noqa: E402

BODY = b"# review brief\n\nline one\nline two\n"


def test_raw_open_flags_keep_the_caller_flags_and_force_binary():
    wanted = os.O_WRONLY | os.O_CREAT
    flags = factory_lib.raw_open_flags(wanted)
    assert flags & wanted == wanted
    if hasattr(os, "O_BINARY"):
        assert flags & os.O_BINARY


def test_factory_write_bytes_round_trips_the_hashed_body(tmp_path):
    assert factory_lib.safe_factory_write_bytes(tmp_path, "review-briefs/all.md", BODY)
    saved = (tmp_path / ".factory" / "review-briefs" / "all.md").read_bytes()
    assert saved == BODY
    assert hashlib.sha256(saved).hexdigest() == hashlib.sha256(BODY).hexdigest()


def test_factory_write_bytes_replaces_a_longer_file_exactly(tmp_path):
    assert factory_lib.safe_factory_write_bytes(tmp_path, "review-briefs/all.md", BODY * 3)
    assert factory_lib.safe_factory_write_bytes(tmp_path, "review-briefs/all.md", BODY)
    assert (tmp_path / ".factory" / "review-briefs" / "all.md").read_bytes() == BODY


def test_factory_append_and_json_keep_their_newlines(tmp_path):
    line = json.dumps({"n": 1}).encode() + b"\n"
    assert factory_lib.safe_factory_append(tmp_path, "ledger.jsonl", line)
    assert factory_lib.safe_factory_append(tmp_path, "ledger.jsonl", line)
    assert (tmp_path / ".factory" / "ledger.jsonl").read_bytes() == line + line
    assert factory_lib.safe_factory_write_json(tmp_path, "state.json", {"a": [1, 2]})
    saved = (tmp_path / ".factory" / "state.json").read_bytes()
    assert b"\r" not in saved
    assert json.loads(saved) == {"a": [1, 2]}


def test_delegation_ledger_and_revocation_keep_bytes(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    record = {"task": "T1", "at": "2026-09-18T00:00:00+00:00"}
    delegate._append_delegation_line(tmp_path, record)
    expected = json.dumps(record).encode() + b"\n"
    assert delegate.delegations_path(tmp_path).read_bytes() == expected
    assert delegate.delegation_mirror_path(tmp_path).read_bytes() == expected

    worker_admission.revoke_worker_admission(
        tmp_path, {"launch_id": "L1", "process_token": "token"})
    saved = worker_admission._revocation_path(tmp_path, "L1").read_bytes()
    assert b"\r" not in saved
    assert json.loads(saved)["launch_id"] == "L1"
