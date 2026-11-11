"""Generated API files stay out of git in new apps; apps adopted earlier keep what they have."""
import json
import subprocess

import pytest

from conftest import ROOT
from test_mcp import _adopted_files_after_sync
from test_setup import _fresh_client

STORY = "FORGE-GENCOMMIT-1"
GENERATED = ("libs/shared/api-types/openapi.json", "libs/shared/api-types/src/api-types.ts")
CONVENTIONS = ROOT / "src" / "forge" / "templates" / "conventions"


@pytest.mark.platform
def test_1_a_new_python_app_does_not_commit_its_generated_api_files(repo, gh, tmp_path):
    # Contract: init ships no generated contract or types, ignores them, and the type check makes
    # them first. Real init and git own this boundary; the live smoke run proves a fresh copy passes.
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "python")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    tracked = set(repo.git("ls-files", cwd=client).splitlines())
    for path in GENERATED:
        assert path not in tracked and not (client / path).exists(), path
        ignored = subprocess.run(["git", "check-ignore", "-q", path], cwd=client)
        assert ignored.returncode == 0, path
    scripts = json.loads((client / "package.json").read_text("utf-8"))["scripts"]
    assert scripts["typecheck"].startswith("corepack pnpm run api-types && ")
    assert "api-types" not in scripts["build"]


@pytest.mark.parametrize("stack", ["typescript", "earlier adopted"])
def test_3_generated_files_stay_out_of_git_for_both_stacks(repo, gh, tmp_path, stack):
    # Contract: the stack page states the rule, the Python page matches it, and the TypeScript
    # starter already follows it. An earlier adopted app keeps every file on sync.
    if stack == "earlier adopted":
        before, after = _adopted_files_after_sync(repo)
        assert after == before
        return
    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    tracked = repo.git("ls-files", cwd=client).splitlines()
    assert not [path for path in tracked
                if "/node_modules/" in f"/{path}" or ".gen." in path
                or (path.rsplit("/", 1)[-1].startswith("openapi") and path.endswith(".json"))]
    scripts = json.loads((client / "package.json").read_text("utf-8"))["scripts"]
    assert scripts["build"].startswith("prisma generate") and scripts["typecheck"].startswith("prisma generate")
    stack_page = (CONVENTIONS / "stack.md").read_text("utf-8")
    assert "stays out of git" in stack_page and "Migrations and\nlock files are records" in stack_page
    python_page = (CONVENTIONS / "python.md").read_text("utf-8")
    assert "Git ignores" in python_page and "do not list them in a part's scope" in python_page
