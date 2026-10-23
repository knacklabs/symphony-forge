"""The starter template keeps its app shape and runs at its real boundary."""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

STORY = "FORGE-STARTER-1"

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "src" / "forge" / "templates" / "starter"
PIN = re.compile(r"[0-9]+(?:\.[0-9]+)*\Z")
LIVE = os.environ.get("FORGE_STARTER_LIVE") == "1"
API_SECURITY_TESTS = (
    "account isolation",
    "production forgot-password does not log a reset link",
)
BROWSER_FLOWS = (
    "sign up then sign in",
    "forgot-password request confirms delivery",
    "Ctrl+B collapses and expands the sidebar",
    "Ctrl+K opens search and goes to Projects",
    "create, edit, and delete a project",
    "switching accounts does not show the previous account projects",
    "theme changes in settings",
    "unknown address shows the 404 page",
    "axe finds no serious problem on the shell",
)
PINNED_PACKAGES = {
    "@nestjs/core": "11.2.7",
    "@playwright/test": "1.56.1",
    "@prisma/client": "7.10.1",
    "@tanstack/react-query": "5.90.5",
    "nx": "22.0.1",
    "prisma": "7.10.1",
    "react": "19.2.0",
    "react-dom": "19.2.0",
    "react-router-dom": "7.9.4",
    "shadcn": "4.21.4",
    "tailwindcss": "4.1.16",
    "vite": "7.1.12",
    "vitest": "3.2.4",
}
NEUTRAL_THEME = {
    "background": ("oklch(1 0 0)", "oklch(0.145 0 0)"),
    "foreground": ("oklch(0.145 0 0)", "oklch(0.985 0 0)"),
    "card": ("oklch(1 0 0)", "oklch(0.205 0 0)"),
    "card-foreground": ("oklch(0.145 0 0)", "oklch(0.985 0 0)"),
    "popover": ("oklch(1 0 0)", "oklch(0.205 0 0)"),
    "popover-foreground": ("oklch(0.145 0 0)", "oklch(0.985 0 0)"),
    "primary": ("oklch(0.205 0 0)", "oklch(0.922 0 0)"),
    "primary-foreground": ("oklch(0.985 0 0)", "oklch(0.205 0 0)"),
    "secondary": ("oklch(0.97 0 0)", "oklch(0.269 0 0)"),
    "secondary-foreground": ("oklch(0.205 0 0)", "oklch(0.985 0 0)"),
    "muted": ("oklch(0.97 0 0)", "oklch(0.269 0 0)"),
    "muted-foreground": ("oklch(0.556 0 0)", "oklch(0.708 0 0)"),
    "accent": ("oklch(0.97 0 0)", "oklch(0.269 0 0)"),
    "accent-foreground": ("oklch(0.205 0 0)", "oklch(0.985 0 0)"),
    "destructive": ("oklch(0.577 0.245 27.325)", "oklch(0.704 0.191 22.216)"),
    "border": ("oklch(0.922 0 0)", "oklch(1 0 0 / 10%)"),
    "input": ("oklch(0.922 0 0)", "oklch(1 0 0 / 15%)"),
    "ring": ("oklch(0.708 0 0)", "oklch(0.556 0 0)"),
    "chart-1": ("oklch(0.646 0.222 41.116)", "oklch(0.488 0.243 264.376)"),
    "chart-2": ("oklch(0.6 0.118 184.704)", "oklch(0.696 0.17 162.48)"),
    "chart-3": ("oklch(0.398 0.07 227.392)", "oklch(0.769 0.188 70.08)"),
    "chart-4": ("oklch(0.828 0.189 84.429)", "oklch(0.627 0.265 303.9)"),
    "chart-5": ("oklch(0.769 0.188 70.08)", "oklch(0.645 0.246 16.439)"),
    "sidebar": ("oklch(0.985 0 0)", "oklch(0.205 0 0)"),
    "sidebar-foreground": ("oklch(0.145 0 0)", "oklch(0.985 0 0)"),
    "sidebar-primary": ("oklch(0.205 0 0)", "oklch(0.488 0.243 264.376)"),
    "sidebar-primary-foreground": ("oklch(0.985 0 0)", "oklch(0.985 0 0)"),
    "sidebar-accent": ("oklch(0.97 0 0)", "oklch(0.269 0 0)"),
    "sidebar-accent-foreground": ("oklch(0.205 0 0)", "oklch(0.985 0 0)"),
    "sidebar-border": ("oklch(0.922 0 0)", "oklch(1 0 0 / 10%)"),
    "sidebar-ring": ("oklch(0.708 0 0)", "oklch(0.556 0 0)"),
}


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _junit_cases(path: Path):
    assert path.is_file(), f"missing test report: {path}"
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    assert cases, f"test report contains no cases: {path}"
    for case in cases:
        assert case.find("failure") is None, ET.tostring(case, encoding="unicode")
        assert case.find("error") is None, ET.tostring(case, encoding="unicode")
        assert case.find("skipped") is None, ET.tostring(case, encoding="unicode")
    return [" ".join(case.attrib.values()).casefold() for case in cases]


