"""Pick related tests in Forge; run pytest in the client's own environment."""
import ast
import configparser
import os
import re
import shlex
import subprocess
import tempfile
import tomllib
from pathlib import Path

from forge import quicktest, repo

COMMANDS = [{"words": "test", "run": "test", "changes_state": False,
             "args": [(("--pytest",), {"dest": "base", "metavar": "BASE"})], "position": 35,
             "help": "run a pytest repo's changed and module-related tests",
             "listing": "| `forge test --pytest <base>` | Run related pytest tests with the repo's test command. |"}]

REFUSALS = {"picker": ("Run forge test --pytest <base> to pick related pytest tests.", "")}


def git_files(*args: str) -> list[str]:
    return subprocess.run(["git", *args, "-z"], check=True, capture_output=True,
                          text=True).stdout.rstrip("\0").split("\0")


def module_parts(path: Path) -> list[str]:
    parts = list(path.with_suffix("").parts)
    return parts[1:] if parts[0] == "src" else parts


def pytest_options(arguments: list[str]) -> str:
    options = os.environ.get("PYTEST_ADDOPTS", "")
    names = ["pytest.ini", ".pytest.ini", "tox.ini", "setup.cfg",
             "pyproject.toml", "pytest.toml", ".pytest.toml"]
    names += [arguments[index + 1] for index, value in enumerate(arguments[:-1])
              if value in {"-c", "--config-file"}]
    names += [value.split("=", 1)[1] for value in arguments if value.startswith("--config-file=")]
    for name in names:
        if not Path(name).is_file():
            continue
        if Path(name).suffix == ".toml":
            config = tomllib.loads(Path(name).read_text("utf-8"))
            section = config.get("tool", {}).get("pytest", {}) if Path(name).name == "pyproject.toml" else config.get("pytest", {})
            value = section.get("ini_options", section).get("addopts", "")
            options += " " + (" ".join(value) if isinstance(value, list) else value)
        else:
            config = configparser.ConfigParser(interpolation=None)
            config.read(name, encoding="utf-8")
            section = "tool:pytest" if Path(name).suffix == ".cfg" else "pytest"
            options += " " + config.get(section, "addopts", fallback="")
    return options


def narrow_command(command: str, excluded: list[str], workers: str, selection: str) -> str:
    # Preserve the shell's setup and quoting; alter only pytest's argument tokens.
    paths = {Path(path).resolve() for path in excluded}
    tokens = list(re.finditer(r'''(?:[^\s"';&|<>]+|"[^"]*"|'[^']*')+|[;&|<>]+''', command))
    replacements = []
    for token in tokens:
        value = token.group().strip("\"'")
        if Path(value.split("::", 1)[0]).resolve() in paths:
            replacements.append((token.start(), token.end(), ""))
    options = [selection] if excluded else []
    configured = command + " " + pytest_options([token.group().strip("\"'") for token in tokens])
    if re.search(r'''(?:^|[\s"'=])(?:-n(?:\s|\d|auto|logical)|--numprocesses(?:=|\s))''', configured):
        caps = [int(cap) for cap in re.findall(r'''(?:^|[\s"'=])--maxprocesses(?:=|\s+)["']?(\d+)''', configured)
                if int(cap) > 0]
        options.append("--maxprocesses=" + str(min([int(workers), *caps])))
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


def test(args) -> int:
    if args.base is None:
        repo.refuse(REFUSALS["picker"])
    changed = git_files("diff", "--no-renames", "--name-only", args.base, "HEAD")
    command = tomllib.loads(Path("forge.toml").read_text("utf-8"))["test"]
    parts = quicktest.test_parts(Path.cwd(), command)
    mixed = any(kind in ("vitest", "jest") for kind, _, _ in parts)
    if mixed:
        command = " && ".join(part for kind, part, _ in parts
                              if kind not in ("vitest", "jest", "node-install"))
    environment = dict(os.environ)
    workers = str(max(1, (os.cpu_count() or 1) // 2))
    environment["PYTEST_XDIST_AUTO_NUM_WORKERS"] = workers
    excluded = []
    if any(Path(name).name in {"conftest.py", "pyproject.toml", "Pipfile"}
           or Path(name).name.endswith(".lock")
           or re.fullmatch(r"requirements.*\.txt|pylock.*\.toml", Path(name).name)
           for name in changed):
        print("Shared test inputs changed; running " +
              ("all Python tests." if mixed else "the full test command."), flush=True)
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
    # Pytest's argument file keeps exclusions off cmd.exe's limited command line.
    with tempfile.TemporaryDirectory(prefix="forge-pytest-") as folder:
        selection = Path(folder) / "selection.txt"
        selection.write_text("".join("--ignore=" + path + "\n" for path in excluded), "utf-8")
        return subprocess.run(narrow_command(command, excluded, workers,
                                              "@" + selection.as_posix()), shell=True,
                              env=environment).returncode
