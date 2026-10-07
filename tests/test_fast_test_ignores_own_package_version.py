"""Release lock changes narrow real pytest; dependency changes still run everything.

The old contract treated every lock change as shared. These command regressions
protect the exception without mocking selection or pytest.
"""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import (  # noqa: F401 (pytest fixtures)
    env, unsynced_up, _repo_adopted_on_the_previous_release,
)

STORY = "FIX-EVERY-VERSION-BUMP-RE-RUNS-THE-WHOLE-TES"


def lockfile(kind, own="1.0", dependency="2.0", *, source="."):
    if kind == "package-lock.json":
        return json.dumps({"name": "shop", "version": own, "lockfileVersion": 3,
                           "packages": {"": {"name": "shop", "version": own},
                                        "node_modules/library": {"version": dependency,
                                                                  "integrity": "unchanged"}}})
    if kind == "Pipfile.lock":
        return json.dumps({"_meta": {"hash": {"sha256": "unchanged"}},
                           "default": {"shop": {"path": source, "editable": True,
                                                "version": "==" + own},
                                       "library": {"version": "==" + dependency,
                                                   "hashes": ["sha256:unchanged"]}}, "develop": {}})
    if kind == "uv.lock":
        return ('version = 1\n[[package]]\nname = "shop"\n'
                f'version = "{own}"\nsource = {{ editable = "{source}" }}\n'
                '[[package]]\nname = "library"\n'
                f'version = "{dependency}"\nsource = {{ registry = "https://example.org/unchanged" }}\n')
    return ('[[package]]\nname = "shop"\n'
            f'version = "{own}"\n[package.source]\ntype = "directory"\nurl = "{source}"\n'
            '[[package]]\nname = "library"\n'
            f'version = "{dependency}"\n[metadata]\ncontent-hash = "unchanged"\n')


def exercise(repo, kind, launcher=None, *, dependency=False, source=".", extra=False):
    settings_path = repo.path / "forge.toml"
    settings = settings_path.read_text("utf-8") if settings_path.exists() else ""
    previous = tomllib.loads(settings).get("test")
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    repo.write("forge.toml", settings.replace("test = " + json.dumps(previous),
                                             "test = " + json.dumps(command))
               if previous is not None else settings + "test = " + json.dumps(command) + "\n")
    repo.write("pyproject.toml", '[project]\nname = "shop"\nversion = "1.0"\n')
    repo.write("package.json", json.dumps({"name": "shop", "version": "1.0"}))
    repo.write(kind, lockfile(kind, source=source))
    # An exempt lock bump does not select lock readers: only the changed Python module does.
    repo.write("src/shop/prices.py", "PRICE = 1\n")
    repo.write("tests/test_release.py", "# shop/prices.py\n"
               "def test_release():\n    assert True\n")
    repo.write("tests/test_unrelated.py", "def test_unrelated():\n    assert True\n")
    repo.git("add", "-A")
    repo.git("-c", f"core.hooksPath={repo.path / '.git/no-hooks'}", "commit", "-qm", "Set up release tests")
    base = repo.git("rev-parse", "HEAD")
    changed = lockfile(kind, own="1.1", dependency="2.1" if dependency else "2.0", source=source)
    if extra:
        changed = changed.replace("unchanged", "changed")
    repo.write(kind, changed)
    repo.write("src/shop/prices.py", "PRICE = 2\n")
    repo.git("add", kind, "src/shop/prices.py")
    repo.git("-c", f"core.hooksPath={repo.path / '.git/no-hooks'}", "commit", "-qm", "Bump version")
    result = subprocess.run([sys.executable, str(launcher or repo.bin / "forge"),
                             "test", "--pytest", base], cwd=repo.path,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    full = dependency or source != "." or extra
    assert ("2 passed" if full else "1 passed") in result.stdout, result.stdout
    assert ("Shared test inputs changed" if full else "Related tests: tests/test_release.py") in result.stdout


@pytest.mark.parametrize("kind", ["uv.lock", "poetry.lock", "Pipfile.lock", "package-lock.json"])
@pytest.mark.parametrize("case", ["own-version", "dependency", "other-fields"])
def test_1_only_own_package_versions_are_exempt_from_shared_inputs(repo, kind, case):
    # A dependency version or hash/source change alongside a release must stay shared.
    exercise(repo, kind, dependency=case == "dependency", extra=case == "other-fields")


@pytest.mark.parametrize("kind", ["uv.lock", "poetry.lock", "Pipfile.lock"])
def test_2_a_local_dependency_is_not_the_repos_own_package(repo, kind):
    exercise(repo, kind, source="../other")


def test_3_new_clients_get_version_only_lock_selection(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    result = repo.forge("init", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    repo.path = client
    exercise(repo, "uv.lock")


def test_4_earlier_adopted_clients_get_version_only_lock_selection(unsynced_up):
    _repo_adopted_on_the_previous_release(unsynced_up)
    repo = unsynced_up.repo
    repo.path = unsynced_up.folder
    exercise(repo, "uv.lock", launcher=unsynced_up.tmp / "uvbin/forge")
