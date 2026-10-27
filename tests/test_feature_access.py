"""Each feature checks its view, create, edit, delete and restore permission on every route."""
import json
import re
import shutil
from pathlib import Path

import pytest

from test_feature_command import (CLIENT_LINE, JOBS_LINE, NOTES_LINE, _run_line, feature_live_run,
                                  require_feature_cases)
from test_setup import _fresh_client
from test_starter_tree import LIVE, STARTER, _require_cases, live_run

pytest_plugins = ("test_python_starter",)

ROOT = Path(__file__).resolve().parents[1]
PYTHON_STARTER = ROOT / "src/forge/templates/starter-python"
TS_CONTROLLER = Path("libs/projects/server/src/projects.controller.ts")
TS_PERMISSIONS = Path("libs/projects/server/src/projects.permissions.ts")
PY_ROUTES = Path("apps/api/app/projects/routes.py")
PY_PERMISSIONS = Path("apps/api/app/projects/permissions.py")
# The permission each projects route needs: (HTTP method, path after /projects).
ROUTE_PERMISSIONS = {
    ("get", ""): "view",
    ("get", "export"): "view",
    ("get", ":id"): "view",
    ("get", ":id/changes"): "view",
    ("post", ""): "create",
    ("put", ":id"): "edit",
    ("delete", ":id"): "delete",
    ("post", ":id/restore"): "restore",
}
FLOWS = (
    "a member does not see the project actions they lack",
    "an admin shows deleted projects and restores one",
)
CASES = {
    "projects-typescript": ("each projects endpoint refuses a member without its permission",
                            "an admin restores a deleted project"),
    "projects-python": ("test_each_projects_endpoint_refuses_a_member_without_its_permission",
                        "test_an_admin_restores_a_deleted_project"),
}


def _typescript_routes(text: str) -> dict[tuple[str, str], list[str]]:
    """Each route method's HTTP verb and path, with the permissions its decorators name."""
    routes = {}
    # Route methods are separated by blank lines; each block holds one method's decorators.
    for block in text.split("\n\n"):
        verb = re.search(r"@(Get|Post|Put|Delete)\((?:'([^']*)')?\)", block)
        if verb:
            path = verb.group(2) or ""
            routes[(verb.group(1).lower(), path)] = re.findall(
                r"@RequirePermission\(\w+\.(\w+)\)", block)
    return routes


def _python_routes(text: str) -> dict[tuple[str, str], list[str]]:
    routes = {}
    for block in re.split(r"\n(?=@router\.)", text):
        verb = re.match(r'@router\.(get|post|put|delete)\(\s*"([^"]*)"', block)
        if verb:
            path = verb.group(2).strip("/").replace("{project_id}", ":id")
            routes[(verb.group(1), path)] = re.findall(
                r"require_permission\(\w+\.(\w+)\)", block)
    return routes


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["projects-typescript", "projects-python", "feature-typescript",
                                     "earlier adopted"])
def test_3_each_feature_checks_its_permissions(repo, gh, tmp_path, starter, request):
    # Audit: a projects route with no permission check, two checks or the wrong permission fails
    # the static check; a guard that lets a member delete or restore, a deleted project shown to
    # a member, or a restore with no history row fails the live cases. The starters' own reports
    # own the behaviour; this test names the cases and checks each route's one permission. Sync
    # must leave an earlier-adopted app's own permissions files and controllers as they are.
    if starter == "earlier adopted":
        # An app adopted on an earlier release that has since edited its own permissions.
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        for path in (TS_CONTROLLER, TS_PERMISSIONS):
            (repo.path / path).parent.mkdir(parents=True, exist_ok=True)
            (repo.path / path).write_text(
                (STARTER / path).read_text("utf-8").replace(
                    "member: ['view', 'create', 'edit']", "member: []"), encoding="utf-8")
        before = {path.relative_to(repo.path): path.read_bytes()
                  for path in (repo.path / "libs").rglob("*") if path.is_file()}
        repo.git("checkout", "-b", "fix/check-permissions-upgrade")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        after = {path.relative_to(repo.path): path.read_bytes()
                 for path in (repo.path / "libs").rglob("*") if path.is_file()}
        assert after == before
        assert "member: []" in (repo.path / TS_PERMISSIONS).read_text("utf-8")
        return

    if starter == "feature-typescript":
        # A feature the command builds names the right permission on each route, and its
        # copied cases pass: notes, whose members get no permission, proves view, create and edit.
        client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        for line in (CLIENT_LINE, JOBS_LINE, NOTES_LINE):
            built = _run_line(repo, client, "bash", line)
            assert built.returncode == 0, built.stdout + built.stderr
        for plural in ("clients", "jobs", "notes"):
            routes = _typescript_routes(
                (client / f"libs/{plural}/server/src/{plural}.controller.ts").read_text("utf-8"))
            assert routes == {route: [permission] for route, permission in ROUTE_PERMISSIONS.items()}
        if LIVE:
            live = feature_live_run(repo, gh, request.getfixturevalue("tmp_path_factory"))
            for plural, one in (("jobs", "job"), ("notes", "note")):
                require_feature_cases(live["api"], f"{plural}.e2e-spec.ts",
                                      (f"each {plural} endpoint refuses a member without its permission",))
                require_feature_cases(live["browser"], f"{plural}.spec.ts",
                                      (f"a member does not see the {one} actions they lack",))
            require_feature_cases(live["api"], "jobs.e2e-spec.ts", ("an admin restores a deleted job",))
            require_feature_cases(live["browser"], "jobs.spec.ts",
                                  ("an admin shows deleted jobs and restores one",))
        return

    typescript = starter == "projects-typescript"
    source = STARTER if typescript else PYTHON_STARTER
    controller, permissions = (TS_CONTROLLER, TS_PERMISSIONS) if typescript else (PY_ROUTES, PY_PERMISSIONS)
    routes = (_typescript_routes if typescript else _python_routes)(
        (source / controller).read_text("utf-8"))
    assert routes == {route: [permission] for route, permission in ROUTE_PERMISSIONS.items()}
    # The one place that maps each role to its permissions: admins all five, members not
    # delete or restore.
    mapping = (source / permissions).read_text("utf-8")
    assert re.search(r"""admin["']?: \[["']view["'], ["']create["'], ["']edit["'], ["']delete["'], ["']restore["']\]""", mapping), mapping
    assert re.search(r"""member["']?: \[["']view["'], ["']create["'], ["']edit["']\]""", mapping), mapping

    client, initialized = _fresh_client(
        repo, gh, tmp_path, "--starter", "react" if typescript else "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert (client / controller).read_bytes() == (source / controller).read_bytes()
    if LIVE:
        live = (live_run(request.getfixturevalue("tmp_path_factory")) if typescript
                else request.getfixturevalue("live_python_starter"))
        _require_cases(live["api"], CASES[starter])
        _require_cases(live["browser"], FLOWS)
