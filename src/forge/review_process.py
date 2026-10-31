"""Adapt the pinned Autoreview process for Windows and concurrent sign-off parts."""
from __future__ import annotations

import runpy
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

# Ported from the old tree's review launcher: the helper starts the reviewer in an empty folder,
# where it can't open the code a finding depends on. Each launcher starts the real one in the
# reviewed checkout instead. The `codex` one swaps that one folder; the read-only sandbox the
# helper asks for stays as it is. The helper gives Claude only web search and refuses Read as a
# tool option, so the `claude` one adds the read-only file tools; --restricted keeps them inside
# the checkout and leaves out every tool that runs commands.
LAUNCHER = '''\
import os, subprocess, sys, time
from pathlib import Path
argv = sys.argv[1:]
if {engine!r} == "codex":
    for i in range(len(argv) - 1):
        if argv[i] in ("-C", "--cd"):
            argv[i + 1] = {tree!r}
    if "exec" in argv:
        i = argv.index("exec")
        argv[i:i] = {quiet!r}
elif "--tools" in argv:
    i = argv.index("--tools") + 1
    argv[i] = ",".join(filter(None, ["Read", "Grep", "Glob", argv[i]]))
    argv.append("--restricted")
# Each engine needs its own stream so parallel calls cannot mix chat and token use.
log = Path({spent!r}) / (str(time.time_ns()) + "-" + str(os.getpid()) + ".jsonl")
with log.open("ab") as spent, subprocess.Popen(
        [*{real!r}, *argv], cwd={tree!r}, stdout=subprocess.PIPE) as engine:
    for line in engine.stdout:
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
        if any(kind in line for kind in (b"thread.started", b"turn.completed", b"session_id")):
            spent.write(line)
sys.exit(engine.returncode)
'''


def main() -> None:
    launcher, mode, helper, *args = sys.argv[1:]
    class EngineProcess(subprocess.Popen):
        def __init__(self, command, *positional, **kwargs):
            if isinstance(command, (list, tuple)) and command and command[0] == launcher:
                command = [sys.executable, *command]
            super().__init__(command, *positional, **kwargs)

    subprocess.Popen = EngineProcess
    sys.argv = [helper, *args]
    sys.path[0] = str(Path(helper).resolve().parent)
    if mode == "serial":
        runpy.run_path(helper, run_name="__main__")
        return
    namespace = runpy.run_path(helper, run_name="forge_autoreview")
    entry = namespace.get("sanitized_main")
    if entry is None:  # Executable helpers can also finish at module scope.
        return
    implementation = entry.__globals__

    def parallel_parts(args: Any, reviewers: list[Any], repo: Path, prompts: list[Any],
                       changed_paths: Any, evidence: Any = None) -> list[tuple[str, Any]]:
        # The pinned helper still owns validation, report merging and process cleanup.
        args.review_usage = reviewers[0].review_usage = []
        with ThreadPoolExecutor(max_workers=len(prompts)) as pool:
            futures = []
            for index, prompt in enumerate(prompts, 1):
                if len(prompts) > 1:
                    text = getattr(prompt, "prompt", prompt)
                    print(f"review pass: {index}/{len(prompts)} "
                          f"({len(text.encode('utf-8'))} prompt bytes)", flush=True)
                futures.append(pool.submit(implementation["run_reviewer"], reviewers[0],
                                           repo, prompt, changed_paths, [], evidence))
            return [(f"chunk {index}/{len(prompts)}", result.result())
                    for index, result in enumerate(futures, 1)]

    implementation["run_review_passes"] = parallel_parts
    raise SystemExit(entry())


if __name__ == "__main__":
    main()
