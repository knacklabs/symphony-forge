"""The starter's module boundaries reject imports outside their public services."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "src" / "forge" / "templates" / "starter"
LIVE = os.environ.get("FORGE_STARTER_LIVE") == "1"
CASES = ("clean", "reach into a module", "the web app imports a backend module")


@pytest.fixture(scope="module")
def lint_starter(tmp_path_factory):
    if not LIVE:
        return None, "set FORGE_STARTER_LIVE=1 to run the modular starter lint cases"
    node = shutil.which("node")
    if not node:
        return None, "Node.js 24 is required for the modular starter lint cases"
    version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30)
    if version.returncode or not version.stdout.strip().startswith("v24."):
        return None, "Node.js 24 is required for the modular starter lint cases"
    corepack = shutil.which("corepack")
    if not corepack:
        return None, "Corepack is required for the modular starter lint cases"

    host_config = tmp_path_factory.mktemp("modular-starter-host")
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

    copy = tmp_path_factory.mktemp("modular-starter")
    shutil.copytree(
        STARTER, copy, dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("node_modules", "dist", ".nx", "coverage"),
    )
    command = [corepack, "pnpm", "install", "--frozen-lockfile"]
    installed = subprocess.run(
        command, cwd=copy, env=env, capture_output=True, text=True, timeout=1800,
        shell=sys.platform == "win32",
    )
    assert installed.returncode == 0, installed.stdout + installed.stderr
    return (copy, env, corepack), None


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("case", CASES)
def test_2_an_import_across_modules_fails_the_starter_tests(lint_starter, case):
    eslint = STARTER / "eslint.config.mjs"
    assert eslint.is_file(), "the starter has no ESLint configuration"
    assert "@nx/enforce-module-boundaries" in eslint.read_text(encoding="utf-8")
    package = json.loads((STARTER / "package.json").read_text(encoding="utf-8"))
    assert package["scripts"]["test"].startswith("corepack pnpm run lint &&")

    live, skip_reason = lint_starter
    if live is None:
        pytest.skip(skip_reason)
    copy, env, corepack = live

    if case == "reach into a module":
        added_file = copy / "libs" / "projects" / "src" / "reach-in.ts"
        added_file.write_text(
            "import { AuthService } from '../../auth/src/auth.service';\n"
            "export const reachedAuthService = AuthService;\n",
            encoding="utf-8",
        )
    elif case == "the web app imports a backend module":
        added_file = copy / "apps" / "web" / "src" / "reach-in.ts"
        added_file.write_text(
            "import { ProjectsService } from '@app/projects';\n"
            "export const reachedProjectsService = ProjectsService;\n",
            encoding="utf-8",
        )
    else:
        added_file = None

    try:
        result = subprocess.run(
            [corepack, "pnpm", "run", "lint"], cwd=copy, env=env,
            capture_output=True, text=True, timeout=300, shell=sys.platform == "win32",
        )
        output = result.stdout + result.stderr
        if case == "clean":
            assert result.returncode == 0, output
        else:
            assert result.returncode != 0, output
            assert "@nx/enforce-module-boundaries" in output, output
            if case == "the web app imports a backend module":
                assert "type:web" in output, output
    finally:
        if added_file is not None:
            added_file.unlink(missing_ok=True)
