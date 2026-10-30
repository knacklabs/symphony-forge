"""Adapt Autoreview's single executable-path option to a Python launcher on Windows.

Only the generated engine script gets the interpreter prefix. All other subprocesses,
including the helper's process groups and isolated environment, keep their normal behavior.
"""
from __future__ import annotations

import runpy
import subprocess
import sys


def main() -> None:
    launcher, helper, *args = sys.argv[1:]
    class EngineProcess(subprocess.Popen):
        def __init__(self, command, *positional, **kwargs):
            if isinstance(command, (list, tuple)) and command and command[0] == launcher:
                command = [sys.executable, *command]
            super().__init__(command, *positional, **kwargs)

    subprocess.Popen = EngineProcess
    sys.argv = [helper, *args]
    runpy.run_path(helper, run_name="__main__")


if __name__ == "__main__":
    main()
