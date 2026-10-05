"""Pick related tests in Forge; run pytest in the client's own environment."""
import ast
import configparser
import os
import re
import shlex
import subprocess
import tomllib
from pathlib import Path

COMMANDS = [{"words": "fasttest", "run": "fasttest", "changes_state": False,
             "args": [(("base",), {})], "position": 35,
             "help": "run a pytest repo's changed and module-related tests",
             "listing": "`forge fasttest <base>` | Run related pytest tests with the repo's test command."}]


def git_files(*args: str) -> list[str]:
    return subprocess.run(["git", *args, "-z"], check=True, capture_output=True,
                          text=True).stdout.rstrip("\0").split("\0")


def module_parts(path: Path) -> list[str]:
    parts = list(path.with_suffix("").parts)
    return parts[1:] if parts[0] == "src" else parts


def pytest_options() -> str:
    options = os.environ.get("PYTEST_ADDOPTS", "")
    for name, section in (("pytest.ini", "pytest"), (".pytest.ini", "pytest"),
                          ("tox.ini", "pytest"), ("setup.cfg", "tool:pytest")):
        config = configparser.ConfigParser(interpolation=None)
        config.read(name, encoding="utf-8")
        options += " " + config.get(section, "addopts", fallback="")
    if Path("pyproject.toml").is_file():
        options += " " + str(tomllib.loads(Path("pyproject.toml").read_text("utf-8"))
                             .get("tool", {}).get("pytest", {}).get("ini_options", {})
                             .get("addopts", ""))
    return options


def narrow_command(command: str, excluded: list[str], workers: str) -> str:
    # Preserve the shell's setup and quoting; alter only pytest's argument tokens.
    paths = {Path(path).resolve() for path in excluded}
    tokens = list(re.finditer(r'''(?:[^\s"';&|<>]+|"[^"]*"|'[^']*')+|[;&|<>]+''', command))
    replacements = []
    for token in tokens:
        value = token.group().strip("\"'")
        if Path(value.split("::", 1)[0]).resolve() in paths:
            replacements.append((token.start(), token.end(), ""))
    options = ["--ignore=" + path for path in excluded]
    if re.search(r"(?:^|\s)(?:-n(?:\s|\d|auto|logical)|--numprocesses(?:=|\s))",
                 command + " " + pytest_options()):
        options.append("--maxprocesses=" + workers)
    # CLI options win over ini and PYTEST_ADDOPTS, including fixed xdist counts.
    additions = (subprocess.list2cmdline(options) if os.name == "nt" else shlex.join(options))
    found = False
    for index, token in enumerate(tokens):
        if Path(token.group().strip("\"'")).name in {"pytest", "pytest.exe"}:
            end = next((part.start() for part in tokens[index + 1:]
                        if part.group()[0] in ";&|<>"), len(command))
            replacements.append((end, end, " " + additions + " "))
            found = True
    if not found:
        # A test launcher must forward its arguments to pytest, just as for a full run.
        command += " " + additions
    for start, end, value in sorted(replacements, reverse=True):
        command = command[:start] + value + command[end:]
    return command


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


def fasttest(args) -> int:
    changed = git_files("diff", "--no-renames", "--name-only", args.base, "HEAD")
    command = tomllib.loads(Path("forge.toml").read_text("utf-8"))["test"]
    environment = dict(os.environ)
    workers = str(max(1, (os.cpu_count() or 1) // 2))
    environment["PYTEST_XDIST_AUTO_NUM_WORKERS"] = workers
    excluded = []
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
        excluded = [path.as_posix() for path in tests if path.as_posix() not in selected]
        print("Related tests: " + ", ".join(selected), flush=True)
    return subprocess.run(narrow_command(command, excluded, workers), shell=True,
                          env=environment).returncode
