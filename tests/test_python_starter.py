"""The Python starter starts through Forge and keeps the API and web app aligned."""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

pytest_plugins = ("test_notes_first_discovery",)

from test_setup import _fresh_client
from test_defaults_formats import DOWNLOAD_FLOW, FORMAT_FLOW, PYTHON_CSV_API_CASES
from test_defaults_organisations import PYTHON_ORGANISATION_API_CASES
from test_starter_tree import BROWSER_FLOWS, _pnpm_root_importer, _require_cases, _run_live_starter

STORY = "FORGE-FASTAPI-1"

ROOT = Path(__file__).resolve().parents[1]
REACT_STARTER = ROOT / "src/forge/templates/starter"
PYTHON_STARTER = ROOT / "src/forge/templates/starter-python"
REACT_PATHS = (Path("apps/web"), Path("tsconfig.base.json"), Path(".npmrc"))
LIVE = os.environ.get("FORGE_STARTER_LIVE") == "1"
API_SECURITY_TESTS = (
    "production_forgot_password_does_not_log_a_reset_link",
)
PYTHON_PACKAGES = {
    "fastapi", "pydantic", "sqlalchemy", "alembic", "uvicorn", "psycopg",
    "pytest", "httpx", "import-linter", "ruff", "mypy",
}
PYTHON_GUIDANCE = (
    "forge init --starter python",
    "In an app made from the Python starter, whose tests run import-linter, copy these fixed rules "
    "into ## Fixed rules instead, and ask nothing about them:",
    "One app split into modules: a FastAPI API on uv, with SQLAlchemy and Alembic on Postgres, and a "
    "React web app on pnpm.",
    "Each module owns its tables, in its own models file.",
    "A module uses another module only through its public service, never through its tables.",
    "The tests run import-linter, so an import of another module's internal files fails them.",
)


def _files_under(path: Path):
    if path.is_file():
        return [path]
    return sorted(candidate for candidate in path.rglob("*") if candidate.is_file())


