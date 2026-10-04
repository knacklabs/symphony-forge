"""Run a pytest repo's changed and module-related tests: python -m forge.fasttest BASE."""
import ast
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path


def git_files(*args: str) -> list[str]:
    return subprocess.run(["git", *args, "-z"], check=True, capture_output=True,
                          text=True).stdout.rstrip("\0").split("\0")


def module_parts(path: Path) -> list[str]:
    parts = list(path.with_suffix("").parts)
    return parts[1:] if parts[0] == "src" else parts


def pytest_load_initial_conftests(early_config, parser, args):
    # Let pytest parse every source of options before imposing our machine limit.
    if hasattr(early_config.option, "numprocesses"):
        limit = int(os.environ["PYTEST_XDIST_AUTO_NUM_WORKERS"])
        args.append("--maxprocesses=" + str(min(limit, early_config.option.maxprocesses or limit)))
    excluded = json.loads(os.environ.get("FORGE_FASTTEST_EXCLUDED", "[]"))
    paths = {Path(path).resolve() for path in excluded}
    args[:] = [arg for arg in args if Path(arg.split("::", 1)[0]).resolve() not in paths]
    args.extend("--ignore=" + path for path in excluded)


def mentions(file: Path, module: str) -> bool:
    text = file.read_text("utf-8")
    # A bare word is not a module reference; qualified paths and imports are.
    path = module.replace(".", "/")
    if "." in module and re.search(r"(?<![\w.])" + re.escape(module) + r"(?![\w])", text):
        return True
    if re.search(r"(?<![\w/])(?:src/)?" + re.escape(path + ".py") + r"(?![\w])", text):
        return True
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False  # pytest reports syntax errors in selected files.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name == module for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom):
            prefix = module_parts(file)[:-node.level] if node.level else []
            imported = ".".join(prefix + ([node.module] if node.module else []))
            if imported == module or any(f"{imported}.{alias.name}" == module
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
    environment["PYTEST_PLUGINS"] = ",".join(filter(None, [
        environment.get("PYTEST_PLUGINS"), "forge.fasttest"]))
    environment.pop("FORGE_FASTTEST_EXCLUDED", None)
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
            parts = module_parts(path)
            if parts[-1] == "__init__":
                parts.pop()
            if parts:
                modules.add(".".join(parts))
        selected = sorted(path.as_posix() for path in tests
                          if path.as_posix() in changed
                          or any(module.rsplit(".", 1)[-1] in path.name
                                 or mentions(path, module)
                                 for module in modules))
        if not selected:
            print("No changed or module-related test files to run.")
            return 0
        # Keep shell setup, test roots and pytest settings in the repo's full command.
        environment["FORGE_FASTTEST_EXCLUDED"] = json.dumps(
            [path.as_posix() for path in tests if path.as_posix() not in selected])
        print("Related tests: " + ", ".join(selected), flush=True)
    return subprocess.run(command, shell=True, env=environment).returncode


if __name__ == "__main__":
    sys.exit(main())
