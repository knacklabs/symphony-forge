"""Native Codex uses the protected delegation lifecycle without the plugin."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest


HARNESS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HARNESS / "factory" / "scripts"))

from forge_cli.codex_runtime import (  # noqa: E402
    native_argv, native_argv_valid, parse_native_result,
    scan_native_result, selected_coordinator,
)
from forge_cli.delegate import (  # noqa: E402
    append_delegation, argv_digest, launch_companion, load_delegations,
)
from forge_cli.stages import _require_successful_launch, task_digest  # noqa: E402
from factory_lib import sha256_of  # noqa: E402


@pytest.fixture()
def native_repo(tmp_path: Path) -> Path:
    base = tmp_path / "repo"
    base.mkdir()
    subprocess.run(["git", "init", "-q", str(base)], check=True)
    schemas = base / "factory" / "schemas"
    schemas.mkdir(parents=True)
    shutil.copy(HARNESS / "factory/schemas/delegation.json", schemas)
    (base / ".factory").mkdir()
    return base


def fake_codex(tmp_path: Path, *, terminal: str = "turn.completed",
               delay: float = 0, exit_code: int = 0,
               session_id: str = "thread-fixture",
               wait_on_new: float = 0,
               completed_message: str = "") -> Path:
    script = tmp_path / ("fake_codex.py" if os.name == "nt" else "codex")
    script.write_text(
        ("" if os.name == "nt" else f"#!{sys.executable}\n") +
        "import json, os, sys, time\n"
        "prompt = sys.stdin.read()\n"
        "resumed = 'resume' in sys.argv\n"
        f"if {wait_on_new!r} and not resumed:\n"
        f"    print(json.dumps({{'type':'thread.started','thread_id':{session_id!r}}}),"
        " flush=True)\n"
        f"    time.sleep({wait_on_new!r})\n"
        "    raise SystemExit(0)\n"
        f"time.sleep({delay!r})\n"
        f"print(json.dumps({{'type':'thread.started','thread_id':{session_id!r}}}))\n"
        "print(json.dumps({'type':'item.completed','item':{'type':'agent_message',"
        f"'text':{completed_message!r} or prompt}}}}))\n"
        f"print(json.dumps({{'type':{terminal!r}}}))\n"
        "with open(os.environ['FAKE_CODEX_CAPTURE'], 'w') as stream:\n"
        "    json.dump({'argv':sys.argv[1:], 'prompt':prompt, "
        "'token':os.environ.get('FORGE_PROCESS_TOKEN'), "
        "'launch_id':os.environ.get('FORGE_LAUNCH_ID')}, stream)\n"
        f"sys.exit({exit_code})\n",
    )
    if os.name != "nt":
        script.chmod(0o755)
        return script
    launcher = tmp_path / "codex.cmd"
    launcher.write_text(
        f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n'
    )
    return launcher


def native_env(monkeypatch, tmp_path: Path, executable: Path) -> Path:
    capture = tmp_path / "capture.json"
    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    monkeypatch.setenv("FAKE_CODEX_CAPTURE", str(capture))
    monkeypatch.setenv("PATH", f"{executable.parent}{os.pathsep}{os.environ['PATH']}")
    return capture


def test_runtime_selection_is_explicit_then_native_then_legacy(monkeypatch):
    monkeypatch.delenv("FORGE_COORDINATOR", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CODEX_SHELL", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    assert selected_coordinator() == "claude"
    monkeypatch.setenv("CLAUDECODE", "1")
    assert selected_coordinator() == "claude"
    monkeypatch.setenv("CODEX_THREAD_ID", "thread")
    assert selected_coordinator() == "codex"
    assert selected_coordinator("claude") == "claude"
    with pytest.raises(SystemExit, match="claude.*codex"):
        selected_coordinator("other")


def test_native_argv_binds_policy_without_resume_dispatch(tmp_path):
    argv = native_argv("/bin/codex", tmp_path, "model", "high", False)
    entry = {
        "executable_path": "/bin/codex", "argv": argv,
        "model": "model", "effort": "high", "write": False,
    }
    assert native_argv_valid(entry, tmp_path, [])
    assert argv[-1] == "-"
    assert argv[argv.index("--enable") + 1] == "hooks"
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert 'approval_policy="never"' in argv
    with pytest.raises(TypeError):
        native_argv(
            "/bin/codex", tmp_path, "model", "high", False,
            resume_session="thread-1",
        )
    historical = {
        **entry,
        "argv": [*argv[:-1], "resume", "thread-1", "-"],
        "resume_session": "thread-1",
        "launch_status": "succeeded",
    }
    assert native_argv_valid(historical, tmp_path, [])
    assert not native_argv_valid(
        {**historical, "launch_status": "running"}, tmp_path, [])


def test_native_write_argv_grants_only_exact_codex_scope_files(tmp_path):
    (tmp_path / ".codex/agents").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".codex/link").symlink_to(outside, target_is_directory=True)
    scope = [
        ".codex/hooks.json",
        ".codex/agents/new.toml",
        ".codex/",
        ".codex/agents/",
        ".codex/../outside.toml",
        "src/",
        ".codex/config.toml",
        ".codex/link/escape.toml",
    ]
    argv = native_argv(
        "/bin/codex", tmp_path, "model", "high", True, scope)
    entry = {
        "executable_path": "/bin/codex", "argv": argv,
        "model": "model", "effort": "high", "write": True,
    }
    grants = [
        argv[index + 1] for index, token in enumerate(argv)
        if token == "--add-dir"
    ]
    assert grants == [
        ".codex/agents/new.toml",
        ".codex/config.toml",
        ".codex/hooks.json",
    ]
    assert argv[-1] == "-"
    assert native_argv_valid(entry, tmp_path, scope)
    assert not native_argv_valid(entry, tmp_path, [])
    legacy = native_argv(
        "/bin/codex", tmp_path, "model", "high", True, [])
    for launch_status in ("running", "failed", "succeeded"):
        assert not native_argv_valid(
            {**entry, "argv": legacy, "launch_status": launch_status},
            tmp_path, scope)
    historical = {
        **entry,
        "argv": [*legacy[:-1], "resume", "thread-1", "-"],
        "resume_session": "thread-1",
        "launch_status": "succeeded",
    }
    assert native_argv_valid(historical, tmp_path, scope)
    assert not native_argv_valid(
        {**historical, "launch_status": "running"}, tmp_path, scope)
    assert "--add-dir" not in native_argv(
        "/bin/codex", tmp_path, "model", "high", False, scope)


def test_native_launch_registers_before_stdin_and_records_terminal_identity(
        native_repo, tmp_path, monkeypatch):
    import forge_cli.codex_runtime as codex_runtime
    import forge_cli.delegate as delegate

    executable = fake_codex(tmp_path)
    capture_path = native_env(monkeypatch, tmp_path, executable)
    scan_calls = []
    real_scan = codex_runtime.scan_native_result

    def scan(path, *, data=None, stream=None):
        scan_calls.append(path)
        assert data is None and stream is not None
        return real_scan(path, stream=stream)

    monkeypatch.setattr(codex_runtime, "scan_native_result", scan)
    monkeypatch.setattr(delegate, "_process_table", lambda: {})
    monkeypatch.setattr(delegate, "_capture_spawn_identity", lambda _proc: "known")
    monkeypatch.setattr(
        delegate, "_wait_and_reap",
        lambda proc, *_args, **_kwargs: proc.wait() == 0,
    )
    real_popen = delegate.subprocess.Popen
    stdin_snapshots = []
    stdin_writes = []
    popen_options = {}

    class StdinProxy:
        def __init__(self, stream):
            self.stream = stream

        def write(self, data):
            stdin_snapshots.append([
                row["launch_status"] for row in load_delegations(native_repo)
            ])
            stdin_writes.append(data)
            return self.stream.write(data)

        def close(self):
            return self.stream.close()

        def __getattr__(self, name):
            return getattr(self.stream, name)

    def popen(*args, **kwargs):
        native_launch = args[0][0] == str(executable)
        if native_launch:
            popen_options.update(kwargs)
        process = real_popen(*args, **kwargs)
        if native_launch:
            process.stdin = StdinProxy(process.stdin)
        return process

    monkeypatch.setattr(delegate.subprocess, "Popen", popen)
    brief = native_repo / ".factory" / "briefs" / "T1.md"
    prompt = "fixture prompt — नमस्ते\nsecond line\nlast line"
    terminal = launch_companion(
        native_repo,
        task_id="T1",
        text=prompt,
        path=brief,
        task_sha256_value="task-digest",
        model="model-pin",
        effort="medium",
        write=False,
    )
    capture = json.loads(capture_path.read_text())
    rows = load_delegations(native_repo)
    assert [row["launch_status"] for row in rows] == [
        "starting", "running", "succeeded",
    ]
    assert stdin_snapshots == [["starting", "running"]]
    assert stdin_writes == [prompt.encode("utf-8")]
    assert terminal["transport"] == "native"
    assert terminal["pid_started"] == "known"
    assert terminal["session_id"] == "thread-fixture"
    assert terminal["brief_path"] == ".factory/briefs/T1.md"
    assert Path(terminal["output_path"]).is_file()
    assert Path(terminal["stderr_path"]).is_file()
    assert capture["prompt"] == prompt
    assert popen_options["text"] is False
    assert "encoding" not in popen_options
    assert "errors" not in popen_options
    assert capture["token"] == terminal["process_token"]
    assert capture["launch_id"] == terminal["launch_id"]
    assert capture["argv"][-1] == "-"
    assert scan_calls == [Path(terminal["output_path"])]


@pytest.mark.parametrize("failed_open", [1, 2])
def test_native_log_open_failure_releases_lock_without_lifecycle_rows(
        native_repo, tmp_path, monkeypatch, failed_open):
    import builtins
    import forge_cli.delegate as delegate
    import forge_cli.doctor as doctor

    executable = fake_codex(tmp_path)
    native_env(monkeypatch, tmp_path, executable)
    monkeypatch.setattr(doctor, "codex_hook_readiness", lambda _base: (True, ""))
    lock = object()
    acquired = []
    released = []
    monkeypatch.setattr(
        delegate, "_acquire_delegation_lock",
        lambda _base, _task, launch_id: acquired.append(launch_id) or lock,
    )
    monkeypatch.setattr(
        delegate, "_release_delegation_lock",
        lambda handle, launch_id: released.append((handle, launch_id)),
    )
    real_open = builtins.open
    opened = []
    calls = 0

    def fail_log_open(path, *args, **kwargs):
        nonlocal calls
        if "native-runs" in Path(path).parts:
            calls += 1
            if calls == failed_open:
                raise OSError("injected log-open failure")
            handle = real_open(path, *args, **kwargs)
            opened.append(handle)
            return handle
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fail_log_open)
    with pytest.raises(OSError, match="injected log-open failure"):
        launch_companion(
            native_repo,
            task_id="T1",
            text="fixture prompt",
            path=native_repo / ".factory" / "briefs" / "T1.md",
            task_sha256_value="task-digest",
            model="model-pin",
            effort="medium",
            write=True,
        )
    assert all(handle.closed for handle in opened)
    assert released == [(lock, acquired[0])]
    assert load_delegations(native_repo) == []


@pytest.mark.parametrize(("limit", "message"), [
    (None, "cannot determine the installed component prompt limit"),
    ("8", "complete prompt requires"),
])
def test_context_prompt_capacity_refuses_before_starting_row(
        native_repo, tmp_path, monkeypatch, capsys, limit, message):
    import forge_cli.delegate as delegate

    executable = fake_codex(tmp_path)
    native_env(monkeypatch, tmp_path, executable)
    if limit is None:
        monkeypatch.delenv("FORGE_COMPONENT_PROMPT_LIMIT_BYTES", raising=False)
    else:
        monkeypatch.setenv("FORGE_COMPONENT_PROMPT_LIMIT_BYTES", limit)
    source = tmp_path / "context.md"
    source.write_text("supplement", encoding="utf-8")
    text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    try:
        with pytest.raises(SystemExit):
            launch_companion(
                native_repo, task_id="grill-plan", text="primary",
                path=native_repo / ".factory" / "grill-brief-plan.md",
                task_sha256_value="a" * 64, model="model-pin", effort="high",
                write=False, context_text=text, context_metadata=metadata,
                context_snapshot=snapshot, context_snapshot_identity=identity,
            )
        assert message in capsys.readouterr().out
        assert load_delegations(native_repo) == []
    finally:
        delegate._cleanup_private_context(snapshot, identity, "")


def test_native_context_launch_frames_exact_snapshot_and_cleans_terminal(
        native_repo, tmp_path, monkeypatch):
    import forge_cli.delegate as delegate

    executable = fake_codex(tmp_path)
    capture_path = native_env(monkeypatch, tmp_path, executable)
    monkeypatch.setenv("FORGE_COMPONENT_PROMPT_LIMIT_BYTES", "1048576")
    monkeypatch.setattr(delegate, "_process_table", lambda: {})
    monkeypatch.setattr(delegate, "_capture_spawn_identity", lambda _proc: "known")
    monkeypatch.setattr(
        delegate, "_wait_and_reap",
        lambda proc, *_args, **_kwargs: proc.wait() == 0,
    )
    source = tmp_path / "context.md"
    source.write_text("supplement", encoding="utf-8")
    text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    terminal = launch_companion(
        native_repo, task_id="grill-plan", text="primary",
        path=native_repo / ".factory" / "grill-brief-plan.md",
        task_sha256_value="a" * 64, model="model-pin", effort="high",
        write=False, context_text=text, context_metadata=metadata,
        context_snapshot=snapshot, context_snapshot_identity=identity,
    )

    prompt = json.loads(capture_path.read_text(encoding="utf-8"))["prompt"]
    assert prompt.startswith("primary\n\n## Untrusted supplemental context")
    assert '<supplemental-context>\n"supplement"\n</supplemental-context>' in prompt
    assert terminal["context"] == metadata
    assert terminal["prompt_sha256"] == hashlib.sha256(
        prompt.encode("utf-8"),
    ).hexdigest()
    assert set(terminal["context"]) == {"supplied", "bytes", "snapshot_id"}
    assert not snapshot.parent.exists()


def test_context_launch_refuses_text_that_does_not_match_stable_snapshot(
        native_repo, tmp_path, monkeypatch, capsys):
    import forge_cli.delegate as delegate

    executable = fake_codex(tmp_path)
    native_env(monkeypatch, tmp_path, executable)
    source = tmp_path / "context.md"
    source.write_text("captured", encoding="utf-8")
    text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    try:
        with pytest.raises(SystemExit):
            launch_companion(
                native_repo, task_id="grill-plan", text="primary",
                path=native_repo / ".factory" / "grill-brief-plan.md",
                task_sha256_value="a" * 64, model="model-pin", effort="high",
                write=False, context_text=text + " drift",
                context_metadata=metadata, context_snapshot=snapshot,
                context_snapshot_identity=identity,
            )
        assert "does not match its stable snapshot" in capsys.readouterr().out
        assert load_delegations(native_repo) == []
    finally:
        delegate._cleanup_private_context(snapshot, identity, "")


def test_claude_context_launch_sends_exact_bound_prompt_over_stdin(
        native_repo, tmp_path, monkeypatch):
    import forge_cli.delegate as delegate

    companion = tmp_path / "fixture_companion.py"
    capture = tmp_path / "companion-capture.json"
    companion.write_text(
        "MAX_PROMPT_BYTES = 1048576\n"
        "import json, os, sys\n"
        "prompt = sys.stdin.buffer.read().decode('utf-8')\n"
        "with open(os.environ['FAKE_COMPANION_CAPTURE'], 'w') as stream:\n"
        "    json.dump({'argv': sys.argv[1:], 'prompt': prompt}, stream)\n"
        "print(json.dumps({'status': 0, 'threadId': 'fixture', "
        "'rawOutput': '{}'}))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FORGE_COORDINATOR", "claude")
    monkeypatch.setenv("FAKE_COMPANION_CAPTURE", str(capture))
    monkeypatch.setattr(delegate, "companion_script", lambda: companion)
    monkeypatch.setattr(delegate.shutil, "which", lambda _name: sys.executable)
    monkeypatch.setattr(delegate, "_process_table", lambda: {})
    monkeypatch.setattr(delegate, "_capture_spawn_identity", lambda _proc: "known")
    monkeypatch.setattr(
        delegate, "_wait_and_reap",
        lambda proc, *_args, **_kwargs: proc.wait() == 0,
    )
    source = tmp_path / "context.md"
    source.write_text("", encoding="utf-8")
    text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    terminal = launch_companion(
        native_repo, task_id="grill-plan", text="primary",
        path=native_repo / ".factory" / "grill-brief-plan.md",
        task_sha256_value="a" * 64, model="model-pin", effort="high",
        write=False, context_text=text, context_metadata=metadata,
        context_snapshot=snapshot, context_snapshot_identity=identity,
    )

    captured = json.loads(capture.read_text(encoding="utf-8"))
    prompt = captured["prompt"]
    assert "--prompt-file" not in captured["argv"]
    assert prompt.startswith("primary\n\n## Untrusted supplemental context")
    assert prompt.count("</supplemental-context>") == 1
    assert json.loads(
        prompt.split("<supplemental-context>\n", 1)[1].rsplit(
            "\n</supplemental-context>", 1,
        )[0]
    ) == ""
    assert terminal["prompt_sha256"] == hashlib.sha256(
        prompt.encode("utf-8"),
    ).hexdigest()
    assert terminal["context"] == metadata
    assert not snapshot.parent.exists()


@pytest.mark.parametrize("status", ["succeeded", "running"])
def test_stale_context_cleanup_is_ledger_correlated_and_bounded(
        native_repo, tmp_path, monkeypatch, status):
    import forge_cli.codex_status as codex_status
    import forge_cli.delegate as delegate

    source = tmp_path / "ordinary-context.md"
    source.write_text("context", encoding="utf-8")
    source.chmod(0o644)
    _text, metadata, snapshot, _identity = delegate.secure_context_snapshot(source)
    row = {
        "launch_id": "launch-stale", "launch_status": status,
        "context": metadata, "pid": 123, "pid_started": "known",
    }
    arbitrary = (
        Path(tempfile.gettempdir())
        / f"forge-context-not-ledger-owned-{tmp_path.name}"
    )
    arbitrary.mkdir(exist_ok=True)
    (arbitrary / "keep.txt").write_text("keep", encoding="utf-8")
    monkeypatch.setattr(delegate, "load_delegations", lambda _base: [row])
    monkeypatch.setattr(
        codex_status, "dead_launches",
        lambda _base: [row] if status == "running" else [],
    )
    try:
        delegate._cleanup_stale_context_snapshots(native_repo)
        assert not snapshot.parent.exists()
        assert (arbitrary / "keep.txt").read_text(encoding="utf-8") == "keep"
    finally:
        shutil.rmtree(arbitrary)


@pytest.mark.parametrize("tamper", ["unknown", "link", "identity"])
def test_stale_context_cleanup_refuses_unknown_link_or_identity_drift(
        native_repo, tmp_path, monkeypatch, tamper):
    import forge_cli.delegate as delegate

    source = tmp_path / "context.md"
    source.write_text("context", encoding="utf-8")
    _text, metadata, snapshot, identity = delegate.secure_context_snapshot(source)
    row = {
        "launch_id": "launch-stale", "launch_status": "failed",
        "context": dict(metadata),
    }
    extra = None
    if tamper == "unknown":
        extra = snapshot.parent / "unknown.txt"
        extra.write_text("unknown", encoding="utf-8")
    elif tamper == "link":
        link_target = tmp_path / "target.txt"
        link_target.write_text("target", encoding="utf-8")
        snapshot.unlink()
        snapshot.symlink_to(link_target)
    else:
        row["context"]["bytes"] += 1
    monkeypatch.setattr(delegate, "load_delegations", lambda _base: [row])
    try:
        with pytest.raises(SystemExit):
            delegate._cleanup_stale_context_snapshots(native_repo)
    finally:
        if tamper == "link":
            snapshot.unlink()
            snapshot.parent.rmdir()
        else:
            if extra is not None:
                extra.unlink()
            delegate._cleanup_private_context(snapshot, identity, "")


def test_stale_context_cleanup_refuses_same_size_regular_file_replacement(
        native_repo, tmp_path, monkeypatch, capsys):
    import forge_cli.delegate as delegate

    source = tmp_path / "context.md"
    source.write_text("context", encoding="utf-8")
    _text, metadata, snapshot, _identity = delegate.secure_context_snapshot(source)
    row = {
        "launch_id": "launch-stale", "launch_status": "failed",
        "context": metadata,
    }
    replacement = snapshot.parent / "replacement.txt"
    replacement.write_bytes(b"changed")
    replacement.chmod(0o600)
    os.replace(replacement, snapshot)
    monkeypatch.setattr(delegate, "load_delegations", lambda _base: [row])

    try:
        with pytest.raises(SystemExit):
            delegate._cleanup_stale_context_snapshots(native_repo)
        assert "identity drifted" in capsys.readouterr().out
        assert snapshot.read_bytes() == b"changed"
    finally:
        snapshot.unlink()
        snapshot.parent.rmdir()


def test_stale_context_cleanup_preserves_unbound_historical_snapshot(
        native_repo, monkeypatch, capsys):
    import forge_cli.delegate as delegate

    opaque = "a" * 32
    directory = Path(tempfile.gettempdir()) / f"forge-context-{opaque}"
    directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    snapshot = directory / "context.txt"
    snapshot.write_bytes(b"context")
    snapshot.chmod(0o600)
    row = {
        "launch_id": "launch-historical", "launch_status": "failed",
        "context": {
            "supplied": True, "bytes": len(b"context"),
            "snapshot_id": f"context-{opaque}",
        },
    }
    monkeypatch.setattr(delegate, "load_delegations", lambda _base: [row])

    try:
        with pytest.raises(SystemExit):
            delegate._cleanup_stale_context_snapshots(native_repo)
        assert "no identity binding" in capsys.readouterr().out
        assert snapshot.read_bytes() == b"context"
    finally:
        snapshot.unlink()
        directory.rmdir()


def test_native_zero_exit_without_completed_turn_is_failed(
        native_repo, tmp_path, monkeypatch, capsys):
    executable = fake_codex(tmp_path, terminal="item.completed")
    native_env(monkeypatch, tmp_path, executable)
    with pytest.raises(SystemExit):
        launch_companion(
            native_repo,
            task_id="T1",
            text="fixture prompt",
            path=native_repo / ".factory" / "briefs" / "T1.md",
            task_sha256_value="task-digest",
            model="model-pin",
            effort="medium",
            write=False,
        )
    assert "turn.completed" in capsys.readouterr().out
    failed = load_delegations(native_repo)[-1]
    assert failed["launch_status"] == "failed"
    assert failed["session_id"] == "thread-fixture"


def test_native_protocol_failure_revokes_write_admission(
        native_repo, tmp_path, monkeypatch):
    executable = fake_codex(tmp_path, terminal="item.completed")
    native_env(monkeypatch, tmp_path, executable)
    import forge_cli.doctor as doctor

    monkeypatch.setattr(doctor, "codex_hook_readiness", lambda _base: (True, ""))
    with pytest.raises(SystemExit):
        launch_companion(
            native_repo,
            task_id="T1",
            text="fixture prompt",
            path=native_repo / ".factory" / "briefs" / "T1.md",
            task_sha256_value="task-digest",
            model="model-pin",
            effort="medium",
            write=True,
        )
    rows = load_delegations(native_repo)
    launch_id = rows[0]["launch_id"]
    marker = native_repo / ".git" / "forge" / "revoked-launches" / f"{launch_id}.json"
    assert marker.is_file()
    assert rows[-1]["launch_status"] == "failed"


def test_native_write_fails_closed_when_hooks_are_not_ready(
        native_repo, tmp_path, monkeypatch, capsys):
    executable = fake_codex(tmp_path)
    native_env(monkeypatch, tmp_path, executable)
    import forge_cli.doctor as doctor

    monkeypatch.setattr(
        doctor, "codex_hook_readiness",
        lambda _base: (False, "exact repo hook source is not trusted"),
    )
    with pytest.raises(SystemExit):
        launch_companion(
            native_repo,
            task_id="T1",
            text="fixture prompt",
            path=native_repo / ".factory" / "briefs" / "T1.md",
            task_sha256_value="task-digest",
            model="model-pin",
            effort="medium",
            write=True,
        )
    assert "exact repo hook source is not trusted" in capsys.readouterr().out
    assert load_delegations(native_repo) == []


def test_native_nonzero_failure_retains_real_session_identity(
        native_repo, tmp_path, monkeypatch):
    executable = fake_codex(tmp_path, terminal="turn.failed", exit_code=3)
    native_env(monkeypatch, tmp_path, executable)
    with pytest.raises(SystemExit):
        launch_companion(
            native_repo,
            task_id="explore",
            text="fixture prompt",
            path=native_repo / ".factory" / "briefs" / "explore.md",
            task_sha256_value="",
            model="model-pin",
            effort="high",
            write=False,
        )
    failed = load_delegations(native_repo)[-1]
    assert failed["launch_status"] == "failed"
    assert failed["exit_code"] == 3
    assert failed["session_id"] == "thread-fixture"


def test_native_identity_survives_only_a_truncated_jsonl_tail(tmp_path):
    output = tmp_path / "native.jsonl"
    output.write_text(
        '{"type":"thread.started","thread_id":"thread-prefix"}\n'
        '{"type":"item.completed"'
    )
    assert scan_native_result(output).session_id == "thread-prefix"
    with pytest.raises(ValueError):
        parse_native_result(output)
    output.write_text(
        '{"type":"thread.started","thread_id":"thread-prefix"}\n'
        'malformed complete line\n'
    )
    assert scan_native_result(output).session_id == ""
    output.write_bytes(
        b'{"type":"thread.started","thread_id":"thread-prefix"}\n'
        + "snowman: \u2603".encode("utf-8")[:-1]
    )
    assert scan_native_result(output).session_id == "thread-prefix"
    with pytest.raises(ValueError):
        parse_native_result(output)
    output.write_bytes(
        b'{"type":"thread.started","thread_id":"thread-prefix"}\n'
        b'broken: \xe2\n'
    )
    assert scan_native_result(output).session_id == ""


def test_stage_launch_gate_requires_exact_native_terminal_stream(
        native_repo, tmp_path):
    task = {"id": "T1", "write_scope": [".codex/hooks.json"]}
    stage = {"started_at": "2026-01-01T00:00:00Z"}
    launch_id = "launch-stage-fixture"
    brief = native_repo / ".factory" / "briefs" / "T1.md"
    brief.parent.mkdir(parents=True)
    brief.write_text("brief")
    logs = Path(subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"], cwd=native_repo,
        check=True, capture_output=True, text=True,
    ).stdout.strip()) / "forge" / "native-runs"
    logs.mkdir(parents=True)
    output = logs / f"{launch_id}.jsonl"
    stderr = logs / f"{launch_id}.stderr.log"
    output.write_text(
        '{"type":"thread.started","thread_id":"thread-fixture"}\n'
        '{"type":"turn.completed"}\n'
    )
    stderr.write_text("")
    argv = native_argv(
        "/bin/codex", native_repo, "model", "medium", True,
        task["write_scope"],
    )
    record = {
        "generated_by": "orchestrator", "at": stage["started_at"],
        "launch_id": launch_id, "task": "T1",
        "brief_sha256": sha256_of(brief), "task_sha256": task_digest(task),
        "write": True, "model": "model", "effort": "medium",
        "write_scope": task["write_scope"],
        "argv": argv, "argv_sha256": argv_digest(argv),
        "process_token": f"delegation-{launch_id}",
        "stage_started_at": stage["started_at"], "transport": "native",
        "executable_path": "/bin/codex",
        "brief_path": ".factory/briefs/T1.md",
        "output_path": str(output), "stderr_path": str(stderr),
    }
    for status in ("starting", "running"):
        append_delegation(native_repo, {**record, "launch_status": status})
    append_delegation(native_repo, {
        **record, "launch_status": "succeeded", "exit_code": 0,
        "session_id": "thread-fixture",
    })
    _require_successful_launch(native_repo, "T1", stage, task)
    output.write_text('{"type":"thread.started","thread_id":"thread-fixture"}\n')
    with pytest.raises(SystemExit):
        _require_successful_launch(native_repo, "T1", stage, task)


def test_concurrent_native_terminal_is_idempotent_and_retry_can_close_stage(
        native_repo):
    task = {"id": "T1", "write_scope": ["src/"]}
    stage = {"started_at": "2026-01-01T00:00:00Z"}
    brief = native_repo / ".factory" / "briefs" / "T1.md"
    brief.parent.mkdir(parents=True)
    brief.write_text("brief")
    git_dir = Path(subprocess.run(
        ["git", "rev-parse", "--absolute-git-dir"], cwd=native_repo,
        check=True, capture_output=True, text=True,
    ).stdout.strip())
    logs = git_dir / "forge" / "native-runs"
    logs.mkdir(parents=True)

    def record(launch_id: str) -> dict:
        output = logs / f"{launch_id}.jsonl"
        stderr = logs / f"{launch_id}.stderr.log"
        argv = native_argv(
            "/bin/codex", native_repo, "model", "medium", True,
            task["write_scope"],
        )
        return {
            "generated_by": "orchestrator", "at": stage["started_at"],
            "launch_id": launch_id, "task": "T1",
            "brief_sha256": sha256_of(brief),
            "task_sha256": task_digest(task), "write": True,
            "write_scope": task["write_scope"],
            "model": "model", "effort": "medium", "argv": argv,
            "argv_sha256": argv_digest(argv),
            "process_token": f"delegation-{launch_id}",
            "stage_started_at": stage["started_at"], "transport": "native",
            "executable_path": "/bin/codex",
            "brief_path": ".factory/briefs/T1.md",
            "output_path": str(output), "stderr_path": str(stderr),
        }

    first = record("launch-first")
    append_delegation(native_repo, {**first, "launch_status": "starting"})
    append_delegation(native_repo, {**first, "launch_status": "running"})
    barrier = threading.Barrier(2)
    errors = []

    def finish(status: str) -> None:
        try:
            barrier.wait()
            append_delegation(native_repo, {
                **first, "launch_status": status,
                "exit_code": 0 if status == "succeeded" else 1,
                "session_id": "thread-first",
            })
        except BaseException as exc:  # surfaced below instead of lost in thread
            errors.append(exc)

    workers = [threading.Thread(target=finish, args=(status,))
               for status in ("failed", "succeeded")]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert errors == []
    first_rows = [row for row in load_delegations(native_repo)
                  if row["launch_id"] == "launch-first"]
    assert len([row for row in first_rows
                if row["launch_status"] in {"failed", "succeeded"}]) == 1

    retry = record("launch-retry")
    output = Path(retry["output_path"])
    output.write_text(
        '{"type":"thread.started","thread_id":"thread-retry"}\n'
        '{"type":"turn.completed"}\n'
    )
    Path(retry["stderr_path"]).write_text("")
    append_delegation(native_repo, {**retry, "launch_status": "starting"})
    append_delegation(native_repo, {**retry, "launch_status": "running"})
    append_delegation(native_repo, {
        **retry, "launch_status": "succeeded", "exit_code": 0,
        "session_id": "thread-retry",
    })
    _require_successful_launch(native_repo, "T1", stage, task)
