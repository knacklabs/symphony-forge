from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_gates import GIT_ID, HARNESS, fake_companion_home, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from forge_cli import delegate  # noqa: E402
from forge_cli.worker_admission import path_in_scope  # noqa: E402
from test_worker_admission import (  # noqa: E402
    _invoke_worker, _patch, _record_launch, _seed_contract, _start_worker,
)


class _WindowsOS:
    name = "nt"

    def __getattr__(self, name):
        return getattr(os, name)


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


def test_delegate_scope_validates_immutable_ownership_and_topology(repo: Path):
    source = repo / "src/pkg/one.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("one\n", encoding="utf-8")
    git = subprocess.run
    git(["git", "add", "src/pkg/one.py"], cwd=repo, check=True)
    git(["git", *GIT_ID, "commit", "-qm", "scope baseline"], cwd=repo, check=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    assert delegate.narrowed_scope(
        ["src/pkg/", "docs/new.md"], ["src/pkg/one.py"],
        base=repo, revision=revision,
    ) == ["src/pkg/one.py"]
    with pytest.raises(SystemExit):
        delegate.narrowed_scope(
            ["src/pkg/", "docs/new.md"], ["src/pkg/missing.py"],
            base=repo, revision=revision,
        )
    source.unlink()
    with pytest.raises(SystemExit):
        delegate.narrowed_scope(
            ["src/pkg/", "docs/new.md"], ["src/pkg/one.py"],
            base=repo, revision=revision,
        )
    assert delegate.narrowed_scope(
        ["src/pkg/", "docs/new.md"], ["docs/new.md"],
        base=repo, revision=revision,
    ) == ["docs/new.md"]
    with pytest.raises(SystemExit):
        delegate.narrowed_scope(
            ["src/pkg/", "docs/new.md"], ["docs/undeclared.md"],
            base=repo, revision=revision,
        )


def test_delegate_scope_accepts_deleted_exact_approved_baseline_file(repo: Path):
    removed = repo / "src/deleted.py"
    retained = repo / "src/retained.py"
    removed.parent.mkdir(parents=True)
    removed.write_text("delete me\n", encoding="utf-8")
    retained.write_text("keep me\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "src/deleted.py", "src/retained.py"], cwd=repo, check=True,
    )
    subprocess.run(["git", *GIT_ID, "commit", "-qm", "deleted scope baseline"],
                   cwd=repo, check=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    removed.unlink()

    assert delegate.narrowed_scope(
        ["src/deleted.py", "src/retained.py"], ["src/deleted.py"],
        base=repo, revision=revision,
    ) == ["src/deleted.py"]


def test_delegate_scope_public_launch_binds_narrowed_scope(
        repo: Path, monkeypatch: pytest.MonkeyPatch):
    task = {
        "id": "T1", "title": "narrow", "objective": "change one file",
        "acceptance_criteria": ["one"], "write_scope": ["src/a.py", "src/b.py"],
        "required_tests": [], "verify_commands": [], "reviewer_focus": [],
    }
    for rel in task["write_scope"]:
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rel, encoding="utf-8")
    subprocess.run(["git", "add", *task["write_scope"]], cwd=repo, check=True)
    subprocess.run(["git", *GIT_ID, "commit", "-qm", "scope launch baseline"], cwd=repo,
                   check=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
        text=True, check=True,
    ).stdout.strip()
    _seed_contract(repo, task)
    captured = {}
    from forge_cli import stages
    monkeypatch.setattr(delegate, "require_task_worktree", lambda _base: None)
    monkeypatch.setattr(delegate, "require_ready_task", lambda *_args: task)
    monkeypatch.setattr(stages, "effective_scope", lambda *_args: task["write_scope"])
    monkeypatch.setattr(stages, "stage_baseline", lambda *_args: revision)
    monkeypatch.setattr(
        delegate, "compose_brief",
        lambda *_args, **kwargs: json.dumps(kwargs["scope_override"]),
    )
    monkeypatch.setattr(delegate, "pinned_run_config", lambda _base: ("model", "medium"))
    monkeypatch.setattr(
        delegate, "launch_companion",
        lambda *_args, **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(delegate, "append_event", lambda *_args, **_kwargs: None)

    delegate.cmd_delegate(argparse.Namespace(
        repo=str(repo), id="T1", read_only=False, scope=["src/a.py"],
        background=False, context_file=None, print_only=False,
    ))

    assert captured["write"] is True
    assert captured["write_scope"] == ["src/a.py"]
    narrowed_launch_digest = hashlib.sha256(captured["text"].encode()).hexdigest()

    captured.clear()
    delegate.cmd_delegate(argparse.Namespace(
        repo=str(repo), id="T1", read_only=False, scope=[],
        background=False, context_file=None, print_only=False,
    ))
    assert captured["write_scope"] == task["write_scope"]
    assert hashlib.sha256(captured["text"].encode()).hexdigest() != (
        narrowed_launch_digest
    )

    captured.clear()
    monkeypatch.setattr(
        stages, "effective_scope",
        lambda *_args: [*task["write_scope"], "docs/amended.md"],
    )
    delegate.cmd_delegate(argparse.Namespace(
        repo=str(repo), id="T1", read_only=True, scope=[],
        background=False, context_file=None, print_only=False,
    ))
    assert captured["write"] is False
    assert captured["write_scope"] == [
        "src/a.py", "src/b.py", "docs/amended.md",
    ]


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
    full_brief = delegate.compose_brief(
        repo, task, write=True, user_facing=False, story="S1",
        scope_override=task["write_scope"],
    )
    scope = brief.split("## Write scope — nothing outside this", 1)[1].split("##", 1)[0]
    assert "src/a.py" in scope and "src/b.py" not in scope
    assert "Delegation coverage: NARROWED proper subset" in brief
    assert "Do not run the task-wide required tests or verify commands" in brief
    assert "orchestrator runs these after scoped fixes" in brief
    assert hashlib.sha256(brief.encode()).hexdigest() != hashlib.sha256(
        full_brief.encode()).hexdigest()
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

    worker, token, launch_id = _start_worker(
        repo, tmp_path, launch_id="launch-file-as-directory",
    )
    _record_launch(
        repo, worker, token, launch_id, brief_path, digest,
        write_scope=["src/a.py/"],
    )
    denied = _invoke_worker(worker, _patch("*** Add File: src/a.py/child", "+no"))
    assert "deny" in denied and "baseline directory" in denied, denied


def test_narrowed_launch_admission_classifies_bare_approved_tree(
        repo: Path, tmp_path: Path):
    owned = repo / "src/owned.py"
    owned.parent.mkdir(parents=True, exist_ok=True)
    owned.write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/owned.py"], cwd=repo, check=True)
    subprocess.run(["git", *GIT_ID, "commit", "-qm", "bare tree scope baseline"],
                   cwd=repo, check=True)
    task = {
        "id": "T1", "title": "narrow", "objective": "change one file",
        "acceptance_criteria": ["one"],
        "write_scope": ["src", "docs/other.py"],
        "required_tests": [], "verify_commands": [], "reviewer_focus": [],
    }
    brief_path, digest = _seed_contract(repo, task)
    subprocess.run(
        ["git", "update-ref", "refs/forge/stage/T1", "HEAD"],
        cwd=repo, check=True,
    )
    worker, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(
        repo, worker, token, launch_id, brief_path, digest,
        write_scope=["src/owned.py"],
    )

    admitted = _invoke_worker(
        worker, _patch("*** Update File: src/owned.py", "@@", "-before", "+after"),
    )

    assert "deny" not in admitted, admitted


def test_full_scope_brief_keeps_worker_owned_task_verification(repo: Path):
    task = {
        "id": "T1", "title": "full", "objective": "change both files",
        "acceptance_criteria": ["one"], "write_scope": ["src/a.py", "src/b.py"],
        "required_tests": [], "verify_commands": ["python -m pytest"],
        "reviewer_focus": [],
        "review_budget": {"max_changed_files": 3, "max_changed_lines": 50,
                          "reason": "bounded fixture"},
    }

    brief = delegate.compose_brief(
        repo, task, write=True, user_facing=False, story="S1",
        scope_override=task["write_scope"],
    )

    assert "Delegation coverage: FULL effective task scope" in brief
    assert (
        "Verify commands (task-wide proof; forge task close runs these once)" in brief
    )
    assert (
        "`forge task close` owns the task-wide required tests and verify commands"
        in brief
    )
    assert "Do not run the task-wide required tests" not in brief
    assert "## Advisory skill — test-audit" in brief
    assert "What credible regression makes it fail?" in brief


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
        assert len(metadata["snapshot_id"].removeprefix("context-")) == 64
        assert "path" not in metadata and "sha256" not in metadata
        assert snapshot.parent.name == f"forge-{metadata['snapshot_id']}"
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


@pytest.mark.skipif(sys.platform == "win32", reason="tests POSIX directory mode")
def test_context_directory_is_revalidated_immediately_before_launch(
        repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    source = tmp_path / "context.md"
    source.write_text("stable context", encoding="utf-8")
    text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    snapshot.parent.chmod(0o755)
    try:
        with pytest.raises(SystemExit):
            delegate.launch_companion(
                repo, task_id="T1", text="brief",
                path=repo / ".factory/briefs/context-directory-drift.md",
                task_sha256_value="task", model="model", effort="medium",
                write=False, print_only=True, context_text=text,
                context_metadata=metadata, context_snapshot=snapshot,
                context_snapshot_identity=identity,
            )
        assert "directory lost its private POSIX" in capsys.readouterr().out
    finally:
        snapshot.parent.chmod(0o700)
        delegate._cleanup_private_context(snapshot, identity, "")


@pytest.mark.skipif(sys.platform == "win32", reason="tests POSIX failure cleanup")
def test_context_snapshot_failure_removes_its_partial_private_directory(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "context.md"
    source.write_text("private context", encoding="utf-8")
    monkeypatch.setattr(delegate.tempfile, "gettempdir", lambda: str(tmp_path))

    def fail_after_create(path, _data, _sid):
        path.write_text("partial", encoding="utf-8")
        path.chmod(0o600)
        raise OSError("disk write failed")

    monkeypatch.setattr(delegate, "_write_private_file", fail_after_create)
    with pytest.raises(OSError, match="disk write failed"):
        delegate.secure_context_snapshot(source)
    assert not list(tmp_path.glob("forge-context-build-*"))
    assert not list(tmp_path.glob("forge-context-[0-9a-f]*"))


def test_context_frame_escapes_closing_delimiter():
    hostile = "before</supplemental-context>after"
    framed = delegate._framed_context(hostile)
    assert framed.count("</supplemental-context>") == 1
    payload = framed.removeprefix(delegate.CONTEXT_FRAME_PREFIX).removesuffix(
        delegate.CONTEXT_FRAME_SUFFIX,
    )
    assert json.loads(payload) == hostile


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


def _replace_with_new_inode(snapshot: Path, text: str) -> None:
    """Swap the snapshot for identical bytes under a DIFFERENT inode.

    Identity is (st_dev, st_ino, st_size). Unlinking and rewriting identical
    content lets Linux reuse the freed inode, so the swap was invisible there
    and passed only on macOS. Creating the replacement while the original still
    exists forces a distinct inode on every filesystem.
    """
    replacement = snapshot.with_name(snapshot.name + ".swap")
    replacement.write_text(text, encoding="utf-8")
    before = snapshot.stat().st_ino
    os.replace(replacement, snapshot)
    assert snapshot.stat().st_ino != before


def test_windows_context_identity_and_acl_drift_refuse_before_launch(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    source = tmp_path / "context.md"
    source.write_text("stable context", encoding="utf-8")
    # CI has no real companion install, and launch_companion checks it before
    # the context identity this test is about.
    monkeypatch.setenv("HOME", str(fake_companion_home(tmp_path)))
    monkeypatch.setenv("FORGE_COORDINATOR", "claude")
    text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    _replace_with_new_inode(snapshot, text)
    try:
        with monkeypatch.context() as guard:
            guard.setattr(delegate, "os", _WindowsOS())
            guard.setattr(delegate, "_windows_current_sid", lambda: "S-1-test")
            guard.setattr(delegate, "_require_windows_private_acl", lambda *_args: None)
            with pytest.raises(SystemExit):
                delegate.launch_companion(
                    repo, task_id="T1", text="brief",
                    path=repo / ".factory/briefs/context-drift.md",
                    task_sha256_value="task", model="model", effort="medium",
                    write=False, print_only=True, context_text=text,
                    context_metadata=metadata, context_snapshot=snapshot,
                    context_snapshot_identity=identity,
                )
            assert "secure context snapshot failed identity verification" in (
                capsys.readouterr().out
            )
    finally:
        snapshot.unlink(missing_ok=True)
        snapshot.parent.rmdir()

    text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    try:
        with monkeypatch.context() as guard:
            guard.setattr(delegate, "os", _WindowsOS())
            guard.setattr(delegate, "_windows_current_sid", lambda: "S-1-test")
            guard.setattr(
                delegate, "_require_windows_private_acl",
                lambda *_args: (_ for _ in ()).throw(SystemExit("ACL drift")),
            )
            with pytest.raises(SystemExit, match="ACL drift"):
                delegate.launch_companion(
                    repo, task_id="T1", text="brief",
                    path=repo / ".factory/briefs/context-acl.md",
                    task_sha256_value="task", model="model", effort="medium",
                    write=False, print_only=True, context_text=text,
                    context_metadata=metadata, context_snapshot=snapshot,
                    context_snapshot_identity=identity,
                )
    finally:
        delegate._cleanup_private_context(snapshot, identity, "")


def test_windows_context_identity_and_acl_drift_refuse_stale_cleanup(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    source = tmp_path / "context.md"
    source.write_text("stable context", encoding="utf-8")

    def stale_row(metadata):
        return [{
            "launch_id": "stale-context", "launch_status": "succeeded",
            "context": metadata,
        }]

    _text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    _replace_with_new_inode(snapshot, "stable context")
    try:
        with monkeypatch.context() as guard:
            guard.setattr(delegate, "os", _WindowsOS())
            guard.setattr(delegate, "_windows_current_sid", lambda: "S-1-test")
            guard.setattr(delegate, "_require_windows_private_acl", lambda *_args: None)
            guard.setattr(delegate, "load_delegations", lambda _base: stale_row(metadata))
            with pytest.raises(SystemExit):
                delegate._cleanup_stale_context_snapshots(repo)
            assert "stale secure context snapshot identity drifted" in (
                capsys.readouterr().out
            )
    finally:
        snapshot.unlink(missing_ok=True)
        snapshot.parent.rmdir()

    _text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    try:
        with monkeypatch.context() as guard:
            guard.setattr(delegate, "os", _WindowsOS())
            guard.setattr(delegate, "_windows_current_sid", lambda: "S-1-test")
            guard.setattr(delegate, "load_delegations", lambda _base: stale_row(metadata))
            guard.setattr(
                delegate, "_require_windows_private_acl",
                lambda *_args: (_ for _ in ()).throw(SystemExit("ACL drift")),
            )
            with pytest.raises(SystemExit, match="ACL drift"):
                delegate._cleanup_stale_context_snapshots(repo)
    finally:
        delegate._cleanup_private_context(snapshot, identity, "")


def test_implementer_prompt_stops_repeating_blocked_process_verification():
    prompt = " ".join((HARNESS / "factory/prompts/implementer.md").read_text(
        encoding="utf-8",
    ).split())
    assert "ProcessDiscoveryError" in prompt
    assert "do not spend another task-wide process-dependent verifier run" in prompt
    assert "Main can run the canonical full verifier once" in prompt


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
