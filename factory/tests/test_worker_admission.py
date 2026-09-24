"""Native edit-hook coverage and protected worker admission."""
from __future__ import annotations

import hashlib
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import psutil
import pytest

from test_gates import HARNESS, git, repo  # noqa: F401

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from factory_lib import task_digest  # noqa: E402
from forge_cli.codex_runtime import native_argv  # noqa: E402


TASK = {
    "id": "T1",
    "title": "hook admission",
    "write_scope": ["src/"],
    "required_tests": [],
    "verify_commands": [],
    "acceptance_criteria": ["A registered native worker can edit its scope."],
}


def _control(repo: Path) -> Path:
    path = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "forge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _hook(repo: Path, payload: dict, env: dict[str, str] | None = None) -> str:
    child_env = {key: value for key, value in os.environ.items()
                 if key not in {"FORGE_PROCESS_TOKEN", "FORGE_LAUNCH_ID"}}
    child_env["FORGE_COORDINATOR"] = "claude"
    child_env.update(env or {})
    proc = subprocess.run(
        [sys.executable, str(repo / "factory/scripts/pre_tool_use.py")],
        cwd=repo,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=child_env,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout


def _patch(*controls: str) -> dict:
    return {
        "tool_name": "apply_patch",
        "permission_mode": "default",
        "tool_input": {
            "command": "\n".join(("*** Begin Patch", *controls, "*** End Patch")),
        },
    }


def _seed_contract(repo: Path, task: dict = TASK) -> tuple[Path, str]:
    (repo / ".factory/harness-source.json").write_text("{}\n", encoding="utf-8")
    brief = repo / ".factory/briefs/T1.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("# T1 protected brief\n", encoding="utf-8")
    control = _control(repo)
    digest = task_digest(task)
    (control / "run.json").write_text(
        json.dumps({"issue_key": "STORY-1", "story": "STORY-1"}),
        encoding="utf-8",
    )
    (control / "decomposition.json").write_text(
        json.dumps({"tasks": [task]}), encoding="utf-8",
    )
    (control / "stages.json").write_text(json.dumps({
        "issue": "STORY-1",
        "stages": [{
            "id": "T1", "status": "active", "started_at": "stage-1",
            "task_sha256": digest,
        }],
    }), encoding="utf-8")
    return brief, digest


def _record_native_preparation(
        repo: Path, brief: Path, digest: str, scope: list[str]) -> None:
    argv_digest = hashlib.sha256(
        json.dumps([], separators=(",", ":")).encode()
    ).hexdigest()
    (_control(repo) / "delegations.jsonl").write_text(
        json.dumps({
            "generated_by": "orchestrator",
            "at": "2026-09-18T00:00:00Z",
            "transport": "host-native",
            "task": "T1",
            "stage_started_at": "stage-1",
            "launch_status": "prepared",
            "write": True,
            "task_sha256": digest,
            "write_scope": scope,
            "model": "",
            "effort": "",
            "argv": [],
            "argv_sha256": argv_digest,
            "brief_path": brief.relative_to(repo).as_posix(),
            "brief_sha256": hashlib.sha256(brief.read_bytes()).hexdigest(),
        }) + "\n",
        encoding="utf-8",
    )


def _worker_script(tmp_path: Path) -> Path:
    script = tmp_path / "hook_worker.py"
    script.write_text(
        "import json, os, subprocess, sys\n"
        "lock, hook, repo = sys.argv[1:4]\n"
        "sys.path.insert(0, os.path.join(repo, 'factory', 'scripts'))\n"
        "from forge_cli.delegate import _lock_file\n"
        "with open(lock, 'a+', encoding='utf-8') as handle:\n"
        " handle.seek(0); handle.truncate()\n"
        " json.dump({'kind':'delegation','launch_id':os.environ['FORGE_LAUNCH_ID'],"
        "'owner_pid':os.getpid()}, handle); handle.flush()\n"
        " _lock_file(handle)\n"
        " print('READY', flush=True)\n"
        " payload = sys.stdin.readline()\n"
        " env = dict(os.environ)\n"
        " if len(sys.argv) > 4: env.pop('FORGE_LAUNCH_ID', None)\n"
        " result = subprocess.run([sys.executable, hook], cwd=repo, input=payload,"
        " capture_output=True, text=True, env=env)\n"
        " print(result.stdout, end='', flush=True)\n",
        encoding="utf-8",
    )
    return script


def _start_worker(repo: Path, tmp_path: Path, *, launch_id: str = "launch-test",
                  task_id: str = "T1", without_launch_id: bool = False,
                  hook_name: str = "pre_tool_use.py"):
    control = _control(repo)
    lock = control / f"locks/task/{task_id}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    token = f"delegation-{launch_id}"
    env = {
        **os.environ,
        "FORGE_COORDINATOR": "claude",
        "FORGE_PROCESS_TOKEN": token,
        "FORGE_LAUNCH_ID": launch_id,
    }
    argv = [sys.executable, str(_worker_script(tmp_path)), str(lock),
            str(repo / "factory/scripts" / hook_name), str(repo)]
    if without_launch_id:
        argv.append("legacy")
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    assert proc.stdout is not None and proc.stdout.readline().strip() == "READY"
    return proc, token, launch_id


def _record_launch(repo: Path, proc: subprocess.Popen[str], token: str,
                   launch_id: str, brief: Path, digest: str, *, running=True,
                   task_id: str = "T1", mode: str = "",
                   transport: str = "native",
                   write_scope: list[str] | None = None) -> None:
    executable = str(Path(sys.executable).resolve())
    argv = (native_argv(executable, repo, "gpt-test", "medium", True)
            if transport == "native"
            else ["node", "/x/codex-companion.mjs", "task", "--write"])
    base = {
        "generated_by": "orchestrator",
        "at": "2026-09-07T00:00:00Z",
        "launch_id": launch_id,
        "task": task_id,
        "brief_sha256": hashlib.sha256(brief.read_bytes()).hexdigest(),
        "task_sha256": digest,
        "write_scope": list(write_scope or TASK["write_scope"]),
        "write": True,
        "model": "gpt-test",
        "effort": "medium",
        "companion_path": executable,
        "argv": argv,
        "argv_sha256": hashlib.sha256(
            json.dumps(argv, separators=(",", ":")).encode()
        ).hexdigest(),
        "launch_status": "starting",
        "process_token": token,
    }
    if transport == "native":
        base.update({
            "transport": "native",
            "executable_path": executable,
            "brief_path": brief.relative_to(repo).as_posix(),
        })
    if mode:
        base["mode"] = mode
    else:
        base.update({"story": "STORY-1", "stage_started_at": "stage-1"})
    rows = [base]
    if running:
        rows.append({
            **base,
            "launch_status": "running",
            "pid": proc.pid,
            "pgid": proc.pid,
            "pid_started": str(psutil.Process(proc.pid).create_time()),
        })
    (_control(repo) / "delegations.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8",
    )


def _invoke_worker(proc: subprocess.Popen[str], payload: dict) -> str:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    proc.stdin.close()
    output = proc.stdout.read()
    proc.wait(timeout=10)
    assert proc.returncode == 0, (proc.stderr.read() if proc.stderr else "")
    return output


def test_codex_native_host_needs_active_stage_but_no_process_identity(repo):
    """Stage and scope authorize native work; PID/session/token/lock do not."""
    denied = _hook(repo, _patch(
        "*** Add File: src/native.py", "+native",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" in denied.lower() and "active task stage" in denied.lower(), denied

    brief, digest = _seed_contract(repo)
    _record_native_preparation(repo, brief, digest, ["src/"])
    admitted = _hook(repo, _patch(
        "*** Add File: src/native.py", "+native",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" not in admitted.lower(), admitted

    from forge_cli.stages import scope_amendments_path
    scope_amendments_path(repo).write_text(json.dumps({
        "tasks": {"T1": {"added_paths": ["amended/"]}},
    }), encoding="utf-8")
    narrowed = _hook(repo, _patch(
        "*** Add File: amended/not-yet-prepared.py", "+refused",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" in narrowed.lower() and "scope" in narrowed.lower(), narrowed
    _record_native_preparation(repo, brief, digest, ["src/", "amended/"])
    amended = _hook(repo, _patch(
        "*** Add File: amended/native.py", "+native",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" not in amended.lower(), amended

    outside = _hook(repo, _patch(
        "*** Add File: other/native.py", "+native",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" in outside.lower() and "scope" in outside.lower(), outside


def test_codex_native_narrowed_scope_descends_from_bare_baseline_tree(repo):
    owned = repo / "src/owned.py"
    owned.parent.mkdir(parents=True)
    owned.write_text("before\n", encoding="utf-8")
    git(repo, "add", "src/owned.py")
    git(repo, "commit", "-qm", "scope baseline")
    task = {**TASK, "write_scope": ["src"]}
    brief, digest = _seed_contract(repo, task)
    git(repo, "update-ref", "refs/forge/stage/T1", "HEAD")
    _record_native_preparation(repo, brief, digest, ["src/owned.py"])

    admitted = _hook(repo, _patch(
        "*** Update File: src/owned.py", "@@", "-before", "+after",
    ), {"FORGE_COORDINATOR": "codex"})

    assert "deny" not in admitted.lower(), admitted
    outside = _hook(repo, _patch(
        "*** Add File: src/other.py", "+outside",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" in outside.lower() and "scope" in outside.lower(), outside


def test_native_bash_recursive_copy_cannot_escape_exact_scope(repo):
    task = {**TASK, "write_scope": ["src/approved"]}
    brief, digest = _seed_contract(repo, task)
    _record_native_preparation(repo, brief, digest, ["src/approved"])
    assert not (repo / ".factory" / "quickfix.json").exists()
    generated = repo / "generated"
    generated.write_text("generated\n", encoding="utf-8")
    generated_tree = repo / "generated-tree"
    generated_tree.mkdir()
    (generated_tree / "file.txt").write_text("generated\n", encoding="utf-8")

    admitted = _hook(repo, {
        "tool_name": "Bash",
        "permission_mode": "default",
        "tool_input": {"command": "cp generated src/approved"},
    }, {"FORGE_COORDINATOR": "codex"})
    assert "deny" not in admitted.lower(), admitted

    output = _hook(repo, {
        "tool_name": "Bash",
        "permission_mode": "default",
        "tool_input": {"command": "cp -R generated-tree src/approved"},
    }, {"FORGE_COORDINATOR": "codex"})

    assert "deny" in output.lower() and "only allows plain file writes" in output.lower(), output


def test_native_bash_write_through_in_scope_symlink_is_scoped_by_its_target(repo):
    task = {**TASK, "write_scope": ["src/alias"]}
    brief, digest = _seed_contract(repo, task)
    target = repo / "src" / "other.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("outside\n", encoding="utf-8")
    (repo / "src" / "alias").symlink_to(Path("other.py"))
    _record_native_preparation(repo, brief, digest, ["src/alias"])

    output = _hook(repo, {
        "tool_name": "Bash",
        "permission_mode": "default",
        "tool_input": {"command": "echo x > src/alias"},
    }, {"FORGE_COORDINATOR": "codex"})

    assert (
        "deny" in output.lower()
        and "outside the active task scope" in output.lower()
    ), output
    assert target.read_text(encoding="utf-8") == "outside\n"


def test_native_bash_delete_scopes_product_symlink_by_lexical_path(repo):
    task = {**TASK, "write_scope": ["src/approved"]}
    brief, digest = _seed_contract(repo, task)
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "x").write_text("outside\n", encoding="utf-8")
    link = repo / "src" / "link"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(Path("../docs/x"))
    _record_native_preparation(repo, brief, digest, ["src/approved"])

    output = _hook(repo, {
        "tool_name": "Bash",
        "permission_mode": "default",
        "tool_input": {"command": "rm src/link"},
    }, {"FORGE_COORDINATOR": "codex"})

    assert (
        "deny" in output.lower()
        and "outside the active task scope" in output.lower()
    ), output
    assert link.is_symlink() and link.readlink() == Path("../docs/x")

    parent_link = repo / "src" / "parent"
    parent_link.symlink_to(Path("../docs"))
    parent_output = _hook(repo, {
        "tool_name": "Bash",
        "permission_mode": "default",
        "tool_input": {"command": "rm src/parent/x"},
    }, {"FORGE_COORDINATOR": "codex"})
    assert (
        "deny" in parent_output.lower()
        and "symlinked" in parent_output.lower()
    ), parent_output

    alias = repo.parent / "app-alias"
    alias.symlink_to(repo, target_is_directory=True)
    alias_output = _hook(repo, {
        "tool_name": "Bash",
        "permission_mode": "default",
        "tool_input": {"command": f"rm {alias / 'src' / 'link'}"},
    }, {"FORGE_COORDINATOR": "codex"})
    assert "deny" in alias_output.lower(), alias_output
    assert link.is_symlink()


@pytest.mark.parametrize(("controls", "write_scope"), [
    (("*** Delete File: outside-link.py",), ["src/old.py"]),
    (("*** Update File: outside-link.py", "*** Move to: src/moved.py",
      "@@", "-old", "+new"), ["src/old.py", "src/moved.py"]),
])
def test_native_patch_delete_or_move_scopes_symlink_by_its_lexical_path(
        repo, controls, write_scope):
    exact_task = {**TASK, "write_scope": write_scope}
    brief, digest = _seed_contract(repo, exact_task)
    target = repo / "src" / "old.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old\n", encoding="utf-8")
    link = repo / "outside-link.py"
    link.symlink_to(Path("src") / "old.py")
    _record_native_preparation(repo, brief, digest, write_scope)

    output = _hook(
        repo, _patch(*controls),
        {"FORGE_COORDINATOR": "codex"},
    )

    assert "deny" in output and "outside the active task scope" in output
    assert link.is_symlink() and link.readlink() == Path("src") / "old.py"


def test_inherited_degraded_window_uses_native_stage_admission(repo):
    """A stale Claude outage window cannot become a native five-file grant."""
    brief, digest = _seed_contract(repo)
    (repo / ".factory" / "quickfix.json").write_text(json.dumps({
        "id": "Q-degraded-inherited",
        "profile": "degraded",
        "kind": "degraded",
        "reason": "historical Claude outage",
        "max_files": 5,
        "files": [],
        "harness_source": True,
    }), encoding="utf-8")

    denied = _hook(repo, _patch(
        "*** Add File: src/native.py", "+native",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" in denied.lower() and "preparation" in denied.lower(), denied

    _record_native_preparation(repo, brief, digest, ["src/"])
    admitted = _hook(repo, _patch(
        "*** Add File: src/native.py", "+native",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" not in admitted.lower(), admitted

    outside = _hook(repo, _patch(
        "*** Add File: other/native.py", "+native",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" in outside.lower() and "scope" in outside.lower(), outside


def test_codex_cannot_open_degraded_window(repo, monkeypatch, capsys):
    from forge_cli import quickfix

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    with pytest.raises(SystemExit):
        quickfix.cmd_degraded_start(argparse.Namespace(
            repo=str(repo), reason="historical Claude outage",
        ))
    assert "Claude-only" in capsys.readouterr().out
    assert not (repo / ".factory" / "quickfix.json").exists()
    assert not (repo / "plans" / "quickfixes").exists()


def test_codex_native_host_denies_direct_and_nested_codex_exec(repo):
    for command in (
        "codex exec inspect",
        "bash -c 'codex exec inspect'",
    ):
        output = _hook(repo, {
            "tool_name": "Bash",
            "permission_mode": "default",
            "tool_input": {"command": command},
        }, {"FORGE_COORDINATOR": "codex"})
        assert "deny" in output.lower() and "native subagent" in output.lower(), output


def test_codex_read_only_delegate_uses_diagnostic_brief(repo, monkeypatch):
    from forge_cli import delegate

    _seed_contract(repo)
    (_control(repo) / "stages.json").write_text(
        json.dumps({"issue": "STORY-1", "stages": []}), encoding="utf-8",
    )
    canonical = repo / ".factory/briefs/T1.md"
    original = canonical.read_bytes()
    captured = {}

    def fake_launch(base, **kwargs):
        captured.update(kwargs)
        return {"action": "spawn_agent"}

    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    monkeypatch.setattr(delegate, "launch_companion", fake_launch)
    monkeypatch.setattr(delegate, "append_event", lambda *_a, **_k: None)
    delegate.cmd_delegate(argparse.Namespace(
        repo=str(repo), id="T1", read_only=True, scope=[], background=False,
        context_file="", print_only=False, effort="",
    ))

    assert captured["path"] == repo / ".factory/diagnostic-briefs/T1.md"
    assert canonical.read_bytes() == original


@pytest.mark.parametrize(("exit_code", "status"), [(1, 1), (0, 2)])
def test_failed_companion_reports_correlated_codex_job_log(
        repo, tmp_path, monkeypatch, capsys, exit_code, status):
    from forge_cli import codex_status, delegate

    _seed_contract(repo)
    home = tmp_path / "home"
    companion = (home / ".claude/plugins/cache/openai-codex/codex/1.0.0"
                 / "scripts/codex-companion.mjs")
    companion.parent.mkdir(parents=True)
    companion.write_text("// fake companion\n", encoding="utf-8")
    (home / ".claude/plugins/installed_plugins.json").write_text(
        json.dumps({"plugins": {"codex@openai-codex": [{
            "installPath": str(companion.parents[1]),
        }]}}), encoding="utf-8",
    )
    node_dir = tmp_path / "bin"
    node_dir.mkdir()
    node = node_dir / "node"
    node.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['FORGE_TEST_JOB_FILE'], 'w', encoding='utf-8') as job:\n"
        " json.dump({'id': 'job-test', 'workspaceRoot': "
        "os.environ['FORGE_TEST_WORKSPACE'], 'createdAt': "
        "'2026-09-24T00:00:00Z', 'logFile': os.environ['FORGE_TEST_LOG']}, job)\n"
        f"print(json.dumps({{'status': {status}, 'jobId': 'job-test', "
        "'rawOutput': 'unfinished lead text'}))\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    node.chmod(0o755)
    log_path = tmp_path / "job.log"
    log_path.write_text("Codex error: out of credits\nTurn failed.\n",
                        encoding="utf-8")
    state_root = tmp_path / "codex-state"
    job_dir = state_root / "project" / "jobs"
    job_dir.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", f"{node_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FORGE_COORDINATOR", "claude")
    monkeypatch.setenv("FORGE_TEST_JOB_FILE", str(job_dir / "job-test.json"))
    monkeypatch.setenv("FORGE_TEST_WORKSPACE", str(repo))
    monkeypatch.setenv("FORGE_TEST_LOG", str(log_path))
    monkeypatch.setattr(codex_status, "STATE_ROOT", state_root)
    monkeypatch.setattr(delegate, "_process_table", lambda: {})
    monkeypatch.setattr(delegate, "_capture_spawn_identity", lambda _proc: "known")
    monkeypatch.setattr(
        delegate, "_wait_and_reap",
        lambda proc, *_args, **_kwargs: proc.wait() is not None,
    )
    with pytest.raises(SystemExit):
        delegate.launch_companion(
            repo, task_id="T1", text="brief", path=repo / ".factory/briefs/T1.md",
            task_sha256_value="task-digest", model="gpt-test", effort="medium",
            write=False,
        )

    output = capsys.readouterr().out
    refusal = next(line for line in output.splitlines()
                   if line.startswith("ERROR:"))
    assert refusal.startswith("ERROR: Codex error: out of credits")
    assert f"Codex companion job log: {log_path}" in output
    assert "unfinished lead text" not in output


def test_known_native_launch_reads_delegation_ledger_once(tmp_path, monkeypatch):
    import factory_lib
    import forge_cli.codex_runtime as codex_runtime
    import forge_cli.worker_admission as admission
    from forge_cli import stages

    real_descends = admission._current_process_descends_from

    launch_id = "launch-native"
    token = f"delegation-{launch_id}"
    argv = ["/usr/bin/codex", "exec", "-"]
    common = {
        "launch_id": launch_id,
        "task": "T1",
        "brief_sha256": "brief-digest",
        "task_sha256": "task-digest",
        "write_scope": ["src/"],
        "write": True,
        "model": "model",
        "effort": "medium",
        "argv": argv,
        "argv_sha256": "argv-digest",
        "process_token": token,
        "transport": "native",
        "executable_path": "/usr/bin/codex",
        "brief_path": ".factory/briefs/T1.md",
        "output_path": "/tmp/native.jsonl",
        "stderr_path": "/tmp/native.stderr.log",
        "stage_started_at": "stage-1",
    }
    rows = [
        {**common, "launch_status": "starting"},
        {
            **common,
            "launch_status": "running",
            "pid": 123,
            "pid_started": "identity",
        },
    ]
    calls = []
    monkeypatch.setenv("FORGE_PROCESS_TOKEN", token)
    monkeypatch.setenv("FORGE_LAUNCH_ID", launch_id)
    monkeypatch.setattr(
        admission, "load_delegations",
        lambda base: calls.append(base) or rows,
    )
    monkeypatch.setattr(admission, "worker_admission_revoked", lambda *_a: False)
    monkeypatch.setattr(admission, "argv_digest", lambda _argv: "argv-digest")
    monkeypatch.setattr(admission, "_process_start_identity", lambda _pid: "identity")
    monkeypatch.setattr(admission, "_current_process_descends_from", lambda *_a: True)
    lock = tmp_path / "lock"
    lock.write_text(json.dumps({
        "kind": "delegation", "launch_id": launch_id, "owner_pid": 123,
    }), encoding="utf-8")
    monkeypatch.setattr(admission, "delegation_lock_path", lambda *_a, **_k: lock)
    monkeypatch.setattr(admission, "_lock_is_held", lambda _path: True)
    brief = tmp_path / ".factory" / "briefs" / "T1.md"
    brief.parent.mkdir(parents=True)
    brief.write_text("brief", encoding="utf-8")
    monkeypatch.setattr(admission, "brief_path", lambda *_a: brief)
    monkeypatch.setattr(admission, "sha256_of", lambda _path: "brief-digest")
    decomposition = tmp_path / "decomposition.json"
    decomposition.write_text(json.dumps({"tasks": [TASK]}), encoding="utf-8")
    run_path = tmp_path / "run.json"
    run_path.write_text(json.dumps({"story": "STORY-1"}), encoding="utf-8")
    monkeypatch.setattr(factory_lib, "protected_decomposition_state_path",
                        lambda _base: decomposition)
    monkeypatch.setattr(admission, "load_stages", lambda _base: {"stages": [{
        "id": "T1", "status": "active", "started_at": "stage-1",
    }]})
    monkeypatch.setattr(admission, "run_state_path", lambda _base: run_path)
    monkeypatch.setattr(admission, "task_digest", lambda _task: "task-digest")
    monkeypatch.setattr(stages, "stage_baseline", lambda *_a: "baseline")
    monkeypatch.setattr(stages, "effective_scope", lambda _base, _task, scope: list(scope))
    classifications = []
    monkeypatch.setattr(
        admission, "classify_scope_entries",
        lambda *args: classifications.append(args) or ["src/"],
    )
    native_validations = []
    monkeypatch.setattr(
        codex_runtime,
        "native_argv_valid",
        lambda *args: native_validations.append(args) or True,
    )

    grant, reason = admission.live_worker_admission(tmp_path)

    assert grant == {"kind": "stage", "scope": ["src/"]}
    assert reason == ""
    assert calls == [tmp_path]
    assert classifications == [(tmp_path, ["src/"], "baseline")]
    assert native_validations == [(rows[-1], tmp_path, ["src/"])]

    original_rows = [dict(row) for row in rows]
    for case in ("missing", "malformed", "mismatched", "changed"):
        rows[:] = [dict(row) for row in original_rows]
        for row in rows:
            if case == "missing":
                row.pop("write_scope")
            elif case == "malformed":
                row["write_scope"] = [""]
            elif case == "mismatched":
                row["write_scope"] = ["other/"]
        if case == "changed":
            rows[-1]["write_scope"] = ["other/"]
        grant, reason = admission.live_worker_admission(tmp_path)
        assert grant is None and reason and len(native_validations) == 1, case
    rows[:] = original_rows

    def fail_process_inspection(_pid):
        raise SystemError("macOS sysctl denied")

    monkeypatch.setattr(psutil, "Process", fail_process_inspection)
    monkeypatch.setattr(admission, "_current_process_descends_from", real_descends)
    grant, reason = admission.live_worker_admission(tmp_path)
    assert grant is None and "outside the registered worker process tree" in reason


def test_context_file_launch_uses_one_handle_snapshot_and_metadata_only_evidence(
        repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from forge_cli import delegate

    _seed_contract(repo)
    (_control(repo) / "stages.json").write_text(
        json.dumps({"issue": "STORY-1", "stages": []}), encoding="utf-8")
    secure = tmp_path / "private"
    secure.mkdir(mode=0o700)
    secure.chmod(0o700)
    source = secure / "context.md"
    source.write_text("one stable snapshot", encoding="utf-8")
    source.chmod(0o600)
    captured = {}

    def fake_launch(base, **kwargs):
        captured.update(kwargs)
        assert kwargs["context_text"] == "one stable snapshot"
        assert kwargs["context_snapshot_identity"]
        return {"launch_status": "succeeded"}

    monkeypatch.setattr(delegate, "launch_companion", fake_launch)
    delegate.cmd_delegate(argparse.Namespace(
        repo=str(repo), id="T1", read_only=True, scope=[], background=False,
        context_file=str(source), print_only=False,
    ))

    assert captured["context_text"] == "one stable snapshot"
    assert captured["context_metadata"]["supplied"] is True
    assert captured["context_metadata"]["bytes"] == len(b"one stable snapshot")
    assert set(captured["context_metadata"]) == {"supplied", "bytes", "snapshot_id"}
    assert not captured["context_snapshot"].parent.exists()

def test_native_worker_patch_add_update_delete_and_move_is_admitted(repo, tmp_path):
    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(repo, proc, token, launch_id, brief, digest)
    output = _invoke_worker(proc, _patch(
        "*** Add File: src/new.py", "+new",
        "*** Update File: src/old.py", "*** Move to: src/moved.py", "@@", "-old", "+new",
        "*** End of File",
        "*** Delete File: src/gone.py",
    ))
    assert "deny" not in output, output


@pytest.mark.parametrize("controls", [
    ("*** Add File: src/link.py", "+new"),
    ("*** Update File: src/link.py", "@@", "-old", "+new"),
    ("*** Update File: src/old.py", "*** Move to: src/link.py",
     "@@", "-old", "+new"),
])
def test_worker_add_or_update_symlink_leaf_is_denied(
        repo, tmp_path, controls):
    brief, digest = _seed_contract(repo)
    target = repo / "src" / "old.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old\n", encoding="utf-8")
    link = repo / "src" / "link.py"
    link.symlink_to("old.py")
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(repo, proc, token, launch_id, brief, digest)

    output = _invoke_worker(proc, _patch(*controls))

    assert "deny" in output and "cannot prove its write paths" in output


def test_companion_worker_reads_state_without_protected_write_authority(
        repo, tmp_path):
    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(repo, tmp_path, launch_id="launch-read")
    _record_launch(repo, proc, token, launch_id, brief, digest)
    read_output = _invoke_worker(proc, {
        "tool_name": "Bash",
        "permission_mode": "default",
        "tool_input": {"command": "./forge next"},
    })
    # This asserts hook permission only; live C8 proof records command execution.
    assert json.loads(read_output) == {}

    protected_before = brief.read_bytes()
    proc, token, launch_id = _start_worker(repo, tmp_path, launch_id="launch-write")
    _record_launch(repo, proc, token, launch_id, brief, digest)
    write_output = _invoke_worker(proc, _patch(
        "*** Update File: .factory/briefs/T1.md",
        "@@", "-# T1 protected brief", "+# changed protected brief",
        "*** End of File",
    ))
    assert "deny" in write_output and "never hand-written" in write_output
    assert brief.read_bytes() == protected_before



def test_stage_worker_may_change_repo_marker_only_when_scope_names_it(repo, tmp_path):
    brief, _ = _seed_contract(repo)
    marker_task = {**TASK, "write_scope": [".factory/harness-source.json"]}
    digest = task_digest(marker_task)
    control = _control(repo)
    (control / "decomposition.json").write_text(
        json.dumps({"tasks": [marker_task]}), encoding="utf-8",
    )
    (control / "stages.json").write_text(json.dumps({
        "issue": "STORY-1",
        "stages": [{
            "id": "T1", "status": "active", "started_at": "stage-1",
            "task_sha256": digest,
        }],
    }), encoding="utf-8")
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(repo, proc, token, launch_id, brief, digest,
                   write_scope=marker_task["write_scope"])
    output = _invoke_worker(
        proc, _patch("*** Delete File: .factory/harness-source.json"),
    )
    assert "deny" not in output, output


def test_current_claude_companion_token_resolves_protected_worker(repo, tmp_path):
    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(
        repo, tmp_path, without_launch_id=True)
    _record_launch(
        repo, proc, token, launch_id, brief, digest, transport="companion",
    )
    output = _invoke_worker(proc, _patch("*** Add File: src/new.py", "+new"))
    assert "deny" not in output, output


def test_client_coordinator_apply_patch_still_locks_product(repo):
    output = _hook(repo, _patch(
        "*** Update File: src/old.py", "@@", "-old", "+new", "*** End of File",
    ))
    assert "deny" in output and "forge delegate" in output


@pytest.mark.parametrize("status", ["coordinator", "starting", "forged"])
def test_unregistered_callers_cannot_write_product(repo, tmp_path, status):
    brief, digest = _seed_contract(repo)
    if status == "coordinator":
        output = _hook(repo, _patch("*** Add File: src/new.py", "+new"))
    elif status == "forged":
        output = _hook(
            repo, _patch("*** Add File: src/new.py", "+new"),
            {"FORGE_PROCESS_TOKEN": "forged", "FORGE_LAUNCH_ID": "launch-forged"},
        )
    else:
        proc, token, launch_id = _start_worker(repo, tmp_path)
        _record_launch(repo, proc, token, launch_id, brief, digest, running=False)
        output = _invoke_worker(proc, _patch("*** Add File: src/new.py", "+new"))
    assert "deny" in output


def test_terminated_worker_and_reused_environment_are_denied(repo, tmp_path):
    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(repo, proc, token, launch_id, brief, digest)
    proc.terminate()
    proc.wait(timeout=10)
    output = _hook(
        repo, _patch("*** Add File: src/new.py", "+new"),
        {"FORGE_PROCESS_TOKEN": token, "FORGE_LAUNCH_ID": launch_id},
    )
    assert "deny" in output and "no longer live" in output


@pytest.mark.parametrize("marker_kind", ["malformed", "directory"])
def test_any_protected_revocation_marker_denies_admission(
        repo, tmp_path, monkeypatch, marker_kind):
    import forge_cli.worker_admission as admission

    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(repo, proc, token, launch_id, brief, digest)
    monkeypatch.setenv("FORGE_PROCESS_TOKEN", token)
    monkeypatch.setenv("FORGE_LAUNCH_ID", launch_id)
    monkeypatch.setattr(admission, "_current_process_descends_from", lambda *_a: True)
    marker = admission._revocation_path(repo, launch_id)
    marker.parent.mkdir(parents=True, exist_ok=True)
    if marker_kind == "directory":
        marker.mkdir()
    else:
        marker.write_text("not JSON", encoding="utf-8")
    try:
        grant, reason = admission.live_worker_admission(repo)
        assert grant is None and "revoked" in reason
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_contract_mutation_and_out_of_scope_move_are_denied(repo, tmp_path):
    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(repo, proc, token, launch_id, brief, digest)
    changed = {**TASK, "write_scope": ["other/"]}
    (_control(repo) / "decomposition.json").write_text(
        json.dumps({"tasks": [changed]}), encoding="utf-8",
    )
    output = _invoke_worker(proc, _patch(
        "*** Update File: src/old.py", "*** Move to: outside.py", "@@", "-old", "+new",
    ))
    assert "deny" in output and "contract changed" in output


def test_scope_classification_is_bound_to_the_immutable_baseline(repo):
    from factory_lib import classify_scope_entries
    from forge_cli.worker_admission import path_in_scope

    (repo / "scope-tree").mkdir()
    (repo / "scope-tree/child.txt").write_text("tree\n")
    (repo / "scope-blob").write_text("blob\n")
    (repo / "scope-link").symlink_to("scope-blob")
    git(repo, "add", "scope-tree", "scope-blob", "scope-link")
    git(repo, "commit", "-qm", "scope baseline shapes")
    baseline = git(repo, "rev-parse", "HEAD").strip()

    classified = classify_scope_entries(
        repo, ["scope-tree", "scope-blob", "scope-link", "absent", "explicit/"],
        baseline,
    )
    assert classified == [
        "scope-tree/", "scope-blob", "scope-link", "absent", "explicit/",
    ]
    assert all(path_in_scope(path, classified) for path in (
        "scope-tree", "scope-tree/new.txt", "scope-blob", "scope-link",
        "absent", "explicit/new.txt",
    ))
    assert not any(path_in_scope(path, classified) for path in (
        "scope-blob/new.txt", "scope-link/new.txt", "absent/new.txt",
    ))

    (repo / "scope-blob").unlink()
    (repo / "scope-blob").mkdir()
    assert not path_in_scope(
        "scope-blob/new.txt",
        classify_scope_entries(repo, ["scope-blob"], baseline),
    )


def test_midstage_task_amendment_requires_a_fresh_launch_without_rebaseline(
        repo, tmp_path):
    brief, started_digest = _seed_contract(repo)
    stage_path = _control(repo) / "stages.json"
    original_stage = stage_path.read_bytes()
    proc, token, launch_id = _start_worker(
        repo, tmp_path, launch_id="launch-before-amendment")
    _record_launch(repo, proc, token, launch_id, brief, started_digest)

    amended = {
        **TASK,
        "acceptance_criteria": ["The amended contract remains writable."],
    }
    amended_digest = task_digest(amended)
    (_control(repo) / "decomposition.json").write_text(
        json.dumps({"tasks": [amended]}), encoding="utf-8",
    )
    stale = _invoke_worker(proc, _patch("*** Add File: src/stale.py", "+stale"))
    assert "deny" in stale and "contract changed" in stale

    proc, token, launch_id = _start_worker(
        repo, tmp_path, launch_id="launch-after-amendment")
    _record_launch(repo, proc, token, launch_id, brief, amended_digest)
    current = _invoke_worker(proc, _patch("*** Add File: src/current.py", "+current"))
    assert "deny" not in current, current
    assert stage_path.read_bytes() == original_stage


@pytest.mark.parametrize(("status", "started_at"), [
    ("done", "stage-1"),
    ("active", "stage-2"),
])
def test_stage_closure_or_restart_invalidates_running_worker(
        repo, tmp_path, status, started_at):
    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(repo, proc, token, launch_id, brief, digest)
    (_control(repo) / "stages.json").write_text(json.dumps({
        "issue": "STORY-1",
        "stages": [{
            "id": "T1", "status": status, "started_at": started_at,
            "task_sha256": digest,
        }],
    }), encoding="utf-8")
    output = _invoke_worker(proc, _patch("*** Add File: src/new.py", "+new"))
    assert "deny" in output and "no longer the active stage" in output


def test_worker_move_target_must_remain_in_scope(repo, tmp_path):
    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(repo, proc, token, launch_id, brief, digest)
    output = _invoke_worker(proc, _patch(
        "*** Update File: src/old.py", "*** Move to: outside.py", "@@", "-old", "+new",
    ))
    assert "deny" in output and "outside the protected task scope" in output


@pytest.mark.parametrize(("controls", "in_scope_controls", "write_scope"), [
    (
        ("*** Delete File: outside-link.py",),
        ("*** Delete File: src/in-scope-link.py",),
        ["src/in-scope-link.py"],
    ),
    (
        ("*** Update File: outside-link.py", "*** Move to: src/moved.py",
         "@@", "-old", "+new"),
        ("*** Update File: src/in-scope-link.py", "*** Move to: src/moved.py",
         "@@", "-old", "+new"),
        ["src/in-scope-link.py", "src/moved.py"],
    ),
])
def test_worker_symlink_entry_is_denied(
        repo, tmp_path, controls, in_scope_controls, write_scope):
    exact_task = {**TASK, "write_scope": write_scope}
    brief, digest = _seed_contract(repo, exact_task)
    target = repo / "src" / "old.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old\n", encoding="utf-8")
    link = repo / "outside-link.py"
    link.symlink_to(Path("src") / "old.py")
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(
        repo, proc, token, launch_id, brief, digest, write_scope=write_scope)

    output = _invoke_worker(proc, _patch(*controls))
    assert "deny" in output and "outside the protected task scope" in output

    in_scope = repo / "src" / "in-scope-link.py"
    in_scope.symlink_to("old.py")
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(
        repo, proc, token, launch_id, brief, digest, write_scope=write_scope)
    output = _invoke_worker(proc, _patch(*in_scope_controls))
    assert "deny" not in output, output

    outside = repo / "outside"
    outside.mkdir()
    ancestor = repo / "src" / "escape"
    ancestor.symlink_to(outside, target_is_directory=True)
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(
        repo, proc, token, launch_id, brief, digest, write_scope=write_scope)
    output = _invoke_worker(proc, _patch(
        "*** Delete File: src/escape/target.py",
    ))
    assert "deny" in output and "cannot prove its write paths" in output


@pytest.mark.parametrize("terminal", ["failed", "succeeded"])
def test_terminal_launch_never_retains_write_admission(repo, tmp_path, terminal):
    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(repo, proc, token, launch_id, brief, digest)
    ledger = _control(repo) / "delegations.jsonl"
    running = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            **running, "launch_status": terminal,
            "exit_code": 0 if terminal == "succeeded" else 1,
        }) + "\n")
    output = _invoke_worker(proc, _patch("*** Add File: src/new.py", "+new"))
    assert "deny" in output and "not exclusively running" in output


def test_native_lite_fix_prepares_without_stage_and_keeps_window_budget(
        repo, monkeypatch, capsys):
    from forge_cli import doctor
    from forge_cli import fix
    from forge_cli.delegate import load_delegations

    (repo / ".factory/harness-source.json").write_text("{}\n", encoding="utf-8")
    window_id = "Q-0002-native-lite"
    (repo / ".factory/quickfix.json").write_text(json.dumps({
        "id": window_id,
        "profile": "lite",
        "reason": "bounded host-native fix",
        "started_at": "2026-09-18T00:00:00Z",
        "max_files": 5,
        "files": [],
        "harness_source": True,
        "base_sha": git(repo, "rev-parse", "HEAD"),
    }), encoding="utf-8")
    monkeypatch.setenv("FORGE_COORDINATOR", "codex")
    monkeypatch.setattr(
        doctor, "codex_hook_readiness", lambda _base: (True, "fixture-ready"),
    )

    fix.cmd_fix(argparse.Namespace(
        description="repair a bounded native issue", repo=str(repo),
    ))

    output = capsys.readouterr().out
    assert '"transport": "host-native"' in output
    assert "NEXT: dispatch" in output
    prepared = load_delegations(repo)[-1]
    assert prepared["transport"] == "host-native"
    assert prepared["launch_status"] == "prepared"
    assert prepared["mode"] == "lite"
    assert prepared["task"] == window_id
    assert prepared["write_scope"] == []
    assert not ({"pid", "session_id", "process_token"} & prepared.keys())

    for index in range(5):
        admitted = _hook(repo, _patch(
            f"*** Add File: src/lite-{index}.py", "+new",
        ), {"FORGE_COORDINATOR": "codex"})
        assert "deny" not in admitted.lower(), admitted
    refused = _hook(repo, _patch(
        "*** Add File: src/lite-over-budget.py", "+new",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" in refused.lower() and "five-file" in refused.lower(), refused

    protected = _hook(repo, _patch(
        "*** Update File: .factory/quickfix.json", "@@", "-{}", "+{}",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" in protected.lower() and "never hand-written" in protected.lower(), protected


def test_native_quickfix_window_is_recording_only(repo):
    (repo / ".factory/harness-source.json").write_text("{}\n", encoding="utf-8")
    (repo / ".factory/quickfix.json").write_text(json.dumps({
        "id": "Q-quickfix-native", "profile": "quickfix",
        "reason": "historical native window", "max_files": 5, "files": [],
        "harness_source": True,
    }), encoding="utf-8")
    refused = _hook(repo, _patch(
        "*** Add File: src/quickfix-native.py", "+refused",
    ), {"FORGE_COORDINATOR": "codex"})
    assert "deny" in refused.lower() and "recording-only" in refused.lower(), refused


def test_live_lite_worker_uses_current_window_and_file_budget(repo, tmp_path):
    (repo / ".factory/harness-source.json").write_text("{}\n", encoding="utf-8")
    window_id = "Q-0001-test"
    (repo / ".factory/quickfix.json").write_text(json.dumps({
        "id": window_id,
        "profile": "lite",
        "reason": "bounded native fix",
        "started_at": "2026-09-07T00:00:00Z",
        "max_files": 5,
        "files": [],
        "harness_source": True,
        "base_sha": git(repo, "rev-parse", "HEAD"),
    }), encoding="utf-8")
    description = "repair one bounded file"
    brief = repo / f".factory/briefs/{window_id}.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(
        f"# Lite fix — {window_id}\n\nFix: {description}\n\nWork only here.\n",
        encoding="utf-8",
    )
    digest = task_digest({
        "acceptance_criteria": [description],
        "required_tests": [],
        "verify_commands": [],
        "write_scope": [],
    })
    proc, token, launch_id = _start_worker(repo, tmp_path, task_id=window_id)
    _record_launch(
        repo, proc, token, launch_id, brief, digest,
        task_id=window_id, mode="lite",
    )
    output = _invoke_worker(proc, _patch("*** Add File: src/lite.py", "+new"))
    assert "deny" not in output, output
    claimed = json.loads((repo / ".factory/quickfix.json").read_text())["files"]
    assert claimed == ["src/lite.py"]


def test_worker_cannot_patch_recorded_factory_state(repo, tmp_path):
    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(repo, tmp_path)
    _record_launch(repo, proc, token, launch_id, brief, digest)
    output = _invoke_worker(proc, _patch(
        "*** Update File: .factory/run.json", "@@", "-{}", "+{}",
    ))
    assert "deny" in output and "never hand-written" in output


@pytest.mark.parametrize("header", [
    "*** Mystery File: src/x.py",
    "*** Add File: ../outside.py",
])
def test_malformed_or_outside_apply_patch_fails_closed(repo, header):
    _seed_contract(repo)
    output = _hook(repo, {
        "tool_name": "apply_patch",
        "tool_input": {"command": f"*** Begin Patch\n{header}\n*** End Patch"},
    })
    assert "deny" in output and "malformed" in output


@pytest.mark.parametrize("transport", ["native", "companion"])
def test_lean_stop_allows_authenticated_registered_worker_handoff(
        repo, tmp_path, transport):
    brief, digest = _seed_contract(repo)
    proc, token, launch_id = _start_worker(
        repo, tmp_path, without_launch_id=transport == "companion",
        hook_name="stop_continue.py",
    )
    _record_launch(repo, proc, token, launch_id, brief, digest,
                   transport=transport)
    output = _invoke_worker(proc, {"handoff": "blocked or complete"})
    assert json.loads(output) == {"continue": True}


def _record_readonly_grill(repo: Path, proc: subprocess.Popen[str],
                           token: str, launch_id: str, *, task_id="grill-task-T1",
                           mutate=None) -> Path:
    brief = repo / ".factory/grill-brief-task-T1.md"
    brief.write_text("# Protected task grill\n", encoding="utf-8")
    executable = str(Path(sys.executable).resolve())
    argv = native_argv(executable, repo, "gpt-test", "medium", False)
    base = {
        "generated_by": "orchestrator", "at": "2026-09-07T00:00:00Z",
        "launch_id": launch_id, "task": task_id,
        "brief_sha256": hashlib.sha256(brief.read_bytes()).hexdigest(),
        "task_sha256": hashlib.sha256(b"task plan").hexdigest(),
        "write": False, "model": "gpt-test", "effort": "medium",
        "argv": argv,
        "argv_sha256": hashlib.sha256(
            json.dumps(argv, separators=(",", ":")).encode()).hexdigest(),
        "launch_status": "starting", "process_token": token,
        "transport": "native", "executable_path": executable,
        "brief_path": brief.relative_to(repo).as_posix(),
        "output_path": str(_control(repo) / "native-runs/grill.jsonl"),
        "stderr_path": str(_control(repo) / "native-runs/grill.stderr"),
        "story": "STORY-1",
    }
    running = {
        **base, "launch_status": "running", "pid": proc.pid, "pgid": proc.pid,
        "pid_started": str(psutil.Process(proc.pid).create_time()),
    }
    if mutate:
        mutate(base, running, brief)
    (_control(repo) / "delegations.jsonl").write_text(
        json.dumps(base) + "\n" + json.dumps(running) + "\n", encoding="utf-8")
    return brief


def test_lean_stop_allows_authenticated_live_native_read_only_grill(repo, tmp_path):
    _seed_contract(repo)
    proc, token, launch_id = _start_worker(
        repo, tmp_path, task_id="grill-task-T1", hook_name="stop_continue.py")
    _record_readonly_grill(repo, proc, token, launch_id)
    output = _invoke_worker(proc, {"handoff": "grill findings"})
    assert json.loads(output) == {"continue": True}


@pytest.mark.parametrize("case", [
    "missing-launch-selector", "unknown-launch", "non-grill", "changed-binding",
    "write-launch", "bad-argv", "changed-brief", "symlink-brief",
    "dead-identity", "revoked",
])
def test_lean_stop_does_not_exempt_untrusted_or_non_grill_launch(
        repo, tmp_path, case):
    _seed_contract(repo)
    proc, token, launch_id = _start_worker(
        repo, tmp_path, task_id="grill-task-T1", hook_name="stop_continue.py",
        without_launch_id=case == "missing-launch-selector")

    def mutate(starting, running, brief):
        if case == "non-grill":
            starting["task"] = running["task"] = "T1"
        elif case == "unknown-launch":
            starting["launch_id"] = running["launch_id"] = "other-launch"
        elif case == "changed-binding":
            running["task_sha256"] = "0" * 64
        elif case == "write-launch":
            argv = native_argv(str(Path(sys.executable).resolve()), repo,
                               "gpt-test", "medium", True)
            for row in (starting, running):
                row["write"] = True
                row["argv"] = argv
                row["argv_sha256"] = hashlib.sha256(
                    json.dumps(argv, separators=(",", ":")).encode()).hexdigest()
        elif case == "bad-argv":
            starting["argv_sha256"] = running["argv_sha256"] = "0" * 64
        elif case == "changed-brief":
            brief.write_text("changed after launch\n", encoding="utf-8")
        elif case == "symlink-brief":
            target = brief.with_name("untrusted.md")
            target.write_text("# Protected task grill\n", encoding="utf-8")
            brief.unlink()
            brief.symlink_to(target)
        elif case == "dead-identity":
            running["pid_started"] = "0"

    _record_readonly_grill(repo, proc, token, launch_id, mutate=mutate)
    if case == "revoked":
        marker = _control(repo) / "revoked-launches" / f"{launch_id}.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("{}", encoding="utf-8")
    output = _invoke_worker(proc, {"handoff": "untrusted"})
    result = json.loads(output)
    assert result.get("decision") == "block" and "Do not stop here" in result["reason"]


def test_context_config_failure_creates_no_private_snapshot(repo, tmp_path, monkeypatch):
    from forge_cli import delegate
    _seed_contract(repo)
    (_control(repo) / "stages.json").write_text(
        json.dumps({"issue": "STORY-1", "stages": []}))
    source = tmp_path / "context.md"
    source.write_text("sensitive context")
    def bad_config(_base):
        raise SystemExit("invalid pinned model")
    monkeypatch.setattr(delegate, "pinned_run_config", bad_config)
    monkeypatch.setattr(delegate, "secure_context_snapshot",
                        lambda _source: pytest.fail("created a snapshot before valid config"))
    with pytest.raises(SystemExit, match="invalid pinned model"):
        delegate.cmd_delegate(argparse.Namespace(
            repo=str(repo), id="T1", read_only=True, scope=[], background=False,
            context_file=str(source), print_only=False))
