"""Native Codex uses the protected delegation lifecycle without the plugin."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
from pathlib import Path

import pytest


HARNESS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HARNESS / "factory" / "scripts"))

from forge_cli.codex_runtime import (  # noqa: E402
    _legacy_native_argv, native_argv, native_argv_valid, parse_native_result,
    scan_native_result, selected_coordinator,
)
from forge_cli.delegate import (  # noqa: E402
    _open_private_log, append_delegation, argv_digest, launch_companion, load_delegations,
    native_agent_type,
)
from forge_cli.stages import _require_successful_launch, task_digest  # noqa: E402
from factory_lib import sha256_of  # noqa: E402


def test_companion_log_is_created_with_private_permissions(tmp_path: Path):
    path = tmp_path / "worker.stdout.log"
    stream = _open_private_log(path)
    stream.close()

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.fixture()
def native_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    base = tmp_path / "repo"
    base.mkdir()
    subprocess.run(["git", "init", "-q", str(base)], check=True)
    schemas = base / "factory" / "schemas"
    schemas.mkdir(parents=True)
    shutil.copy(HARNESS / "factory/schemas/delegation.json", schemas)
    (base / ".factory").mkdir()
    # These focused native-launch fixtures do not model a real Codex checkout;
    # the readiness gate itself has dedicated regression coverage below.
    from forge_cli import doctor
    monkeypatch.setattr(
        doctor, "codex_hook_readiness", lambda _base: (True, "fixture-ready"),
    )
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


def test_native_role_registry_pins_lanes_and_keeps_debugger_for_hard_diagnosis():
    config = tomllib.loads(
        (HARNESS / ".codex" / "config.toml").read_text(encoding="utf-8"))
    explore = tomllib.loads(
        (HARNESS / ".codex" / "explore.config.toml").read_text(encoding="utf-8"))
    assert (config["agents"]["default_subagent_model"],
            config["agents"]["default_subagent_reasoning_effort"]) == (
        "gpt-6-luna", "max")
    assert (explore["model"], explore["model_reasoning_effort"]) == (
        "gpt-6-sol", "medium")

    expected = {
        "coder": ("gpt-6-luna", "max"),
        "frontend": ("gpt-6-luna", "max"),
        "tester": ("gpt-6-luna", "max"),
        "refactorer": ("gpt-6-luna", "max"),
        "worker": ("gpt-6-luna", "max"),
        "lite": ("gpt-6-luna", "max"),
        "explorer": ("gpt-6-sol", "medium"),
        "architect": ("gpt-6-sol", "high"),
        "debugger": ("gpt-6-sol", "high"),
        "planner": ("gpt-6-sol", "high"),
        "planner-high": ("gpt-6-sol", "high"),
        "docs-decomposer": ("gpt-6-sol", "high"),
        "griller": ("gpt-6-sol", "high"),
        "security": ("gpt-6-sol", "high"),
        "performance": ("gpt-6-sol", "high"),
        "functional-checker": ("gpt-6-sol", "high"),
    }
    actual = {}
    for name, row in config["agents"].items():
        if not isinstance(row, dict) or "config_file" not in row:
            continue
        profile = tomllib.loads(
            (HARNESS / ".codex" / row["config_file"]).read_text(
                encoding="utf-8"))
        actual[name] = (profile["model"], profile["model_reasoning_effort"])
    assert actual == expected
    assert all(model != "gpt-6-luna" or effort == "max"
               for model, effort in actual.values())

    assert native_agent_type(
        "fix-regression", {"title": "ordinary diagnosed regression fix"},
        write=True,
    ) == "worker"
    assert native_agent_type(
        "diagnose-hard", {"difficult_diagnosis": True}, write=True,
    ) == "debugger"
    assert native_agent_type(
        "diagnose-hard", {"diagnosis": "difficult root cause"}, write=False,
    ) == "debugger"
    assert native_agent_type(
        "api-work", {"title": "Implement the backend API"}, write=True,
    ) == "coder"


def test_codex_delegate_prepares_host_native_role_without_process_launch_or_pins(
        native_repo, monkeypatch):
    """The CLI prepares work; the Codex host owns native subagent dispatch."""
    import forge_cli.delegate as delegate

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    real_popen = delegate.subprocess.Popen

    def guarded_popen(argv, *args, **kwargs):
        if argv and Path(str(argv[0])).name.lower().startswith("codex"):
            pytest.fail("Codex native delegation launched a nested Codex CLI")
        return real_popen(argv, *args, **kwargs)

    monkeypatch.setattr(delegate.subprocess, "Popen", guarded_popen)
    monkeypatch.setattr(
        delegate.shutil, "which",
        lambda *_a, **_k: pytest.fail("Codex native delegation resolved a CLI"),
    )
    descriptor = launch_companion(
        native_repo,
        task_id="T1",
        text="# bounded task\n",
        path=native_repo / ".factory/briefs/T1.md",
        task_sha256_value="a" * 64,
        model="must-not-be-forwarded",
        effort="must-not-be-forwarded",
        write=True,
        write_scope=["src/"],
        background=True,
        story="STORY-1",
        stage_started_at="stage-1",
    )

    assert descriptor["action"] == "spawn_agent"
    assert descriptor["agent_type"] != "default"
    assert descriptor["write_scope"] == ["src/"]
    assert descriptor["background"] is True
    assert "not alone" in descriptor["message"]
    assert descriptor["followup_action"] == "followup_task"
    assert descriptor["target"] == descriptor["task_name"]
    assert "spawn_agent" in descriptor["dispatch_guidance"]
    assert "followup_task" in descriptor["dispatch_guidance"]
    assert not ({"model", "thinking", "reasoning", "reasoning_effort"} & descriptor.keys())

    prepared = load_delegations(native_repo)[-1]
    assert prepared["transport"] == "host-native"
    assert prepared["launch_status"] == "prepared"
    assert prepared["task"] == "T1"
    assert prepared["story"] == "STORY-1"
    assert prepared["stage_started_at"] == "stage-1"
    assert prepared["brief_sha256"] == hashlib.sha256(
        (native_repo / ".factory/briefs/T1.md").read_bytes()
    ).hexdigest()
    assert prepared["task_sha256"] == "a" * 64
    assert prepared["write_scope"] == ["src/"]
    assert not ({"pid", "pgid", "pid_started", "process_token", "session_id"} & prepared.keys())


def test_native_write_refuses_before_brief_or_preparation_when_hooks_unready(
        native_repo, monkeypatch, capsys):
    import forge_cli.doctor as doctor
    import forge_cli.delegate as delegate

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    monkeypatch.setattr(
        doctor, "codex_hook_readiness", lambda _base: (False, "fixture hook failure"),
    )
    with pytest.raises(SystemExit):
        delegate.launch_companion(
            native_repo,
            task_id="T1",
            text="# bounded task\n",
            path=native_repo / ".factory" / "briefs/T1.md",
            task_sha256_value="a" * 64,
            model="ignored",
            effort="ignored",
            write=True,
            write_scope=["src/"],
        )

    assert "hook readiness" in capsys.readouterr().out
    assert not (native_repo / ".factory" / "briefs" / "T1.md").exists()
    assert load_delegations(native_repo) == []
    assert not (native_repo / ".git" / "delegations" / "locks").exists()


def test_native_read_only_and_print_only_skip_hook_readiness(
        native_repo, monkeypatch):
    import forge_cli.doctor as doctor
    import forge_cli.delegate as delegate

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    monkeypatch.setattr(
        doctor, "codex_hook_readiness", lambda _base: (False, "fixture hook failure"),
    )
    readonly = delegate.launch_companion(
        native_repo,
        task_id="grill-plan",
        text="# read-only\n",
        path=native_repo / ".factory" / "diagnostic-briefs/grill-plan.md",
        task_sha256_value="b" * 64,
        model="ignored",
        effort="ignored",
        write=False,
    )
    preview = delegate.launch_companion(
        native_repo,
        task_id="T1",
        text="# preview\n",
        path=native_repo / ".factory" / "diagnostic-briefs/T1.md",
        task_sha256_value="c" * 64,
        model="ignored",
        effort="ignored",
        write=True,
        write_scope=["src/"],
        print_only=True,
    )
    assert readonly["write"] is False
    assert preview["write"] is True
    rows = load_delegations(native_repo)
    assert len(rows) == 1 and rows[0]["write"] is False


def test_native_context_descriptor_delivers_validated_source_metadata(
        native_repo, tmp_path, monkeypatch, capsys):
    import forge_cli.delegate as delegate

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    source = tmp_path / "private-context.md"
    secret = "untrusted supplemental detail"
    source.write_text(secret, encoding="utf-8")
    text, metadata, snapshot, identity = delegate.secure_context_snapshot(
        source, base=native_repo,
    )

    descriptor = launch_companion(
        native_repo, task_id="grill-plan", text="# primary\n",
        path=native_repo / ".factory/grill-brief-plan.md",
        task_sha256_value="b" * 64, model="ignored", effort="ignored",
        write=False, context_text=text, context_metadata=metadata,
        context_snapshot=snapshot, context_snapshot_identity=identity,
        context_source_path=str(source),
    )

    expected = {
        "source_path": str(source.absolute()),
        "bytes": len(secret.encode("utf-8")),
        "sha256": hashlib.sha256(secret.encode("utf-8")).hexdigest(),
        "snapshot_id": metadata["snapshot_id"],
    }
    assert descriptor["context_file"] == expected
    assert load_delegations(native_repo)[-1]["context_file"] == expected
    assert source.read_text(encoding="utf-8") == secret
    assert not snapshot.parent.exists()
    assert secret not in capsys.readouterr().out


def test_native_argv_binds_policy_without_resume_dispatch(tmp_path):
    argv = native_argv("/bin/codex", tmp_path, "model", "high", False)
    entry = {
        "executable_path": "/bin/codex", "argv": argv,
        "model": "model", "effort": "high", "write": False,
    }
    assert native_argv_valid(entry, tmp_path, [])
    assert argv[-1] == "-"
    assert argv[argv.index("--enable") + 1] == "hooks"
    assert argv[argv.index("--sandbox") + 1] == "danger-full-access"
    assert 'approval_policy="never"' in argv
    assert "--add-dir" not in argv
    with pytest.raises(TypeError):
        native_argv(
            "/bin/codex", tmp_path, "model", "high", False,
            resume_session="thread-1",
        )
    retired = list(argv)
    retired[retired.index("danger-full-access")] = "read-only"
    assert native_argv_valid(
        {**entry, "argv": retired, "launch_status": "succeeded"},
        tmp_path,
        [],
    )
    assert not native_argv_valid({**entry, "argv": retired}, tmp_path, [])
    historical = {
        **entry,
        "argv": [*retired[:-1], "resume", "thread-1", "-"],
        "resume_session": "thread-1",
        "launch_status": "succeeded",
    }
    assert native_argv_valid(historical, tmp_path, [])
    assert not native_argv_valid(
        {**historical, "launch_status": "running"}, tmp_path, [])
    assert not native_argv_valid(
        {**historical, "argv": [*argv[:-1], "resume", "thread-1", "-"]},
        tmp_path,
        [],
    )


def test_native_write_argv_uses_full_access_and_validates_exact_retired_scope(
        tmp_path):
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
    retired_grants = [
        ".codex/agents/new.toml",
        ".codex/config.toml",
        ".codex/hooks.json",
    ]
    assert argv[argv.index("--sandbox") + 1] == "danger-full-access"
    assert "--add-dir" not in argv
    assert argv[-1] == "-"
    assert native_argv_valid(entry, tmp_path, scope)
    assert native_argv_valid(entry, tmp_path, [])

    retired = list(argv)
    retired[retired.index("danger-full-access")] = "workspace-write"
    retired[-1:-1] = [
        token
        for path in retired_grants
        for token in ("--add-dir", path)
    ]
    for launch_status in ("failed", "succeeded"):
        assert native_argv_valid(
            {**entry, "argv": retired, "launch_status": launch_status},
            tmp_path,
            scope,
        )
        unscoped = _legacy_native_argv(
            "/bin/codex", tmp_path, "model", "high", True, [],
        )
        unscoped[-1:] = ["resume", "historical-session", "-"]
        assert native_argv_valid(
            {**entry, "argv": unscoped, "launch_status": launch_status,
             "resume_session": "historical-session"},
            tmp_path,
            scope,
        )
    assert not native_argv_valid(
        {**entry, "argv": unscoped, "launch_status": "running",
         "resume_session": "historical-session"},
        tmp_path,
        scope,
    )
    for launch_status in (None, "starting", "running"):
        candidate = {**entry, "argv": retired}
        if launch_status is not None:
            candidate["launch_status"] = launch_status
        assert not native_argv_valid(candidate, tmp_path, scope)
    malformed = [
        [*retired[:-1], "--add-dir", ".codex/extra.toml", "-"],
        [*retired[:retired.index("--add-dir")],
         "--add-dir", retired_grants[1],
         "--add-dir", retired_grants[0],
         *retired[retired.index("--add-dir") + 4:]],
        [*retired[:-1], "unexpected", "-"],
    ]
    for historical_argv in malformed:
        assert not native_argv_valid(
            {**entry, "argv": historical_argv, "launch_status": "succeeded"},
            tmp_path,
            scope,
        )
    historical = {
        **entry,
        "argv": [*retired[:-1], "resume", "thread-1", "-"],
        "resume_session": "thread-1",
        "launch_status": "succeeded",
    }
    assert native_argv_valid(historical, tmp_path, scope)
    assert not native_argv_valid(
        {**historical, "launch_status": "running"}, tmp_path, scope)
    assert not native_argv_valid(
        {**historical, "argv": [*historical["argv"][:-1], "extra", "-"]},
        tmp_path,
        scope,
    )










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
        "import json, os, stat, sys\n"
        "regular = stat.S_ISREG(os.fstat(0).st_mode)\n"
        "prompt = sys.stdin.buffer.read().decode('utf-8')\n"
        "with open(os.environ['FAKE_COMPANION_CAPTURE'], 'w') as stream:\n"
        "    json.dump({'argv': sys.argv[1:], 'prompt': prompt,\n"
        "               'regular': regular}, stream)\n"
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
    # A pipe filled after spawn races Node's non-blocking stdin read (EAGAIN).
    assert captured["regular"] is True
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
        native_repo, tmp_path, monkeypatch, capsys):
    import forge_cli.delegate as delegate

    opaque = "a" * 32
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    directory = tmp_path / f"forge-context-{opaque}"
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
