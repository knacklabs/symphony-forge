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


def serve(name: str) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from forge import checks, github, repo
    github.wait_for_reset = True
    values = json.loads(sys.stdin.readline())
    values["top"] = Path(values["top"])

    def send(value):
        print(PREFIX + json.dumps(value), flush=True)

    def slot(value):
        send({"slot": value})
        if sys.stdin.readline() != "continue\n":
            raise KeyboardInterrupt

    if values.pop("has_slot"):
        values["slot"] = slot
    try:
        getattr(checks, name)(**values)
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


def pinned(python: str, args: list[str]) -> int:
    from forge import checks
    from forge.cli import main
    for name in ("wait", "after_code_ci"):
        if hasattr(checks, name):
            setattr(checks, name, bridge(getattr(checks, name), python))
    sys.argv = ["forge", *args]
    return main()


if __name__ == "__main__":
    if sys.argv[1] == "serve":
        raise SystemExit(serve(sys.argv[2]))
    raise SystemExit(pinned(sys.argv[1], sys.argv[2:]))
