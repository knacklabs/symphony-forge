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

from forge import init, machine, quicktest, repo

COMMANDS = [{"words": "test", "run": "test", "changes_state": False,
             "args": [(("--pytest",), {"dest": "base", "metavar": "BASE"})], "position": 35,
             "help": "Run related tests in the machine test lane, or pick pytest tests with --pytest",
             "listing": "| `forge test` | Run fast_test (else test) in the machine test lane; `--pytest <base>` picks related pytest tests. |"}]


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


def narrow_command(command: str, excluded: list[str], workers: str) -> str:
    # Preserve the shell's setup and quoting; alter only pytest's argument tokens.
    paths = {Path(path).resolve() for path in excluded}
    tokens = list(re.finditer(r'''(?:[^\s"';&|<>]+|"[^"]*"|'[^']*')+|[;&|<>]+''', command))
    replacements = []
    for token in tokens:
        value = token.group().strip("\"'")
        if Path(value.split("::", 1)[0]).resolve() in paths:
            replacements.append((token.start(), token.end(), ""))
    options = ["-p", "_forge_pytest_selection"] if excluded else []
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
    """CI owns the full suite; close's default selects tests by their filenames."""
    changed = git_files("diff", "--no-renames", "--name-only", f"{base}...HEAD")
    changed += git_files("ls-files", "--others", "--exclude-standard")
    tests = [name for name in git_files("ls-files", "--cached", "--others", "--exclude-standard")
             if Path(name).is_file() and re.search(r"^test_|_test\.|[.]test[.]|[.]spec[.]|_spec[.]|[.]e2e-spec[.]",
                                                  Path(name).name)]
    stems = {Path(name).stem for name in changed if name not in tests}
    selected = [name for name in tests if name in changed or any(
        re.match(r"^(?:test_" + re.escape(stem) + r"(?:_|\.)|" + re.escape(stem)
                 + r"(?:_test\.|_spec\.|\.test\.|\.spec\.|\.e2e-spec\.))", Path(name).name)
        for stem in stems)]
    if not selected:
        print("No changed or source-named test files to run.", flush=True)
        return 0
    print("Related tests: " + ", ".join(sorted(selected)), flush=True)
    command = repo.config(Path.cwd())["test"]
    root = Path.cwd().resolve()

    def expand(directory, command):
        package = directory / "package.json"
        config = json.loads(package.read_text("utf-8")) if package.is_file() else {}
        scripts = config.get("scripts", {})
        for kind, part, passthrough in quicktest.test_parts(directory, command):
            words = shlex.split(part)
            script = words[2] if words[:2] in (["npm", "run"], ["npm", "run-script"]) else (
                words[1] if words[:1] == ["npm"] and len(words) > 1 else "")
            if script == "test" and "--workspaces" in words:
                workspaces = config.get("workspaces", [])
                if isinstance(workspaces, dict):
                    workspaces = workspaces.get("packages", [])
                for workspace in sorted({path for pattern in workspaces for path in directory.glob(pattern)
                                         if (path / "package.json").is_file()}):
                    if "test" in json.loads((workspace / "package.json").read_text("utf-8")).get("scripts", {}):
                        yield from expand(workspace, "npm test")
            elif script == "test" and "&&" in scripts.get(script, ""):
                if "pretest" in scripts:
                    yield directory, "setup", "npm run pretest", ""
                yield from expand(directory, scripts[script])
                if "posttest" in scripts:
                    yield directory, "setup", "npm run posttest", ""
            else:
                runner = shlex.split(scripts.get(script, part))
                if "playwright" in runner:
                    index = runner.index("playwright")
                    if runner[index + 1:index + 2] == ["test"]:
                        kind = "playwright"
                        if words[:1] == ["playwright"]:
                            part = "npm exec -- " + part
                    else:
                        kind = "setup"
                if words[:2] == ["docker", "compose"]:
                    kind = "setup"
                yield directory, kind, part, passthrough

    parts = list(expand(root, command))
    all_selected = selected
    commands = []
    environment = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix="forge-close-tests-") as folder:
        excluded = [(root / name).as_posix() for name in tests if name not in selected]
        selection = Path(folder) / "_forge_pytest_selection.py"
        selection.write_text("from pathlib import Path\n"
                             "def pytest_configure(config):\n"
                             "    excluded = {Path(p).resolve() for p in " + json.dumps(excluded) + "}\n"
                             "    config.args = [p for p in config.args if Path(p.split('::', 1)[0]).resolve() not in excluded]\n"
                             "    config.option.ignore = (config.option.ignore or []) + " + json.dumps(excluded) + "\n",
                             "utf-8")
        environment["PYTHONPATH"] = os.pathsep.join([folder, environment.get("PYTHONPATH", "")])
        if any(kind == "vitest" for _, kind, _, _ in parts):
            preload = Path(folder) / "vitest-config.cjs"
            preload.write_text("const prefix = " + json.dumps(Path(folder).as_posix() + "/selection-") + ";\n" + r"""
if (/(?:^|[\\/])(?:vitest(?:\.m?js)?|cli\.js)$/.test(process.argv[1] || '') &&
    process.argv.some(arg => arg.startsWith(prefix))) {
  const kept = process.argv.slice(0, 2);
  process.env.FORGE_CLOSE_VITEST_CONFIG = '';
  for (let i = 2; i < process.argv.length; i++) {
    const arg = process.argv[i];
    const config = arg === '--config' || arg === '-c' ? process.argv[++i] :
      arg.startsWith('--config=') || arg.startsWith('-c=') ? arg.slice(arg.indexOf('=') + 1) : undefined;
    if (config === undefined) kept.push(arg);
    else if (config.startsWith(prefix)) kept.push('--config', config);
    else process.env.FORGE_CLOSE_VITEST_CONFIG = config;
  }
  process.argv = kept;
}
""", "utf-8")
            environment["NODE_OPTIONS"] = (environment.get("NODE_OPTIONS", "") + " --require "
                                           + json.dumps(preload.as_posix(), ensure_ascii=False)).strip()
        for directory, kind, part, passthrough in parts:
            selected = [(root / name).relative_to(directory).as_posix() for name in all_selected
                        if (root / name).is_relative_to(directory)]
            if kind == "python":
                if any(name.endswith(".py") for name in selected):
                    commands.append((narrow_command(part, excluded, str(machine.half_cores())), directory))
            elif kind in ("node-install", "setup") or (kind == "node-check" and re.search(r"\b(?:lint|typecheck)\b", part)):
                commands.append((part, directory))
            elif part == dict(init.STACKS).get("go.mod"):
                for package_dir in sorted({Path(name).parent for name in selected if name.endswith("_test.go")}):
                    package = "./" + package_dir.as_posix()
                    listed = repo.run("go", "list", "-json", package, cwd=directory)
                    if listed.returncode:
                        print(listed.stdout + listed.stderr, flush=True)
                        return listed.returncode
                    info = json.loads(listed.stdout)
                    active = info.get("TestGoFiles", []) + info.get("XTestGoFiles", [])
                    names = []
                    for name in selected:
                        if Path(name).parent == package_dir and Path(name).name in active:
                            source = (directory / name).read_text("utf-8")
                            source = re.sub(r'//[^\n]*|/\*.*?\*/|`[^`]*`|"(?:\\.|[^"\\])*"'
                                            r"|'(?:\\.|[^'\\])*'", "", source, flags=re.S)
                            names += re.findall(r"^\s*func\s+((?:Test|Example|Fuzz)\w*)\s*\(", source, re.M)
                    if names:
                        words = ["go", "test", "-v", "-run", "^(?:" + "|".join(names) + ")$", package]
                        commands.append((subprocess.list2cmdline(words) if os.name == "nt" else shlex.join(words), directory))
            else:
                files = [name for name in selected if not name.endswith(".py")] if kind in ("vitest", "jest", "playwright") else selected
                if files:
                    if kind == "node-check" and shlex.split(part)[0] == "npm" and "--" not in shlex.split(part):
                        passthrough = " --"
                    if kind == "jest":
                        passthrough += " --runTestsByPath"
                    if kind == "playwright":
                        passthrough += " --pass-with-no-tests"
                    words = shlex.split(part)
                    if words[:2] == ["npm", "exec"] and "--" not in words:
                        tokens = list(re.finditer(r'''(?:[^\s"']+|"[^"]*"|'[^']*')+''', part))
                        start = tokens[quicktest._npm_runner_index(words)].start()
                        part = part[:start] + "-- " + part[start:]
                    # shortcut: custom launchers must forward file arguments; use fast_test otherwise.
                    batches = [files]
                    while batches:
                        batch = batches.pop(0)
                        arguments = ([re.escape((directory / name).resolve().as_posix()).replace("/", r"[/\\]") + "$"
                                      for name in batch] if kind == "playwright" else batch)
                        if kind in ("vitest", "jest"):
                            selection = Path(folder) / (f"selection-{len(commands)}" + (
                                ".mjs" if kind == "vitest" else ".cjs"))
                            paths = json.dumps([(directory / name).resolve().as_posix() for name in batch])
                            if kind == "jest":
                                selection.write_text("const {resolve} = require('node:path');\n"
                                    "const selected = new Set(" + paths + ".map(p => resolve(p)));\n"
                                    "module.exports = paths => ({filtered: paths.filter(p => selected.has(resolve(p)))});\n",
                                    "utf-8")
                                arguments = ["--filter", selection.as_posix()] + batch
                            else:
                                selection.write_text("""import {resolve, dirname} from 'node:path';
import {existsSync} from 'node:fs';
import {createRequire} from 'node:module';
const require = createRequire(process.argv[1]);
const {BaseSequencer} = await import(require.resolve('vitest/node'));
const {loadConfigFromFile} = await import(require.resolve('vite'));
const selected = new Set(SELECTED.map(p => resolve(p)));
export default async env => {
  const args = process.argv.slice(2);
  const values = flags => args.flatMap((arg, i) => flags.includes(arg) ? [args[i + 1]] :
    flags.some(flag => arg.startsWith(flag + '=')) ? [arg.slice(arg.indexOf('=') + 1)] : []);
  const root = resolve(values(['--root', '-r']).at(-1) || process.cwd());
  let original = process.env.FORGE_CLOSE_VITEST_CONFIG;
  if (original) original = resolve(root, original);
  const names = ['vitest.config', 'vite.config'].flatMap(name =>
    ['ts', 'mts', 'cts', 'js', 'mjs', 'cjs'].map(ext => name + '.' + ext));
  for (let dir = root; !original; dir = dirname(dir)) {
    original = names.map(name => resolve(dir, name)).find(existsSync);
    if (dir === dirname(dir)) break;
  }
  const config = original ? (await loadConfigFromFile(env, original, root)).config : {};
  config.test ||= {};
  config.test.sequence ||= {};
  const Sequencer = config.test.sequence.sequencer || BaseSequencer;
  config.test.sequence.sequencer = class extends Sequencer {
    async sort(specs) { return super.sort(specs.filter(s => selected.has(resolve(s.moduleId || s[1])))); }
  };
  return config;
};
""".replace("SELECTED", paths, 1), "utf-8")
                                arguments = ["--config", selection.as_posix()] + batch
                        arguments = subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)
                        narrowed = part + passthrough + " " + arguments
                        # Leave room for npm's wrapper within Windows' shell limit.
                        if kind in ("vitest", "jest", "playwright") and len(narrowed) > 6000 and len(batch) > 1:
                            middle = len(batch) // 2
                            batches[:0] = [batch[:middle], batch[middle:]]
                        else:
                            commands.append((narrowed, directory))
        for command, directory in commands:
            status = subprocess.run(command, shell=True, env=environment, cwd=directory).returncode
            if status:
                return status
        return 0


