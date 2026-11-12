"""The guide moves an existing Python app off committed API types, and the worker brief carries the steps."""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401 (the shared fixture unsynced_up builds on)
from test_feature_command import ADOPTED
from test_feature_remove import SYNCED, _flat
from test_task import story
from test_upgrade_command import NAME as UPGRADE, RELEASE, unsynced_up  # noqa: F401
from test_worker import calls, install_claude
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "FORGE-GENCOMMIT-1"
CONTRACT = "libs/shared/api-types/openapi.json"
TYPES = "libs/shared/api-types/src/api-types.ts"
REMOVE = f"git rm --cached --ignore-unmatch {CONTRACT} {TYPES}"
# The steps are the same sentences in the guide and in the worker brief.
STEPS = [
    f"Run `{REMOVE}`. This removes only these two files from git's index, whichever of them is "
    "still tracked, and keeps them on disk. It does not stop when one of them is already "
    "untracked. Do not clean the work tree and use no path pattern.",
    "Add both paths to `.gitignore`.",
    "Start the `typecheck` script in `package.json` with `corepack pnpm run api-types && `.",
    "If `scripts/test.mjs` picks parts, run `api-types` before any `tsc` call, and let a change "
    "under `apps/api/app/` select the web part too, as the new starter does.",
    "Remove the two paths from the scope of planned parts. Leave their `After` links as they are: "
    "parts that add a module still share other files, such as `apps/api/app/main.py`.",
    "Delete these two files on disk, by their two full paths and nothing else (a file that is not "
    "there needs nothing). This is safe: `api-types` writes both files from the API code every "
    "time, and nothing else is in them. Then run the repo's test command. It must pass and must "
    "make both files again. Forge's local test runs in this checkout, so this step is what proves "
    "that a fresh copy works.",
    "A branch that changed one or both files gets a modify/delete conflict when it merges the "
    f"default branch. Run `{REMOVE}`: it keeps the removal for whichever of the two paths is still "
    "in the index, and does not stop on a path that is already gone. Then run its tests.",
]
GUIDE_ONLY = [
    f"New Python starter apps keep the API contract file (`{CONTRACT}`) and its types "
    f"(`{TYPES}`) out of git.",
    "Existing apps keep theirs on upgrade and sync; until an app has moved over, a part that "
    "changes the API lists both files in its scope as today, so Forge still sees that those parts "
    "change the same files.",
    "When you write the next plan or fix for a Python app and `git ls-files` lists one or both of "
    "those paths, offer the owner the move-over fix in one line, before more API parts; on a yes, "
    "start one fix with `forge start`.",
]


def _python_release_over_adopted(repo) -> None:
    shutil.copytree(ADOPTED, repo.path, dirs_exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / "starter.tar"
        subprocess.run(["git", "archive", "--format=tar", f"--output={archive}",
                        "9d8defe842c8ecff983a5bc00e60786613840df5:src/forge/templates/starter-python"],
                       cwd=ROOT, check=True, capture_output=True)
        extracted = Path(directory) / "starter"
        shutil.unpack_archive(archive, extracted)
        shutil.copytree(extracted, repo.path, dirs_exist_ok=True)


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_4_an_earlier_python_app_keeps_its_committed_files(unsynced_up):
    up = unsynced_up
    repo, no_hooks = up.repo, f"core.hooksPath={(up.tmp / 'no-hooks').as_posix()}"
    _python_release_over_adopted(repo)
    before = {rel: (repo.path / rel).read_bytes() for rel in (CONTRACT, TYPES, "package.json",
                                                              "scripts/test.mjs", "scripts/affected.mjs")}
    repo.git("switch", "-q", "-c", "adoption")
    repo.git("add", "-A")
    repo.git("-c", no_hooks, "commit", "-q", "-m", "The earlier Python app")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "adoption")
    repo.git("-c", no_hooks, "push", "-q", "origin", "main")
    adopted = repo.git("rev-parse", "HEAD")
    upgraded = up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    repo.git("merge", "-q", "--ff-only", f"fix/{UPGRADE}")
    repo.git("-c", no_hooks, "push", "-q", "origin", "main")
    repo.git("switch", "-q", "-c", "fix/gencommit-sync")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    changed = sorted(set(repo.git("diff", "--name-only", adopted).splitlines() + repo.git(
        "ls-files", "--others", "--exclude-standard").splitlines()))
    # Upgrade and sync write Forge's own files and .gitignore, and no app file or product document.
    assert not [p for p in changed if not SYNCED.fullmatch(p) and p != ".gitignore"], changed
    assert not [p for p in changed if p.startswith(("apps/", "libs/"))], changed
    for rel, content in before.items():
        assert (repo.path / rel).read_bytes() == content, rel
    tracked = repo.git("ls-files").splitlines()
    assert CONTRACT in tracked and TYPES in tracked
    old = set(repo.git("show", f"{adopted}:.gitignore").splitlines())
    new = set((repo.path / ".gitignore").read_text("utf-8").splitlines())
    assert new - old <= {"forge.local.toml"}, new - old


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_5_the_guide_and_the_brief_give_the_move_over_steps(client):
    for host in (".claude", ".codex"):
        skill = _flat((client.path / host / "skills/forge/SKILL.md").read_text("utf-8"))
        for piece in GUIDE_ONLY + STEPS:
            assert _flat(piece) in skill, (host, piece[:60])
        start = skill.index(_flat(GUIDE_ONLY[0]))
        assert "git clean" not in skill[start:skill.index(_flat(STEPS[-1])) + len(_flat(STEPS[-1]))]

    log = install_claude(client)
    story(client)
    assert client.forge("task", "start", "BOARD/API").returncode == 0
    worked = client.forge("work", "BOARD/API")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = _flat(calls(log)[-1]["brief"])
    for piece in STEPS:
        assert _flat(piece) in brief, piece[:60]
