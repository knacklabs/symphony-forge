from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_gates import HARNESS, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import delegate  # noqa: E402
from forge_cli.worker_admission import path_in_scope  # noqa: E402
from test_worker_admission import (  # noqa: E402
    _invoke_worker, _patch, _record_launch, _seed_contract, _start_worker,
)


def test_delegate_scope_must_be_strict_subset_of_approved_write_scope():
    approved = ["src/a.py", "src/pkg/", "docs/readme.md"]
    assert delegate.narrowed_scope(approved, ["src/a.py"]) == ["src/a.py"]
    assert delegate.narrowed_scope(approved, ["src/pkg/one.py"]) == ["src/pkg/one.py"]
    assert delegate.narrowed_scope(approved, []) == approved
    with pytest.raises(SystemExit):
        delegate.narrowed_scope(approved, approved)
    with pytest.raises(SystemExit):
        delegate.narrowed_scope(approved, ["other.py"])
    with pytest.raises(SystemExit):
        delegate.narrowed_scope(approved, ["src/a.py", "src\\a.py"])
    with pytest.raises(SystemExit):
        delegate.narrowed_scope(approved, ["src/a.py/"])


def test_delegate_scope_is_bound_to_brief_launch_identity_and_existing_write_scope(
        repo: Path, tmp_path: Path):
    task = {
        "id": "T1", "title": "narrow", "objective": "change one file",
        "acceptance_criteria": ["one"], "write_scope": ["src/a.py", "src/b.py"],
        "required_tests": [], "verify_commands": [], "reviewer_focus": [],
        "review_budget": {"max_changed_files": 3, "max_changed_lines": 50,
                          "reason": "bounded fixture"},
    }
    # compose_brief reads optional repo contracts; minimal absent inputs are valid.
    brief = delegate.compose_brief(
        repo, task, write=True, user_facing=False, story="S1",
        scope_override=["src/a.py"],
    )
    scope = brief.split("## Write scope — nothing outside this", 1)[1].split("##", 1)[0]
    assert "src/a.py" in scope and "src/b.py" not in scope
    assert path_in_scope("src/a.py", ["src/a.py"])

    brief_path, digest = _seed_contract(repo, task)
    worker, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(
        repo, worker, token, launch_id, brief_path, digest,
        write_scope=["src/a.py"],
    )
    admitted = _invoke_worker(worker, _patch("*** Add File: src/a.py", "+ok"))
    assert "deny" not in admitted, admitted
    worker, token, launch_id = _start_worker(
        repo, tmp_path, launch_id="launch-sibling",
    )
    _record_launch(
        repo, worker, token, launch_id, brief_path, digest,
        write_scope=["src/a.py"],
    )
    denied = _invoke_worker(worker, _patch("*** Add File: src/b.py", "+no"))
    assert "deny" in denied, denied


def test_hook_refuses_write_outside_narrowed_delegate_scope():
    assert path_in_scope("src/a.py", ["src/a.py"])
    assert path_in_scope("src/pkg/child.py", ["src/pkg/"])
    assert not path_in_scope("src/b.py", ["src/a.py"])
    assert not path_in_scope("src/pkg-other/x", ["src/pkg/"])


