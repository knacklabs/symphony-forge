"""Delivered package cache contracts, through init and sync.

Audit: absent cache inputs cause repeated downloads; bootstrap coverage checks
versions only. Public workflow inputs need no production test seam.
"""
import json
import shlex
import shutil
import subprocess

import pytest

from conftest import ROOT
from test_setup import _fresh_client

STORY = "FIX-EVERY-CLIENT-CI-RUN-DOWNLOADS-PACKAGES-A"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("kind", ["typescript", "python"])
def test_1_new_client_reuses_packages_and_dependency_layers(repo, gh, tmp_path, kind):
    args = ("--starter", "python") if kind == "python" else ("--starter",)
    client, result = _fresh_client(repo, gh, tmp_path, *args)
    assert result.returncode == 0, result.stdout + result.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    for job in (workflow.split("\n  tests:\n")[1].split("\n  forge-pr-check:\n")[0],
                workflow.split("\n  full-suite:\n")[1].split("\n  full-suite-result:\n")[0]):
        assert "actions/cache@v4" in job
        assert "pnpm/action-setup@" not in job
        assert "cache: pnpm" not in job
        assert "hashFiles('pnpm-lock.yaml')" in job
        for store in ("~/.local/share/pnpm/store", "~/Library/pnpm/store",
                      "~/AppData/Local/pnpm/store"):
            assert store in job
        assert "enable-cache: true" in job

    # The Dockerfile is a public build contract. Run its exact manifest collector
    # against a workspace with a new package and a removed optional package.
    docker = (client / "Dockerfile").read_text("utf-8")
    docker = docker.split("\nFROM python:", 1)[0] if kind == "python" else docker
    lines = docker.splitlines()
    assert not any(line.startswith("COPY ") and ".npmrc" in line for line in lines)
    assert any(line.startswith("COPY ") and "pnpm-lock.yaml pnpm-workspace.yaml ./" in line
               for line in lines)
    manifest_copy = next(index for index, line in enumerate(lines)
                         if line.startswith("COPY --from=manifests ") and "/manifests/ ./" in line)
    install = lines.index("RUN corepack pnpm install --frozen-lockfile")
    source_copy = max(index for index, line in enumerate(lines)
                      if line.startswith("COPY ") and line.endswith(". ."))
    assert manifest_copy < install < source_copy
    assert "corepack pnpm run build" in docker

    collector_line = next(line for line in lines if line.startswith("RUN node -e "))
    collector = shlex.split(collector_line.removeprefix("RUN "))
    assert collector[:2] == ["node", "-e"]
    source = tmp_path / "source"
    source.mkdir()
    manifests = {path.relative_to(client) for path in client.rglob("package.json")
                 if "node_modules" not in path.parts}
    removed = next(path for path in sorted(manifests, key=lambda item: item.as_posix())
                   if path.as_posix() != "package.json")
    for manifest in manifests - {removed}:
        target = source / manifest
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(client / manifest, target)
    added = source / "libs/generated/contracts/package.json"
    added.parent.mkdir(parents=True)
    added.write_text("{}\n", encoding="utf-8")
    result = subprocess.run(collector, cwd=source, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    collected = {path.relative_to(tmp_path / "manifests").as_posix()
                 for path in (tmp_path / "manifests").rglob("package.json")}
    expected = {path.as_posix() for path in manifests - {removed}}
    expected.add("libs/generated/contracts/package.json")
    assert collected == expected
