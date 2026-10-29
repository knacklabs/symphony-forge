"""Pick related tests in Forge; run pytest in the client's own environment."""
import ast
import configparser
import json
import os
import re
import shlex
import subprocess
import tempfile
import tomllib
from pathlib import Path

from forge import docskip, init, machine, quicktest, repo

COMMANDS = [{"words": "test", "run": "test", "changes_state": False,
             "args": [(("--pytest",), {"dest": "base", "metavar": "BASE"}),
                      (("--full",), {"action": "store_true"}),
                      (("--change",), {"action": "store_true"})], "position": 35,
             "help": "Run tests in the machine test lane; --change selects related tests and checks",
             "listing": "| `forge test` | Run fast_test (else test) in the machine test lane; `--change` runs the change's related tests and checks; `--pytest <base>` picks related pytest tests. |"}]


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
            try:
                config = tomllib.loads(Path(name).read_text("utf-8"))
            except tomllib.TOMLDecodeError:
                continue  # Let pytest report an invalid config if it uses this file.
            section = config.get("tool", {}).get("pytest", {}) if Path(name).name == "pyproject.toml" else config.get("pytest", {})
            value = section.get("ini_options", section).get("addopts", "")
            options += " " + (" ".join(value) if isinstance(value, list) else value)
        else:
            config = configparser.ConfigParser(interpolation=None)
            config.read(name, encoding="utf-8")
            section = "tool:pytest" if Path(name).suffix == ".cfg" else "pytest"
            options += " " + config.get(section, "addopts", fallback="")
    return options


XDIST = re.compile(r'''(?:^|[\s"'=])(?:-n(?:\s|\d|auto|logical)|--numprocesses(?:=|\s))''')


def node_worker_environment(environment: dict[str, str]) -> None:
    """Enforce the allocation when a Node runner starts, including inside package scripts."""
    preload = "--require " + json.dumps(Path(__file__).with_name("node_workers.cjs").as_posix(),
                                       ensure_ascii=False)
    options = environment.get("NODE_OPTIONS", "")
    if preload not in options:
        environment["NODE_OPTIONS"] = f"{options} {preload}".strip()


def node_worker_budget(command: str, workers: str) -> str:
    """Add missing direct runner caps; the Node preload bounds explicit and scripted caps."""
    segment = re.compile(r'''(?:[^;&|<>()"']|"[^"]*"|'[^']*')+''')
    replacements = []
    for part in segment.finditer(command):
        text = part.group().rstrip()
        try:
            words = shlex.split(text)
        except ValueError:
            continue  # Leave shell constructs we cannot identify to their runner.
        index = 0
        if words[:1] == ["npx"]:
            index = 2 if words[1:2] == ["--no-install"] else 1
        elif words[:2] in (["npm", "exec"], ["pnpm", "exec"], ["yarn", "exec"]):
            index = quicktest._npm_runner_index(words) if words[0] == "npm" else 2
        name = words[index].replace("\\", "/").rsplit("/", 1)[-1] if index < len(words) else ""
        name = name.removesuffix(".cmd").removesuffix(".exe")
        if name not in {"vitest", "jest"}:
            continue
        if any(arg.split("=", 1)[0] in {"--maxWorkers", "--runInBand", "-i"}
               for arg in words[index + 1:]):
            continue
        if words[:2] == ["npm", "exec"] and "--" not in words[:index]:
            tokens = list(re.finditer(r'''(?:[^\s"']+|"[^"]*"|'[^']*')+''', text))
            start = tokens[index].start()
            text = text[:start] + "-- " + text[start:]
        text += f" --maxWorkers={workers}"
        replacements.append((part.start(), part.start() + len(part.group().rstrip()), text))
    for start, end, text in reversed(replacements):
        command = command[:start] + text + command[end:]
    return command