@pytest.mark.skipif(sys.platform == "win32", reason="tests POSIX snapshot ownership and modes")
def test_context_file_security_no_follow_modes_identity_capacity_and_cleanup(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    secure = tmp_path / "secure"
    secure.mkdir(mode=0o700)
    secure.chmod(0o700)
    source = secure / "context.md"
    source.write_text("private context", encoding="utf-8")
    source.chmod(0o600)
    text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    try:
        assert text == "private context"
        assert metadata == {
            "supplied": True, "bytes": len(b"private context"),
            "snapshot_id": metadata["snapshot_id"],
        }
        assert "path" not in metadata and "sha256" not in metadata
        assert snapshot.read_text(encoding="utf-8") == text
        assert snapshot.stat().st_mode & 0o777 == 0o600
        snapshot.write_text("changed context", encoding="utf-8")
        with pytest.raises(SystemExit):
            delegate._validate_private_file(snapshot, "", identity)
        snapshot.write_text(text, encoding="utf-8")
    finally:
        root = snapshot.parent
        delegate._cleanup_private_context(snapshot, identity, "")
    assert not root.exists()

    for mode in (0o644, 0o444):
        source.chmod(mode)
        _text, _metadata, snapshot, identity = delegate.secure_context_snapshot(source)
        assert snapshot.stat().st_mode & 0o777 == 0o600
        assert snapshot.parent.stat().st_mode & 0o777 == 0o700
        delegate._cleanup_private_context(snapshot, identity, "")
    source.chmod(0o600)
    extra_link = secure / "extra-link.md"
    os.link(source, extra_link)
    with pytest.raises(SystemExit):
        delegate.secure_context_snapshot(source)
    extra_link.unlink()
    link = secure / "link.md"
    link.symlink_to(source)
    with pytest.raises(SystemExit):
        delegate.secure_context_snapshot(link)
    source.write_bytes(b"x" * (delegate.CONTEXT_MAX_BYTES + 1))
    with pytest.raises(SystemExit):
        delegate.secure_context_snapshot(source)


def test_windows_private_acl_validation_refuses_extra_allow_aces(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sid = "S-1-5-21-123"
    state = {
        "Owner": sid, "Protected": True,
        "Access": [{"Identity": sid, "Type": "Allow", "Inherited": False,
                    "Rights": 0x1F01FF}],
    }
    monkeypatch.setattr(delegate, "_windows_acl_state", lambda _path: state)
    delegate._require_windows_private_acl(tmp_path, sid)
    state["Access"][0].pop("Rights")
    with pytest.raises(SystemExit):
        delegate._require_windows_private_acl(tmp_path, sid)
    state["Access"][0]["Rights"] = 0x20089
    with pytest.raises(SystemExit):
        delegate._require_windows_private_acl(tmp_path, sid)
    state["Access"][0]["Rights"] = 0x1F01FF
    state["Access"].append({"Identity": "S-1-5-21-999", "Type": "Allow",
                            "Inherited": False, "Rights": 0x20089})
    with pytest.raises(SystemExit):
        delegate._require_windows_private_acl(tmp_path, sid)


def test_windows_path_script_transports_shell_sensitive_unicode_path_as_data(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "résumé ' ; [x] $(exit 1).md"
    sid = "S-1-5-21-123"
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "{}", "")

    monkeypatch.setattr(delegate.subprocess, "run", run)
    delegate._run_windows_path_script("$inputData.path", path, sid)
    argv, kwargs = calls[0]
    assert argv[:4] == ["powershell", "-NoProfile", "-NonInteractive", "-Command"]
    assert len(argv) == 5 and str(path) not in argv[4] and sid not in argv[4]
    assert kwargs["input"].isascii()
    assert json.loads(kwargs["input"]) == {"path": str(path), "sid": sid}


@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows ACLs")
def test_context_file_native_windows_protected_dacl_owner_reopen_and_stale_cleanup(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "private ' ; [x] $(exit 1).md"
    source.write_text("windows context", encoding="utf-8")
    sid = delegate._windows_current_sid()
    original = delegate._run_windows_path_script

    def diagnose(script, path, sid=""):
        result = original(script, path, sid)
        if path == source:
            print(json.dumps({
                "returncode": result.returncode,
                "stdout": result.stdout[:8192],
                "stderr": result.stderr[:8192],
                "stdout_length": len(result.stdout),
                "stderr_length": len(result.stderr),
            }, ensure_ascii=True))
        return result

    def protect_source(set_owner: bool = True):
        owner = "$acl.SetOwner($sid);" if set_owner else ""
        script = (
            "$ErrorActionPreference='Stop';"
            "$sid=New-Object Security.Principal.SecurityIdentifier($inputData.sid);"
            "$acl=New-Object Security.AccessControl.FileSecurity;"
            f"{owner}$acl.SetAccessRuleProtection($true,$false);"
            "$rule=New-Object Security.AccessControl.FileSystemAccessRule("
            "$sid,'FullControl','Allow');$acl.AddAccessRule($rule);"
            "[IO.File]::SetAccessControl($inputData.path,$acl)"
        )
        result = delegate._run_windows_path_script(script, source, sid)
        assert result.returncode == 0, (result.stdout[:8192], result.stderr[:8192])
        delegate._require_windows_private_acl(source, sid)

    monkeypatch.setattr(delegate, "_run_windows_path_script", diagnose)
    protect_source()
    text, _metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    assert text == "windows context"
    delegate._require_windows_private_acl(snapshot.parent, sid)
    delegate._require_windows_private_acl(snapshot, sid)
    delegate._cleanup_private_context(snapshot, identity, sid)
    assert not snapshot.parent.exists()
    try:
        result = subprocess.run(
            ["icacls", str(source), "/grant", "*S-1-5-11:(R)"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        _text, _metadata, snapshot, identity = delegate.secure_context_snapshot(source)
        delegate._require_windows_private_acl(snapshot, sid)
        delegate._require_windows_private_acl(snapshot.parent, sid)
        delegate._cleanup_private_context(snapshot, identity, sid)
        result = subprocess.run(
            ["icacls", str(source), "/remove", "*S-1-5-11",
             "/grant:r", f"*{sid}:(R)"], capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        _text, _metadata, snapshot, identity = delegate.secure_context_snapshot(source)
        delegate._require_windows_private_acl(snapshot, sid)
        delegate._require_windows_private_acl(snapshot.parent, sid)
        delegate._cleanup_private_context(snapshot, identity, sid)
    finally:
        protect_source(set_owner=False)
