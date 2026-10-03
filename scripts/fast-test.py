"""Run Forge's changed and module-related test files, using its full pytest settings."""
import os
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path


changed = subprocess.run(
    ["git", "diff", "--no-renames", "--name-only", "-z", sys.argv[1], "HEAD"],
    check=True, capture_output=True, text=True,
).stdout.split("\0")
command = tomllib.loads(Path("forge.toml").read_text("utf-8"))["test"]
if not any(Path(name).name in {"conftest.py", "pyproject.toml", "uv.lock"}
           for name in changed):
    modules = {Path(name).stem for name in changed
               if name.endswith(".py") and not name.startswith("tests/")}
    selected = sorted(path.as_posix() for path in Path("tests").rglob("test_*.py")
                      if path.as_posix() in changed
                      or any(name in path.read_text("utf-8") for name in modules))
    if not selected:
        print("No changed or module-related test files to run.")
        sys.exit(0)
    # Keep the full command's setup and pytest options in one place: forge.toml.
    args = shlex.split(command)
    index = args.index("tests")
    args[index:index + 1] = selected
    command = shlex.join(args)
    print("Related tests: " + ", ".join(selected), flush=True)
else:
    print("Shared test inputs changed; running the full test command.", flush=True)

# pytest-xdist's auto mode honors this explicit worker count, including on fallback.
environment = {**os.environ, "PYTEST_XDIST_AUTO_NUM_WORKERS": str(max(1, (os.cpu_count() or 1) // 2))}
sys.exit(subprocess.run(command, shell=True, env=environment).returncode)
