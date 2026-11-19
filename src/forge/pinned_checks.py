"""Run a pinned command, with just its CI waits in the newer installed Python.

The pinned package need not know this bridge exists. Its callbacks and refusal
identities stay in that process; the installed checks keep their own imports.
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from functools import wraps
from pathlib import Path

PREFIX = "forge-ci-bridge:"


def before_push(top: Path, branch: str, slot=None) -> None:
    from forge import checks, repo, task
    found = task.branch_item(branch, top)
    if found:
        item, state = found
        # The pinned review already decided whether this result is clean.
        serious = (state.get("review") or {}).get("status") != "clean"
        checks.after_code_ci(top, item, branch, repo.config(top), serious, slot)


def serve(name: str) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from forge import checks, github, repo
    github.wait_for_reset = True
    values = json.loads(sys.stdin.readline())
    values["top"] = Path(values["top"])
    if name == "wait":
        values.setdefault("branch", repo.current_branch(values["top"]))

    def send(value):
        print(PREFIX + json.dumps(value), flush=True)

    def slot(value):
        send({"slot": value})
        if sys.stdin.readline() != "continue\n":
            raise KeyboardInterrupt

    if values.pop("has_slot"):
        values["slot"] = slot
    try:
        (before_push if name == "before_push" else getattr(checks, name))(**values)
    except repo.Refused as error:
        send({"error": str(error), "code": error.code,
              "entry": next((key for key, entry in checks.REFUSALS.items() if entry is error.entry), None)})
        return 0
    send({"done": True})
    return 0


def bridge(function, python: str):
    signature = inspect.signature(function)

    @wraps(function)
    def call(*args, **kwargs):
        from forge import checks, repo
        values = dict(signature.bind(*args, **kwargs).arguments)
        slot = values.pop("slot", None)
        values["top"] = str(values["top"])
        values["has_slot"] = slot is not None
        if "serious" in values:
            values["serious"] = bool(values["serious"])
        command = [python, str(Path(__file__).resolve()), "serve", function.__name__]
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              text=True, encoding="utf-8",
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"}) as process:
            try:
                process.stdin.write(json.dumps(values) + "\n")
                process.stdin.flush()
                answer = None
                for line in process.stdout:
                    if not line.startswith(PREFIX):
                        print(line, end="", flush=True)
                        continue
                    message = json.loads(line[len(PREFIX):])
                    if "slot" in message:
                        slot(message["slot"])
                        process.stdin.write("continue\n")
                        process.stdin.flush()
                    else:
                        answer = message
                status = process.wait()
                if status or answer is None:
                    raise subprocess.CalledProcessError(status or 1, command)
                if "error" in answer:
                    raise repo.Refused(answer["error"], "", answer["code"],
                                       checks.REFUSALS.get(answer["entry"]))
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait()
    return call


class QueueProcesses:
    """Keep the released queue's pipes and relay, replacing only its Python bootstrap."""

    def __init__(self, source: Path, python: str):
        self.source, self.python = source, python

    def __getattr__(self, name):
        return getattr(subprocess, name)

    def Popen(self, argv, *args, **kwargs):
        if list(argv[:2]) == [sys.executable, "-c"] and list(argv[3:4]) == ["land"]:
            bootstrap = (f"import sys, runpy; sys.path.insert(0, {str(self.source)!r}); "
                         f"runpy.run_path({str(Path(__file__).resolve())!r}, run_name='__main__')")
            argv = [sys.executable, "-c", bootstrap, self.python, *argv[3:]]
        return subprocess.Popen(argv, *args, **kwargs)


def pinned(python: str, args: list[str]) -> int:
    from importlib.util import find_spec
    from forge import __version__, checks, close, repo, sync
    from forge.cli import main

    original_synced = close._synced

    @wraps(original_synced)
    def synced(top, item, *rest, **kwargs):
        default = f"origin/{repo.default_branch(top)}"
        pin = repo._pin(repo.git("show", "HEAD:forge.toml", cwd=top))
        base = repo.git("merge-base", "HEAD", default, cwd=top)
        previous = repo._pin(repo.git("show", f"{base}:forge.toml", cwd=top))
        incoming = repo._pin(repo.git("show", f"{default}:forge.toml", cwd=top))
        # An unchanged old pin is not an upgrade needing a fresh sync. Keep the
        # released guide check; actual pin changes still use its original gate.
        if (pin == __version__ == previous and incoming
                and tuple(map(int, pin.split("."))) < tuple(map(int, incoming.split(".")))):
            if hasattr(sync, "check_guides"):
                return sync.check_guides(top, rest[0] if rest else kwargs.get("changed_files", []))
            return None
        return original_synced(top, item, *rest, **kwargs)

    close._synced = synced
    if not hasattr(checks, "after_code_ci"):
        original_push, original_close = close._push, close.close
        wait_before_push = bridge(before_push, python)
        slot = None

        @wraps(original_close)
        def closing(options, *rest, **kwargs):
            nonlocal slot
            previous_slot, slot = slot, getattr(options, "check_slot", None)
            try:
                return original_close(options, *rest, **kwargs)
            finally:
                slot = previous_slot

        @wraps(original_push)
        def push(top, branch, *rest, **kwargs):
            wait_before_push(top, branch, slot)
            return original_push(top, branch, *rest, **kwargs)

        close.close, close._push = closing, push

    for name in ("wait", "after_code_ci"):
        if hasattr(checks, name):
            setattr(checks, name, bridge(getattr(checks, name), python))
    if hasattr(repo, "run_release"):
        original_release = repo.run_release

        def release(version, words, cwd):
            if words and words[0] in ("close", "merge", "land"):
                return subprocess.run([python, str(Path(__file__).resolve()), "release",
                                       version, *words], cwd=cwd, env=repo.uv_env()).returncode
            return original_release(version, words, cwd)

        repo.run_release = release
    if find_spec("forge.land") is not None:
        from forge import land
        land.subprocess = QueueProcesses(Path(land.__file__).resolve().parent.parent, python)
    sys.argv = ["forge", *args]
    return main()


if __name__ == "__main__":
    if sys.argv[1] == "serve":
        raise SystemExit(serve(sys.argv[2]))
    if sys.argv[1] == "release":
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from forge import repo
        raise SystemExit(repo.run_release(sys.argv[2], sys.argv[3:], Path.cwd()))
    raise SystemExit(pinned(sys.argv[1], sys.argv[2:]))