def narrow_command(command: str, excluded: list[str], workers: str, always: list[str], *,
                   launchers: bool = True) -> str:
    command = node_worker_budget(command, workers)
    # Preserve the shell's setup and quoting; alter only pytest's argument tokens.
    paths = {Path(path).resolve() for path in excluded}
    tokens = list(re.finditer(r'''(?:[^\s"';&|<>]+|"[^"]*"|'[^']*')+|[;&|<>]+''', command))
    pytest_tokens = [index for index, token in enumerate(tokens)
                     if Path(token.group().strip("\"'")).name in {"pytest", "pytest.exe"}]
    if not launchers and not pytest_tokens:
        return command
    replacements = []
    for token in tokens:
        value = token.group().strip("\"'")
        if Path(value.split("::", 1)[0]).resolve() in paths:
            replacements.append((token.start(), token.end(), ""))
    options = ["-p", "_forge_pytest_selection"] if excluded or always else []
    configured = command + " " + pytest_options([token.group().strip("\"'") for token in tokens])
    if XDIST.search(configured):
        caps = [int(cap) for cap in re.findall(r'''(?:^|[\s"'=])--maxprocesses(?:=|\s+)["']?(\d+)''', configured)
                if int(cap) > 0]
        options.append("--maxprocesses=" + str(min([int(workers), *caps])))
    options += always  # forge.toml's always_test, whatever roots the command names
    # CLI options win over ini and PYTEST_ADDOPTS, including fixed xdist counts.
    additions = (subprocess.list2cmdline(options) if os.name == "nt" else shlex.join(options))
    for index in pytest_tokens:
        end = next((part.start() for part in tokens[index + 1:]
                    if part.group()[0] in ";&|<>"), len(command))
        replacements.append((end, end, " " + additions + " "))
    if not pytest_tokens:
        # A test launcher must forward its arguments to pytest, just as for a full run.
        command += " " + additions
    for start, end, value in sorted(replacements, reverse=True):
        command = command[:start] + value + command[end:]
    return command


def mentions(file: Path, module: str, module_path: Path) -> bool:
    text = file.read_text("utf-8")
    # A bare word is not a module reference; qualified paths and imports are.
    path = module_path.as_posix().removeprefix("src/")
    if "." in module and re.search(r"(?<![\w.])" + re.escape(module) + r"(?![\w])", text):
        return True
    if re.search(r"(?<![\w/])(?:src/)?" + re.escape(path) + r"(?![\w])", text):
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


def manifest_test_inputs_unchanged(path: Path, base: str) -> bool:
    """Fail closed unless only explicitly harmless TOML statements changed."""
    build = {("tool", "hatch", "build"), ("tool", "hatch", "build", "targets", "wheel"),
             ("tool", "hatch", "build", "targets", "sdist")}
    snapshots = []
    try:
        for ref in (base, None):
            if ref is None:
                text = path.read_text("utf-8") if path.is_file() else ""
            else:
                shown = subprocess.run(["git", "show", f"{ref}:{path.as_posix()}"],
                                       capture_output=True, text=True)
                text = shown.stdout if shown.returncode == 0 else ""
            tomllib.loads(text)
            section, statement, remaining = (), "", []
            for line in text.splitlines(keepends=True):
                statement += line
                try:
                    value = tomllib.loads(statement)
                except tomllib.TOMLDecodeError:
                    continue  # Consume multiline values before recognizing headers or keys.
                if statement.lstrip().startswith("["):
                    header = re.fullmatch(r"\s*\[([\w.-]+)\]\s*(?:#.*)?", statement.strip())
                    section = tuple(header[1].split(".")) if header else ()
                    safe = section == ("project",) or section in build or (
                        section[:-1] in build and section[-1:] == ("force-include",))
                else:
                    key, item = next(iter(value.items())) if len(value) == 1 else ("", None)
                    safe = (section == ("project",) and key in {"version", "description"}
                            and isinstance(item, str))
                    if section in build:
                        safe = (key in {"include", "exclude"} and isinstance(item, list)
                                and all(isinstance(entry, str) for entry in item)) or (
                            key == "force-include" and isinstance(item, dict)
                            and all(isinstance(entry, str) for entry in item.values()))
                    elif section[:-1] in build and section[-1:] == ("force-include",):
                        safe = len(value) == 1 and isinstance(item, str)
                if not safe:
                    # Preserve both text and table context: deleting a safe header may move an unsafe key.
                    remaining.append((section, statement))
                statement = ""
            if statement:
                return False
            snapshots.append(remaining)
    except (OSError, ValueError, TypeError, AttributeError):
        return False
    return snapshots[0] == snapshots[1]