def test(args) -> int:
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
        status, report = review.test_run(top, review.close_test(top, base, closing=False), base, always=True)
        print(report)
        return status
    changed = git_files("diff", "--no-renames", "--name-only", args.base)
    changed += git_files("ls-files", "--others", "--exclude-standard")
    command = tomllib.loads(Path("forge.toml").read_text("utf-8"))["test"]
    parts = quicktest.test_parts(Path.cwd(), command)
    mixed = any(kind in ("vitest", "jest") for kind, _, _ in parts)
    if mixed:
        command = " && ".join(part for kind, part, _ in parts
                              if kind not in ("vitest", "jest", "node-install", "node-check"))
    environment = dict(os.environ)
    workers = str(machine.half_cores())
    environment["PYTEST_XDIST_AUTO_NUM_WORKERS"] = workers
    environment["FORGE_TEST_CPUS"] = workers
    excluded = []
    shared = [name for name in changed
              if Path(name).name in {"conftest.py", "pyproject.toml", "Pipfile", "package-lock.json"}
              or Path(name).name.endswith(".lock")
              or re.fullmatch(r"requirements.*\.txt|pylock.*\.toml", Path(name).name)]
    if any(not manifest_test_inputs_unchanged(Path(name), args.base)
           if Path(name).name == "pyproject.toml" else
           Path(name).name not in {"uv.lock", "poetry.lock", "Pipfile.lock", "package-lock.json"}
           or not own_version_only(Path(name), args.base) for name in shared):
        print("Shared test inputs changed; running " +
              ("all Python tests." if mixed else "the full test command."), flush=True)
    else:
        tests = [Path(name) for name in git_files("ls-files", "--cached", "--others",
                                                "--exclude-standard")
                 if (Path(name).name.startswith("test_") or Path(name).name.endswith("_test.py"))
                 and name.endswith(".py") and Path(name).is_file()]
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
        selected = []
        for path in tests:
            if (path.as_posix() in changed
                    or any(mentions(path, module, source)
                           for module, source in modules)):
                selected.append(path.as_posix())
        selected.sort()
        if not selected:
            print("No changed or module-related test files to run.")
            return 0
        # Keep shell setup, test roots and pytest settings in the repo's full command.
        excluded = [path.as_posix() for path in tests if path.as_posix() not in selected]
        print("Related tests: " + ", ".join(selected), flush=True)
    # A temporary pytest hook supports pre-8.2 clients without filling cmd.exe's command line.
    with tempfile.TemporaryDirectory(prefix="forge-pytest-") as folder:
        if excluded:
            selection = Path(folder) / "_forge_pytest_selection.py"
            selection.write_text("def pytest_configure(config):\n"
                                 "    config.option.ignore = (config.option.ignore or []) + "
                                 + json.dumps(excluded) + "\n", "utf-8")
            environment["PYTHONPATH"] = os.pathsep.join(
                [folder, environment.get("PYTHONPATH", "")])
        return subprocess.run(narrow_command(command, excluded, workers), shell=True,
                              env=environment).returncode
