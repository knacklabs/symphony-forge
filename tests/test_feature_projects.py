"""A new starter app's projects have the paged list, the detail screen and the change history."""
import json
import shutil
from pathlib import Path

import pytest

from test_setup import _fresh_client
from test_starter_tree import LIVE, STARTER, _require_cases, live_run

pytest_plugins = ("test_python_starter",)

STORY = "FORGE-FEATURE-1"
ROOT = Path(__file__).resolve().parents[1]
PYTHON_STARTER = ROOT / "src/forge/templates/starter-python"
FLOWS = (
    "a reloaded projects list link keeps its search, filters and page",
    "create, view, edit, and delete a project",
    "a project's detail screen shows its recent changes",
)
CASES = {
    "typescript": (
        STARTER,
        (Path("apps/api/test/projects.e2e-spec.ts"), Path("apps/web/e2e/projects.spec.ts")),
        ("pages projects with next and previous cursors", "filters projects by search and filters",
         "records each project change in the change history"),
    ),
    "python": (
        PYTHON_STARTER,
        (Path("apps/api/tests/test_projects.py"),),
        ("test_pages_projects_with_next_and_previous_cursors",
         "test_filters_projects_by_search_and_filters",
         "test_records_each_project_change_in_the_change_history"),
    ),
}


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python", "earlier adopted"])
def test_5_projects_have_the_list_detail_and_history(repo, gh, tmp_path, starter, request):
    # Audit: init must ship each starter's projects cases, and the live run must pass them through
    # the real API, database and browser. A dropped test file, a list that pages by number or a
    # list link that forgets its search would fail here, and so would a project change that
    # writes no Change history row or a detail screen without its recent changes. The live
    # starter reports own the behaviour; this test names the cases. Sync must leave an adopted
    # app's files alone.
    if starter == "earlier adopted":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        page = repo.path / "libs/projects/web/src/pages/projects-page.tsx"
        page.parent.mkdir(parents=True)
        page.write_text("export function ProjectsPage() { return null; }\n", encoding="utf-8")
        before = {path.relative_to(repo.path): path.read_bytes()
                  for path in (repo.path / "libs").rglob("*") if path.is_file()}
        repo.git("checkout", "-b", "fix/check-projects-upgrade")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        after = {path.relative_to(repo.path): path.read_bytes()
                 for path in (repo.path / "libs").rglob("*") if path.is_file()}
        assert after == before
        return

    source, case_files, api_cases = CASES[starter]
    client, initialized = _fresh_client(
        repo, gh, tmp_path, "--starter", "react" if starter == "typescript" else "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    for case_file in case_files:
        assert (source / case_file).is_file(), case_file
        assert (client / case_file).read_bytes() == (source / case_file).read_bytes()
    if LIVE:
        live = (live_run(request.getfixturevalue("tmp_path_factory")) if starter == "typescript"
                else request.getfixturevalue("live_python_starter"))
        _require_cases(live["api"], api_cases)
        _require_cases(live["browser"], FLOWS)