def own_version_only(path: Path, base: str) -> bool:
    """Compare the base and current locks, ignoring only an identified root package's version."""
    snapshots = []
    try:
        for ref in (base, None):
            def read(name: str):
                text = (path.with_name(name).read_text("utf-8") if ref is None else
                        subprocess.run(["git", "show", f"{ref}:{path.with_name(name).as_posix()}"],
                                       check=True, capture_output=True, text=True).stdout)
                return json.loads(text) if name.endswith(".json") or name == "Pipfile.lock" else tomllib.loads(text)

            lock = read(path.name)
            if path.name == "package-lock.json":
                name = read("package.json")["name"]
                if lock["name"] != name:
                    return False
                entries = [lock]
                if "packages" in lock:
                    root = lock["packages"][""]
                    if root.get("name", name) != name:
                        return False
                    entries.append(root)
            else:
                manifest = read("pyproject.toml")
                name = (manifest.get("project") or manifest["tool"]["poetry"])["name"]
                normalize = lambda value: re.sub(r"[-_.]+", "-", value).lower()
                if path.name == "Pipfile.lock":
                    entries = [entry for group in ("default", "develop")
                               for key, entry in lock.get(group, {}).items()
                               if normalize(key) == normalize(name)
                               and entry.get("path") == "." and entry.get("editable") is True]
                else:
                    entries = [entry for entry in lock["package"]
                               if normalize(entry["name"]) == normalize(name)
                               and (entry.get("source") in ({"editable": "."}, {"virtual": "."})
                                    if path.name == "uv.lock" else
                                    entry.get("source", {}).get("type") == "directory"
                                    and entry["source"].get("url") == ".")]
            if not entries:
                return False
            for entry in entries:
                if not isinstance(entry.get("version"), str):
                    return False
                entry["version"] = None
            snapshots.append(lock)
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError, TypeError, AttributeError):
        return False  # Missing or unrecognized inputs must retain the full-suite fallback.
    return snapshots[0] == snapshots[1]


def close_tests(base: str) -> int:
    """Use supported runners' selection; leave other commands unchanged."""
    command = repo.grouped(Path.cwd(), repo.config(Path.cwd())["test"])
    parts = quicktest.test_parts(Path.cwd(), command)
    package = Path("package.json")
    if command == init.NODE_TEST:
        if not package.is_file():
            return 0
        command = " && ".join(part for _, part, _ in parts)
    command = node_worker_budget(command, machine.test_cpus())
    parts = quicktest.test_parts(Path.cwd(), command)
    scripts = json.loads(package.read_text("utf-8")).get("scripts", {}) if package.is_file() else {}
    # Compound scripts forward npm arguments to the last command, not every runner.
    if not parts or re.search(r"[;|]", command) or any(re.search(r"&&|[;|]", scripts[script])
            for kind, part, _ in parts if kind in ("vitest", "jest")
            for script in scripts if re.search(r"\b" + re.escape(script) + r"\b", part)):
        return subprocess.run(command, shell=True).returncode
    if not any(kind in ("vitest", "jest") for kind, _, _ in parts):
        if any(kind == "python" for kind, _, _ in parts):
            return pytest_tests(base, command)
        return subprocess.run(command, shell=True).returncode
    for kind, part, passthrough in parts:
        if kind == "python":
            status = pytest_tests(base, part)
        else:
            if kind in ("vitest", "jest"):
                words = shlex.split(part)
                if words[:2] == ["npm", "exec"] and "--" not in words:
                    tokens = list(re.finditer(r'''(?:[^\s"']+|"[^"]*"|'[^']*')+''', part))
                    start = tokens[quicktest._npm_runner_index(words)].start()
                    part = part[:start] + "-- " + part[start:]
                changed = "--changed" if kind == "vitest" else "--changedSince"
                argument = subprocess.list2cmdline([base]) if os.name == "nt" else shlex.quote(base)
                part += f"{passthrough} {changed} {argument} --passWithNoTests"
            status = subprocess.run(part, shell=True).returncode
        if status:
            return status
    return 0


