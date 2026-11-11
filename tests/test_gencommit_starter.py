"""Generated API files stay out of git in new apps; apps adopted earlier keep what they have."""
import fnmatch
import json
import posixpath
import re
import subprocess

import pytest

from conftest import ROOT
from test_mcp import _adopted_files_after_sync
from test_setup import _fresh_client

STORY = "FORGE-GENCOMMIT-1"
GENERATED = ("libs/shared/api-types/openapi.json", "libs/shared/api-types/src/api-types.ts")
CONVENTIONS = ROOT / "src" / "forge" / "templates" / "conventions"
STACK_RULE = (
    "A file that a script makes from the app's code every time (the Prisma client, an API contract and the "
    "types made from it) stays out of git. It goes in `.gitignore`, and the type check and test scripts that "
    "need it run its script first, as `prisma generate` runs first in `build` and `typecheck`.",
    "Migrations and lock files are records: commit them.",
    "An app that already commits such a file keeps doing so until a fix moves it out.",
)
OUTPUT_FLAG = re.compile(r"(?:^|\s)(?:-o|--output|--outDir|--out-dir)[ =](\S+)")


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


def _generator_outputs(client, tracked):
    """Where the starter's own generators write: Prisma, tsc, nx outputs and output flags in scripts."""
    found = {"node_modules"}  # the Prisma client goes here unless a generator block names an output
    for path in tracked:
        folder, name = posixpath.split(path)
        if not name.endswith((".json", ".prisma")):
            continue
        text = (client / path).read_text("utf-8")
        commands = []
        if name.endswith(".prisma"):
            found.update(posixpath.normpath(posixpath.join(folder, out)) for out in
                         re.findall(r"generator\s+\w+\s*\{[^}]*?output\s*=\s*\"([^\"]+)\"", text))
        elif name.startswith("tsconfig"):
            options = json.loads(text).get("compilerOptions", {})
            found.update(posixpath.normpath(posixpath.join(folder, options[key]))
                         for key in ("outDir", "tsBuildInfoFile") if key in options)
        elif name == "project.json":
            for target in json.loads(text).get("targets", {}).values():
                found.update(out.replace("{workspaceRoot}/", "").replace("{projectRoot}", folder)
                             for out in target.get("outputs", []))
                commands.append(target.get("options", {}).get("command", ""))
        elif name == "package.json":
            commands.extend(json.loads(text).get("scripts", {}).values())
        found.update(posixpath.normpath(posixpath.join(folder, out))
                     for command in commands for out in OUTPUT_FLAG.findall(command))
    return found


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
    outputs = _generator_outputs(client, tracked)
    assert {"node_modules", "apps/api/dist", "libs/core/server/dist"} <= outputs, outputs
    assert not [path for path in tracked
                if "/node_modules/" in f"/{path}" or ".gen." in path
                or (path.rsplit("/", 1)[-1].startswith("openapi") and path.endswith(".json"))
                or any(fnmatch.fnmatchcase(path, out) or fnmatch.fnmatchcase(path, f"{out}/*") for out in outputs)]
    # Records stay in git: the lock file and the migrations.
    assert "pnpm-lock.yaml" in tracked and any(
        path.startswith("apps/api/prisma/migrations/") and path.endswith("/migration.sql") for path in tracked)
    scripts = json.loads((client / "package.json").read_text("utf-8"))["scripts"]
    assert scripts["build"].startswith("prisma generate") and scripts["typecheck"].startswith("prisma generate")
    stack_page = " ".join((CONVENTIONS / "stack.md").read_text("utf-8").split())
    for sentence in STACK_RULE:
        assert sentence in stack_page, sentence
    python_page = (CONVENTIONS / "python.md").read_text("utf-8")
    assert "Git ignores" in python_page and "do not list them in a part's scope" in python_page
