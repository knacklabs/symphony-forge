"""Delivered package cache contracts, through init and sync.

Audit: absent cache inputs cause repeated downloads; bootstrap coverage checks
versions only. Public workflow inputs need no production test seam.
"""
import json
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client

STORY = "FIX-EVERY-CLIENT-CI-RUN-DOWNLOADS-PACKAGES-A"


@pytest.mark.parametrize("kind", ["typescript", "python"])
def test_1_new_client_reuses_packages_and_dependency_layers(repo, gh, tmp_path, kind):
    args = ("--starter", "python") if kind == "python" else ("--starter",)
    client, result = _fresh_client(repo, gh, tmp_path, *args)
    assert result.returncode == 0, result.stdout + result.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    for job in (workflow.split("\n  tests:\n")[1].split("\n  forge-pr-check:\n")[0],
                workflow.split("\n  full-suite:\n")[1].split("\n  full-suite-result:\n")[0]):
        assert "cache: pnpm" in job
        assert "cache-dependency-path: pnpm-lock.yaml" in job
        assert job.index("pnpm/action-setup@") < job.index("actions/setup-node@")
        assert "enable-cache: true" in job
    # The Dockerfile is a public build contract: source must not be an install
    # layer input. Existing smoke tests own actual builds, with no extra build.
    docker = (client / "Dockerfile").read_text("utf-8").split("FROM python:")[0]
    install = docker.index("RUN corepack pnpm install --frozen-lockfile")
    before, after = docker[:install], docker[install:]
    assert "COPY . ." not in before and "COPY --chown=node:node . ." not in before
    for manifest in client.rglob("package.json"):
        if "node_modules" not in manifest.parts:
            assert manifest.relative_to(client).as_posix() in before
    assert "pnpm-lock.yaml" in before and "pnpm-workspace.yaml" in before
    assert "COPY" in after and "corepack pnpm run build" in after


def test_2_earlier_adopted_client_sync_adds_cache_and_keeps_app_dockerfile(repo):
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    repo.git("checkout", "-qb", "fix/cache-packages")
    current = repo.forge("--version").stdout.split()[-1]
    config = (repo.path / "forge.toml").read_text("utf-8").replace("v1.2.2", current)
    repo.write("forge.toml", config)
    repo.write("package.json", json.dumps({"scripts": {"test": "npm test"}}))
    repo.write("package-lock.json", "{}\n")
    original = "FROM node:24\nCOPY . .\nRUN npm ci\n"
    repo.write("Dockerfile", original)
    result = repo.forge("sync")
    assert result.returncode == 0, result.stdout + result.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text("utf-8")
    assert "cache: npm" in workflow and "cache-dependency-path: package-lock.json" in workflow
    assert "enable-cache: true" in workflow
    assert (repo.path / "Dockerfile").read_text("utf-8") == original
