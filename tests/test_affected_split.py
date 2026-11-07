"""A changed test command selects each supported step at Forge's command boundary."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install, patient
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

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


def _without_version(text):
    return "\n".join(line for line in text.splitlines()
                     if not line.startswith("version = ")) + "\n"


def _python_files(client):
    (client / "pyproject.toml").write_text(
        '[project]\nname = "client"\nversion = "1.0"\n'
        '[tool.pytest.ini_options]\npythonpath = ["src"]\n', "utf-8")
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
    _configure(repo, client, "cd sub && vitest run && playwright test && node check.js")
    base = repo.git("rev-parse", "HEAD", cwd=client)
    (client / "sub" / "app.ts").write_text("export const value = 2;\n", "utf-8")

    result = repo.forge("test", "--change", cwd=client)

    assert result.returncode == 0, result.stdout + result.stderr
    actual = _calls(calls)
    assert [call["name"] for call in actual] == ["vitest", "playwright", "node"], actual
    assert actual[0]["args"][0] == "run" and "--changed" in actual[0]["args"], actual[0]
    assert actual[0]["args"][actual[0]["args"].index("--changed") + 1] == base, actual[0]
    assert actual[0]["args"][-1] == "--passWithNoTests", actual[0]
    assert any(arg.startswith("--maxWorkers=") for arg in actual[0]["args"]), actual[0]
    assert actual[1]["args"] == ["test", "--only-changed=" + base]
    assert actual[2]["args"] == ["check.js"]
    assert all(Path(call["cwd"]).name == "sub" for call in actual), actual
    selected = [line for line in result.stdout.splitlines() if line.startswith("Test selection:")]
    assert len(selected) == 3, result.stdout
    assert any("vitest" in line and "--changed" in line for line in selected), selected
    assert any("playwright" in line and "--only-changed" in line for line in selected), selected
    assert any("node check.js" in line and "whole" in line for line in selected), selected

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

    # An Nx workspace still leaves Python steps to their own selectors.
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
        ("ruff", ["check", "src/cart.py"]), ("mypy", ["src/cart.py"]),
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
def test_2_a_python_chain_selects_related_tests_and_changed_file_checks(
        repo, gh, tmp_path, monkeypatch, unsynced_up):
    client = _new_repo(repo, gh, tmp_path)
    _python_files(client)
    initialized = repo.forge("init", "--actions", "yes", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert json.loads(next(line.partition("=")[2] for line in (client / "forge.toml").read_text(
        "utf-8").splitlines() if line.startswith("test ="))) == "uv run pytest"
    calls = _recorders(repo, tmp_path, monkeypatch, ("ruff", "mypy"))
    python = json.dumps(Path(sys.executable).as_posix())
    _configure(repo, client, f"ruff check . && mypy . && {python} -m pytest tests -q")
    (client / "src" / "cart.py").write_text("VALUE = 2\n", "utf-8")

    result = repo.forge("test", "--change", cwd=client)

    assert result.returncode == 0, result.stdout + result.stderr
    assert [(call["name"], call["args"]) for call in _calls(calls)] == [
        ("ruff", ["check", "src/cart.py"]), ("mypy", ["src/cart.py"]),
    ]
    selected = [line for line in result.stdout.splitlines() if line.startswith("Test selection:")]
    assert len(selected) == 3, result.stdout
    assert any("ruff" in line and "src/cart.py" in line for line in selected), selected
    assert any("mypy" in line and "src/cart.py" in line for line in selected), selected
    assert any("pytest" in line and "tests/test_cart.py" in line for line in selected), selected
    assert "tests/test_unrelated.py" not in result.stdout, result.stdout
    assert "1 passed" in result.stdout, result.stdout

    (client / "src" / "cart.py").write_text("VALUE = 1\n", "utf-8")
    (client / "assets.json").write_text("{}\n", "utf-8")
    patient(lambda: calls.unlink(missing_ok=True))
    no_python = repo.forge("test", "--change", cwd=client)
    assert no_python.returncode == 0, no_python.stdout + no_python.stderr
    assert _calls(calls) == []

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
    # The app owner can add changed-file checkers later without giving Nx ownership.
    settings = up.folder / "forge.toml"
    settings.write_text(settings.read_text("utf-8").replace(
        'test = "uv run pytest"', 'test = "ruff check . && mypy . && uv run pytest"'), "utf-8")
    patient(lambda: calls.unlink(missing_ok=True))
    checked = up.repo.forge("test", "--change", cwd=up.folder)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert [(call["name"], call["args"]) for call in _calls(calls)] == [
        ("ruff", ["check", "src/cart.py"]), ("mypy", ["src/cart.py"]),
    ]
    assert "1 passed" in checked.stdout, checked.stdout
