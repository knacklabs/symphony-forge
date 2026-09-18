"""Proof commands the worker cannot run in its sandbox run on the host (0080).

On Windows the worker's restricted account cannot read the Corepack and pnpm
caches under the user profile, nor the store-linked node_modules, so seven of
WF-BIO-1 T4's ten proofs could not run inside the sandbox at all: the worker
reported "cannot run here", the coordinator ran them by hand, and the two
never shared one output. The worker now ASKS: it writes a request naming a
declared proof, and the harness -- already waiting on that worker -- runs
exactly that declared command on the host and writes the result where the
worker reads it. Nothing the worker types is executed on the host: a request
names a verify command the task declares or a required-test id, and anything
else is refused with a result that says so. Every run lands in the task
journal like any other proof.

Worker caches (Corepack, npm, XDG) live under `<worktree>/.forge-cache/`,
readable by the sandbox and excluded from Git, so a tool that only needs its
own cache no longer fails on the profile ACL.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from factory_lib import active_story_key, clean_git_env, repo_root

from .common import fail

CACHE_DIR = ".forge-cache"
REQUESTS_DIR = "proof-requests"
RESULTS_DIR = "proof-results"
POLL_SECONDS = 1.0


def cache_dir(base: Path) -> Path:
    return base / CACHE_DIR


def requests_dir(base: Path) -> Path:
    return cache_dir(base) / REQUESTS_DIR


def results_dir(base: Path) -> Path:
    return cache_dir(base) / RESULTS_DIR


def ensure_cache_excluded(base: Path) -> None:
    """`.forge-cache/` never reaches the stage measurement or a commit."""
    probe = subprocess.run(
        ["git", "rev-parse", "--git-path", "info/exclude"], cwd=base,
        capture_output=True, text=True, env=clean_git_env(), encoding="utf-8",
    )
    if probe.returncode != 0 or not probe.stdout.strip():
        return
    exclude = Path(probe.stdout.strip())
    if not exclude.is_absolute():
        exclude = base / exclude
    line = f"{CACHE_DIR}/"
    try:
        current = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
    except OSError:
        return
    if line in current.splitlines():
        return
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a", encoding="utf-8") as handle:
        if current and not current.endswith("\n"):
            handle.write("\n")
        handle.write(f"# forge: worker caches and proof requests (0080)\n{line}\n")


def worker_cache_env(base: Path) -> dict[str, str]:
    """Cache locations for the worker, inside the worktree it can read."""
    root = cache_dir(base)
    env = {
        "COREPACK_HOME": str(root / "corepack"),
        "npm_config_cache": str(root / "npm"),
        "XDG_CACHE_HOME": str(root / "xdg"),
    }
    for path in list(env.values()) + [str(requests_dir(base)), str(results_dir(base))]:
        Path(path).mkdir(parents=True, exist_ok=True)
    ensure_cache_excluded(base)
    return env


def declared_proofs(task: dict) -> list[dict]:
    proofs = [{"kind": "verify", "command": str(command)}
              for command in task.get("verify_commands") or [] if str(command).strip()]
    for proof in task.get("required_tests") or []:
        if isinstance(proof, dict) and all(
                isinstance(proof.get(key), str) for key in ("id", "path", "command")):
            proofs.append({"kind": "required_test", "id": proof["id"],
                           "path": proof["path"], "command": proof["command"]})
    return proofs


def _match(request: dict, task: dict) -> dict | None:
    kind = request.get("kind")
    for proof in declared_proofs(task):
        if proof["kind"] != kind:
            continue
        if kind == "verify" and proof["command"] == request.get("command"):
            return proof
        if kind == "required_test" and proof["id"] == request.get("id"):
            return proof
    return None


def _write_result(base: Path, name: str, payload: dict) -> None:
    target = results_dir(base) / f"{name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def service_proof_requests(base: Path, stage_id: str, task: dict,
                           story: str = "") -> int:
    """Run every pending request that names a declared proof; refuse the rest.
    Called from the delegate's wait loop; never raises."""
    from .journal import append
    from .stages import _execute, _output_tail
    served = 0
    pending = sorted(requests_dir(base).glob("*.json")) if requests_dir(base).is_dir() else []
    for path in pending:
        name = path.stem
        if (results_dir(base) / f"{name}.json").exists():
            continue
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _write_result(base, name, {"status": "refused",
                                       "reason": f"request is not JSON: {exc}"})
            continue
        proof = _match(request, task) if isinstance(request, dict) else None
        if proof is None:
            _write_result(base, name, {
                "status": "refused",
                "reason": "the host runs only this task's declared proofs: "
                          + ", ".join(
                              p["command"] if p["kind"] == "verify" else f"required test {p['id']!r}"
                              for p in declared_proofs(task)) or "(none declared)",
            })
            continue
        env = os.environ.copy()
        process_token = f"proof-request-{uuid.uuid4().hex}"
        env["FORGE_PROCESS_TOKEN"] = process_token
        env["PYTHONUTF8"] = "1"
        junit = ""
        started = time.monotonic()
        try:
            if proof["kind"] == "verify":
                label = proof["command"]
                code, out, err = _execute(base, stage_id, "verify command", env=env,
                                          process_token=process_token,
                                          command=proof["command"])
            else:
                import shlex
                label = f"required test {proof['id']!r}"
                report = results_dir(base) / f"{name}.junit.xml"
                report.unlink(missing_ok=True)
                tokens = [token.replace("{report}", str(report))
                          .replace("{path}", proof["path"]).replace("{id}", proof["id"])
                          for token in shlex.split(proof["command"])]
                while tokens and "=" in tokens[0] and not tokens[0].startswith("="):
                    key, value = tokens.pop(0).split("=", 1)
                    env[key] = value
                code, out, err = _execute(base, stage_id, label, env=env,
                                          process_token=process_token, tokens=tokens)
                if report.is_file():
                    junit = report.relative_to(base).as_posix()
        except SystemExit as exc:
            _write_result(base, name, {"status": "failed", "reason": str(exc)})
            continue
        except Exception as exc:  # noqa: BLE001 - the wait loop must survive
            _write_result(base, name, {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"})
            continue
        elapsed = int(time.monotonic() - started)
        tail = _output_tail(out, err)
        _write_result(base, name, {"status": "done", "command": label, "exit_code": code,
                                   "elapsed_s": elapsed, "output_tail": tail, "junit": junit})
        served += 1
        story = story or active_story_key(base)
        if story:
            try:
                append(base, story, stage_id, kind="proof", by="harness",
                       title=f"worker asked, host ran: {label}: "
                             f"{'passed' if code == 0 else f'failed (exit {code})'} in {elapsed}s",
                       body=tail, command=label, exit_code=int(code), elapsed_s=elapsed)
            except SystemExit as exc:
                print(f"journal: proof request not recorded: {exc}")
    return served


def cmd_proof_run(args: argparse.Namespace) -> None:
    """Worker side: ask the host to run one declared proof and wait for it."""
    base = Path(args.repo).resolve() if args.repo else repo_root()
    if bool(args.id) == bool(args.verify):
        fail("proof run: name exactly one of --id <required test id> or --verify \"<command>\"")
    request = ({"kind": "required_test", "id": args.id} if args.id
               else {"kind": "verify", "command": args.verify})
    name = f"{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    requests_dir(base).mkdir(parents=True, exist_ok=True)
    (requests_dir(base) / f"{name}.json").write_text(
        json.dumps(request) + "\n", encoding="utf-8")
    result_path = results_dir(base) / f"{name}.json"
    label = args.id or args.verify
    print(f"proof run: asked the host to run {label}; waiting (request {name})", flush=True)
    deadline = time.monotonic() + float(args.timeout)
    last_note = time.monotonic()
    while not result_path.exists():
        if time.monotonic() > deadline:
            fail(f"proof run: no result for {name} after {args.timeout}s. The harness "
                 "services requests only while `forge delegate` is waiting on this "
                 "worker; if it is, raise a signal.")
        if time.monotonic() - last_note > 60:
            print("proof run: still waiting on the host", flush=True)
            last_note = time.monotonic()
        time.sleep(POLL_SECONDS)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("status") != "done":
        fail(f"proof run: {result.get('status')}: {result.get('reason')}")
    print(result.get("output_tail") or "(no output)")
    if result.get("junit"):
        print(f"junit report: {result['junit']}")
    code = int(result.get("exit_code") or 0)
    print(f"proof run: {label} {'passed' if code == 0 else f'failed (exit {code})'} "
          f"in {result.get('elapsed_s', '?')}s", flush=True)
    sys.exit(code)
