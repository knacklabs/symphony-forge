"""A changed test command selects each supported step at Forge's command boundary."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install, patient
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import RELEASE, env, unsynced_up  # noqa: F401

STORY = "FORGE-AFFECTED-1"
pytestmark = pytest.mark.platform


def _recorders(repo, tmp_path, monkeypatch, names):
    log = tmp_path / "runner-calls.jsonl"
    monkeypatch.setenv("RUNNER_CALLS", str(log))
    for name in names:
        _install(repo.bin, name, f'''#!{sys.executable}
import json, os, pathlib, sys
with pathlib.Path(os.environ["RUNNER_CALLS"]).open("a", encoding="utf-8") as calls:
    calls.write(json.dumps({{"name": pathlib.Path(sys.argv[0]).name, "args": sys.argv[1:],
                            "cwd": pathlib.Path.cwd().as_posix()}}) + "\\n")
for index in range(int(os.environ.get("RUNNER_NOISE", "0"))):
    print(f"runner output {{index}}")
''')
    return log


def _calls(path):
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []


def _nx_stub(repo, tmp_path):
    log = tmp_path / "nx-calls.jsonl"
    _install(repo.bin, "nx", f'''#!{sys.executable}
import json, os, pathlib, sys
with pathlib.Path({json.dumps(log.as_posix())}).open("a", encoding="utf-8") as calls:
    calls.write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:] == ["show", "projects", "--with-target", "test"]:
    print(os.environ.get("NX_TEST_PROJECTS", "[]"))
''')
    return log


def _npm_stub(repo):
    _install(repo.bin, "npm", f'''#!{sys.executable}
import subprocess, sys
args = sys.argv[1:]
forward = args[args.index("--") + 1:] if "--" in args else []
raise SystemExit(subprocess.run(["playwright", "test", *forward]).returncode)
''')


def _without_version(text):
    return "\n".join(line for line in text.splitlines()
                     if not line.startswith("version = ")) + "\n"


def _python_files(client):
    (client / "pyproject.toml").write_text(
        '[project]\nname = "client"\nversion = "1.0"\n'
        '[tool.pytest.ini_options]\npythonpath = ["src"]\n'
        'markers = ["unit: unit tests", "integration: integration tests"]\n', "utf-8")
    (client / "src").mkdir(exist_ok=True)
    (client / "src" / "cart.py").write_text("VALUE = 1\n", "utf-8")
    (client / "tests").mkdir(exist_ok=True)
    (client / "tests" / "test_cart.py").write_text(
        "from cart import VALUE\ndef test_cart():\n    assert VALUE == 2\n", "utf-8")
    (client / "tests" / "test_unrelated.py").write_text(
        "def test_unrelated():\n    raise AssertionError('unrelated test ran')\n", "utf-8")


def _configure(repo, client, command):
    settings = client / "forge.toml"
    lines = [line for line in settings.read_text("utf-8").splitlines()
             if not line.startswith(("test =", "fast_test ="))]
    lines.insert(1, "test = " + json.dumps(command))
    settings.write_text("\n".join(lines) + "\n", "utf-8")
    repo.git("add", "-A", cwd=client)
    no_hooks = repo.bin.parent / "no-hooks"
    no_hooks.mkdir(exist_ok=True)
    repo.git("-c", f"core.hooksPath={no_hooks}", "commit", "--allow-empty", "-qm",
             "Configure changed test command", cwd=client)
    repo.git("-c", f"core.hooksPath={no_hooks}", "push", "-q", "origin", "main", cwd=client)


@pytest.mark.timeout(360)
def test_1_a_client_chain_selects_each_runner_and_keeps_the_shell_directory(
        repo, gh, tmp_path, monkeypatch, unsynced_up):
    client = _new_repo(repo, gh, tmp_path)
    assert repo.forge("init", "--actions", "yes", cwd=client).returncode == 0
    calls = _recorders(repo, tmp_path, monkeypatch, ("vitest", "playwright", "node"))
    (client / "sub").mkdir()
    (client / "sub" / "app.ts").write_text("export const value = 1;\n", "utf-8")
    for prefix in ("", "cd sub && "):
        (client / "sub/app.ts").write_text("export const value = 1;\n", "utf-8")
        _configure(repo, client, prefix + "vitest run && playwright test && node check.js")
        base = repo.git("rev-parse", "HEAD", cwd=client)
        (client / "sub/app.ts").write_text("export const value = 2;\n", "utf-8")
        patient(lambda: calls.unlink(missing_ok=True))

        result = repo.forge("test", "--change", cwd=client)

        assert result.returncode == 0, result.stdout + result.stderr
        actual = _calls(calls)
        assert [call["name"] for call in actual] == ["vitest", "playwright", "node"], actual
        assert actual[0]["args"][0] == "run", actual[0]
        assert any(arg.startswith("--maxWorkers=") for arg in actual[0]["args"]), actual[0]
        assert actual[2]["args"] == ["check.js"]
        assert all(Path(call["cwd"]) == (client / "sub" if prefix else client)
                   for call in actual), actual
        selected = [line for line in result.stdout.splitlines() if line.startswith("Test selection:")]
        assert len(selected) == (4 if prefix else 3), result.stdout
        if prefix:
            # The owner's narrow rule preserves cd but selects nothing after it.
            assert "--changed" not in actual[0]["args"], actual[0]
            assert actual[1]["args"] == ["test"], actual[1]
            assert all("whole command" in line for line in selected), selected
        else:
            assert actual[0]["args"][actual[0]["args"].index("--changed") + 1] == base, actual[0]
            assert actual[0]["args"][-1] == "--passWithNoTests", actual[0]
            assert actual[1]["args"] == ["test", "--only-changed=" + base], actual[1]
        assert any("node check.js" in line and "whole" in line for line in selected), selected

    # A direct Playwright command is independent of the root package's
    # compound test script. An npm step after cd now stays whole.
    (client / "package.json").write_text(json.dumps(
        {"scripts": {"test": "vitest run && node check.js"}}), "utf-8")
    (client / "web").mkdir()
    (client / "web" / "package.json").write_text(json.dumps(
        {"scripts": {"test": "playwright test"}}), "utf-8")
    (client / "web" / "app.spec.ts").write_text("export const value = 1;\n", "utf-8")
    _configure(repo, client, "playwright test")
    base = repo.git("rev-parse", "HEAD", cwd=client)
    (client / "web" / "app.spec.ts").write_text("export const value = 2;\n", "utf-8")
    patient(lambda: calls.unlink(missing_ok=True))
    direct_playwright = repo.forge("test", "--change", cwd=client)
    assert direct_playwright.returncode == 0, direct_playwright.stdout + direct_playwright.stderr
    playwright = next(call for call in _calls(calls) if call["name"] == "playwright")
    assert playwright["args"] == ["test", "--only-changed=" + base], playwright

    _npm_stub(repo)
    _configure(repo, client, "cd web && npm test")
    base = repo.git("rev-parse", "HEAD", cwd=client)
    (client / "web" / "app.spec.ts").write_text("export const value = 3;\n", "utf-8")
    patient(lambda: calls.unlink(missing_ok=True))
    web_npm = repo.forge("test", "--change", cwd=client)
    assert web_npm.returncode == 0, web_npm.stdout + web_npm.stderr
    playwright = next(call for call in _calls(calls) if call["name"] == "playwright")
    assert playwright["args"] == ["test"], playwright
    assert Path(playwright["cwd"]).name == "web", playwright

    # Unsupported shell flow keeps the full command. A docs-only edit runs no test step.
    for separator in (";", "|"):
        repo.git("checkout", "--", "sub/app.ts", cwd=client)
        _configure(repo, client, f"vitest run {separator} node check.js")
        (client / "sub" / "app.ts").write_text("export const value = 3;\n", "utf-8")
        patient(lambda: calls.unlink(missing_ok=True))
        whole = repo.forge("test", "--change", cwd=client)
        assert whole.returncode == 0, whole.stdout + whole.stderr
        assert "whole command" in whole.stdout
        whole_calls = _calls(calls)
        assert sorted(call["name"] for call in whole_calls) == ["node", "vitest"], whole_calls
        assert all("--changed" not in call["args"] and "--only-changed" not in call["args"]
                   for call in whole_calls)
    repo.git("checkout", "--", "sub/app.ts", cwd=client)
    _configure(repo, client, "vitest run && playwright test && node check.js")
    (client / "docs").mkdir(exist_ok=True)
    (client / "docs" / "guide.md").write_text("A docs-only change.\n", "utf-8")
    patient(lambda: calls.unlink(missing_ok=True))
    docs = repo.forge("test", "--change", cwd=client)
    assert docs.returncode == 0, docs.stdout + docs.stderr
    assert "docs only" in (docs.stdout + docs.stderr).lower()
    assert _calls(calls) == []

    # Nx owns a target when its workspace reports one. Otherwise it runs the
    # configured command whole; run-many --all always stays whole.
    nx_calls = _nx_stub(repo, tmp_path)
    monkeypatch.setenv("NX_TEST_PROJECTS", '["api"]')
    (client / "nx.json").write_text("{}\n", "utf-8")
    (client / "src").mkdir(exist_ok=True)
    (client / "src" / "api.ts").write_text("export const value = 1;\n", "utf-8")
    _configure(repo, client, "nx run-many -t test && vitest run")
    base = repo.git("rev-parse", "HEAD", cwd=client)
    (client / "src" / "api.ts").write_text("export const value = 2;\n", "utf-8")
    patient(lambda: calls.unlink(missing_ok=True))
    patient(lambda: nx_calls.unlink(missing_ok=True))
    affected = repo.forge("test", "--change", cwd=client)
    assert affected.returncode == 0, affected.stdout + affected.stderr
    nx_args = _calls(nx_calls)
    assert ["affected", "-t", "test", "--base=" + base] in nx_args, nx_args
    vitest = next(call for call in _calls(calls) if call["name"] == "vitest")
    assert "--changed" in vitest["args"] and base in vitest["args"], vitest
    assert any("nx" in line and "affected" in line for line in affected.stdout.splitlines()), affected.stdout

    repo.git("checkout", "--", "src/api.ts", cwd=client)
    _configure(repo, client, "nx run-many -t test && vitest run")
    (client / "src" / "api.ts").write_text("export const value = 3;\n", "utf-8")
    monkeypatch.setenv("NX_TEST_PROJECTS", "[]")
    patient(lambda: calls.unlink(missing_ok=True))
    patient(lambda: nx_calls.unlink(missing_ok=True))
    no_target = repo.forge("test", "--change", cwd=client)
    assert no_target.returncode == 0, no_target.stdout + no_target.stderr
    assert ["run-many", "-t", "test"] in _calls(nx_calls)
    assert not any(call[:1] == ["affected"] for call in _calls(nx_calls))
    assert any("nx run-many -t test" in line and "whole" in line
               for line in no_target.stdout.splitlines()), no_target.stdout

    repo.git("checkout", "--", "src/api.ts", cwd=client)
    _configure(repo, client, "nx run-many --all -t test")
    (client / "src" / "api.ts").write_text("export const value = 4;\n", "utf-8")
    monkeypatch.setenv("NX_TEST_PROJECTS", '["api"]')
    patient(lambda: nx_calls.unlink(missing_ok=True))
    all_projects = repo.forge("test", "--change", cwd=client)
    assert all_projects.returncode == 0, all_projects.stdout + all_projects.stderr
    assert ["run-many", "--all", "-t", "test"] in _calls(nx_calls)
    assert not any(call[:1] == ["affected"] for call in _calls(nx_calls))
    assert "whole" in all_projects.stdout

    # Environment expansion and arguments after `--` keep their shell
    # meaning when an Nx step is changed to affected. Project filters stay whole.
    repo.git("checkout", "--", "src/api.ts", cwd=client)
    mode = "%MODE%" if sys.platform == "win32" else "$MODE"
    _configure(repo, client, f"nx run-many -t test --configuration={mode} -- --inspect")
    base = repo.git("rev-parse", "HEAD", cwd=client)
    (client / "src" / "api.ts").write_text("export const value = 5;\n", "utf-8")
    monkeypatch.setenv("NX_TEST_PROJECTS", '["api"]')
    monkeypatch.setenv("MODE", "development")
    patient(lambda: nx_calls.unlink(missing_ok=True))
    expanded = repo.forge("test", "--change", cwd=client)
    assert expanded.returncode == 0, expanded.stdout + expanded.stderr
    nx_args = _calls(nx_calls)
    assert ["affected", "-t", "test", "--configuration=development", "--base=" + base,
            "--", "--inspect"] in nx_args, nx_args

    repo.git("checkout", "--", "src/api.ts", cwd=client)
    _configure(repo, client, "nx run-many -t test --projects api")
    (client / "src" / "api.ts").write_text("export const value = 6;\n", "utf-8")
    patient(lambda: nx_calls.unlink(missing_ok=True))
    projects = repo.forge("test", "--change", cwd=client)
    assert projects.returncode == 0, projects.stdout + projects.stderr
    nx_args = _calls(nx_calls)
    assert ["run-many", "-t", "test", "--projects", "api"] in nx_args, nx_args
    assert not any(call[:1] == ["affected"] for call in nx_args), nx_args
    assert "whole" in projects.stdout

    # A variable target is outside the narrow rule, so there is no target probe
    # and the shell still expands the original run-many invocation.
    repo.git("checkout", "--", "src/api.ts", cwd=client)
    target = "%TARGET%" if sys.platform == "win32" else "$TARGET"
    _configure(repo, client, f'nx run-many -t "{target}"')
    (client / "src/api.ts").write_text("export const value = 8;\n", "utf-8")
    monkeypatch.setenv("TARGET", "test")
    patient(lambda: nx_calls.unlink(missing_ok=True))
    variable = repo.forge("test", "--change", cwd=client)
    assert variable.returncode == 0, variable.stdout + variable.stderr
    assert _calls(nx_calls) == [["run-many", "-t", "test"]], _calls(nx_calls)
    assert "whole command" in variable.stdout, variable.stdout

    # The pull request report keeps selection lines when the runner output is
    # longer than the normal displayed tail.
    repo.git("checkout", "--", "src/api.ts", cwd=client)
    _configure(repo, client, "vitest run && node check.js")
    (client / "src" / "api.ts").write_text("export const value = 7;\n", "utf-8")
    monkeypatch.setenv("RUNNER_NOISE", "45")
    patient(lambda: calls.unlink(missing_ok=True))
    noisy = repo.forge("test", "--change", cwd=client)
    assert noisy.returncode == 0, noisy.stdout + noisy.stderr
    assert "Test selection: vitest run:" in noisy.stdout, noisy.stdout
    assert "Test selection: node check.js: whole command." in noisy.stdout, noisy.stdout
    monkeypatch.delenv("RUNNER_NOISE", raising=False)

    # An Nx workspace leaves plain pytest to its own picker. Checkers run whole.
    _python_files(client)
    calls = _recorders(repo, tmp_path, monkeypatch, ("ruff", "mypy"))
    python = json.dumps(Path(sys.executable).as_posix())
    _configure(repo, client, f"ruff check . && mypy . && {python} -m pytest tests -q")
    (client / "src" / "cart.py").write_text("VALUE = 2\n", "utf-8")
    patient(lambda: calls.unlink(missing_ok=True))
    patient(lambda: nx_calls.unlink(missing_ok=True))
    nx_python = repo.forge("test", "--change", cwd=client)
    assert nx_python.returncode == 0, nx_python.stdout + nx_python.stderr
    assert [(call["name"], call["args"]) for call in _calls(calls)] == [
        ("ruff", ["check", "."]), ("mypy", ["."]),
    ]
    assert _calls(nx_calls) == []
    assert "1 passed" in nx_python.stdout, nx_python.stdout
    assert "Test selection: nx" not in nx_python.stdout

    # An earlier-adopted client keeps its test command through upgrade and sync.
    up = unsynced_up
    patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path,
                                    dirs_exist_ok=True))
    adopted_calls = _recorders(up.repo, tmp_path, monkeypatch, ("vitest", "playwright", "node"))
    (up.repo.path / "src").mkdir(exist_ok=True)
    (up.repo.path / "src" / "app.ts").write_text("export const value = 1;\n", "utf-8")
    _configure(up.repo, up.repo.path, "vitest run && playwright test && node check.js")
    old_settings = (up.repo.path / "forge.toml").read_text("utf-8")
    upgraded = up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    synced = up.repo.forge("sync", cwd=up.folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    new_settings = (up.folder / "forge.toml").read_text("utf-8")
    assert _without_version(new_settings) == _without_version(old_settings)
    before_doctor = (up.folder / "forge.toml").read_bytes()
    doctor = up.repo.forge("doctor", cwd=up.folder)
    assert "playwright test --only-changed={base}" in doctor.stdout, doctor.stdout + doctor.stderr
    assert (up.folder / "forge.toml").read_bytes() == before_doctor
    (up.folder / "src" / "app.ts").write_text("export const value = 2;\n", "utf-8")
    adopted_base = up.repo.git("merge-base", "origin/main", "HEAD", cwd=up.folder)
    patient(lambda: adopted_calls.unlink(missing_ok=True))
    adopted = up.repo.forge("test", "--change", cwd=up.folder)
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    actual = _calls(adopted_calls)
    assert [call["name"] for call in actual] == ["vitest", "playwright", "node"], actual
    assert "--changed" in actual[0]["args"] and adopted_base in actual[0]["args"], actual[0]
    assert actual[1]["args"] == ["test", "--only-changed=" + adopted_base]
    assert actual[2]["args"] == ["check.js"]


@pytest.mark.timeout(360)
def test_2_a_python_chain_selects_only_plain_pytest_steps(
        repo, gh, tmp_path, monkeypatch, unsynced_up):
    client = _new_repo(repo, gh, tmp_path)
    _python_files(client)
    initialized = repo.forge("init", "--actions", "yes", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert json.loads(next(line.partition("=")[2] for line in (client / "forge.toml").read_text(
        "utf-8").splitlines() if line.startswith("test ="))) == "uv run pytest"
    calls = _recorders(repo, tmp_path, monkeypatch, ("ruff", "mypy"))
    python = json.dumps(Path(sys.executable).as_posix())

    # Marks are now whole steps. Inserting required tests into marked steps can
    # deselect them and fail; only the following plain pytest step owns them.
    (client / "marked").mkdir()
    marked = client / "marked/test_marks.py"
    marked.write_text("import pytest\n@pytest.mark.unit\ndef test_unit():\n    assert True\n"
                      "@pytest.mark.integration\ndef test_integration():\n    assert True\n", "utf-8")
    (client / "checks").mkdir()
    (client / "checks/test_required.py").write_text(
        "from pathlib import Path\ndef test_required():\n"
        "    with Path('required-ran.txt').open('a', encoding='utf-8') as out:\n"
        "        out.write('ran')\n", "utf-8")
    (client / ".forge/always-tests.txt").write_text("checks/test_required.py\n", "utf-8")
    _configure(repo, client, f"{python} -m pytest marked -q -m unit && "
               f"{python} -m pytest marked -q -m integration && {python} -m pytest tests -q")
    marked.write_text(marked.read_text("utf-8") + "# Changed marked tests\n", "utf-8")
    marks = repo.forge("test", "--change", cwd=client)
    assert marks.returncode == 0, marks.stdout + marks.stderr
    assert marks.stdout.count("1 passed") == 3, marks.stdout
    assert (client / "required-ran.txt").read_text("utf-8") == "ran"
    selections = [line for line in marks.stdout.splitlines() if line.startswith("Test selection:")]
    assert len(selections) == 3 and all("whole command" in line for line in selections[:2]), selections
    assert "checks/test_required.py" in selections[2], selections
    patient(lambda: (client / ".forge/always-tests.txt").unlink())
    patient(lambda: (client / "required-ran.txt").unlink())

    # After cd pytest runs whole, keeping its original directory and arguments.
    (client / "backend" / "tests").mkdir(parents=True)
    backend_test = client / "backend" / "tests" / "test_backend.py"
    backend_test.write_text("def test_backend():\n    assert True\n", "utf-8")
    _configure(repo, client, "cd backend && pytest tests")
    backend_test.write_text("def test_backend():\n    assert 1 == 1\n", "utf-8")
    backend = repo.forge("test", "--change", cwd=client)
    assert backend.returncode == 0, backend.stdout + backend.stderr
    assert "Test selection: pytest tests: whole command." in backend.stdout, backend.stdout
    assert "1 passed" in backend.stdout, backend.stdout

    _configure(repo, client, f"ruff check src && mypy src && {python} -m pytest tests -q")
    (client / "src" / "cart.py").write_text("VALUE = 2\n", "utf-8")

    result = repo.forge("test", "--change", cwd=client)

    assert result.returncode == 0, result.stdout + result.stderr
    assert [(call["name"], call["args"]) for call in _calls(calls)] == [
        ("ruff", ["check", "src"]), ("mypy", ["src"]),
    ]
    selected = [line for line in result.stdout.splitlines() if line.startswith("Test selection:")]
    assert len(selected) == 3, result.stdout
    assert any("ruff" in line and "whole command" in line for line in selected), selected
    assert any("mypy" in line and "whole command" in line for line in selected), selected
    assert any("pytest" in line and "tests/test_cart.py" in line for line in selected), selected
    assert "tests/test_unrelated.py" not in result.stdout, result.stdout
    assert "1 passed" in result.stdout, result.stdout

    (client / "src" / "cart.py").write_text("VALUE = 1\n", "utf-8")
    (client / "assets.json").write_text("{}\n", "utf-8")
    patient(lambda: calls.unlink(missing_ok=True))
    no_python = repo.forge("test", "--change", cwd=client)
    assert no_python.returncode == 0, no_python.stdout + no_python.stderr
    assert [(call["name"], call["args"]) for call in _calls(calls)] == [
        ("ruff", ["check", "src"]), ("mypy", ["src"]),
    ]

    # A quoted expression is shell-safe but pytest keeps its own filtering whole.
    _recorders(repo, tmp_path, monkeypatch, ("node",))
    (client / "src" / "cart.py").write_text("VALUE = 1\n", "utf-8")
    _configure(repo, client,
               f'{python} -m pytest tests -q -k "(cart or order)" && node check.js')
    (client / "src" / "cart.py").write_text("VALUE = 2\n", "utf-8")
    patient(lambda: calls.unlink(missing_ok=True))
    quoted = repo.forge("test", "--change", cwd=client)
    assert quoted.returncode == 0, quoted.stdout + quoted.stderr
    assert "whole command" in quoted.stdout, quoted.stdout
    assert "Test selection: pytest:" not in quoted.stdout, quoted.stdout
    assert "unsupported shell flow" not in quoted.stdout.lower(), quoted.stdout
    assert "1 passed" in quoted.stdout, quoted.stdout
    assert [(call["name"], call["args"]) for call in _calls(calls)] == [
        ("node", ["check.js"]),
    ]

    # Plain pytest calls keep their own paths. Only the first plain call gets
    # always_test files, so a required test does not run again in each step.
    (client / "src" / "basket.py").write_text("VALUE = 1\n", "utf-8")
    (client / "src" / "order.py").write_text("VALUE = 1\n", "utf-8")
    (client / "tests" / "unit").mkdir(exist_ok=True)
    (client / "tests" / "unit" / "test_basket.py").write_text(
        "from basket import VALUE\ndef test_basket():\n    assert VALUE == 2\n", "utf-8")
    (client / "tests" / "integration").mkdir(exist_ok=True)
    (client / "tests" / "integration" / "test_order.py").write_text(
        "from order import VALUE\ndef test_order():\n    assert VALUE == 1\n", "utf-8")
    step_commands = (
        f"{python} -m pytest tests/unit && {python} -m pytest tests/integration",
        f"{python} -m pytest tests/unit/test_basket.py && "
        f"{python} -m pytest tests/integration/test_order.py",
    )
    for command in step_commands:
        (client / "src" / "basket.py").write_text("VALUE = 1\n", "utf-8")
        (client / ".forge/always-tests.txt").write_text("checks/test_required.py\n", "utf-8")
        _configure(repo, client, command)
        (client / "src" / "basket.py").write_text("VALUE = 2\n", "utf-8")
        steps = repo.forge("test", "--change", cwd=client)
        assert steps.returncode == 0, steps.stdout + steps.stderr
        assert steps.stdout.count("2 passed") == 1, steps.stdout
        assert (client / "required-ran.txt").read_text("utf-8") == "ran"
        assert "tests/integration/test_order.py" not in steps.stdout, steps.stdout
        selected = [line for line in steps.stdout.splitlines()
                    if line.startswith("Test selection: pytest:")]
        assert len(selected) == 2, steps.stdout
        assert "tests/unit/test_basket.py" in selected[0], selected
        assert "checks/test_required.py" in selected[0], selected
        assert "none (no related tests)" in selected[1], selected
        patient(lambda: (client / ".forge/always-tests.txt").unlink())
        patient(lambda: (client / "required-ran.txt").unlink())

    # An earlier-adopted Python client keeps its command through upgrade and
    # sync, and Forge still selects the related pytest module.
    up = unsynced_up
    patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path,
                                    dirs_exist_ok=True))
    _python_files(up.repo.path)
    _configure(up.repo, up.repo.path, "uv run pytest")
    old_settings = (up.repo.path / "forge.toml").read_text("utf-8")
    upgraded = up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    synced = up.repo.forge("sync", cwd=up.folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert _without_version((up.folder / "forge.toml").read_text("utf-8")) == \
        _without_version(old_settings)
    uv = up.repo.bin / "uv"
    uv_text = uv.read_text("utf-8")
    marker = 'release = args[3].rsplit("@", 1)[1]'
    assert marker in uv_text
    uv.write_text(uv_text.replace(
        marker,
        'if args[:2] == ["run", "pytest"]:\n'
        '    sys.exit(subprocess.run([sys.executable, "-m", "pytest", *args[2:]]).returncode)\n'
        + marker), "utf-8")
    (up.folder / "src" / "cart.py").write_text("VALUE = 2\n", "utf-8")
    adopted = up.repo.forge("test", "--change", cwd=up.folder)
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    assert "Test selection: pytest:" in adopted.stdout, adopted.stdout
    assert "tests/test_cart.py" in adopted.stdout, adopted.stdout
    assert "1 passed" in adopted.stdout, adopted.stdout
    # Later checker steps run whole; adding them does not change the pytest picker.
    settings = up.folder / "forge.toml"
    settings.write_text(settings.read_text("utf-8").replace(
        'test = "uv run pytest"', 'test = "ruff check . && mypy . && uv run pytest"'), "utf-8")
    patient(lambda: calls.unlink(missing_ok=True))
    checked = up.repo.forge("test", "--change", cwd=up.folder)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert [(call["name"], call["args"]) for call in _calls(calls)] == [
        ("ruff", ["check", "."]), ("mypy", ["."]),
    ]
    assert "1 passed" in checked.stdout, checked.stdout