def test(args) -> int:
    if args.full:
        from forge import fullrun

        return fullrun.run(repo.root())
    if args.base is None:
        from forge import review
        top = repo.root()
        cfg = repo.config(top)
        if not (cfg["fast_test"] or cfg["test"]):
            print("forge.toml names no test command, so forge test ran none.")
            return 0
        base = f"origin/{repo.default_branch(top)}"
        if repo.run("git", "rev-parse", "--verify", base, cwd=top).returncode:
            raise repo.Refused(f"Fetch {base} first: run git fetch origin, then forge test.", "")
        # CI groups reuse their own passes; explicit ungrouped commands always execute.
        status, report = review.test_run(top, review.close_test(top, base, closing=args.change), base,
                                        always=not (args.change and "FORGE_GROUPS" in os.environ),
                                        closing=args.change)
        print(report)
        return status
    from forge import review

    top = Path.cwd().resolve()
    command = repo.grouped(top, tomllib.loads(Path("forge.toml").read_text("utf-8"))["test"])
    # A picker launched by close or bare forge test keeps that command's one place.
    parent = os.environ.get("FORGE_TEST_LANE")
    if parent and any(run["id"] == parent and run["kind"] == "test" and run.get("started_at")
                      and run.get("checkout_root") == top.as_posix() for run in machine.entries()):
        return pytest_tests(args.base, command)
    item = review.branch_item(repo.current_branch(top), top)
    entry = machine.join("test", top, item[0] if item else None, None, None)
    try:
        return pytest_tests(args.base, command, entry)
    finally:
        machine.leave(entry)


def related(base: str) -> tuple[list[str], list[str], bool, list[str]]:
    """The selected test files, all test files, whether shared inputs changed (all selected), and
    the changed sources no test file names."""
    changed = git_files("diff", "--no-renames", "--name-only", base)
    changed += git_files("ls-files", "--others", "--exclude-standard")
    tests = [Path(name) for name in git_files("ls-files", "--cached", "--others",
                                            "--exclude-standard")
             if (Path(name).name.startswith("test_") or Path(name).name.endswith("_test.py"))
             and name.endswith(".py") and Path(name).is_file()]
    fixtures = [Path(name).parent for name in changed if Path(name).name == "conftest.py"]
    shared_names = [name for name in changed
              if name == "conftest.py"
              or Path(name).name in {"pyproject.toml", "Pipfile", "package-lock.json"}
              or Path(name).name.endswith(".lock")
              or re.fullmatch(r"requirements.*\.txt|pylock.*\.toml", Path(name).name)]
    shared = [Path(name) for name in shared_names if (
           not manifest_test_inputs_unchanged(Path(name), base)
           if Path(name).name == "pyproject.toml" else
           Path(name).name not in {"uv.lock", "poetry.lock", "Pipfile.lock", "package-lock.json"}
           or not own_version_only(Path(name), base))]
    shared_changed = any(path.parent == Path(".") for path in shared)
    modules = []
    for name in changed:
        path = Path(name)
        if path.suffix != ".py" or path in tests or path.name.startswith("test_"):
            continue
        parts = module_parts(path)
        if parts[-1] == "__init__":
            parts.pop()
        if parts:
            modules.append((".".join(parts), path))
    missed = [source.as_posix() for module, source in modules
              if not any(mentions(path, module, source) for path in tests)]
    everything = [path.as_posix() for path in tests]
    if shared_changed:
        return everything, everything, True, missed
    picked = {path for path in tests
                      if path.as_posix() in changed
                      or any(path.is_relative_to(folder) for folder in fixtures)
                      or any(path.is_relative_to(source.parent) or mentions(path, "", source)
                             for source in shared)
                      or any(mentions(path, module, source) for module, source in modules)}
    dependencies = docskip.test_dependencies(tests)
    while True:
        expanded = picked | {path for path, sources in dependencies.items() if sources & picked}
        if expanded == picked:
            return sorted(path.as_posix() for path in picked), everything, False, missed
        picked = expanded


