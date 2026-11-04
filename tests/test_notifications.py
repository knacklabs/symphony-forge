"""The TypeScript waiting-list API ships to new apps and leaves adopted app code alone."""
import json
import shutil
from pathlib import Path

import pytest

from test_setup import _fresh_client
from test_starter_tree import LIVE, _require_cases, live_run

STORY = "FORGE-AFTERDEMO-1"
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "earlier adopted"])
def test_1_a_waiting_record_shows_in_the_persons_list(
    repo, gh, tmp_path, starter, tmp_path_factory,
):
    # Audit: init must deliver the notifications API files, while sync must preserve an app
    # adopted before this release. Runtime behavior belongs to the copied API e2e case below;
    # no existing init/sync or API test covers this feature. These are the real Forge boundaries.
    if starter == "earlier adopted":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        historical_files = {
            Path("apps/api/src/legacy.ts"): "export const legacyApi = true;\n",
            Path("libs/projects/server/src/legacy.ts"): "export const legacyProjectService = true;\n",
        }
        for relative, content in historical_files.items():
            target = repo.path / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        before = {
            path.relative_to(repo.path): path.read_bytes()
            for folder in ("apps", "libs")
            for path in (repo.path / folder).rglob("*")
            if path.is_file()
        }
        assert all(relative in before for relative in historical_files)
        repo.git("checkout", "-b", "fix/notifications-sync")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        after = {
            path.relative_to(repo.path): path.read_bytes()
            for folder in ("apps", "libs")
            for path in (repo.path / folder).rglob("*")
            if path.is_file()
        }
        assert after == before
        return

    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    expected = (
        Path("apps/api/prisma/schema/notifications.prisma"),
        Path("apps/api/test/notifications.e2e-spec.ts"),
    )
    for relative in expected:
        assert (client / relative).is_file(), relative
    assert (client / "libs/notifications").is_dir()
    migrations = client / "apps/api/prisma/migrations"
    assert any(
        path.is_dir() and path.name.endswith("_notifications") and (path / "migration.sql").is_file()
        for path in migrations.iterdir()
    )

    if LIVE:
        _require_cases(live_run(tmp_path_factory)["api"], (
            "a person sees the records that wait for them, with a count",
        ))