def _assert_first_commit_has(client: Path, source: Path, target: Path):
    files = _files_under(source)
    assert files, f"missing starter files under {source}"
    [first_commit] = subprocess.run(
        ["git", "rev-list", "HEAD"], cwd=client, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    for source_file in files:
        relative = source_file.relative_to(source) if source.is_dir() else Path(source.name)
        destination = target / relative if source.is_dir() else target
        copied = subprocess.run(
            ["git", "show", f"{first_commit}:{destination.as_posix()}"],
            cwd=client, capture_output=True, check=True,
        ).stdout
        assert copied == source_file.read_bytes(), destination


def _assert_python_guidance(client: Path):
    for host in (".claude", ".codex"):
        guide = (client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
        joined = " ".join(guide.split())
        for text in PYTHON_GUIDANCE:
            assert text in joined, (host, text)


def _assert_python_tree(client: Path):
    for source in _files_under(PYTHON_STARTER):
        _assert_first_commit_has(client, source, source.relative_to(PYTHON_STARTER))
    for rel in REACT_PATHS:
        _assert_first_commit_has(client, REACT_STARTER / rel, rel)
    _assert_first_commit_has(
        client, ROOT / "src/forge/templates/skeleton/.dockerignore", Path(".dockerignore")
    )

    assert not (client / "apps/api/src").exists()
    assert not (client / "libs/auth").exists()
    assert not (client / "prisma.config.ts").exists()
    assert not (client / "nx.json").exists()

    api = client / "apps/api"
    pyproject = tomllib.loads((api / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["tool"]["mypy"] == {
        "strict": True,
        "plugins": ["pydantic.mypy"],
        "files": ["app", "tests"],
    }
    requirements = list(pyproject["project"].get("dependencies", []))
    for group in pyproject.get("dependency-groups", {}).values():
        requirements.extend(group)
    for group in pyproject["project"].get("optional-dependencies", {}).values():
        requirements.extend(group)
    declared = {}

    for entry in requirements:
        match = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([0-9]+(?:\.[0-9]+)*)$", entry)
        assert match, f"Python dependency is not pinned to one exact version: {entry}"
        declared[match.group(1).lower().replace("_", "-")] = match.group(2)
    assert set(declared) == PYTHON_PACKAGES
    lock = tomllib.loads((api / "uv.lock").read_text(encoding="utf-8"))
    locked = {package["name"].lower().replace("_", "-"): package["version"]
              for package in lock["package"]}
    for name, version in declared.items():
        assert locked.get(name) == version, (name, locked.get(name), version)

    package = json.loads((client / "package.json").read_text(encoding="utf-8"))
    react_package = json.loads((REACT_STARTER / "package.json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"pnpm@[0-9]+(?:\.[0-9]+)*", package["packageManager"])
    all_dependencies = {}
    react_dependencies = {}
    for group in ("dependencies", "devDependencies", "optionalDependencies"):
        versions = package.get(group, {})
        all_dependencies.update(versions)
        react_dependencies.update(react_package.get(group, {}))
        for name, version in versions.items():
            assert re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", version), (name, version)
    for name, version in all_dependencies.items():
        if name in react_dependencies:
            assert version == react_dependencies[name], (name, version)
    assert all_dependencies["openapi-typescript"] == "7.13.0"
    assert not any(name.startswith(("@nestjs/", "@prisma/", "@nx/")) or name in ("prisma", "nx")
                   for name in all_dependencies)
    lock_importer = _pnpm_root_importer((client / "pnpm-lock.yaml").read_text(encoding="utf-8"))
    for group in ("dependencies", "devDependencies", "optionalDependencies"):
        assert set(lock_importer.get(group, {})) == set(package.get(group, {})), group
        for name, version in package.get(group, {}).items():
            locked = lock_importer[group][name]
            assert locked["specifier"] == version, (group, name)
            assert locked["version"] == version or locked["version"].startswith(version + "("), (group, name)

    assert (api / ".python-version").read_text(encoding="utf-8").strip() == "3.14"
    for module in ("auth", "projects", "organisations", "history"):
        assert (api / "app" / module / "models.py").is_file()
    assert (api / "migrations/versions/0001_initial.py").is_file()
    scripts = package["scripts"]
    assert "ruff check" in scripts["lint"] and "ruff format --check" in scripts["lint"]
    assert "mypy" in scripts["typecheck"]
    assert "api-types" in scripts["test"] and "test:imports" in scripts["test"]
    assert scripts["test"].index("api-types") < scripts["test"].index("typecheck")
    assert "./api-types" in (client / "libs/shared/src/index.ts").read_text(encoding="utf-8")

    dockerfile = (client / "Dockerfile").read_text(encoding="utf-8")
    for line in (
        "FROM node:24",
        "corepack pnpm install --frozen-lockfile && corepack pnpm run build",
        "python:3.14-slim-bookworm",
        "ghcr.io/astral-sh/uv:0.13.0",
        "uv sync --frozen --no-dev",
        "EXPOSE 3000",
        "alembic upgrade head",
    ):
        assert line in dockerfile, line
    docker_command = next(line.removeprefix("CMD ") for line in dockerfile.splitlines()
                          if line.startswith("CMD "))
    command = json.loads(docker_command)
    assert "exec uv run --no-sync uvicorn app.main:app --host 0.0.0.0" in command[-1]
    assert '--port "${PORT:-3000}"' in command[-1]
    assert "--no-access-log" in command[-1]
    assert "exit 1" in command[-1]
    assert "**/.venv" in (ROOT / "src/forge/templates/skeleton/.dockerignore").read_text("utf-8")
    assert "**/__pycache__" in (ROOT / "src/forge/templates/skeleton/.dockerignore").read_text("utf-8")

    assert (client / "scripts/test.mjs").is_file()
    assert not (client / "scripts/test-build.mjs").exists()
    compose = (client / "compose.test.yml").read_text(encoding="utf-8")
    assert "urllib.request.urlopen" in compose

    readme = (client / "README.md").read_text(encoding="utf-8")
    assert "node scripts/test.mjs" in readme
    assert "How it works" in readme
    for term in ("app.auth", "app.projects", "import-linter", "OpenAPI", "API types"):
        assert term in readme
    _assert_python_guidance(client)


@pytest.fixture(scope="module")
def live_python_starter(tmp_path_factory):
    if not shutil.which("uv"):
        pytest.skip("uv is required for the Python starter smoke run")
    sources = tuple((REACT_STARTER / rel, rel) for rel in REACT_PATHS) + (
        (PYTHON_STARTER, Path(".")),
        (ROOT / "src/forge/templates/skeleton/.dockerignore", Path(".dockerignore")),
    )
    return _run_live_starter(tmp_path_factory, sources, ("GET /health returned 200",))


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize(
    ("case", "adoption"),
    [pytest.param("new", "new init", id="new"),
     pytest.param("wheel", "new init", id="wheel"),
     pytest.param("adopted", "previous release upgrade and sync", id="adopted")],
)
def test_1_a_python_backend_app_starts_from_the_fastapi_starter(
    repo, gh, tmp_path, case, adoption, request,
):
    # Audit: init must create the Python app as its first commit, packaged installs must carry
    # every starter file, and sync must give an earlier-adopted repo the same Python guidance.
    # Regressions include a missing init option, omitted wheel data, or missing sync guidance.
    # Existing starter tests cover the React default and its own sync text, not Python selection.
    # The real Forge command, installed wheel, and existing adoption fixture are the boundaries.
    if case == "wheel":
        built = subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(tmp_path / "dist")],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        assert built.returncode == 0, built.stdout + built.stderr
        files = [
            Path(path.decode("utf-8"))
            for path in subprocess.run(
                ["git", "ls-files", "-z", "src/forge/templates/starter-python"],
                cwd=ROOT, capture_output=True, check=True,
            ).stdout.split(b"\0")
            if path
        ]
        assert files, "the Python starter tree is empty"
        with zipfile.ZipFile(next((tmp_path / "dist").glob("*.whl"))) as wheel:
            for tracked in files:
                source = ROOT / tracked
                relative = tracked.relative_to(Path("src/forge/templates/starter-python")).as_posix()
                packaged = f"forge/templates/starter-python/{relative}"
                assert wheel.read(packaged) == source.read_bytes(), packaged

        # Audit: pip compiles the template Python files during an ordinary wheel install.
        # ZIP checks cannot detect init decoding those generated files as template text.
        # Run the installed entry point with only GitHub stubbed, without a production seam.
        environment = tmp_path / "installed"
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True,
                       capture_output=True, timeout=120)
        scripts = environment / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        installed = subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", "--no-index",
             str(next((tmp_path / "dist").glob("*.whl")))],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        assert installed.returncode == 0, installed.stdout + installed.stderr
        [templates] = [directory / "forge/templates/starter-python"
                       for directory in environment.rglob("site-packages")
                       if (directory / "forge/templates/starter-python").is_dir()]
        assert list(templates.rglob("*.pyc")), "pip did not compile the Python templates"

        client, remote = tmp_path / "wheel-client", tmp_path / "wheel-client.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
        repo.git("remote", "add", "origin", str(remote), cwd=client)
        gh.respond("api", stdout="{}")
        gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
                   stdout='{"message":"Branch not protected","status":"404"}')
        env = {**os.environ, "PATH": str(scripts) + os.pathsep + os.environ["PATH"]}
        command = scripts / ("forge.exe" if os.name == "nt" else "forge")
        initialized = subprocess.run(
            [str(command), "init", "--starter", "python"], cwd=client, env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=240,
        )
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        _assert_python_tree(client)
        committed = repo.git("ls-files", cwd=client).splitlines()
        assert not any("__pycache__" in Path(path).parts
                       or Path(path).suffix in {".pyc", ".pyo"} for path in committed)
        return

    if case == "adopted":
        client = request.getfixturevalue("client")
        _assert_python_guidance(client)
        return

    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    _assert_python_tree(client)
    assert tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["test"] == (
        "node scripts/test.mjs"
    )
    if LIVE:
        live = request.getfixturevalue("live_python_starter")
        _require_cases(
            live["api"],
            API_SECURITY_TESTS + PYTHON_ORGANISATION_API_CASES + PYTHON_CSV_API_CASES,
        )
        _require_cases(live["browser"], BROWSER_FLOWS + (FORMAT_FLOW, DOWNLOAD_FLOW))


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("case", ["clean", "reach into a module", "reach into organisations"])
def test_2_an_import_of_another_modules_internals_fails_the_tests(case, request):
    # Audit: the import-linter contract protects the public-service module boundary at its CLI.
    # A removed or misconfigured contract lets a real cross-module import pass. Existing tests
    # cover Nx boundaries in the React starter; no Python contract exists yet. No production seam
    # is needed because the test runs the app's `lint-imports` command in the composed tree.
    pyproject = tomllib.loads((PYTHON_STARTER / "apps/api/pyproject.toml").read_text("utf-8"))
    config = pyproject["tool"]["importlinter"]
    assert config["root_package"] == "app"
    contracts = {contract["name"]: contract for contract in config["contracts"]}
    guidance = (
        "A module uses another module only through its public service in its __init__.py, "
        "never through its internal files."
    )
    for module in ("core", "auth", "projects", "organisations", "history"):
        contract = contracts[f"{module} internals"]
        assert contract["protected_modules"] == [f"app.{module}.*"]
        assert contract["allowed_importers"] == [f"app.{module}"]
        assert contract["broken_contract_guidance"] == guidance
    scripts = json.loads((PYTHON_STARTER / "package.json").read_text("utf-8"))["scripts"]
    assert "test:imports" in scripts["test"]

    if not LIVE:
        return
    folder = request.getfixturevalue("live_python_starter")["folder"]
    injected = folder / "apps/api/app/projects/reach_in.py"
    module = "organisations" if case == "reach into organisations" else "auth"
    service = "OrganisationsService" if module == "organisations" else "AuthService"
    if case != "clean":
        injected.write_text(
            f"from app.{module}.service import {service}\n\nREACHED_SERVICE = {service}\n",
            encoding="utf-8",
        )
    try:
        result = subprocess.run(
            ["uv", "--directory", "apps/api", "run", "lint-imports"],
            cwd=folder, capture_output=True, text=True, encoding="utf-8", timeout=180,
        )
        if case == "clean":
            assert result.returncode == 0, result.stdout + result.stderr
        else:
            output = result.stdout + result.stderr
            assert result.returncode != 0, output
            assert f"{module} internals" in output
            assert "only through its public service" in output
    finally:
        if injected.exists():
            injected.unlink()


def _rename_project_response_field(folder: Path):
    schema_path = folder / "apps/api/app/projects/schema.py"
    schema = schema_path.read_text(encoding="utf-8")
    tree = ast.parse(schema)
    response_classes = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        has_name = any(
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "name"
            for statement in node.body
        )
        if has_name and node.name == "Project":
            response_classes.append(node)
    assert response_classes, "the public Project response model has no name field"
    lines = schema.splitlines(keepends=True)
    [response] = response_classes
    field = next(
        statement for statement in response.body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id == "name"
    )
    changed, count = re.subn(r"^(\s*)name(?=\s*:)", r"\1title", lines[field.lineno - 1])
    assert count == 1
    lines[field.lineno - 1] = changed
    schema_path.write_text("".join(lines), encoding="utf-8")
    return schema_path, schema


def _run_api_types_and_typecheck(folder: Path):
    generated = subprocess.run(
        ["corepack", "pnpm", "run", "api-types"], cwd=folder,
        capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    assert generated.returncode == 0, generated.stdout + generated.stderr
    checked = subprocess.run(
        ["corepack", "pnpm", "run", "typecheck"], cwd=folder,
        capture_output=True, text=True, encoding="utf-8", timeout=180,
    )
    return checked


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("case", ["clean", "the API renames a field"])
def test_3_the_tests_fail_when_the_api_changes_a_field_the_web_app_uses(case, request):
    # Audit: the generated OpenAPI types must reach the web type checker. A stale or disconnected
    # generation step lets API response changes compile. Existing React starter tests do not have
    # a Python OpenAPI source. The test runs the root commands, with no test-only production seam.
    shared = (PYTHON_STARTER / "libs/shared/src/index.ts").read_text(encoding="utf-8")
    assert "./api-types" in shared
    scripts = json.loads((PYTHON_STARTER / "package.json").read_text(encoding="utf-8"))["scripts"]
    assert "api-types" in scripts["test"] and scripts["test"].index("api-types") < scripts["test"].index("typecheck")
    assert "openapi-typescript" in scripts["api-types"]
    if not LIVE:
        return

    folder = request.getfixturevalue("live_python_starter")["folder"]
    if case == "clean":
        checked = _run_api_types_and_typecheck(folder)
        assert checked.returncode == 0, checked.stdout + checked.stderr
        return

    schema_path, original = _rename_project_response_field(folder)
    try:
        checked = _run_api_types_and_typecheck(folder)
        output = checked.stdout + checked.stderr
        assert checked.returncode != 0, output
        assert re.search(r"apps[/\\]+web[/\\]+src[/\\]+features[/\\]+projects[/\\]+", output), output
    finally:
        schema_path.write_text(original, encoding="utf-8")
