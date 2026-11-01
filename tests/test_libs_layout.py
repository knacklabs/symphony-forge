"""A new app puts contracts and server code in separate module libraries."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_setup import _fresh_client
from test_starter_tree import (
    API_SECURITY_TESTS,
    API_ZOD_CASES,
    LIVE,
    PYTHON_REACT_PATHS,
    STARTER,
    _assert_first_commit_has,
    _require_cases,
    live_run,
    live_python_run,
)
from test_worker import calls, install_claude

STORY = "FORGE-LIBS-1"

SERVER_LIBRARIES = (
    ("@app/shared-util", "libs/shared/util", "util", "shared"),
    ("@app/core-server", "libs/core/server", "server", "core"),
    ("@app/auth-contracts", "libs/auth/contracts", "contracts", "auth"),
    ("@app/auth-server", "libs/auth/server", "server", "auth"),
    ("@app/projects-contracts", "libs/projects/contracts", "contracts", "projects"),
    ("@app/projects-server", "libs/projects/server", "server", "projects"),
    ("@app/organisations-contracts", "libs/organisations/contracts", "contracts", "organisations"),
    ("@app/organisations-server", "libs/organisations/server", "server", "organisations"),
    ("@app/history-contracts", "libs/history/contracts", "contracts", "history"),
    ("@app/history-server", "libs/history/server", "server", "history"),
)
PYTHON_STARTER = ROOT / "src" / "forge" / "templates" / "starter-python"


def _check_module_web_boundary(folder, corepack, env, expected_rule):
    library = folder / "libs/projects/web"
    source = library / "src/index.ts"
    library.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    (library / "project.json").write_text(json.dumps({
        "name": "@app/projects-web",
        "projectType": "library",
        "sourceRoot": (Path("libs") / "projects" / "web" / "src").as_posix(),
        "tags": ["type:web", "scope:projects"],
    }), encoding="utf-8")
    (library / "package.json").write_text(json.dumps({
        "name": "@app/projects-web",
        "version": "1.0.0",
        "private": True,
        "exports": {".": {
            "@app/source": "./" + Path("src/index.ts").as_posix(),
            "types": "./" + Path("src/index.ts").as_posix(),
        }},
    }), encoding="utf-8")
    source.write_text("export const page = true;\n", encoding="utf-8")
    command = [corepack, "pnpm", "run", "lint"]
    try:
        clean = subprocess.run(
            command, cwd=folder, env=env, capture_output=True, text=True,
            timeout=300, shell=sys.platform == "win32",
        )
        assert clean.returncode == 0, clean.stdout + clean.stderr
        source.write_text("import '@app/organisations-server';\n", encoding="utf-8")
        blocked = subprocess.run(
            command, cwd=folder, env=env, capture_output=True, text=True,
            timeout=300, shell=sys.platform == "win32",
        )
        output = blocked.stdout + blocked.stderr
        assert blocked.returncode != 0, output
        assert expected_rule in output, output
    finally:
        shutil.rmtree(library)


@pytest.fixture(scope="module")
def lint_starter(tmp_path_factory):
    if not LIVE:
        return None, "set FORGE_STARTER_LIVE=1 to run the starter lint cases"
    node = shutil.which("node")
    if not node:
        return None, "Node.js 24 is required for the starter lint cases"
    version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30)
    if version.returncode or not version.stdout.strip().startswith("v24."):
        return None, "Node.js 24 is required for the starter lint cases"
    corepack = shutil.which("corepack")
    if not corepack:
        return None, "Corepack is required for the starter lint cases"

    host_config = tmp_path_factory.mktemp("libs-layout-host")
    user_home = host_config / "home"
    user_home.mkdir()
    env = os.environ.copy()
    for name in tuple(env):
        if name.lower().startswith(("npm_config_", "pnpm_config_")):
            env.pop(name)
    env.update({
        "HOME": str(user_home),
        "COREPACK_HOME": str(host_config / "corepack"),
        "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
        "PNPM_CONFIG_STORE_DIR": str(host_config / "pnpm-store"),
        "XDG_CONFIG_HOME": str(host_config / "xdg-config"),
    })
    if sys.platform == "win32":
        env["USERPROFILE"] = str(user_home)
    assert not any(name.lower().startswith("npm_config_") for name in env)

    copy = tmp_path_factory.mktemp("libs-layout-starter")
    shutil.copytree(
        STARTER, copy, dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("node_modules", "dist", ".nx", "coverage"),
    )
    installed = subprocess.run(
        [corepack, "pnpm", "install", "--frozen-lockfile"], cwd=copy, env=env,
        capture_output=True, text=True, timeout=1800, shell=sys.platform == "win32",
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    return (copy, env, corepack), None


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_1_server_code_is_split_by_module(tmp_path_factory, lint_starter):
    # Audit: this protects the starter's public library layout and its Nx project tags.
    # A regression that leaves code in the old mixed folders or omits a contracts/server project
    # makes a new app impossible to split at module boundaries. Existing starter tests cover build
    # shape, and the old modular test only checked generic lint failures; neither owns this layout.
    # The test reads the product template and exercises a copied app, with no test-only seam.
    for name, folder, role, scope in SERVER_LIBRARIES:
        path = STARTER / folder
        assert path.is_dir(), folder
        project = json.loads((path / "project.json").read_text(encoding="utf-8"))
        assert project["name"] == name
        assert project["sourceRoot"] == (Path(folder) / "src").as_posix()
        assert f"type:{role}" in project["tags"]
        assert f"scope:{scope}" in project["tags"]
        assert [tag for tag in project["tags"] if tag.startswith("type:")] == [f"type:{role}"]
        assert (path / "package.json").is_file()
        assert (path / "tsconfig.json").is_file()

    for old_path in (
        "libs/shared/src",
        "libs/core/src",
        "libs/auth/src",
        "libs/projects/src",
        "libs/organisations/src",
        "libs/history/src",
    ):
        assert not (STARTER / old_path).exists(), old_path

    live, skip_reason = lint_starter
    if live is None:
        if LIVE:
            pytest.skip(skip_reason)
        return
    copy, env, corepack = live

    lint = subprocess.run(
        [corepack, "pnpm", "run", "lint"], cwd=copy, env=env,
        capture_output=True, text=True, timeout=300, shell=sys.platform == "win32",
    )
    assert lint.returncode == 0, lint.stdout + lint.stderr

    cases = (
        ("libs/projects/server/src/reach-in.ts",
         "import { AuthService } from '@app/auth-server';\n"
         "export const reachedAuthService = AuthService;\n"),
        ("libs/projects/server/src/reach-in.ts",
         "import { AuthService } from '../../../auth/server/src/auth.service';\n"
         "export const reachedAuthService = AuthService;\n"),
        ("libs/projects/contracts/src/reach-in.ts",
         "import { ProjectsService } from '@app/projects-server';\n"
         "export const reachedProjectsService = ProjectsService;\n"),
    )
    for relative, source in cases:
        added_file = copy / relative
        added_file.write_text(source, encoding="utf-8")
        try:
            result = subprocess.run(
                [corepack, "pnpm", "run", "lint"], cwd=copy, env=env,
                capture_output=True, text=True, timeout=300, shell=sys.platform == "win32",
            )
        finally:
            added_file.unlink(missing_ok=True)
        output = result.stdout + result.stderr
        assert result.returncode != 0, output
        assert "@nx/enforce-module-boundaries" in output, output

    _require_cases(live_run(tmp_path_factory)["api"], API_SECURITY_TESTS + API_ZOD_CASES)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_2_a_new_module_web_library_cannot_import_another_modules_server(lint_starter):
    # Screen code leaves the starter, but module boundaries stay in force for screens agents add.
    # A fresh module web library with a cross-module server import must fail lint; the retained
    # server-library tests do not exercise this frontend rule. The temporary app is the real lint
    # boundary and needs no production seam.
    live, skip_reason = lint_starter
    if live is None:
        if LIVE:
            pytest.skip(skip_reason)
        return
    copy, env, corepack = live
    _check_module_web_boundary(copy, corepack, env, "@nx/enforce-module-boundaries")


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_3_the_python_web_app_uses_the_same_libraries(repo, gh, tmp_path, tmp_path_factory):
    # Audit: this protects the Python init output and the web import boundary.
    # A missing web copy, changed Python API file, or removed lint pattern breaks the contract.
    # Existing Python starter coverage checks its packaged tree and API types, but not Python web
    # boundary failures. This uses Forge init, its first commit, and the live starter.
    # Pages and hooks add parent segments to relative imports; root-only probes miss that bypass.
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    for relative in PYTHON_REACT_PATHS:
        _assert_first_commit_has(client, STARTER / relative, relative)

    for module in ("auth", "history", "organisations", "projects"):
        relative = Path("libs") / module / "contracts"
        _assert_first_commit_has(client, PYTHON_STARTER / relative, relative)
    shared_api_types = Path("libs/shared/api-types")
    _assert_first_commit_has(client, PYTHON_STARTER / shared_api_types, shared_api_types)

    api_starter = PYTHON_STARTER / "apps/api"
    _assert_first_commit_has(client, api_starter, Path("apps/api"))
    [first_commit] = subprocess.run(
        ["git", "rev-list", "HEAD"], cwd=client, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    api_files = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", first_commit, "--", "apps/api"],
        cwd=client, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    expected_api_files = {
        (Path("apps/api") / path.relative_to(api_starter)).as_posix()
        for path in api_starter.rglob("*") if path.is_file()
    }
    assert set(api_files) == expected_api_files

    if not LIVE:
        return

    live = live_python_run(tmp_path_factory)
    folder = live["folder"]
    _check_module_web_boundary(
        folder, shutil.which("corepack"), os.environ.copy(),
        "A module web library uses another module only through its contracts.",
    )


@pytest.mark.platform
@pytest.mark.parametrize("case", ("new", "adopted"), ids=("new", "adopted"))
def test_6_existing_apps_keep_their_layout(repo, gh, tmp_path, case):
    # Audit: this protects the install and sync boundary for both new and earlier-adopted apps.
    # A regression could copy the new folders into an app whose code still uses the old layout.
    # Existing tests check generic adoption and starter file copying, but not this app-specific
    # layout across `forge sync`. It needs no production seam because both paths use Forge commands.
    if case == "new":
        client, initialized = _fresh_client(repo, gh, tmp_path, "--starter")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        assert (client / "libs/shared/util").is_dir()
        assert not (client / "libs/shared/src").exists()
        return

    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                    dirs_exist_ok=True)
    client = repo.path
    for path, text in (
        ("libs/shared/src/index.ts", "export const appOwned = true;\n"),
        ("libs/projects/src/projects.service.ts", "export class ProjectsService {}\n"),
        ("apps/web/src/features/projects/pages/projects-page.tsx",
         "export const ProjectsPage = () => null;\n"),
        ("apps/api/prisma/schema/projects.prisma",
         "model Project {\n  id String @id @default(uuid())\n}\n"),
    ):
        destination = client / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
    config = client / "forge.toml"
    version = repo.forge("--version").stdout.split()[-1]
    settings = config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version))
    config.write_text(re.sub(r'^workers = ".*"$', 'workers = "claude"', settings, flags=re.M),
                      encoding="utf-8")
    _fixture_git(repo, tmp_path, "add", "-A", cwd=client)
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Prepare the earlier client", cwd=client)
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main", cwd=client)
    started = repo.forge("fix", "start", "Keep existing app layout", "--done",
                         "The existing app keeps its code and schema after sync", "--kind",
                         "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    top = Path(re.search(r" in (.+)\n", started.stdout)[1])
    app_files = (
        "libs/shared/src/index.ts",
        "libs/projects/src/projects.service.ts",
        "apps/web/src/features/projects/pages/projects-page.tsx",
        "apps/api/prisma/schema/projects.prisma",
    )
    before = {path: (top / path).read_bytes() for path in app_files}
    synced = repo.forge("sync", cwd=top)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert before == {path: (top / path).read_bytes() for path in app_files}
    assert not (top / "libs/shared/util").exists()
    assert not (top / "libs/projects/contracts").exists()
    _fixture_git(repo, tmp_path, "add", "-A", cwd=top)
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Sync the app guide", cwd=top)
    log = install_claude(repo)
    item = re.search(r"Next: forge work ([^\s]+)", started.stdout)[1]
    worked = repo.forge("work", item, cwd=top)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = calls(log)[-1]["brief"]
    match = re.search(r"how-to.*?is in `([^`]+)`", brief, re.S)
    assert match, brief
    conventions = Path(match[1])
    stack = (conventions / "stack.md").read_text(encoding="utf-8")
    assert "An app made before this layout keeps its own folders and schema; follow the folders it has." in stack