def _theme_block(css: str, selector: str):
    match = re.search(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", css)
    assert match, f"missing {selector} theme tokens"
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", match.group(1)))


def _stop_process_group(process):
    if process.poll() is not None:
        return process.communicate()
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        return process.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.communicate()


@pytest.fixture(scope="module")
def live_starter(tmp_path_factory):
    if not shutil.which("node"):
        pytest.skip("Node.js is required for the starter smoke run")
    if not shutil.which("docker"):
        pytest.skip("Docker is required for the starter smoke run")
    if sys.platform == "win32":
        pytest.skip("The starter smoke run uses Linux containers")
    context = subprocess.run(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        capture_output=True, text=True, timeout=30,
    )
    if context.returncode:
        pytest.skip("A Docker daemon is required for the starter smoke run")
    tools = subprocess.run(
        ["docker", "info", "--format", "{{json .ClientInfo.Plugins}}"],
        capture_output=True, text=True, timeout=30,
    )
    if tools.returncode:
        pytest.skip("A Docker daemon is required for the starter smoke run")

    host_config = tmp_path_factory.mktemp("starter-host-config")
    npm_userconfig = host_config / "npmrc"
    npm_userconfig.write_text("", encoding="utf-8")
    npm_cache = host_config / "npm-cache"
    npm_cache.mkdir()
    docker_config = host_config / "docker-config"
    docker_config.mkdir()
    (docker_config / "config.json").write_text("{}", encoding="utf-8")
    # Keep installed CLI tools available without inheriting registry credentials or settings.
    plugins = docker_config / "cli-plugins"
    plugins.mkdir()
    for plugin in json.loads(tools.stdout):
        if plugin.get("Name") in ("compose", "buildx") and isinstance(plugin.get("Path"), str):
            (plugins / f"docker-{plugin['Name']}").symlink_to(Path(plugin["Path"]).resolve())

    env = os.environ.copy()
    for name in tuple(env):
        if name.lower().startswith(("npm_config_", "docker_")):
            env.pop(name)
    env.update({
        "NPM_CONFIG_USERCONFIG": str(npm_userconfig),
        "NPM_CONFIG_CACHE": str(npm_cache),
        "PLAYWRIGHT_BROWSERS_PATH": str(host_config / "browsers"),
        "DOCKER_CONFIG": str(docker_config),
        "DOCKER_HOST": context.stdout.strip(),
    })
    docker = subprocess.run(["docker", "info"], capture_output=True, text=True,
                            timeout=30, env=env)
    if docker.returncode:
        pytest.skip("A Docker daemon is required for the starter smoke run")

    copy = tmp_path_factory.mktemp("starter-smoke")
    shutil.copytree(
        STARTER, copy, dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("node_modules", "dist", ".nx", "reports",
                                      "test-results", "playwright-report", "coverage"),
    )
    shutil.copyfile(ROOT / "src" / "forge" / "templates" / "skeleton" / "Dockerfile",
                    copy / "Dockerfile")
    shutil.copyfile(ROOT / "src" / "forge" / "templates" / "skeleton" / ".dockerignore",
                    copy / ".dockerignore")
    project = "starter-smoke-" + uuid.uuid4().hex[:12]
    env.update({"PWD": str(copy), "FORGE_STARTER_LIVE": "1", "COMPOSE_PROJECT_NAME": project})
    process = None
    try:
        process = subprocess.Popen(
            ["node", Path("scripts") / "test.mjs"], cwd=copy, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            output, _ = process.communicate(timeout=1800)
        except subprocess.TimeoutExpired:
            output, _ = _stop_process_group(process)
            pytest.fail(f"starter smoke command timed out after 1800 seconds\n{output}")
        assert process.returncode == 0, output
        assert "Cached API build and lint after web build passed" in output, output
        assert "GET /health returned 200" in output, output
        return {
            "api": _junit_cases(copy / "test-results" / "api.xml"),
            "browser": _junit_cases(copy / "test-results" / "browser.xml"),
        }
    finally:
        if process is not None and process.poll() is None:
            _stop_process_group(process)
        cleanup = subprocess.run(
            ["docker", "compose", "-f", "compose.test.yml", "down", "--volumes",
             "--remove-orphans"], cwd=copy, env=env, capture_output=True, text=True,
            timeout=180)
        assert cleanup.returncode == 0, cleanup.stdout + cleanup.stderr


def _require_cases(cases, expected):
    for name in expected:
        assert any(name.casefold() in case for case in cases), (
            f"test report did not show a passing case named {name!r}; cases: {cases}")


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_1_the_starter_is_a_runnable_stack(request):
    required_files = (
        Path(".env.example"), Path("package.json"), Path("package-lock.json"), Path("nx.json"),
        Path("compose.test.yml"), Path("scripts") / "test.mjs",
        Path("scripts") / "test-build.mjs", Path("README.md"),
        Path("apps") / "api" / "prisma" / "schema.prisma",
        Path("apps") / "api" / "test" / "api.e2e-spec.ts",
        Path("apps") / "api" / "vitest.config.ts",
        Path("apps") / "web" / "e2e" / "starter-shell.spec.ts",
        Path("apps") / "web" / "playwright.config.ts",
        Path("apps") / "web" / "vitest.config.ts",
    )
    for rel in required_files:
        assert (STARTER / rel).is_file(), rel
    for rel in (Path("apps") / "web", Path("apps") / "api", Path("libs") / "shared"):
        assert (STARTER / rel).is_dir(), rel

    package = _json(STARTER / "package.json")
    assert "workspaces" not in package, "the starter uses Nx project targets"
    lock = _json(STARTER / "package-lock.json")
    assert "nx" in package.get("devDependencies", {})
    assert package.get("scripts", {}).get("build")
    assert package.get("scripts", {}).get("start:prod")
    assert package.get("scripts", {}).get("test")
    for group in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, version in package.get(group, {}).items():
            assert isinstance(version, str) and PIN.fullmatch(version), (name, version)
    dependencies = package.get("dependencies", {}) | package.get("devDependencies", {})
    for name, version in PINNED_PACKAGES.items():
        assert dependencies.get(name) == version, (name, dependencies.get(name), version)
    lock_root = lock["packages"][""]
    for group in ("dependencies", "devDependencies", "optionalDependencies"):
        assert lock_root.get(group, {}) == package.get(group, {})
    for name, version in PINNED_PACKAGES.items():
        lock_path = (Path("node_modules") / name).as_posix()
        assert lock["packages"][lock_path]["version"] == version
    # Axe's peer must use the same Page type and browser protocol as the test runner.
    for path, entry in lock["packages"].items():
        if path.endswith("/playwright-core"):
            assert entry["version"] == dependencies["@playwright/test"]

    command = f"node {(Path('scripts') / 'test.mjs').as_posix()}"
    assert command in (STARTER / "README.md").read_text(encoding="utf-8")
    dockerfile = (ROOT / "src" / "forge" / "templates" / "skeleton" / "Dockerfile").read_text(
        encoding="utf-8")
    assert "RUN npm ci && npm run build" in dockerfile
    assert "WORKDIR /app" in dockerfile
    assert "npx prisma migrate deploy" in dockerfile
    assert "exec npm run start:prod" in dockerfile
    assert "--workspace" not in dockerfile

    if LIVE:
        _require_cases(request.getfixturevalue("live_starter")["api"], API_SECURITY_TESTS)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_2_the_starter_shell_comes_from_shadcn_components(request):
    web = STARTER / "apps" / "web" / "src"
    ui = web / "components" / "ui"
    shell_file = web / "components" / "app-shell.tsx"
    assert shell_file.is_file(), "the app shell is missing"
    shell = shell_file.read_text(encoding="utf-8")
    assert "SidebarProvider" in shell
    assert 'collapsible="icon"' in shell
    assert "SidebarTrigger" in shell
    assert "SidebarRail" in shell

    router = web / "app.tsx"
    assert router.is_file(), "the React Router configuration is missing"
    routes = router.read_text(encoding="utf-8")
    for route in ("/sign-in", "/sign-up", "/forgot-password", "/reset-password",
                  "/settings", "/projects", "*"):
        assert route in routes, route

    ui_stems = {path.stem for path in ui.rglob("*.tsx")}
    assert ui_stems, "shadcn/ui source components are missing"
    duplicates = [
        path for path in web.rglob("*.tsx")
        if not path.is_relative_to(ui) and path.stem in ui_stems
    ]
    assert not duplicates, f"shadcn components were copied outside components/ui: {duplicates}"

    hooks = STARTER / "apps" / "web" / "src" / "features" / "projects" / "hooks"
    assert hooks.is_dir(), "project hooks must live in the projects feature folder"

    css = (web / "index.css").read_text(encoding="utf-8")
    light = _theme_block(css, ":root")
    dark = _theme_block(css, ".dark")
    system_font = _theme_block(css, "@theme inline")
    assert light.get("radius") == "0.625rem"
    assert system_font.get("font-sans") == (
        'ui-sans-serif, system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", '
        '"Segoe UI Symbol", "Noto Color Emoji"')
    for token, (light_value, dark_value) in NEUTRAL_THEME.items():
        assert light.get(token) == light_value, (token, light.get(token), light_value)
        assert dark.get(token) == dark_value, (token, dark.get(token), dark_value)

    if LIVE:
        _require_cases(request.getfixturevalue("live_starter")["browser"], BROWSER_FLOWS)
