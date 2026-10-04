"""Run a pytest repo's changed and module-related tests: python -m forge.fasttest BASE."""
import ast
import os
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path


def git_files(*args: str) -> list[str]:
    return subprocess.run(["git", *args, "-z"], check=True, capture_output=True,
                          text=True).stdout.rstrip("\0").split("\0")


def mentions(text: str, module: str) -> bool:
    # A bare word is not a module reference; qualified paths and imports are.
    path = module.replace(".", "/")
    if "." in module and re.search(r"(?<![\w.])" + re.escape(module) + r"(?![\w])", text):
        return True
    if re.search(r"(?<![\w/])" + re.escape(path + ".py") + r"(?![\w])", text):
        return True
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False  # pytest reports syntax errors in selected files.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name == module for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module == module or any(f"{node.module}.{alias.name}" == module
                                            for alias in node.names):
                return True
    return False


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m forge.fasttest BASE", file=sys.stderr)
        return 1
    changed = git_files("diff", "--no-renames", "--name-only", sys.argv[1], "HEAD")
    command = tomllib.loads(Path("forge.toml").read_text("utf-8"))["test"]
    environment = dict(os.environ)
    workers = str(max(1, (os.cpu_count() or 1) // 2))
    environment["PYTEST_XDIST_AUTO_NUM_WORKERS"] = workers
    # Explicit worker counts must obey the same limit as auto, including full fallback.
    command = re.sub(r"(?<!\S)(-n\s*|--numprocesses[=\s]+)(auto|logical|\d+)(?!\S)",
                     lambda match: match[1] + (workers if match[2] in {"auto", "logical"}
                                              else str(min(int(match[2]), int(workers)))), command)
    if any(Path(name).name in {"conftest.py", "pyproject.toml", "Pipfile"}
           or Path(name).name.endswith(".lock")
           or re.fullmatch(r"requirements.*\.txt|pylock.*\.toml", Path(name).name)
           for name in changed):
        print("Shared test inputs changed; running the full test command.", flush=True)
    else:
        tests = [Path(name) for name in git_files("ls-files", "--cached", "--others",
                                                "--exclude-standard")
                 if (Path(name).name.startswith("test_") or Path(name).name.endswith("_test.py"))
                 and name.endswith(".py") and Path(name).is_file()]
        modules = set()
        for name in changed:
            path = Path(name)
            if path.suffix != ".py" or path in tests or path.name.startswith("test_"):
                continue
            parts = list(path.with_suffix("").parts)
            if parts[0] == "src":
                parts.pop(0)
            if parts[-1] == "__init__":
                parts.pop()
            if parts:
                modules.add(".".join(parts))
        selected = sorted(path.as_posix() for path in tests
                          if path.as_posix() in changed
                          or any(module.rsplit(".", 1)[-1] in path.name
                                 or mentions(path.read_text("utf-8"), module)
                                 for module in modules))
        if not selected:
            print("No changed or module-related test files to run.")
            return 0
        # Keep shell setup, test roots and pytest settings in the repo's full command.
        ignores = ["--ignore=" + path.as_posix() for path in tests
                   if path.as_posix() not in selected]
        environment["PYTEST_ADDOPTS"] = (environment.get("PYTEST_ADDOPTS", "") + " "
                                         + shlex.join(ignores))
        print("Related tests: " + ", ".join(selected), flush=True)
    return subprocess.run(command, shell=True, env=environment).returncode


if __name__ == "__main__":
    sys.exit(main())