# The temporary pytest plugin: skip unpicked files, keep picked tests and each always_test entry,
# and fail the run when an entry ran no test. xdist forwards each test's report to the controller.
SELECTION = """import os, pathlib, pytest
IGNORE, PICKED, ALWAYS = {}, {}, {}
RAN, ROOT = set(), []
def pytest_configure(config):
    config.option.ignore = (config.option.ignore or []) + IGNORE
    ROOT.append(pathlib.Path(str(config.rootdir)))
def name(nodeid):  # relative to the repo, as forge.toml names it, whatever pytest's rootdir
    file, _, rest = nodeid.partition("::")
    return pathlib.Path(os.path.relpath(ROOT[0] / file)).as_posix() + ("::" + rest if rest else "")
def runs(nodeid, entry):
    return nodeid == entry or nodeid.startswith((entry + "::", entry + "["))
def pytest_collection_modifyitems(config, items):
    if PICKED is None or not ALWAYS:
        return
    def kept(item):
        nodeid = name(item.nodeid)
        return nodeid.split("::")[0] in PICKED or any(runs(nodeid, entry) for entry in ALWAYS)
    dropped = [item for item in items if not kept(item)]
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = [item for item in items if kept(item)]
def pytest_runtest_logreport(report):
    if report.when == "call":
        RAN.add(name(report.nodeid))
def pytest_sessionfinish(session):
    if hasattr(session.config, "workerinput"):
        return  # the controller sees every worker's reports
    # ponytail: grouped runs cannot report entries removed by marks or -k; pytest still
    # rejects missing files and nodes. One-group runs retain the ran-no-test check.
    if int(os.environ.get("FORGE_GROUPS", "1")) > 1:
        return
    for entry in ALWAYS:
        if not any(runs(nodeid, entry) for nodeid in
                   RAN | set(getattr(session.config, "_forge_prior_passed", []))):
            print("\\nforge.toml's always_test names " + entry
                  + ", which ran no test; fix or remove it in forge.toml.", flush=True)
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
"""


# Forge's pytest results hook, loaded into every close run: each test's node ID, relative to the
# repo, and outcome (passed, failed, skipped, xfail, xpass, or error for a failed setup or
# teardown). xdist forwards each test's report to the controller, which alone writes the file.
RESULTS_HEADER = "# forge test results\n"
INVOCATION_HEADER = "# forge pytest invocation "
RETRY_HEADER = "# forge pytest retry\n"
RETRY_STEP = "# forge pytest retry invocation\n"
RESULTS = """import json, os, pathlib, pytest
FILE, ROOT = [], []
FAILED, PASSED = set(), set()
INVOCATION_HEADER = """ + repr(INVOCATION_HEADER) + """
RETRY_HEADER = """ + repr(RETRY_HEADER) + """
RETRY_STEP = """ + repr(RETRY_STEP) + """
@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # A pytest that a test starts itself is the client's own run: it gets neither this hook nor
    # close's results file. xdist workers need neither; the controller records their reports.
    plugins = ",".join(name for name in os.environ.pop("PYTEST_PLUGINS", "").split(",")
                       if name.strip() not in ("", "_forge_test_results"))
    os.environ.update({"PYTEST_PLUGINS": plugins} if plugins else {})
    retry = os.environ.pop("FORGE_RETRY_FILES", None)
    if retry:
        before, _, after = pathlib.Path(retry).read_text("utf-8").partition(RETRY_HEADER)
        previous = [json.loads(line[len(INVOCATION_HEADER):]) for line in before.splitlines()
                    if line.startswith(INVOCATION_HEADER)]
        index = after.count(RETRY_STEP)
        with pathlib.Path(retry).open("a", encoding="utf-8") as results:
            results.write(RETRY_STEP)
        # Replay the executed prefix in order. Later commands retain their original scope.
        if index < len(previous):
            previous = previous[index]
            if not previous["files"]:
                pytest.exit("Close keeps this pytest command's earlier result.", returncode=previous["exit"])
            config.args = previous["files"]
            config.option.file_or_dir = config.args
            config.option.splits = config.option.group = None
            # Xdist workers reconstruct the original CLI args, losing this file selection.
            # Run the failed files here instead of collecting the whole group again.
            config.option.dist = "no"
            config._forge_prior_passed = previous["passed"]
    path = os.environ.pop("FORGE_TEST_RESULTS", None)
    if path and not hasattr(config, "workerinput"):
        FILE.append(pathlib.Path(path))
        with FILE[0].open("a", encoding="utf-8") as results:  # close emptied it before the command
            results.write(""" + repr(RESULTS_HEADER) + """)
    ROOT.append(pathlib.Path(str(config.rootdir)))
def pytest_runtest_logreport(report):
    if not FILE or report.when != "call" and report.passed:
        return
    if report.when == "call":
        outcome = (("xfail" if report.skipped else "xpass") if hasattr(report, "wasxfail")
                   else report.outcome)
    else:
        outcome = "skipped" if report.skipped else "error"
    _write_result(outcome, report.nodeid)
def pytest_collectreport(report):
    if FILE and report.failed:
        _write_result("error", report.nodeid)
def _write_result(outcome, nodeid):
    file, _, rest = nodeid.partition("::")
    if outcome in ("failed", "error"):
        FAILED.add((ROOT[0] / file).resolve().as_posix())
    nodeid = pathlib.Path(os.path.relpath(ROOT[0] / file)).as_posix() + ("::" + rest if rest else "")
    if outcome == "passed":
        PASSED.add(nodeid)
    with FILE[0].open("a", encoding="utf-8") as results:
        results.write(outcome + " " + nodeid + "\\n")
@pytest.hookimpl(hookwrapper=True)
def pytest_sessionfinish(session):
    yield  # Capture the final status, including always_test validation.
    if FILE:
        invocation = dict(files=sorted(FAILED), passed=sorted(PASSED), exit=int(session.exitstatus))
        with FILE[0].open("a", encoding="utf-8") as results:
            results.write(INVOCATION_HEADER + json.dumps(invocation) + "\\n")
"""


