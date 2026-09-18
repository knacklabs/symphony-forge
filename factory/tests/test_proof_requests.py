"""Proofs the worker cannot run in its sandbox run on the host while the
harness waits (decision 0080).

WF-BIO-1 T4: seven of ten proofs could not run inside the worker's sandbox
(profile caches unreadable by its restricted account); the worker reported
"cannot run here", the coordinator ran them by hand, and neither saw the
other's output. The worker now asks for a DECLARED proof and reads one
result the host wrote.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from test_gates import (  # noqa: F401
    HARNESS, STAGE_TASK, _fake_psutil_module, delegation_ledger, git,
    record_task_grill, repo, run, start_stage,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
from factory_lib import load_json, protected_decomposition_state_path  # noqa: E402
from forge_cli import journal  # noqa: E402
from forge_cli.proof_requests import (  # noqa: E402
    requests_dir, results_dir, service_proof_requests, worker_cache_env,
)


def _counting_task(tmp_path: Path) -> tuple[dict, Path]:
    counter = tmp_path / "host-runs.txt"
    counter.write_text("0")
    command = (
        "python3 -c \"import pathlib; p = pathlib.Path(r'" + str(counter) + "'); "
        "p.write_text(str(int(p.read_text()) + 1))\""
    )
    return {**STAGE_TASK, "verify_commands": [command]}, counter


def _recorded(repo: Path) -> dict:
    decomp = load_json(protected_decomposition_state_path(repo), default={})
    return next(t for t in decomp.get("tasks", []) if t.get("id") == "T1")


def _request(repo: Path, name: str, payload: dict) -> None:
    requests_dir(repo).mkdir(parents=True, exist_ok=True)
    (requests_dir(repo) / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


def _result(repo: Path, name: str) -> dict:
    return json.loads((results_dir(repo) / f"{name}.json").read_text(encoding="utf-8"))


def test_the_host_runs_only_a_declared_proof_for_the_worker(repo, tmp_path):
    task, counter = _counting_task(tmp_path)
    start_stage(repo, tmp_path, task)
    recorded = _recorded(repo)
    _request(repo, "r1", {"kind": "verify", "command": task["verify_commands"][0]})
    _request(repo, "r2", {"kind": "verify", "command": "python3 -c \"print('pwned')\""})
    _request(repo, "r3", {"kind": "required_test", "id": "no_such_test"})
    assert service_proof_requests(repo, "T1", recorded, "ENG-1") == 1
    done = _result(repo, "r1")
    assert done["status"] == "done" and done["exit_code"] == 0, done
    assert counter.read_text() == "1"
    refused = _result(repo, "r2")
    assert refused["status"] == "refused" and "declared proofs" in refused["reason"], refused
    assert _result(repo, "r3")["status"] == "refused"
    # Serviced once: a second pass runs nothing again.
    assert service_proof_requests(repo, "T1", recorded, "ENG-1") == 0
    assert counter.read_text() == "1"
    proofs = [e for e in journal.entries(repo, "ENG-1", "T1") if e["kind"] == "proof"]
    assert any(e["title"].startswith("worker asked, host ran") and e["exit_code"] == 0
               for e in proofs), proofs


def test_a_required_test_request_gets_its_junit_where_the_worker_can_read_it(repo, tmp_path):
    start_stage(repo, tmp_path, STAGE_TASK)
    recorded = _recorded(repo)
    _request(repo, "t1", {"kind": "required_test", "id": "test_stage_contract"})
    assert service_proof_requests(repo, "T1", recorded, "ENG-1") == 1
    done = _result(repo, "t1")
    assert done["status"] == "done" and done["exit_code"] == 0, done
    assert done["junit"] == ".forge-cache/proof-results/t1.junit.xml"
    assert (repo / done["junit"]).is_file()
    assert "test_stage_contract" in (repo / done["junit"]).read_text(encoding="utf-8")


def test_proof_run_waits_for_the_host_and_exits_with_its_code(repo, tmp_path):
    task, counter = _counting_task(tmp_path)
    start_stage(repo, tmp_path, task)
    recorded = _recorded(repo)
    proc = subprocess.Popen(
        [sys.executable, str(repo / "factory/scripts/forge.py"), "proof", "run",
         "--verify", task["verify_commands"][0], "--timeout", "60"],
        cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace")
    deadline = time.monotonic() + 60
    while proc.poll() is None and time.monotonic() < deadline:
        service_proof_requests(repo, "T1", recorded, "ENG-1")
        time.sleep(0.2)
    out = proc.communicate(timeout=10)[0]
    assert proc.returncode == 0, out
    assert "asked the host to run" in out and "passed in" in out, out
    assert counter.read_text() == "1"
    # An undeclared command is refused, and the worker's command says why.
    proc = subprocess.run(
        [sys.executable, str(repo / "factory/scripts/forge.py"), "proof", "run",
         "--verify", "rm -rf /", "--timeout", "5"],
        cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace")
    # No harness is waiting on this "worker": the request times out honestly.
    assert proc.returncode != 0 and "no result" in proc.stdout + proc.stderr
    pending = [p for p in requests_dir(repo).glob("*.json")
               if not (results_dir(repo) / p.name).exists()]
    assert service_proof_requests(repo, "T1", recorded, "ENG-1") == 0
    assert all(_result(repo, p.stem)["status"] == "refused" for p in pending)
    assert counter.read_text() == "1"


def test_worker_caches_live_inside_the_worktree_and_stay_out_of_git(repo):
    env = worker_cache_env(repo)
    assert env["COREPACK_HOME"] == str(repo / ".forge-cache" / "corepack")
    assert env["npm_config_cache"] == str(repo / ".forge-cache" / "npm")
    assert env["XDG_CACHE_HOME"] == str(repo / ".forge-cache" / "xdg")
    for path in env.values():
        assert Path(path).is_dir()
    (repo / ".forge-cache" / "npm" / "blob").write_text("cache", encoding="utf-8")
    assert ".forge-cache" not in git(repo, "status", "--porcelain", "-uall")
    worker_cache_env(repo)  # idempotent: one exclude line, not one per launch
    exclude = Path(git(repo, "rev-parse", "--git-path", "info/exclude").strip())
    if not exclude.is_absolute():
        exclude = repo / exclude
    assert exclude.read_text(encoding="utf-8").count(".forge-cache/") == 1


def test_the_delegate_wait_loop_serves_a_request_from_the_companion(repo, tmp_path):
    """The fake companion writes a request for the task's own verify command
    and exits only once the host has written the result."""
    task, counter = _counting_task(tmp_path)
    start_stage(repo, tmp_path, task)
    home = tmp_path / "asking-home"
    script = home / ".claude/plugins/cache/openai-codex/codex/1.0.0/scripts/codex-companion.mjs"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "import fs from 'node:fs'; import path from 'node:path';\n"
        "const base = process.cwd();\n"
        "const dir = path.join(base, '.forge-cache', 'proof-requests');\n"
        "fs.mkdirSync(dir, {recursive: true});\n"
        "fs.writeFileSync(path.join(dir, 'ask.json'), JSON.stringify({kind: 'verify', "
        "command: process.env.FORGE_TEST_VERIFY}));\n"
        "const result = path.join(base, '.forge-cache', 'proof-results', 'ask.json');\n"
        "const started = Date.now();\n"
        "while (!fs.existsSync(result) && Date.now() - started < 90000) {\n"
        "  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 200);\n"
        "}\n"
        "process.stdout.write(JSON.stringify({ok: fs.existsSync(result), "
        "argv: process.argv.slice(2)}));\n",
        encoding="utf-8")
    metadata = home / ".claude/plugins/installed_plugins.json"
    metadata.write_text(json.dumps({"version": 2, "plugins": {"codex@openai-codex": [{
        "scope": "user", "installPath": str(script.parents[1]), "version": "1.0.0"}]}}))
    record_task_grill(repo, _recorded(repo))
    env = {"HOME": str(home), "FORGE_COORDINATOR": "claude",
           "PYTHONPATH": str(_fake_psutil_module(tmp_path)),
           "FORGE_TEST_VERIFY": task["verify_commands"][0]}
    code, out = run(repo, "forge.py", "delegate", "T1", env=env)
    assert code == 0, out
    done = _result(repo, "ask")
    assert done["status"] == "done" and done["exit_code"] == 0, done
    assert counter.read_text() == "1"
    assert '"ok": true' in out.replace('"ok":true', '"ok": true'), out
