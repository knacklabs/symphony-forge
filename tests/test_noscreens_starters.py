"""A new app keeps its API and build setup without shipping screen files."""
import io
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest

from test_defaults_formats import PYTHON_CSV_API_CASES
from test_defaults_organisations import PYTHON_ORGANISATION_API_CASES
from test_python_starter import API_SECURITY_TESTS as PYTHON_API_SECURITY_TESTS
from test_starter_tree import (
    API_SECURITY_TESTS,
    API_ZOD_CASES,
    BROWSER_FLOWS,
    LIVE,
    _require_cases,
    live_python_run,
    live_run,
)
from test_setup import _fresh_client
from test_app_constitution import _fixture_git

STORY = "FORGE-NOSCREENS-1"
ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "src/forge/templates/starter"
PREVIOUS_STARTER_REF = "v1.2.25"


def _assert_no_screens(client: Path) -> None:
    web = client / "apps/web"
    assert not list(web.rglob("*-page.tsx"))
    assert not list(web.rglob("pages"))
    assert not list(web.rglob("app-shell.tsx"))
    assert not (web / "src/app.tsx").exists()
    for module in ("auth", "history", "organisations", "projects"):
        assert not (client / "libs" / module / "web").exists()
    for path in (
        "libs/shared/ui/src/components/auth-page-frame.tsx",
        "libs/core/web/src/route-error-page.tsx",
        "libs/core/web/src/agent-access-dialog.tsx",
    ):
        assert not (client / path).exists()


def _earlier_app(repo, gh, tmp_path):
    """Build an earlier starter app from its release tree, then upgrade it with Forge."""
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    archive = subprocess.run(
        ["git", "archive", "--format=tar", PREVIOUS_STARTER_REF,
         "src/forge/templates/starter"],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout
    old_root = tmp_path / "earlier-starter"
    old_root.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        bundle.extractall(old_root)
    old_starter = old_root / "src/forge/templates/starter"
    old_files = {
        path.relative_to(old_starter)
        for path in old_starter.rglob("*") if path.is_file()
    }
    current_files = {
        path.relative_to(STARTER)
        for path in STARTER.rglob("*") if path.is_file()
    }
    for relative in current_files - old_files:
        (client / relative).unlink(missing_ok=True)
    for relative in old_files:
        destination = client / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old_starter / relative, destination)
    assert (client / "apps/web/src/app.tsx").is_file()
    repo.git("checkout", "-q", "-b", "fix/noscreens-sync", cwd=client)
    repo.git("add", "-A", cwd=client)
    # This restores an already-adopted app; it is fixture setup, not a new Forge change.
    _fixture_git(repo, tmp_path, "commit", "-qm", "Build earlier starter app", cwd=client)
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    changed = repo.git("status", "--porcelain=v1", "-uall", cwd=client).splitlines()
    app_changes = [line for line in changed if Path(line[3:]).parts[0] in {"apps", "libs"}]
    lock_changes = [line for line in changed if Path(line[3:]).name in {
        "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "uv.lock",
    }]
    assert not app_changes + lock_changes, changed
    return client


@pytest.mark.platform
@pytest.mark.parametrize("starter", ["typescript", "python", "earlier adopted"])
def test_1_a_new_app_has_no_screens_and_keeps_its_api(
    repo, gh, tmp_path, starter, tmp_path_factory,
):
    # Audit: init must leave new apps with the API and build-only web setup, and sync must not
    # rewrite app code in an earlier-adopted repo. A screen copied into either starter or an
    # upgrade that edits app files would fail. Existing starter checks do not own this generated
    # tree contract; the live starter tests below use its real API and browser entry points.
    # Forge init and sync are the tested boundary; this needs no production seam.
    if starter == "earlier adopted":
        client = _earlier_app(repo, gh, tmp_path)
        assert (client / "apps/web/src/app.tsx").is_file()
        return

    init_args = ("--starter", "python") if starter == "python" else ("--starter",)
    client, initialized = _fresh_client(repo, gh, tmp_path, *init_args)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    _assert_no_screens(client)
    for path in (
        "apps/web/index.html",
        "apps/web/vite.config.ts",
        "apps/web/playwright.config.ts",
        "apps/web/src/main.tsx",
        "apps/web/src/index.css",
        "apps/web/e2e/served-app.spec.ts",
        "libs/core/web/src/api-client.ts",
        "libs/shared/ui/components.json",
    ):
        assert (client / path).is_file(), path

    if starter == "typescript":
        server_modules = list((STARTER / "libs").glob("*/server"))
        assert server_modules
        for source in server_modules:
            assert (client / source.relative_to(STARTER)).is_dir(), source
    else:
        python_app = ROOT / "src/forge/templates/starter-python/apps/api/app"
        api_modules = [path for path in python_app.iterdir() if path.is_dir()]
        assert api_modules
        for source in api_modules:
            assert (client / "apps/api/app" / source.name).is_dir(), source

    if LIVE:
        live = (live_python_run(tmp_path_factory) if starter == "python"
                else live_run(tmp_path_factory))
        expected_api = (
            PYTHON_API_SECURITY_TESTS + PYTHON_ORGANISATION_API_CASES + PYTHON_CSV_API_CASES
            if starter == "python" else API_SECURITY_TESTS + API_ZOD_CASES
        )
        _require_cases(live["api"], expected_api)
        _require_cases(live["browser"], BROWSER_FLOWS)