def test_process(top, item, command, env, entry, ran, log):
    """Stream one attempt's progress and stop its process group on interruption."""
    from forge import codex

    with log.open("a", encoding="utf-8") as sink, subprocess.Popen(
            command, shell=True, cwd=top, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", **codex.GROUP) as process:
        try:
            machine.started(entry, process.pid)
            output, total, completed, finished = [], None, 0, set()
            for line in process.stdout:
                sink.write(line)
                sink.flush()
                output.append(line)
                found = re.search(r"collected (\d+) items?(.*)|\[(\d+) items?\]", line)
                if found:
                    selected = re.search(r" / (\d+) selected", found[2] or "")
                    total = int(selected[1] if selected else found[1] or found[3])
                    completed = 0
                    finished.clear()
                marks = re.search(r"(?:^|\s)([.FsxXE]+)\s+\[\s*\d+%\]", line)
                result = re.search(r"(\S+::.*?)\s+(?:PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)\b.*\[\s*\d+%\]", line)
                if not result and re.search(r"\[\s*\d+%\]", line):
                    result = re.search(r"\b(?:PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)\s+(\S+::.*?)\s*$", line)
                tap = re.match(r"(?:ok|not ok) (\d+)\b|1\.\.(\d+)", line)
                if tap and tap[2]:
                    total = int(tap[2])
                if result:
                    finished.add(result[1])  # teardown errors repeat the same test's id
                    completed = len(finished)
                elif tap and tap[1]:
                    completed = int(tap[1])
                elif marks:
                    # A quiet error can be setup or a second report for teardown.
                    # Keep done unknown until a percentage gives an exact count.
                    completed = completed + len(marks[1]) if completed is not None and "E" not in marks[1] else None
                    if completed is None and total is not None:
                        percent = int(re.search(r"(\d+)%", line)[1])
                        lower, upper = (percent * total + 99) // 100, min(total, ((percent + 1) * total + 99) // 100 - 1)
                        completed = lower if lower == upper else None
                if found or marks or result or tap:
                    repo.record_progress(top, item, ran["run_id"], done=completed, total=total)
                    with machine._queue() as runs:
                        for run in runs:
                            if run["id"] == entry["id"]:
                                run["progress"] = {"done": completed, "total": total}
            done = subprocess.CompletedProcess(command, process.wait(), "".join(output))
        except BaseException:
            if process.poll() is None:
                codex._stop(codex.identity(process.pid) or {"pid": process.pid}, True)
                process.wait()
            raise
    return done


def pytest_tests(base: str, command: str, entry: dict | None = None) -> int:
    parts = quicktest.test_parts(Path.cwd(), command)
    mixed = any(kind in ("vitest", "jest") for kind, _, _ in parts)
    if mixed:
        command = " && ".join(part for kind, part, _ in parts
                              if kind not in ("vitest", "jest", "node-install", "node-check"))
        parts = quicktest.test_parts(Path.cwd(), command)
    environment = dict(os.environ)
    worker = environment.pop("FORGE_WORKER_TESTS", None) == "1"
    allocation = entry
    if allocation is None and (parent := environment.get("FORGE_TEST_LANE")):
        allocation = next((run for run in machine.entries() if run["id"] == parent
                           and run["kind"] == "test"), None)
    workers = machine.test_cpus(allocation)
    environment["PYTEST_XDIST_AUTO_NUM_WORKERS"] = workers
    environment["FORGE_TEST_CPUS"] = workers
    node_worker_environment(environment)
    if entry is not None:
        environment["FORGE_TEST_LANE"] = entry["id"]
    excluded = []
    # Read as forge test --pytest reads test: close has already checked forge.toml.
    always = tomllib.loads(Path("forge.toml").read_text("utf-8")).get("always_test", [])
    picked, tests, shared_changed, missed = related(base)
    # Tests that run the program from outside never name its files, so say what local runs miss.
    from forge import review  # imported late: review's imports lead back here
    print("".join(f"{review.GAP}{source}. The nightly full run covers it.\n" for source in missed),
          end="", flush=True)
    if worker and len(picked) * 3 > len(tests):
        print("Broad selection: only the item's tests run locally. Other tests are skipped. "
              "The nightly full run covers the rest.", flush=True)
        item = review.branch_item(repo.current_branch(Path.cwd()), Path.cwd())
        if item and "/" in item[0]:
            named = review.cells(review.task(Path.cwd(), item[0])[2].get("tests", ""))
            always = list(dict.fromkeys(always + named))
            picked = []
        else:
            changed = git_files("diff", "--no-renames", "--name-only", base)
            changed += git_files("ls-files", "--others", "--exclude-standard")
            picked = [path for path in tests if path in changed]
        shared_changed = False
    if not shared_changed:
        if not picked and not always:
            print("No changed or module-related test files to run.")
            checks = " && ".join(part for kind, part, _ in parts if kind != "python")
            return subprocess.run(checks, shell=True, env=environment).returncode if checks else 0
        # Keep shell setup, test roots and pytest settings in the repo's full command.
        listed = {entry.split("::")[0] for entry in always}
        excluded = [path for path in tests if path not in picked and path not in listed]
    if shared_changed:
        print("Shared test inputs changed; running " +
              ("all Python tests." if mixed else "the full test command."), flush=True)
    else:
        print("Related tests: " + ", ".join(picked + always), flush=True)
    # A temporary pytest hook supports pre-8.2 clients without filling cmd.exe's command line.
    with tempfile.TemporaryDirectory(prefix="forge-pytest-") as folder:
        if excluded or always:
            selection = Path(folder) / "_forge_pytest_selection.py"
            selection.write_text(SELECTION.format(repr(excluded), repr(None if shared_changed else picked),
                                                  repr(always)), "utf-8")
            environment["PYTHONPATH"] = os.pathsep.join(
                [folder, environment.get("PYTHONPATH", "")])
        if entry is None:
            return subprocess.run(narrow_command(command, excluded, workers, always), shell=True,
                                  env=environment).returncode
        from forge import codex

        with subprocess.Popen(narrow_command(command, excluded, workers, always), shell=True,
                              env=environment, **codex.GROUP) as process:
            try:
                machine.started(entry, process.pid)
                return process.wait()
            except BaseException:
                codex._stop(codex.identity(process.pid) or {"pid": process.pid}, True)
                process.wait()
                raise
