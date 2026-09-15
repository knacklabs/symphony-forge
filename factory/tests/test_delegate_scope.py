from __future__ import annotations

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


def test_context_file_security_no_follow_modes_identity_capacity_and_cleanup(
        tmp_path: Path):
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

    source.chmod(0o644)
    text, _, ordinary_snapshot, ordinary_identity = (
        delegate.secure_context_snapshot(source)
    )
    assert text == "private context"
    delegate._cleanup_private_context(ordinary_snapshot, ordinary_identity, "")
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
    monkeypatch.setattr(delegate, "_windows_acl_state", lambda _path: {
        "Owner": sid, "Protected": True,
        "Access": [{"Identity": sid, "Type": "Allow", "Inherited": False}],
    })
    delegate._require_windows_private_acl(tmp_path, sid)
    monkeypatch.setattr(delegate, "_windows_acl_state", lambda _path: {
        "Owner": sid, "Protected": True,
        "Access": [
            {"Identity": sid, "Type": "Allow", "Inherited": False},
            {"Identity": "S-1-5-21-999", "Type": "Allow", "Inherited": False},
        ],
    })
    with pytest.raises(SystemExit):
        delegate._require_windows_private_acl(tmp_path, sid)


@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows ACLs")
def test_context_file_native_windows_protected_dacl_owner_reopen_and_stale_cleanup(
        tmp_path: Path):
    source = tmp_path / "ordinary-context.md"
    source.write_text("windows context", encoding="utf-8")
    text, _metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    sid = delegate._windows_current_sid()
    assert text == "windows context"
    delegate._require_windows_private_acl(snapshot.parent, sid)
    delegate._require_windows_private_acl(snapshot, sid)
    delegate._cleanup_private_context(snapshot, identity, sid)
    assert not snapshot.parent.exists()
